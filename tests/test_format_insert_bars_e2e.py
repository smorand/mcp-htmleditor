"""E2E tests for the floating format bar and the insert bar of SPEC-0002 (E2E-013, FR-002, FR-003, US-0155)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import FrameLocator, Page

from tests.browser_wait import settle, wait_for_js
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import build_deck, write_deck

COVER = ".slide-cover-title"
FRAME_DOC = "document.getElementById('content-frame').contentDocument"
COVER_EDITABLE = f"() => {{ const h = {FRAME_DOC}.querySelector('{COVER}'); return !!h && h.isContentEditable; }}"
FORMAT_BAR_SHOWN = (
    f"() => {{ const b = {FRAME_DOC}.getElementById('_mcp_format_bar'); return !!b && b.style.display === 'flex'; }}"
)
OUTSIDE_FRAME_POINT = {"x": 2, "y": 2}


@pytest.fixture
def deck(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> ServedDeck:
    folder = tmp_path / "work"
    folder.mkdir()
    return serve_deck(Path(write_deck(folder / "deck.html", build_deck("ei", ("Couverture", "Sommaire", "Merci")))))


def _open_in_edit_mode(page: Page, deck: ServedDeck) -> FrameLocator:
    page.goto(f"http://127.0.0.1:{deck.port}/")
    page.wait_for_function(f"() => {{ const d = {FRAME_DOC}; return d && d.querySelector('{COVER}'); }}")
    page.click("#edit-mode-btn")
    wait_for_js(page, COVER_EDITABLE, True, what="the cover title editable")
    return page.frame_locator("#content-frame")


def _select_cover_text(page: Page, frame: FrameLocator) -> None:
    frame.locator(COVER).click()
    page.keyboard.press("Home")
    page.keyboard.press("Shift+End")
    wait_for_js(page, FORMAT_BAR_SHOWN, True, what="the format bar shown on a selection")


@needs_chromium
def test_insert_bar_shows_four_buttons_in_a_zone(page: Page, deck: ServedDeck) -> None:
    """E2E-013: a click into an editable zone shows the insert bar with its four buttons."""
    frame = _open_in_edit_mode(page, deck)
    frame.locator(COVER).click()
    buttons = frame.locator("#_mcp_insert_bar button")
    wait_for_js(
        page,
        f"() => {{ const b = {FRAME_DOC}.getElementById('_mcp_insert_bar');"
        " return !!b && getComputedStyle(b).display; }",
        "flex",
        what="the insert bar shown",
    )
    assert buttons.count() == 4
    labels = [buttons.nth(i).inner_text() for i in range(4)]
    for label, expected in zip(labels, ("Image", "Tableau", "Ligne HR", "Lien"), strict=True):
        assert expected in label
    for i in range(4):
        assert buttons.nth(i).is_visible()


@needs_chromium
def test_format_bar_follows_the_selection(page: Page, deck: ServedDeck) -> None:
    """E2E-013: shown on a selection, hidden when a click inside the zone collapses it."""
    frame = _open_in_edit_mode(page, deck)
    assert not frame.locator("#_mcp_format_bar").is_visible()
    frame.locator(COVER).click()
    page.keyboard.press("End")
    for _ in range(4):
        page.keyboard.press("Shift+ArrowLeft")
    wait_for_js(page, FORMAT_BAR_SHOWN, True, what="the format bar shown on a selection")
    assert frame.locator("#_mcp_format_bar").is_visible()
    frame.locator(COVER).click(position={"x": 5, "y": 5})
    wait_for_js(page, FORMAT_BAR_SHOWN, False, what="the format bar hidden after the selection collapsed")
    assert not frame.locator("#_mcp_format_bar").is_visible()


@needs_chromium
def test_format_bar_hides_on_a_click_outside_every_zone(page: Page, deck: ServedDeck) -> None:
    """E2E-013 (FR-002): a click outside every editable zone hides the bar."""
    frame = _open_in_edit_mode(page, deck)
    _select_cover_text(page, frame)
    frame.locator("body").click(position=OUTSIDE_FRAME_POINT)
    wait_for_js(page, FORMAT_BAR_SHOWN, False, what="the format bar hidden after a click outside", bound=2.0)


@needs_chromium
def test_format_bar_stays_when_the_bar_itself_is_pressed(page: Page, deck: ServedDeck) -> None:
    """A press on a button of the bar is not a click outside: the bar stays visible."""
    frame = _open_in_edit_mode(page, deck)
    _select_cover_text(page, frame)
    frame.locator('#_mcp_format_bar [data-cmd="bold"]').click()
    settle(page)
    assert frame.locator("#_mcp_format_bar").is_visible()
