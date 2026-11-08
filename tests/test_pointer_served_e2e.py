"""The pointer in the editor's presentation of a served deck (SPEC-0017, US-0103, US-0104).

Deck P (or Deck O) is served by one editor server per test (``serve_deck``) and shown in the module page at 1600 by
900; ``#present-btn`` presents it, the keyboard focus lands in the deck and L turns the pointer on
(``present_served``). Every read goes through the framed document (``FRAME_DOC``). A key "typed with the focus in
the editor page" is dispatched on the editor page's own document (``dispatch_key``, SPEC-0016 DEC-002): headless
Chromium keeps the focus in the iframe, so ``page.keyboard`` would never reach the editor's relay.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import Page

from mcp_htmleditor import config as config_module
from tests.browser_wait import settle, wait_for_file, wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.pointer_support import (
    FRAME_DOC,
    RING_LINE,
    SCALE,
    PointerState,
    click_centre,
    deck_o,
    deck_p_path,
    dispatch_key,
    is_ringed,
    next_frames,
    open_deck_p,
    open_served,
    pointer_control,
    pointer_file_page,
    pointer_state,
    present_served,
    present_with,
    resize_presented,
    ring_around,
    wait_presenting,
    wait_ringed,
    wait_slide_settled,
    wait_state,
)
from tests.width_support import SAVE_COUNTER_SCRIPT, count_polls, wait_polls

__all__ = ["deck_p_path", "pointer_file_page"]

BACKGROUND = (800, 450)  # slide 1's empty middle (pointer_support.SLIDE_1_BODY)
POLL_MS = 100
# E2E-028 waits for quiet status polls (DEC-017): 10 polls of 100 ms outlast the editor's longest autosave delay
# (800 ms, editor-save.js), so a save the pointer would trigger is sent before the file is compared.
QUIET_POLLS = 10

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
def fast_poll(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The editor polls ``/status`` every 100 ms, so an agent write reloads and quiet polls pass quickly."""
    monkeypatch.setenv("HTMLEDITOR_POLL_INTERVAL", str(POLL_MS))
    config_module.reset_settings_cache()
    yield
    monkeypatch.delenv("HTMLEDITOR_POLL_INTERVAL")
    config_module.reset_settings_cache()


@pytest.fixture
def served_p(
    tmp_path: Path, deck_p_path: Path, serve_deck: Callable[[Path], ServedDeck], fast_poll: None
) -> ServedDeck:
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


# US-0104: the editor's Pointeur control, the relay of L, edit mode and the save (DEC-013, DEC-014, DEC-019).

EDIT_MODE_ON = (
    "() => { const e = document.getElementById('content-frame').contentDocument"
    ".querySelector('[data-editable~=\"text\"]'); return !!e && e.isContentEditable; }"
)
SHOWN_SLIDE = f"() => {{ const d = {FRAME_DOC}; return [...d.querySelectorAll('[data-type=\"slide\"]')]"
SHOWN_SLIDE += ".findIndex(s => s.classList.contains('active')); }"
# The editor page point over slide 1's empty middle while the deck is shown in the frame (not presented).
SLIDE_MIDDLE = (
    "() => { const f = document.getElementById('content-frame'); const fr = f.getBoundingClientRect();"
    " const r = f.contentDocument.getElementById('slide-0').getBoundingClientRect();"
    " return [fr.left + r.left + r.width / 2, fr.top + r.top + r.height / 2]; }"
)
NOTICES_SHOWN = "() => ['save-conflict', 'save-error'].filter(id => !document.getElementById(id).hidden)"
CARET_AT_END = (
    "([sel]) => { const d = document.getElementById('content-frame').contentDocument; const el = d.querySelector(sel);"
    " el.focus(); const range = d.createRange(); range.selectNodeContents(el); range.collapse(false);"
    " const sel2 = d.getSelection(); sel2.removeAllRanges(); sel2.addRange(range); }"
)


@pytest.fixture
def served_o(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], fast_poll: None) -> ServedDeck:
    path = tmp_path / "deck-o.html"
    path.write_text(deck_o(), encoding="utf-8")
    return serve_deck(path)


