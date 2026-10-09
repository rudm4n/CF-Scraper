"""Lettura dei cookie di callingfans.com dal profilo di Firefox.

Firefox salva i cookie in chiaro in cookies.sqlite (a differenza di Chrome,
che li cifra). Il file è bloccato mentre Firefox è aperto, quindi lo copiamo
in una cartella temporanea insieme al WAL prima di leggerlo.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

DOMAIN = "callingfans.com"


def firefox_profile_roots() -> list[Path]:
    home = Path.home()
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        return [Path(appdata) / "Mozilla" / "Firefox" / "Profiles"] if appdata else []
    if sys.platform == "darwin":
        return [home / "Library" / "Application Support" / "Firefox" / "Profiles"]
    return [
        home / ".mozilla" / "firefox",
        home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
        home / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
    ]


def find_cookie_dbs(roots: list[Path] | None = None) -> list[Path]:
    """cookies.sqlite di tutti i profili, dal più recente."""
    dbs = [db for root in (roots or firefox_profile_roots()) if root.is_dir()
           for db in root.glob("*/cookies.sqlite")]
    return sorted(dbs, key=lambda p: p.stat().st_mtime, reverse=True)


def read_cookies(db: Path, domain: str = DOMAIN) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "cookies.sqlite"
        shutil.copy2(db, copy)
        for suffix in ("-wal", "-shm"):
            side = db.with_name(db.name + suffix)
            if side.exists():
                shutil.copy2(side, copy.with_name(copy.name + suffix))
        conn = sqlite3.connect(copy)
        try:
            rows = conn.execute(
                "SELECT name, value, expiry FROM moz_cookies "
                "WHERE host = ? OR host = ? OR host LIKE ? ORDER BY lastAccessed",
                (domain, "." + domain, "%." + domain),
            ).fetchall()
        finally:
            conn.close()
    now = time.time()
    # expiry in secondi; alcune versioni lo salvano in millisecondi.
    return {name: value for name, value, expiry in rows
            if not expiry or (expiry / 1000 if expiry > 1e11 else expiry) > now}


def firefox_cookie_header(roots: list[Path] | None = None) -> tuple[str, Path]:
    dbs = find_cookie_dbs(roots)
    if not dbs:
        raise FileNotFoundError("Nessun profilo Firefox trovato.")
    for db in dbs:
        cookies = read_cookies(db)
        if cookies:
            return "; ".join(f"{k}={v}" for k, v in cookies.items()), db
    raise LookupError(
        f"Nessun cookie di {DOMAIN} nei profili Firefox: fai login sul sito con Firefox e riprova."
    )
