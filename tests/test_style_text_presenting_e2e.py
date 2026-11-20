"""SPEC-0030 (US-0168): presenting a deck does not change the style text of ``<html>`` in the saved file.

BT-001 and BT-009. The deck's own runtime sets the presenting scale on ``<html>`` through the style object, which
reserializes the other declarations (``color:#161616`` becomes ``color: rgb(22, 22, 22);``); the file must keep the
text the document was loaded with. Real headless Chromium against a real editor server; assertions read the file.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from tests.browser_wait import wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.style_text_support import serve_deck_s2

FRAME = "document.getElementById('content-frame').contentDocument"
FRAME_EDITABLE = (
    f"() => {{ const e = {FRAME}.querySelector('[data-editable~=\"text\"]'); return !!e && e.isContentEditable; }}"
)
FULLSCREEN = f"() => {FRAME}.fullscreenElement ? {FRAME}.fullscreenElement.tagName : null"
TYPED = "ZQX"


def _html_style(path: Path) -> str | None:
    html = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser").find("html")
    assert html is not None
    style = html.get("style")
    return None if style is None else str(style)


def _present_and_type(page: Page, deck: ServedDeck) -> None:
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto(f"http://127.0.0.1:{deck.port}/", wait_until="networkidle")
    wait_until(
        page,
        lambda: page.evaluate("document.getElementById('toolbar-filename').textContent"),
        lambda text: text != "\u2014",
        what="the edit button wired",
    )
    page.click("#edit-mode-btn")
    wait_for_js(page, FRAME_EDITABLE, True, what="edit mode on")
    page.click("#present-btn")
    wait_for_js(page, FULLSCREEN, "HTML", what="presenting")
    page.frame_locator("#content-frame").locator('.slide.active [data-editable~="text"]').first.click()
    page.keyboard.type(TYPED)
    wait_until(page, lambda: TYPED in deck.path.read_text(encoding="utf-8"), lambda saved: saved, what="the autosave")


def _leave(page: Page) -> None:
    page.evaluate(f"{FRAME}.exitFullscreen()")
    wait_for_js(page, FULLSCREEN, None, what="presenting left")
    page.evaluate("() => saveContent()")


@needs_chromium
def test_bt001_presenting_then_saving_keeps_the_html_style_text(
    page: Page, serve_deck: Callable[[Path], ServedDeck], tmp_path: Path
) -> None:
    deck = serve_deck_s2(tmp_path, serve_deck)

    _present_and_type(page, deck)
    assert page.evaluate(f"() => {FRAME}.documentElement.getAttribute('style')") != "color:#161616"  # the deck's mark
    assert _html_style(deck.path) == "color:#161616"
    page.evaluate("() => saveContent()")
    assert _html_style(deck.path) == "color:#161616"
    _leave(page)

    assert _html_style(deck.path) == "color:#161616"
    assert not re.search(r'style="[^"]*--fs-scale', deck.path.read_text(encoding="utf-8"))


@needs_chromium
def test_bt009_a_deck_without_a_html_style_has_none_after_presenting(
    page: Page, serve_deck: Callable[[Path], ServedDeck], tmp_path: Path
) -> None:
    deck = serve_deck_s2(tmp_path, serve_deck, html_style=None)

    _present_and_type(page, deck)
    _leave(page)

    assert _html_style(deck.path) is None
