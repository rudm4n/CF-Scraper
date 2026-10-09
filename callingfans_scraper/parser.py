"""Parser dell'HTML di CallingFans (piattaforma basata su Sponzy/Laravel).

Gli endpoint /ajax/... non rispondono JSON ma frammenti HTML con una
`div.card-updates` per post. Il parser estrae da ogni card i media che il tuo
account vede già: i post PPV non comprati hanno solo `div.content-locked` e
vengono saltati.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from .models import Area, Creator, Media, MediaType

BASE_URL = "https://callingfans.com"

_VIDEO_EXT = {"mp4", "mov", "m4v", "webm", "mkv"}
_AUDIO_EXT = {"mp3", "m4a", "wav", "ogg", "aac"}


@dataclass(frozen=True)
class ProfileInfo:
    profile_id: str
    total_posts: int


def parse_profile(html: str) -> ProfileInfo:
    """Legge `profile_id` e `totalPosts` dalle variabili JS della pagina profilo."""
    pid = re.search(r"profile_id\s*=\s*['\"]?(\d+)", html)
    if not pid:
        raise ValueError("profile_id non trovato: pagina profilo non valida o sessione scaduta")
    total = re.search(r"totalPosts\s*=\s*['\"]?(\d+)", html)
    return ProfileInfo(pid.group(1), int(total.group(1)) if total else 0)


def is_logged_in(html: str) -> bool:
    return "/logout" in html


def _strip_query(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _media_type(url: str, default: MediaType) -> MediaType:
    ext = urlsplit(url).path.rsplit(".", 1)[-1].lower()
    if ext in _VIDEO_EXT:
        return MediaType.VIDEO
    if ext in _AUDIO_EXT:
        return MediaType.AUDIO
    return default


def _card_creator(card: Tag) -> Creator | None:
    handle = card.find("small", string=re.compile(r"^\s*@"))
    if handle:
        username = handle.get_text(strip=True).lstrip("@")
    else:
        link = card.select_one(".media-body h5 a[href]")
        if not link:
            return None
        username = urlsplit(link["href"]).path.strip("/").split("/")[0]
    if not username:
        return None
    # L'username è stabile e compare sia nei post sia negli acquisti:
    # usarlo come id evita di riscaricare lo stesso media dalle due sezioni.
    return Creator(id=username.lower(), username=username)


def _card_date(card: Tag) -> datetime:
    tag = card.select_one("small.timeAgo[data]")
    if tag:
        try:
            return datetime.fromisoformat(tag["data"])
        except ValueError:
            pass
    return datetime.fromtimestamp(0, tz=timezone.utc)


def _card_media_urls(card: Tag) -> list[tuple[str, MediaType]]:
    found: list[tuple[str, MediaType]] = []
    for a in card.select("a.glightbox[href]"):
        found.append((a["href"], MediaType.IMAGE))
    for src in card.select("video source[src], video[src]"):
        found.append((src["src"], MediaType.VIDEO))
    for src in card.select("audio source[src], audio[src]"):
        found.append((src["src"], MediaType.AUDIO))
    seen: set[str] = set()
    out = []
    for url, kind in found:
        url = _strip_query(urljoin(BASE_URL, url))
        if url in seen or url.startswith("javascript:"):
            continue
        seen.add(url)
        out.append((url, _media_type(url, kind)))
    return out


def parse_cards(html: str) -> list[Tag]:
    return BeautifulSoup(html, "html.parser").select("div.card-updates[data]")


def parse_post_media(html: str, area: Area, creator: Creator | None = None) -> Iterator[Media]:
    """Media sbloccati presenti nelle card dell'HTML.

    `creator` forza il creator (pagina profilo); se None si legge da ogni card
    (acquisti, feed).
    """
    for card in parse_cards(html):
        post_id = card["data"]
        owner = creator or _card_creator(card)
        if owner is None:
            continue
        text_tag = card.select_one(".update-text")
        text = text_tag.get_text(" ", strip=True) if text_tag else ""
        created = _card_date(card)
        for url, kind in _card_media_urls(card):
            yield Media(
                id=urlsplit(url).path.rsplit("/", 1)[-1].rsplit(".", 1)[0],
                url=url,
                media_type=kind,
                area=area,
                creator=owner,
                post_id=post_id,
                created_at=created,
                text=text,
            )