def _dot_at_background(state: PointerState) -> bool:
    dot = state["dot"]
    return dot is not None and abs(dot["x"] - BACKGROUND[0]) <= 1 and abs(dot["y"] - BACKGROUND[1]) <= 1


def _not_presented(state: PointerState) -> bool:
    return state["fullscreen"] is None


def _move_and_read(page: Page) -> PointerState:
    """Move the mouse to the slide's empty middle and read the deck once it has drawn."""
    page.mouse.move(*BACKGROUND)
    next_frames(page, FRAME_DOC)
    return pointer_state(page, FRAME_DOC)


def _turn_edit_mode(page: Page, on: bool) -> None:
    page.click("#edit-mode-btn")
    wait_for_js(page, EDIT_MODE_ON, on, what=f"edit mode {'on' if on else 'off'}")


def _assert_nothing_of_the_pointer(saved: str, baseline: str) -> None:
    """No layer element, no pointer state on <html>; the deck's own pointer CSS (cursor:none) kept as it was."""
    soup = BeautifulSoup(saved, "html.parser")
    assert soup.select("#deck-pointer-layer, #deck-pointer-dot, #deck-pointer-ring") == []
    assert soup.html is not None
    assert "data-deck-pointer" not in soup.html.attrs
    assert saved.count("cursor:none") == baseline.count("cursor:none")


@needs_chromium
def test_pointer_served_focus_in_the_deck(pointer_file_page: Page, served_p: ServedDeck) -> None:
    """E2E-002."""
    page = pointer_file_page
    open_served(page, served_p.port)
    present_with(page, "#present-btn")
    wait_until(page, lambda: page.evaluate("document.activeElement.id"), lambda v: v == "content-frame", what="focus")

    page.keyboard.press("l")
    page.mouse.move(*BACKGROUND)
    wait_state(page, _dot_at_background, "the dot at (800, 450)", FRAME_DOC)
    page.keyboard.press("l")
    state = wait_state(page, lambda s: not s["on"], "pointer off", FRAME_DOC)
    assert (state["dot"], state["layer"]) == (None, False)
    assert state["cursor"] != "none"


@needs_chromium
def test_pointer_served_l_from_the_editor_page_toggles_once(pointer_file_page: Page, served_p: ServedDeck) -> None:
    """E2E-003."""
    page = pointer_file_page
    open_served(page, served_p.port)
    present_with(page, "#present-btn")

    assert dispatch_key(page, "l"), "the relay did not take L"
    state = _move_and_read(page)
    assert state["on"], "L from the editor page did not turn the pointer on (or toggled it twice)"
    assert _dot_at_background(state), state
    dispatch_key(page, "ArrowRight")
    assert pointer_state(page, FRAME_DOC)["current"] == 1
    dispatch_key(page, "L")
    state = _move_and_read(page)
    assert (state["on"], state["dot"], state["layer"]) == (False, None, False)


@needs_chromium
def test_pointer_served_pointeur_control(pointer_file_page: Page, served_p: ServedDeck) -> None:
    """E2E-004."""
    page = pointer_file_page
    open_served(page, served_p.port)
    control = pointer_control(page)
    assert control["exists"] and control["shown"], control
    assert control["afterPresent"] and control["left"] > control["presentRight"], control
    assert control["title"] == control["label"] == "Présenter avec le pointeur (L)"
    assert control["text"] == "Pointeur"

    present_with(page, "#pointer-btn")
    assert pointer_state(page, FRAME_DOC)["on"], "Pointeur presented with the pointer off"
    assert _dot_at_background(_move_and_read(page))

    page.keyboard.press("Escape")
    wait_state(page, _not_presented, "full screen left", FRAME_DOC)
    present_with(page, "#present-btn")
    state = _move_and_read(page)
    assert (state["on"], state["dot"]) == (False, None), "the present control started with the pointer on"

    page.keyboard.press("Escape")
    wait_state(page, _not_presented, "full screen left", FRAME_DOC)
    present_with(page, "#pointer-btn")
    assert pointer_state(page, FRAME_DOC)["on"]
    text = served_p.path.read_text(encoding="utf-8")
    served_p.path.write_text(text.replace("Plain <strong>", "Changed <strong>", 1), encoding="utf-8")
    wait_until(
        page,
        lambda: page.evaluate(f"({FRAME_DOC}).body.textContent.includes('Changed paragraph')"),
        bool,
        what="the agent's write reloaded the deck",
    )
    wait_until(page, lambda: page.evaluate(f"({FRAME_DOC}).readyState"), lambda v: v == "complete", what="loaded")
    state = _move_and_read(page)
    assert (state["on"], state["dot"], state["layer"]) == (False, None, False)


