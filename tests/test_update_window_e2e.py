"""SPEC-0027 (US-0156): the agent update window in the browser (SPEC-0001 E2E-004 and E2E-005, FR-004).

While the window is open the overlay shows and the preview is not loaded again; when it closes the preview reloads
exactly once and shows the new content.
"""

from __future__ import annotations

import os
import time

import pytest
from playwright.sync_api import Page

from mcp_htmleditor import config as config_module
from mcp_htmleditor.state import get_state
from tests.browser_wait import settle, wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium

COVER = ".slide-cover-title"
AGENT_TITLE = "Titre de la fenetre"
OVERLAY = "() => getComputedStyle(document.getElementById('update-overlay')).display"
COVER_TEXT = (
    "() => { const d = document.getElementById('content-frame').contentDocument;"
    f" const h = d && d.querySelector('{COVER}'); return h ? h.textContent : null; }}"
)


@pytest.fixture
def fast_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTMLEDITOR_POLL_INTERVAL", "100")
    config_module.reset_settings_cache()


def _open(page: Page, deck: ServedDeck) -> list[str]:
    loads: list[str] = []
    page.on("request", lambda req: loads.append(req.url) if "/content-frame" in req.url else None)
    page.goto(f"http://127.0.0.1:{deck.port}/")
    wait_for_js(page, COVER_TEXT, "Couverture", what="the cover shown")
    return loads


def _agent_writes_title(deck: ServedDeck) -> None:
    source = deck.path.read_text(encoding="utf-8")
    assert "Couverture" in source
    deck.path.write_text(source.replace("Couverture", AGENT_TITLE), encoding="utf-8")
    later = time.time() + 10
    os.utime(deck.path, (later, later))


@needs_chromium
def test_e2e_004_the_overlay_shows_and_the_preview_is_not_loaded_while_the_window_is_open(
    page: Page, fast_poll: None, served_deck: ServedDeck
) -> None:
    loads = _open(page, served_deck)
    before = len(loads)
    get_state().set_update_flag(True)
    try:
        wait_for_js(page, OVERLAY, "flex", what="the update overlay shown")
        _agent_writes_title(served_deck)
        settle(page)  # about ten poll cycles at the forced 100 ms interval
        assert len(loads) == before
        assert page.evaluate(COVER_TEXT) == "Couverture"
    finally:
        get_state().set_update_flag(False)


@needs_chromium
def test_e2e_005_the_preview_reloads_exactly_once_after_the_window_closes(
    page: Page, fast_poll: None, served_deck: ServedDeck
) -> None:
    loads = _open(page, served_deck)
    before = len(loads)
    get_state().set_update_flag(True)
    wait_for_js(page, OVERLAY, "flex", what="the update overlay shown")
    _agent_writes_title(served_deck)
    get_state().set_update_flag(False)
    wait_for_js(page, OVERLAY, "none", what="the update overlay hidden")
    wait_for_js(page, COVER_TEXT, AGENT_TITLE, what="the new title shown after the reload")
    wait_until(page, lambda: len(loads), lambda count: count >= before + 1, what="a reload")
    settle(page)
    assert len(loads) == before + 1
