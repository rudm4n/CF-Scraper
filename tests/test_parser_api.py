"""Test su HTML sintetico che riproduce la struttura delle card di CallingFans."""

import httpx
import pytest

from callingfans_scraper.api import ApiError, CallingFansAPI
from callingfans_scraper.auth import Auth
from callingfans_scraper.models import Area, Creator, MediaType
from callingfans_scraper.parser import parse_post_media, parse_profile

B = "https://callingfans.com"


def card(post_id: int, body: str, user: str = "Alice_1") -> str:
    return f"""
<div class="card mb-3 card-updates views rounded-large" data="{post_id}">
  <div class="card-body"><div class="media"><div class="media-body">
    <h5 class="mb-0"><a href="{B}/{user}"> Alice </a>
      <small class="text-muted font-14">@{user}</small></h5>
    <small class="timeAgo text-muted" data="2026-10-09T14:49:12+02:00">4 ore fa</small>
  </div></div></div>
  <div class="card-body pt-0 pb-3"><p class="update-text">Testo {post_id}</p></div>
  {body}
</div>"""


IMAGE = card(101, f"""<div class="btn-block">
  <a href="{B}/files/storage/101/abc.png" class="glightbox w-100" data-gallery="gallery101">
    <img src="{B}/files/storage/101/abc.png?w=960&amp;h=980"></a>
  <a href="{B}/files/storage/101/def.jpg" class="glightbox w-100" data-gallery="gallery101">
    <img src="{B}/files/storage/101/def.jpg?w=960"></a></div>""")
VIDEO = card(102, f"""<div class="btn-block">
  <video class="js-player w-100" data-poster="{B}/public/uploads/updates/videos/x-poster.jpg">
    <source src="{B}/public/uploads/updates/videos/vid123-converted.mp4" type="video/mp4"></video></div>""")
LOCKED = card(103, f"""<div class="btn-block content-locked"
  style="background: url({B}/media/storage/focus/photo/9) no-repeat">
  <a href="javascript:void(0);" data-toggle="modal" data-target="#payPerViewForm">Sblocca</a></div>""")


def test_parse_profile():
    html = 'var profile_id = 6313;\n var totalPosts =  1354;'
    info = parse_profile(html)
    assert (info.profile_id, info.total_posts) == ("6313", 1354)
    with pytest.raises(ValueError):
        parse_profile("<html></html>")


def test_parse_post_media_images_video_and_locked():
    items = list(parse_post_media(IMAGE + VIDEO + LOCKED, Area.POSTS))
    assert [(m.post_id, m.id, m.media_type) for m in items] == [
        ("101", "abc", MediaType.IMAGE),
        ("101", "def", MediaType.IMAGE),
        ("102", "vid123-converted", MediaType.VIDEO),
    ]
    assert items[0].url == f"{B}/files/storage/101/abc.png"  # niente ?w= : risoluzione piena
    assert items[0].creator == Creator(id="alice_1", username="Alice_1")
    assert items[0].text == "Testo 101"
    assert items[0].created_at.year == 2026
    assert items[2].extension == "mp4"


def make_api(handler) -> CallingFansAPI:
    client = httpx.Client(base_url=B, transport=httpx.MockTransport(handler), follow_redirects=True)
    return CallingFansAPI(Auth(cookie="s=1"), delay=0, client=client)


def test_posts_paginates_until_empty():
    pages = {0: IMAGE + VIDEO, 2: LOCKED, 3: ""}
    seen_params = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/Alice_1":
            return httpx.Response(200, text="profile_id = 77; totalPosts = 0;")
        assert req.url.path == "/ajax/updates"
        assert req.headers["X-Requested-With"] == "XMLHttpRequest"
        seen_params.append(dict(req.url.params))
        return httpx.Response(200, text=pages[int(req.url.params["skip"])])

    items = list(make_api(handler).posts(Creator("alice_1", "Alice_1")))
    assert [m.id for m in items] == ["abc", "def", "vid123-converted"]
    assert [p["skip"] for p in seen_params] == ["0", "2", "3"]
    assert all(p["id"] == "77" for p in seen_params)


def test_paginate_stops_on_repeated_page():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, text=IMAGE)  # il server ignora skip

    items = list(make_api(handler).purchased())
    assert len(items) == 2 and len(calls) == 2


def test_login_redirect_raises():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/login":
            return httpx.Response(200, text="login")
        return httpx.Response(302, headers={"Location": f"{B}/login"})

    with pytest.raises(ApiError):
        make_api(handler).profile("Alice_1")
