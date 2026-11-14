"""Icon only toolbar (SPEC-0022 amendment 2026-11-14): aria-labels, 1 s tooltip, download button and ``GET /download``.

Real headless Chromium for the browser tests. Observations go through ``wait_until`` (no fixed sleeps); the one
measured delay (the 1 s of the tooltip) is the only timing assertion and is marked ``# pacing:``.
"""

from __future__ import annotations

import http.client
import re
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote

from playwright.sync_api import Page

from mcp_htmleditor.state import get_state
from tests.browser_wait import wait_until
from tests.conftest import ServedDeck, needs_chromium

STATIC = Path(__file__).resolve().parent.parent / "src" / "mcp_htmleditor" / "static"
CONTROLS_JS = """() => [...document.querySelectorAll('#toolbar button, #toolbar a')].map(el => {
  const clone = el.cloneNode(true);
  clone.querySelectorAll('.tb-badge').forEach(b => b.remove());
  return {id: el.id, text: clone.textContent.trim(), label: el.getAttribute('aria-label'),
          title: el.getAttribute('title'), tip: el.dataset.tip, svg: !!el.querySelector('svg')};
})"""
TIP_JS = """() => { const t = document.getElementById('tb-tip'), r = t.getBoundingClientRect();
  const k = t.querySelector('.tip-keys');
  return {visible: getComputedStyle(t).visibility === 'visible', name: t.querySelector('.tip-name').textContent,
          keys: k.hidden ? '' : k.textContent,
          left: r.left, right: r.right, top: r.top, bottom: r.bottom, vw: document.documentElement.clientWidth,
          vh: window.innerHeight, delay: getComputedStyle(t).transitionDelay,
          pe: getComputedStyle(t).pointerEvents}; }"""


