from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

from .api import ApiError, CallingFansAPI
from .auth import Auth, AuthError
from .browser_cookies import firefox_cookie_header
from .config import Config
from .db import MediaDB
from .downloader import download_all
from .models import Area, Creator


def _clean_cookie(raw: str) -> str:
    raw = raw.strip()
    if raw.lower().startswith("cookie:"):
        raw = raw[len("cookie:"):].strip()
    return raw


def cmd_auth(args: argparse.Namespace) -> int:
    if args.firefox:
        try:
            cookie, db = firefox_cookie_header()
        except (FileNotFoundError, LookupError) as exc:
            print(f"Errore: {exc}", file=sys.stderr)
            return 2
        print(f"Cookie letti da {db}")
    elif args.cookie_file:
        cookie = _clean_cookie(Path(args.cookie_file).expanduser().read_text(encoding="utf-8"))
    else:
        print("Incolla il valore dell'header Cookie (F12 > Network > una richiesta > Headers) e premi Invio.")
        print("Se il terminale non incolla, usa `auth --firefox` oppure `auth --cookie-file FILE`.")
        cookie = _clean_cookie(input("Cookie: "))
    if not cookie:
        print("Errore: cookie vuoto.", file=sys.stderr)
        return 2
    path = Auth(cookie=cookie, user_agent=args.user_agent or "").save()
    print(f"Credenziali salvate in {path} (permessi 600).")
    if args.cookie_file:
        print(f"Ora puoi cancellare {args.cookie_file}: contiene la tua sessione.")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    cfg = Config.load()
    if args.save_dir:
        cfg.save_dir = str(Path(args.save_dir).expanduser().resolve())
    if args.template:
        cfg.filename_template = args.template
    if args.workers:
        cfg.max_concurrent_downloads = args.workers
    path = cfg.save(None)
    for key, value in vars(cfg).items():
        print(f"{key}: {value}")
    print(f"\n(salvato in {path})")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    cfg = Config.load()
    api = CallingFansAPI(Auth.load(), delay=cfg.request_delay_seconds)
    try:
        api.check_session()
        for creator in api.subscriptions():
            print(creator.username)
    except ApiError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 2
    finally:
        api.close()
    return 0


def _download(items, *, area_label, args, cfg, save_dir, db, dl_client) -> int:
    items = list(items)
    print(f"== {area_label}: {len(items)} media trovati")
    if args.dry_run:
        for m in items:
            print(f"   {m.creator.username}\t{m.media_type.value}\t{m.post_id}\t{m.url}")
        return 0
    res = download_all(
        items,
        save_dir=save_dir,
        template=cfg.filename_template,
        db=db,
        client=dl_client,
        max_workers=cfg.max_concurrent_downloads,
    )
    print(f"   scaricati {len(res.downloaded)}, già presenti {res.skipped}, falliti {len(res.failed)}")
    for media, err in res.failed:
        print(f"   ! {media.id}: {err}", file=sys.stderr)
    return len(res.failed)


def cmd_scrape(args: argparse.Namespace) -> int:
    cfg = Config.load()
    areas = [Area(a) for a in (args.areas or cfg.areas)]
    save_dir = Path(args.save_dir or cfg.save_dir).expanduser()

    auth = Auth.load()
    api = CallingFansAPI(auth, delay=cfg.request_delay_seconds)
    db = MediaDB(save_dir / ".callingfans.db")
    # Le immagini in /files/storage/... sono protette: servono i cookie anche qui.
    dl_headers = {k: v for k, v in auth.headers().items() if k != "Accept"}
    dl_client = httpx.Client(
        headers=dl_headers, timeout=httpx.Timeout(30.0, read=300.0), follow_redirects=True
    )
    failed = 0
    common = dict(args=args, cfg=cfg, save_dir=save_dir, db=db, dl_client=dl_client)
    try:
        api.check_session()
        if args.creators:
            creators = [Creator(id=u.lstrip("@").lower(), username=u.lstrip("@")) for u in args.creators]
        else:
            creators = api.subscriptions()
        wanted = {c.id for c in creators}

        per_creator = {
            Area.POSTS: api.posts,
            Area.MESSAGES: api.messages,
            Area.STORIES: api.stories,
            Area.HIGHLIGHTS: api.highlights,
        }
        for creator in creators:
            for area in areas:
                if area not in per_creator:
                    continue
                try:
                    items = per_creator[area](creator)
                    failed += _download(items, area_label=f"{creator.username} / {area.value}", **common)
                except NotImplementedError as exc:
                    print(f"== {creator.username} / {area.value}: saltato, {exc}", file=sys.stderr)

        if Area.PURCHASED in areas:
            # Gli acquisti sono una lista unica dell'account: li filtro sui creator scelti.
            items = (m for m in api.purchased() if not args.creators or m.creator.id in wanted)
            failed += _download(items, area_label="acquisti", **common)
    except ApiError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 2
    finally:
        dl_client.close()
        db.close()
        api.close()
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="callingfans-scraper",
        description="Scarica i contenuti dei tuoi abbonamenti CallingFans.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("auth", help="salva i cookie della tua sessione")
    src = a.add_mutually_exclusive_group()
    src.add_argument("--firefox", action="store_true", help="leggi i cookie dal profilo di Firefox")
    src.add_argument("--cookie-file", help="file di testo con il valore dell'header Cookie")
    a.add_argument("--user-agent", help="User-Agent del browser (opzionale)")
    a.set_defaults(func=cmd_auth)

    c = sub.add_parser("config", help="mostra o modifica la configurazione")
    c.add_argument("--save-dir")
    c.add_argument("--template", help="es. {username}/{area}/{date}_{media_id}.{ext}")
    c.add_argument("--workers", type=int, help="download in parallelo")
    c.set_defaults(func=cmd_config)

    sub.add_parser("list", help="elenca i creator a cui sei abbonato").set_defaults(func=cmd_list)

    s = sub.add_parser("scrape", help="scarica i media")
    s.add_argument("-u", "--creators", nargs="+", help="solo questi username (default: tutti)")
    s.add_argument(
        "-a", "--areas", nargs="+", choices=[a.value for a in Area],
        help="sezioni da scaricare (default: tutte)",
    )
    s.add_argument("--save-dir", help="cartella di destinazione per questo giro")
    s.add_argument("--dry-run", action="store_true", help="elenca i media senza scaricarli")
    s.set_defaults(func=cmd_scrape)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (AuthError, NotImplementedError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
