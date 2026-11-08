"""The pointer in the editor's presentation of a served deck (SPEC-0017, US-0103).

Deck P is served by one editor server per test (``serve_deck``) and shown in the module page at 1600 by 900;
``#present-btn`` presents it, the keyboard focus lands in the deck and L turns the pointer on (``present_served``).
Every read goes through the framed document (``FRAME_DOC``).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page

from tests.browser_wait import settle, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.pointer_support import (
    FRAME_DOC,
    RING_LINE,
    SCALE,
    click_centre,
    deck_p_path,
    is_ringed,
    pointer_file_page,
    pointer_state,
    present_served,
    resize_presented,
    ring_around,
    wait_ringed,
    wait_state,
)

__all__ = ["deck_p_path", "pointer_file_page"]

BACKGROUND = (800, 450)  # slide 1's empty middle (pointer_support.SLIDE_1_BODY)

TILE_LOOK = (
    "() => {{ const cs = getComputedStyle(({doc}).getElementById('tile-a'));"
    " return [cs.outline, cs.boxShadow, cs.border, cs.backgroundColor, cs.transform]; }}"
)
# Records the timing of every animation started in the deck, so the ring's appearance can be read once over.
SPY_ANIMATIONS = (
    "() => {{ const win = ({doc}).defaultView; const animate = win.Element.prototype.animate;"
    " win.ringAnimations = [];"
    " win.Element.prototype.animate = function (frames, options) {{"
    "   if (this.id === 'deck-pointer-ring') win.ringAnimations.push(options);"
    "   return animate.call(this, frames, options); }}; }}"
)


@pytest.fixture
def served_p(tmp_path: Path, deck_p_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> ServedDeck:
    copy = tmp_path / "deck-p.html"
    shutil.copyfile(deck_p_path, copy)
    return serve_deck(copy)


@needs_chromium
def test_pointer_served_click_rings_a_tile(pointer_file_page: Page, served_p: ServedDeck) -> None:
    """E2E-006."""
    page = pointer_file_page
    present_served(page, served_p.port)
    look = page.evaluate(TILE_LOOK.format(doc=FRAME_DOC))
    page.evaluate(SPY_ANIMATIONS.format(doc=FRAME_DOC))

    click_centre(page, "#tile-a", FRAME_DOC)
    wait_ringed(page, "#tile-a", FRAME_DOC)
    ring = pointer_state(page, FRAME_DOC)["ring"]
    assert ring["border"] == pytest.approx(RING_LINE * SCALE, abs=1)
    assert page.evaluate(TILE_LOOK.format(doc=FRAME_DOC)) == look
    durations = page.evaluate(f"({FRAME_DOC}).defaultView.ringAnimations.map(o => o.duration)")
    assert durations, "the ring's appearance was not animated (no reduced motion asked)"
    assert all(duration <= 200 for duration in durations), durations


@needs_chromium
def test_pointer_served_table_is_one_box(pointer_file_page: Page, served_p: ServedDeck) -> None:
    """E2E-008. A click on the ringed table would remove its ring (FR-NEW-006, E2E-009), so a click on the slide
    background clears it between the two cell clicks: each cell click then rings from no ring."""
    page = pointer_file_page
    present_served(page, served_p.port)
    click_centre(page, "#table-p tr:nth-child(2) td:first-child", FRAME_DOC)
    first = wait_ringed(page, "#table-p", FRAME_DOC)
    page.mouse.click(*BACKGROUND)
    wait_state(page, lambda s: s["rings"] == 0, "the ring cleared", FRAME_DOC)
    click_centre(page, "#table-p tr:first-child td:last-child", FRAME_DOC)
    second = wait_ringed(page, "#table-p", FRAME_DOC)
    assert second["ring"] == first["ring"]


@needs_chromium
def test_pointer_served_button_runs_ring_unchanged(pointer_file_page: Page, served_p: ServedDeck) -> None:
    """E2E-014."""
    page = pointer_file_page
    present_served(page, served_p.port)
    click_centre(page, "#btn-count", FRAME_DOC)
    settle(page)
    assert page.evaluate(f"({FRAME_DOC}).getElementById('btn-count').textContent") == "Count 1"
    state = pointer_state(page, FRAME_DOC)
    assert (state["on"], state["ring"], state["rings"]) == (True, None, 0)


@needs_chromium
def test_pointer_served_scaling_and_resizing(pointer_file_page: Page, served_p: ServedDeck) -> None:
    """E2E-024."""
    page = pointer_file_page
    present_served(page, served_p.port)
    click_centre(page, "#tile-a", FRAME_DOC)
    before = wait_ringed(page, "#tile-a", FRAME_DOC)

    session = resize_presented(page, 1280, 720)
    try:
        page.mouse.move(640, 360)
        state = wait_state(
            page,
            lambda s: s["dot"] is not None and abs(s["dot"]["x"] - 640) <= 1 and abs(s["dot"]["y"] - 360) <= 1,
            "the dot at (640, 360)",
            FRAME_DOC,
        )
        assert state["dot"]["d"] == pytest.approx(24, abs=1)
        after = wait_until(
            page,
            lambda: ring_around(page, "#tile-a", FRAME_DOC),
            lambda c: is_ringed(c, 1280 / 960),
            what="Tile A ringed at scale 1.3333",
        )
        assert after["box"] != before["box"], "the tile did not move with the resize"
    finally:
        session.send("Emulation.clearDeviceMetricsOverride")
