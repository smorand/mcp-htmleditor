"""SPEC-0027 (US-0156): autosave timing, status dots and reloads of the editor page (SPEC-0002 E2E-014 to E2E-016).

Real headless Chromium against a real editor server (``served_deck``). Timing is asserted as a state, never as a lower
time bound: the old state is read at the moment of the action, the new state is awaited with a 3 s bound.
"""

from __future__ import annotations

import os
import time

import pytest
from playwright.sync_api import Page

from mcp_htmleditor import config as config_module
from mcp_htmleditor.state import get_state
from tests.browser_wait import settle, wait_for_file, wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium

COVER = ".slide-cover-title"
SAVED = "rgb(66, 190, 101)"
PENDING = "rgb(255, 131, 43)"
UPDATING = "rgb(241, 194, 27)"
DOT = "() => getComputedStyle(document.getElementById('toolbar-status')).color"
SAVE_BOUND = 3.0
HOLD_SAVES = """
(() => {
  const send = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    const method = ((init && init.method) || "GET").toUpperCase();
    return method === "POST" && url.pathname === "/content" ? new Promise(() => {}) : send(input, init);
  };
})();
"""
COVER_EDITABLE = (
    "() => { const d = document.getElementById('content-frame').contentDocument;"
    f" const h = d && d.querySelector('{COVER}'); return !!h && h.isContentEditable; }}"
)


@pytest.fixture
def fast_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTMLEDITOR_POLL_INTERVAL", "100")
    config_module.reset_settings_cache()


def _open_in_edit_mode(page: Page, deck: ServedDeck) -> list[str]:
    """Open the editor, switch edit mode on; return the list that records every load of the preview frame."""
    loads: list[str] = []
    page.on("request", lambda req: loads.append(req.url) if "/content-frame" in req.url else None)
    page.goto(f"http://127.0.0.1:{deck.port}/")
    page.wait_for_function(
        "() => { const d = document.getElementById('content-frame').contentDocument;"
        f" return d && d.querySelector('{COVER}'); }}"
    )
    page.click("#edit-mode-btn")
    wait_for_js(page, COVER_EDITABLE, True, what="the cover title editable")
    return loads


def _type_in_cover(page: Page, text: str) -> None:
    page.frame_locator("#content-frame").locator(COVER).click()
    page.keyboard.press("End")
    page.keyboard.type(text)


def _wait_dot(page: Page, color: str, what: str) -> None:
    wait_for_js(page, DOT, color, what=what)


@needs_chromium
def test_e2e_014_typing_saves_after_the_delay_and_the_file_is_old_until_then(
    page: Page, fast_poll: None, served_deck: ServedDeck
) -> None:
    """FR-004: pending at once with the old title on disk, the new title within 3 s."""
    _open_in_edit_mode(page, served_deck)
    _type_in_cover(page, "Zq7Xk")
    _wait_dot(page, PENDING, "the dot orange while the change is pending")
    on_disk = served_deck.path.read_text(encoding="utf-8")
    assert "Zq7Xk" not in on_disk
    wait_for_file(page, served_deck.path, "Zq7Xk", bound=SAVE_BOUND)
    _wait_dot(page, SAVED, "the dot green after the save")


@needs_chromium
def test_e2e_014_leaving_the_zone_saves(page: Page, fast_poll: None, served_deck: ServedDeck) -> None:
    """FR-005: the focus leaves the zone, the text is on disk and the dot is green within 3 s."""
    _open_in_edit_mode(page, served_deck)
    _type_in_cover(page, "BLUR")
    page.frame_locator("#content-frame").locator("body").click(position={"x": 5, "y": 5})
    wait_for_file(page, served_deck.path, "BLUR", bound=SAVE_BOUND)
    _wait_dot(page, SAVED, "the dot green after the save on blur")


@needs_chromium
def test_e2e_014_a_structural_action_saves(page: Page, fast_poll: None, served_deck: ServedDeck) -> None:
    """FR-006: inserting a slide is on disk within 3 s."""
    _open_in_edit_mode(page, served_deck)
    before = served_deck.path.read_text(encoding="utf-8").count('data-type="slide"')
    page.click("#btn-insert-after")
    page.wait_for_selector("#slide-picker .picker-card")
    page.click("#slide-picker .picker-card")
    wait_until(
        page,
        lambda: served_deck.path.read_text(encoding="utf-8").count('data-type="slide"'),
        lambda count: count == before + 1,
        what="the new slide on disk",
        bound=SAVE_BOUND,
    )


@needs_chromium
def test_e2e_015_the_dot_is_green_orange_yellow_then_green(
    page: Page, fast_poll: None, served_deck: ServedDeck
) -> None:
    """FR-007: saved, pending, agent update in progress, saved again."""
    _open_in_edit_mode(page, served_deck)
    _wait_dot(page, SAVED, "the dot green at rest")
    _type_in_cover(page, "D")
    _wait_dot(page, PENDING, "the dot orange while pending")
    _wait_dot(page, SAVED, "the dot green after the save")
    get_state().set_update_flag(True)
    try:
        _wait_dot(page, UPDATING, "the dot yellow during the agent update")
    finally:
        get_state().set_update_flag(False)
    _wait_dot(page, SAVED, "the dot green after the update closed")


@needs_chromium
def test_e2e_016_the_pages_own_save_does_not_reload_the_frame(
    page: Page, fast_poll: None, served_deck: ServedDeck
) -> None:
    """FR-008: a typed change is saved by the page and the preview is not loaded again."""
    loads = _open_in_edit_mode(page, served_deck)
    before = len(loads)
    _type_in_cover(page, "OWN")
    wait_for_file(page, served_deck.path, "OWN", bound=SAVE_BOUND)
    _wait_dot(page, SAVED, "the dot green after the page's own save")
    settle(page)
    assert len(loads) == before


@needs_chromium
def test_e2e_016_no_reload_while_changes_are_pending(page: Page, fast_poll: None, served_deck: ServedDeck) -> None:
    """FR-008: the file changes on disk while a typed change is pending; the preview is not loaded again."""
    page.add_init_script(HOLD_SAVES)
    loads = _open_in_edit_mode(page, served_deck)
    before = len(loads)
    _type_in_cover(page, "PEND")
    _wait_dot(page, PENDING, "the dot orange while pending")
    # the save is held (HOLD_SAVES), so the change stays pending for the whole observation below
    source = served_deck.path.read_text(encoding="utf-8")
    served_deck.path.write_text(source.replace("</body>", "<!-- agent --></body>", 1), encoding="utf-8")
    later = time.time() + 10
    os.utime(served_deck.path, (later, later))
    settle(page)  # about ten poll cycles at the forced 100 ms interval
    assert len(loads) == before