@needs_chromium
def test_pointer_served_edit_mode_and_save_keep_no_pointer(pointer_file_page: Page, served_p: ServedDeck) -> None:
    """E2E-018 (DEC-019); a save while the pointer is on writes nothing of it either (DEC-014)."""
    page = pointer_file_page
    open_served(page, served_p.port)
    _turn_edit_mode(page, True)
    page.evaluate("() => saveContent()")
    baseline = served_p.path.read_text(encoding="utf-8")
    _turn_edit_mode(page, False)

    present_with(page, "#pointer-btn")
    click_centre(page, "#tile-a", FRAME_DOC)
    wait_ringed(page, "#tile-a", FRAME_DOC)
    page.evaluate("() => saveContent()")
    _assert_nothing_of_the_pointer(served_p.path.read_text(encoding="utf-8"), baseline)
    page.keyboard.press("Escape")
    wait_state(page, _not_presented, "full screen left", FRAME_DOC)

    _turn_edit_mode(page, True)
    assert not pointer_control(page)["shown"], "Pointeur shows while edit mode is on"
    present_with(page, "#present-btn")
    page.keyboard.press("l")
    dispatch_key(page, "l")
    state = _move_and_read(page)
    assert (state["on"], state["dot"], state["layer"]) == (False, None, False)
    page.keyboard.press("Escape")
    wait_state(page, _not_presented, "full screen left", FRAME_DOC)

    page.evaluate(CARET_AT_END, ["#slide-0 p[data-editable]"])
    page.keyboard.type("l")
    assert page.evaluate(f"({FRAME_DOC}).querySelector('#slide-0 p').textContent") == "Plain paragraphl"
    page.evaluate("() => saveContent()")
    saved = wait_for_file(page, served_p.path, "paragraphl")
    expected = {
        baseline.replace(">paragraph</strong>", ">paragraphl</strong>", 1),
        baseline.replace("paragraph</strong>", "paragraph</strong>l", 1),
    }
    assert saved in expected, "the save wrote more than the typed letter"
    _assert_nothing_of_the_pointer(saved, baseline)


@needs_chromium
def test_pointer_served_pointing_leaves_the_file_byte_identical(pointer_file_page: Page, served_p: ServedDeck) -> None:
    """E2E-028."""
    page = pointer_file_page
    before = served_p.path.read_bytes()
    open_served(page, served_p.port)
    page.evaluate(SAVE_COUNTER_SCRIPT)
    count_polls(page)

    present_with(page, "#present-btn")
    page.keyboard.press("l")
    wait_state(page, lambda s: s["on"], "pointer on", FRAME_DOC)
    for selector in ("#tile-a", "#tile-b", "#table-p"):
        click_centre(page, selector, FRAME_DOC)
        wait_ringed(page, selector, FRAME_DOC)
    page.keyboard.press("ArrowRight")
    page.keyboard.press("l")
    wait_state(page, lambda s: not s["on"] and s["current"] == 1, "slide 2, pointer off", FRAME_DOC)
    page.keyboard.press("Escape")
    wait_state(page, _not_presented, "full screen left", FRAME_DOC)
    wait_polls(page, QUIET_POLLS)

    assert served_p.path.read_bytes() == before
    assert page.evaluate("() => window.__widthSaves") == 0, "the editor sent a save"
    assert page.evaluate(NOTICES_SHOWN) == []


