import sqlite3
import time

import pytest

from callingfans_scraper.browser_cookies import firefox_cookie_header
from callingfans_scraper.cli import main


def make_profile(root, name, rows):
    prof = root / name
    prof.mkdir(parents=True)
    conn = sqlite3.connect(prof / "cookies.sqlite")
    conn.execute(
        "CREATE TABLE moz_cookies (name TEXT, value TEXT, host TEXT, path TEXT, "
        "expiry INTEGER, lastAccessed INTEGER)"
    )
    conn.executemany("INSERT INTO moz_cookies VALUES (?, ?, ?, '/', ?, 0)", rows)
    conn.commit()
    conn.close()


def test_reads_only_callingfans_and_unexpired(tmp_path):
    future, past = int(time.time()) + 3600, int(time.time()) - 3600
    make_profile(tmp_path, "a.default", [
        ("callingfans_session", "abc", "callingfans.com", future),
        ("XSRF-TOKEN", "xyz", ".callingfans.com", future),
        ("old", "1", "callingfans.com", past),
        ("other", "2", "example.com", future),
    ])
    header, db = firefox_cookie_header([tmp_path])
    assert header == "callingfans_session=abc; XSRF-TOKEN=xyz"
    assert db.name == "cookies.sqlite"


def test_no_cookies_raises(tmp_path):
    make_profile(tmp_path, "a.default", [("x", "1", "example.com", 0)])
    with pytest.raises(LookupError):
        firefox_cookie_header([tmp_path])


def test_auth_cookie_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CALLINGFANS_CONFIG_DIR", str(tmp_path / "cfg"))
    f = tmp_path / "c.txt"
    f.write_text("Cookie: a=1; b=2\n")
    assert main(["auth", "--cookie-file", str(f)]) == 0
    saved = (tmp_path / "cfg" / "auth.json").read_text()
    assert '"cookie": "a=1; b=2"' in saved