def _get(deck: ServedDeck, route: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", deck.port, timeout=60)
    try:
        conn.request("GET", route, headers=headers or {})
        response = conn.getresponse()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
    finally:
        conn.close()


def _open(page: Page, deck: ServedDeck) -> None:
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(f"http://127.0.0.1:{deck.port}/")
    wait_until(
        page,
        lambda: page.evaluate("document.getElementById('toolbar-filename').textContent"),
        lambda v: v == deck.path.name,
        what="file name in the toolbar",
    )


# ---- static guard -------------------------------------------------------------------------------


def test_no_toolbar_control_carries_a_title_attribute() -> None:
    html = (STATIC / "editor.html").read_text(encoding="utf-8")
    toolbar = html[html.index('<div id="toolbar">') : html.index('<div id="tb-tip"')]
    controls = re.findall(r"<(?:button|a)\b[^>]*>", toolbar)
    assert len(controls) >= 15
    assert [c for c in controls if re.search(r"\stitle=", c)] == []
    for js in STATIC.glob("editor*.js"):
        assert not re.search(r"(?:Btn|Toggle)\.title\s*=", js.read_text(encoding="utf-8")), js.name


# ---- /download ----------------------------------------------------------------------------------


def test_download_headers_and_exact_bytes(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    path = tmp_path / "Résumé é.html"
    data = "<!DOCTYPE html><html><body><p>é \u2014 \r\n  tail</p></body></html>".encode()
    path.write_bytes(data)
    deck = serve_deck(path)
    before = sorted(p.name for p in tmp_path.iterdir())
    status, headers, body = _get(deck, "/download")
    assert status == 200 and body == data
    assert headers["content-type"] == "text/html; charset=utf-8"
    assert headers["cache-control"].startswith("no-store")
    disposition = headers["content-disposition"]
    assert disposition.startswith("attachment; filename=\"R_sum_ _.html\"; filename*=UTF-8''")
    assert unquote(disposition.split("filename*=UTF-8''")[1]) == path.name
    assert int(headers["content-length"]) == len(data)
    assert sorted(p.name for p in tmp_path.iterdir()) == before and path.read_bytes() == data


def test_download_refusals(served_deck: ServedDeck) -> None:
    status, _, body = _get(served_deck, "/download", {"Host": "evil.example"})
    assert status == 403 and b"forbidden host" in body
    status, _, body = _get(served_deck, "/download", {"Origin": "https://evil.example"})
    assert status == 403 and b"forbidden origin" in body
    conn = http.client.HTTPConnection("127.0.0.1", served_deck.port, timeout=60)
    try:
        conn.request("POST", "/download", body=b"{}", headers={"Content-Type": "application/json"})
        assert conn.getresponse().status == 404
    finally:
        conn.close()
    get_state().current_file = None
    status, _, body = _get(served_deck, "/download")
    assert status == 404 and b"No file loaded" in body


# ---- toolbar ------------------------------------------------------------------------------------


@needs_chromium
def test_every_control_is_an_icon_with_an_accessible_name(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    controls = page.evaluate(CONTROLS_JS)
    ids = [c["id"] for c in controls]
    for expected in (
        "ask-ai-btn",
        "edit-mode-btn",
        "undo-btn",
        "redo-btn",
        "present-btn",
        "pointer-btn",
        "presenter-btn",
        "notes-btn",
        "requests-toggle",
        "export-pptx-btn",
        "export-docx-btn",
        "btn-insert-before",
        "btn-insert-after",
        "btn-delete-slide",
        "btn-insert-block-before",
        "btn-insert-block-after",
        "download-btn",
        "help-btn",
    ):
        assert expected in ids
    assert ids[-2:] == ["download-btn", "help-btn"]
    for c in controls:
        assert c["text"] == "", c
        assert c["label"] and c["label"].startswith(c["tip"]), c
        assert c["title"] is None and c["svg"], c
    badge = page.text_content("#requests-badge")
    assert badge == "(0)" and page.get_attribute("#requests-toggle", "aria-label") == "Requests (0)"


@needs_chromium
def test_edit_button_pressed_style_and_state(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    bg = "() => getComputedStyle(document.getElementById('edit-mode-btn')).backgroundColor"
    assert page.get_attribute("#edit-mode-btn", "aria-pressed") == "false"
    page.click("#edit-mode-btn")
    assert (
        wait_until(
            page, lambda: page.get_attribute("#edit-mode-btn", "aria-pressed"), lambda v: v == "true", what="pressed"
        )
        == "true"
    )
    wait_until(page, lambda: page.evaluate(bg), lambda v: v == "rgb(15, 98, 254)", what="pressed colour")
    assert page.is_visible("#edit-mode-btn .edit-dot")


@needs_chromium
def test_download_button_downloads_the_file_on_disk(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    assert page.is_visible("#download-btn")
    assert page.get_attribute("#download-btn", "href") == "/download"
    with page.expect_download() as info:
        page.click("#download-btn")
    download = info.value
    assert download.suggested_filename == served_deck.path.name
    assert Path(download.path()).read_bytes() == served_deck.path.read_bytes()


@needs_chromium
def test_tooltip_appears_after_one_second_with_name_and_keys(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    assert page.evaluate(TIP_JS)["delay"] == "0s, 0s"
    page.hover("#edit-mode-btn")
    started = time.monotonic()
    assert page.evaluate("document.getElementById('tb-tip').classList.contains('armed')")
    armed = page.evaluate(TIP_JS)
    assert armed["delay"] == "1s, 1s" and armed["pe"] == "none"
    assert armed["visible"] is False or time.monotonic() - started >= 1
    shown = wait_until(page, lambda: page.evaluate(TIP_JS), lambda t: t["visible"], what="tooltip visible", bound=5)
    assert time.monotonic() - started >= 0.9  # pacing: the 1 s tooltip delay is the thing measured
    assert shown["name"] == "Édition" and shown["keys"] == "E"
    bar = page.evaluate("document.getElementById('edit-mode-btn').getBoundingClientRect().bottom")
    assert shown["top"] >= bar
    page.mouse.move(800, 600)
    assert (
        wait_until(page, lambda: page.evaluate(TIP_JS), lambda t: not t["visible"], what="tooltip hidden")["visible"]
        is False
    )


@needs_chromium
def test_tooltip_hides_on_click_and_escape_and_follows_keyboard_focus(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    page.hover("#ask-ai-btn")
    wait_until(page, lambda: page.evaluate(TIP_JS), lambda t: t["visible"], what="visible", bound=5)
    page.click("#ask-ai-btn")
    assert page.evaluate(TIP_JS)["visible"] is False
    page.mouse.move(800, 600)
    page.hover("#help-btn")
    wait_until(page, lambda: page.evaluate(TIP_JS), lambda t: t["visible"], what="visible again", bound=5)
    page.keyboard.press("Escape")
    assert page.evaluate(TIP_JS)["visible"] is False
    page.mouse.move(800, 600)
    page.focus("#requests-toggle")
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    shown = wait_until(page, lambda: page.evaluate(TIP_JS), lambda t: t["visible"], what="focus tooltip", bound=5)
    assert shown["name"].startswith("Requests")


@needs_chromium
def test_rightmost_icon_tooltips_stay_inside_the_viewport(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    for selector, name in (("#help-btn", "Raccourcis clavier"), ("#download-btn", "Télécharger le fichier HTML")):
        page.mouse.move(800, 600)
        page.hover(selector)
        tip = wait_until(
            page,
            lambda: page.evaluate(TIP_JS),
            lambda t, n=name: t["visible"] and t["name"] == n,
            what=f"{selector} tooltip",
            bound=5,
        )
        assert tip["left"] >= 0 and tip["right"] <= tip["vw"], tip
        assert tip["bottom"] <= tip["vh"]
    narrow = page.evaluate(TIP_JS)
    assert narrow["right"] <= narrow["vw"]