@needs_chromium
def test_pointer_served_existing_keys_with_the_pointer_on(
    pointer_file_page: Page, served_p: ServedDeck, deck_p_path: Path
) -> None:
    """E2E-031: opened directly (keys to the deck), then served (keys typed in the editor page)."""
    page = pointer_file_page
    keys = ("ArrowRight", " ", "ArrowLeft", "End", "Home")
    expected = [1, 2, 1, 2, 0]

    open_deck_p(page, deck_p_path)
    page.keyboard.press("f")
    wait_presenting(page)
    wait_slide_settled(page)
    page.keyboard.press("l")
    click_centre(page, "#tile-a")
    wait_ringed(page, "#tile-a")
    shown = []
    for index, key in enumerate(keys):
        page.keyboard.press("Space" if key == " " else key)
        state = wait_state(page, lambda s, i=index: s["current"] == expected[i], f"after {key!r}")
        if index == 0:
            wait_state(page, lambda s: s["rings"] == 0, "the ring gone after the first key")
        shown.append(state["current"])
    assert shown == expected
    page.keyboard.press("Escape")
    wait_state(page, _not_presented, "full screen left (opened directly)")

    open_served(page, served_p.port)
    present_with(page, "#present-btn")
    dispatch_key(page, "l")
    click_centre(page, "#tile-a", FRAME_DOC)
    wait_ringed(page, "#tile-a", FRAME_DOC)
    shown = []
    for index, key in enumerate(keys):
        dispatch_key(page, key)
        shown.append(pointer_state(page, FRAME_DOC)["current"])
        if index == 0:
            wait_state(page, lambda s: s["rings"] == 0, "the ring gone after the first key", FRAME_DOC)
    assert shown == expected
    dispatch_key(page, "Escape")
    wait_state(page, _not_presented, "full screen left (served)", FRAME_DOC)


@needs_chromium
def test_pointer_served_deck_without_the_pointer(pointer_file_page: Page, served_o: ServedDeck) -> None:
    """E2E-035: Deck O shows no Pointeur control, L changes nothing and raises no page error."""
    page = pointer_file_page
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    open_served(page, served_o.port)
    control = pointer_control(page)
    assert control["exists"] and not control["shown"], control

    present_with(page, "#present-btn")
    page.keyboard.press("l")
    assert not dispatch_key(page, "l"), "the relay took L for a deck without the pointer"
    state = _move_and_read(page)
    assert (state["on"], state["dot"], state["layer"], state["current"]) == (False, None, False, 0)
    dispatch_key(page, "ArrowRight")
    assert pointer_state(page, FRAME_DOC)["current"] == 1
    dispatch_key(page, "Escape")
    wait_state(page, _not_presented, "full screen left", FRAME_DOC)
    assert errors == []


@needs_chromium
def test_pointer_served_l_typed_in_edit_mode(pointer_file_page: Page, served_p: ServedDeck) -> None:
    """E2E-038."""
    page = pointer_file_page
    open_served(page, served_p.port)
    _turn_edit_mode(page, True)
    shown = page.evaluate(SHOWN_SLIDE)

    page.evaluate(CARET_AT_END, ["#tile-a .tile-title"])
    page.keyboard.type("L")
    assert page.evaluate(f"({FRAME_DOC}).querySelector('#tile-a .tile-title').textContent") == "Tile AL"
    state = _move_and_read(page)
    assert (state["on"], state["dot"], state["layer"]) == (False, None, False)

    page.mouse.click(*page.evaluate(SLIDE_MIDDLE))
    assert page.evaluate(f"({FRAME_DOC}).activeElement.tagName") == "BODY", "the click landed in a text"
    page.keyboard.press("L")
    dispatch_key(page, "L")
    state = _move_and_read(page)
    assert (state["on"], state["dot"], state["layer"]) == (False, None, False)
    assert page.evaluate(SHOWN_SLIDE) == shown
