"""E2E test of SPEC-0002 FR-018: keys typed in an editable zone do not move the slide (E2E-018, US-0155)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

from tests.browser_wait import wait_for_js
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import build_deck, write_deck

COVER = ".slide-cover-title"
FRAME_DOC = "document.getElementById('content-frame').contentDocument"
COVER_EDITABLE = f"() => {{ const h = {FRAME_DOC}.querySelector('{COVER}'); return !!h && h.isContentEditable; }}"
ACTIVE_SLIDE_ID = f"() => {{ const s = {FRAME_DOC}.querySelector('.slide.active'); return s ? s.dataset.id : null; }}"
COVER_TEXT = f"() => {FRAME_DOC}.querySelector('{COVER}').textContent"
IS_FULLSCREEN = (
    "() => !!document.fullscreenElement || !!document.getElementById('content-frame').contentDocument.fullscreenElement"
)


@needs_chromium
def test_typing_keys_in_a_zone_keep_the_slide(
    page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-018: Space, arrows, Home, End and F stay in the zone."""
    folder = tmp_path / "work"
    folder.mkdir()
    deck = serve_deck(Path(write_deck(folder / "deck.html", build_deck("ei", ("Couverture", "Sommaire", "Merci")))))
    page.goto(f"http://127.0.0.1:{deck.port}/")
    page.wait_for_function(f"() => {{ const d = {FRAME_DOC}; return d && d.querySelector('{COVER}'); }}")
    page.click("#edit-mode-btn")
    wait_for_js(page, COVER_EDITABLE, True, what="the cover title editable")
    first = page.evaluate(ACTIVE_SLIDE_ID)
    assert first

    page.frame_locator("#content-frame").locator(COVER).click()
    page.keyboard.press("End")
    for key in ("Space", "ArrowRight", "ArrowLeft", "Home", "End", "F"):
        page.keyboard.press(key)

    wait_for_js(page, COVER_TEXT, "Couverture F", what="Space and F typed in the cover title")
    assert page.evaluate(ACTIVE_SLIDE_ID) == first
    assert page.evaluate(IS_FULLSCREEN) is False
