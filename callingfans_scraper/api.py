"""Client di CallingFans.

Il sito è basato su Sponzy (Laravel): le pagine sono HTML renderizzato dal
server e la paginazione passa da endpoint /ajax/... che restituiscono
frammenti HTML. Endpoint ricavati da public/js/app-functions.js del sito:

    /ajax/updates?id=<profile_id>&skip=N&total=T   post di un creator
    /ajax/user/purchases?skip=N&total=T            post comprati (PPV)

Messaggi, storie, highlights e lista abbonamenti non sono ancora mappati:
servono le pagine HTML di esempio.
"""

from __future__ import annotations

import time
from typing import Any, Iterator

import httpx

from .auth import Auth
from .models import Area, Creator, Media
from .parser import BASE_URL, ProfileInfo, is_logged_in, parse_cards, parse_post_media, parse_profile


class ApiError(RuntimeError):
    pass


class CallingFansAPI:
    def __init__(self, auth: Auth, *, delay: float = 0.5, client: httpx.Client | None = None):
        self._delay = delay
        self.client = client or httpx.Client(
            base_url=BASE_URL,
            headers=auth.headers(),
            timeout=httpx.Timeout(30.0, read=120.0),
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    def get_html(self, path: str, params: dict[str, Any] | None = None, *, ajax: bool = False,
                 retries: int = 5) -> str:
        """GET con pausa tra le richieste e backoff su 429/5xx."""
        headers = {"X-Requested-With": "XMLHttpRequest"} if ajax else None
        for attempt in range(1, retries + 1):
            time.sleep(self._delay)
            resp = self.client.get(path, params=params, headers=headers)
            if resp.status_code in (401, 403, 419):
                raise ApiError(
                    f"{resp.status_code} su {path}: sessione scaduta, "
                    "riesegui `callingfans-scraper auth`."
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == retries:
                    break
                time.sleep(float(resp.headers.get("Retry-After", 2**attempt)))
                continue
            resp.raise_for_status()
            if resp.url.path.rstrip("/").endswith("/login"):
                raise ApiError("Rediretto al login: sessione scaduta, riesegui `callingfans-scraper auth`.")
            return resp.text
        raise ApiError(f"{path}: troppi tentativi falliti (ultimo status {resp.status_code})")

    def check_session(self) -> None:
        if not is_logged_in(self.get_html("/")):
            raise ApiError("Non risulti loggato: cookie non validi o scaduti, riesegui `callingfans-scraper auth`.")

    def profile(self, username: str) -> ProfileInfo:
        return parse_profile(self.get_html(f"/{username}"))

    def subscriptions(self) -> list[Creator]:
        """Creator a cui sei abbonato."""
        raise NotImplementedError(
            "lista abbonamenti non ancora mappata (serve HTML di /my/subscriptions): "
            "per ora indica i creator con -u"
        )

    def _paginate(self, path: str, params: dict[str, Any], total: int) -> Iterator[str]:
        """Scorre un endpoint /ajax/... a blocchi: skip = card già ricevute."""
        skip = 0
        seen: set[str] = set()
        while True:
            html = self.get_html(path, {**params, "skip": skip, "total": total}, ajax=True)
            ids = [c["data"] for c in parse_cards(html)]
            new = [i for i in ids if i not in seen]
            if not new:
                return
            seen.update(new)
            skip += len(ids)
            yield html
            if total and skip >= total:
                return

    def posts(self, creator: Creator) -> Iterator[Media]:
        info = self.profile(creator.username)
        for page in self._paginate("/ajax/updates", {"id": info.profile_id}, info.total_posts):
            yield from parse_post_media(page, Area.POSTS, creator)

    def purchased(self) -> Iterator[Media]:
        """Tutti i post comprati, di qualunque creator."""
        for page in self._paginate("/ajax/user/purchases", {}, 0):
            yield from parse_post_media(page, Area.PURCHASED)

    def messages(self, creator: Creator) -> Iterator[Media]:
        raise NotImplementedError("messaggi non ancora mappati: serve HTML di una chat (/messages/...)")

    def stories(self, creator: Creator) -> Iterator[Media]:
        raise NotImplementedError("storie non ancora mappate: serve HTML con le storie aperte")

    def highlights(self, creator: Creator) -> Iterator[Media]:
        raise NotImplementedError("highlights non ancora mappati: serve HTML di esempio")
