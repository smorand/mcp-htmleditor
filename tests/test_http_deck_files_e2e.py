"""SPEC-0023 (US-0121): the editor server answers the files next to the open deck, and nothing outside its folder.

E2E-021 to E2E-025, E2E-071, and the exploit tests E2E-SEC-001 to E2E-SEC-006 and E2E-SEC-010. Requests are sent
as written through a raw socket (``tests.http_support``), so encoded and dot dot paths reach the server unchanged.
The absence of effect is read on other channels: the answer bytes searched for the secret, the server log, the
request list of the deck and the deck's bytes.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

import pytest
from PIL import Image
from playwright.sync_api import Page

from mcp_htmleditor.deck_files import deck_file
from tests.breathe_support import BOOTSTRAP
from tests.browser_wait import wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.http_support import RawReply, exchange

SECRET = b"TOP-SECRET-42"
NOT_FOUND = {"error": "Not found"}
Serve = Callable[[Path], ServedDeck]


def png(width: int = 7, height: int = 5) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (12, 123, 112)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """``deck/talk.html`` (the starting point with one linked picture), SECRET and SECRET-PNG in the parent folder."""
    deck = tmp_path / "deck"
    (deck / "assets").mkdir(parents=True)
    html = BOOTSTRAP.read_text(encoding="utf-8").replace(
        '<aside data-role="speaker-notes"></aside>',
        '<img id="linked" src="assets/photo.png" alt="p"><aside data-role="speaker-notes"></aside>',
        1,
    )
    (deck / "talk.html").write_text(html, encoding="utf-8")
    (deck / "assets" / "photo.png").write_bytes(png())
    (tmp_path / "secret.txt").write_bytes(SECRET)
    (tmp_path / "secret.png").write_bytes(SECRET)
    return deck


def get(served: ServedDeck, path: str, host: str | None = None) -> RawReply:
    head = f"GET {path} HTTP/1.1\r\nHost: {host or f'127.0.0.1:{served.port}'}\r\nConnection: close\r\n\r\n"
    return exchange(served.port, head.encode("iso-8859-1"))


def refused(reply: RawReply) -> bool:
    return reply.status == 404 and json.loads(reply.body) == NOT_FOUND and SECRET not in reply.raw


def not_served(caplog: pytest.LogCaptureFixture, path: str) -> int:
    return sum(1 for r in caplog.records if r.getMessage() == f"Refused GET {path}: not served")


# -- E2E-021 to E2E-025, E2E-071 ------------------------------------------------------------------------------


@needs_chromium
def test_editor_shows_a_linked_picture(folder: Path, serve_deck: Serve, page: Page) -> None:
    """E2E-021."""
    served = serve_deck(folder / "talk.html")
    reply = get(served, "/assets/photo.png")
    assert reply.status == 200
    assert reply.body == (folder / "assets" / "photo.png").read_bytes()
    assert reply.headers["content-type"] == "image/png"
    assert reply.headers["cache-control"] == "no-store, must-revalidate"
    assert reply.headers["x-content-type-options"] == "nosniff"
    page.goto(f"http://127.0.0.1:{served.port}/")
    natural = (
        "() => { const d = document.getElementById('content-frame').contentDocument;"
        " const i = d && d.getElementById('linked'); return i && i.complete ? i.naturalWidth : 0; }"
    )
    assert wait_until(page, lambda: page.evaluate(natural), lambda width: width == 7, what="linked picture loaded") == 7


def test_encoded_and_upper_case_names(folder: Path, serve_deck: Serve) -> None:
    """E2E-022."""
    served = serve_deck(folder / "talk.html")
    (folder / "assets" / "My Photo é.jpg").write_bytes(b"jpeg bytes")
    (folder / "assets" / "IMG_01.JPG").write_bytes(b"camera bytes")
    reply = get(served, "/assets/" + quote("My Photo é.jpg"))
    assert (reply.status, reply.body, reply.headers["content-type"]) == (200, b"jpeg bytes", "image/jpeg")
    reply = get(served, "/assets/IMG_01.JPG?v=2")
    assert (reply.status, reply.body, reply.headers["content-type"]) == (200, b"camera bytes", "image/jpeg")


def test_inner_dot_dot_staying_inside(folder: Path, serve_deck: Serve) -> None:
    """E2E-023: no folder assets/sub exists; the dot dot is resolved on the text."""
    served = serve_deck(folder / "talk.html")
    (folder / "assets" / "a.png").write_bytes(b"a png")
    reply = get(served, "/assets/sub/../a.png")
    assert (reply.status, reply.body) == (200, b"a png")


def test_wrong_type_missing_file_trailing_slash(
    folder: Path, serve_deck: Serve, caplog: pytest.LogCaptureFixture
) -> None:
    """E2E-024."""
    caplog.set_level(logging.WARNING)
    served = serve_deck(folder / "talk.html")
    (folder / "notes.txt").write_text("notes")
    (folder / "script.js").write_text("alert(1)")
    for path in ("/notes.txt", "/script.js", "/missing.png", "/assets/"):
        assert refused(get(served, path)), path
        assert not_served(caplog, path) == 1, path


def test_nothing_is_served_with_no_deck_open() -> None:
    """E2E-024, second half: with no deck open every such path is refused."""
    assert deck_file(None, "/assets/photo.png") is None


def test_editor_pages_win(folder: Path, serve_deck: Serve) -> None:
    """E2E-025."""
    served = serve_deck(folder / "talk.html")
    (folder / "static").mkdir()
    (folder / "static" / "editor.js").write_text("DECK COPY")
    (folder / "review").mkdir()
    (folder / "review" / "fig.png").write_bytes(png())
    reply = get(served, "/static/editor.js")
    assert reply.status == 200
    assert b"DECK COPY" not in reply.body
    assert b"function" in reply.body
    assert refused(get(served, "/review/fig.png"))


@needs_chromium
def test_served_file_forbids_type_guessing(folder: Path, serve_deck: Serve, page: Page) -> None:
    """E2E-071."""
    (folder / "assets" / "photo.png").write_bytes(b"<script>alert(1)</script>")
    served = serve_deck(folder / "talk.html")
    reply = get(served, "/assets/photo.png")
    assert reply.headers["content-type"] == "image/png"
    assert reply.headers["x-content-type-options"] == "nosniff"
    dialogs: list[str] = []
    page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
    page.goto(f"http://127.0.0.1:{served.port}/assets/photo.png", wait_until="load")
    assert page.evaluate("() => document.querySelectorAll('script').length") == 0
    assert dialogs == []


# -- exploits (occurrence #2 of the class sweep) --------------------------------------------------------------


def test_sec_001_dot_dot_climbing_out(folder: Path, serve_deck: Serve, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    served = serve_deck(folder / "talk.html")
    assert get(served, "/assets/photo.png").status == 200  # the route is live: the 404 below is containment
    assert refused(get(served, "/../secret.png"))
    assert not_served(caplog, "/../secret.png") == 1


def test_sec_002_encoded_dot_dot(folder: Path, serve_deck: Serve) -> None:
    served = serve_deck(folder / "talk.html")
    assert get(served, "/assets/photo.png").status == 200
    assert refused(get(served, "/%2e%2e/secret.png"))
    assert refused(get(served, "/assets/..%2f..%2fsecret.png"))


def test_sec_003_link_escaping_the_folder(folder: Path, serve_deck: Serve) -> None:
    (folder / "assets" / "leak.png").symlink_to("../../secret.png")
    served = serve_deck(folder / "talk.html")
    assert get(served, "/assets/photo.png").status == 200
    assert refused(get(served, "/assets/leak.png"))


def test_sec_004_absolute_path(folder: Path, serve_deck: Serve, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    served = serve_deck(folder / "talk.html")
    assert get(served, "/assets/photo.png").status == 200
    encoded = "/" + quote(str(folder.parent), safe="").replace("/", "%2F") + "%2Fsecret.png"
    assert refused(get(served, encoded))
    assert not_served(caplog, encoded) == 1


def test_sec_005_hidden_file_and_nul(folder: Path, serve_deck: Serve, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    (folder / ".secret.png").write_bytes(SECRET)
    (folder / "assets" / "shown.png").symlink_to("../.secret.png")
    served = serve_deck(folder / "talk.html")
    for path in ("/.secret.png", "/assets/photo.png%00.png", "/secret.txt%00.png", "/assets/shown.png"):
        reply = get(served, path)
        assert refused(reply), (path, reply.status)
        assert not_served(caplog, path) == 1, path


def test_sec_006_untrusted_host(folder: Path, serve_deck: Serve) -> None:
    served = serve_deck(folder / "talk.html")
    reply = get(served, "/assets/photo.png", host="evil.example")
    assert reply.status == 403
    assert (folder / "assets" / "photo.png").read_bytes() not in reply.raw


SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><script>'
    "document.documentElement.setAttribute('data-ran', '1');"
    "fetch('/requests', {method: 'POST', headers: {'Content-Type': 'application/json'},"
    " body: JSON.stringify({instruction: 'PWNED', slide: 'slide-0'})});"
    "</script></svg>"
)


@needs_chromium
def test_sec_010_scripted_svg(folder: Path, serve_deck: Serve, page: Page) -> None:
    (folder / "assets" / "x.svg").write_text(SVG)
    deck = folder / "talk.html"
    before = deck.read_bytes()
    served = serve_deck(deck)
    reply = get(served, "/assets/x.svg")
    assert reply.headers["content-security-policy"] == "sandbox; script-src 'none'"
    page.goto(f"http://127.0.0.1:{served.port}/assets/x.svg", wait_until="load")
    page.wait_for_timeout(300)  # pacing: give a script that would run the time to send its request
    assert page.evaluate("() => document.documentElement.getAttribute('data-ran')") is None
    listing = get(served, "/requests")
    assert listing.status == 200
    assert b"PWNED" not in listing.body
    assert deck.read_bytes() == before
