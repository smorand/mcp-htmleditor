"""SPEC-0015 E2E-017 to E2E-019, E2E-026, E2E-027, E2E-032, E2E-036 and E2E-039 (US-0092): interrupted drags,
saves during a drag, conflicts and a stopped server.

Real headless Chromium against a real editor server. One page is shared by the module (DEC-011), one server
per test, the poll every 100 ms. Every saved result is read in the file on disk, every notice in the shell.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import Page, expect

from mcp_htmleditor import config as config_module
from mcp_htmleditor.http_server import start_http_server, stop_http_server
from mcp_htmleditor.state import get_state
from tests.browser_wait import settle, wait_for_file, wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.test_save_ui_e2e import CONFLICT_TEXT, LOST_TEXT, PENDING_DOT_COLOR
from tests.width_support import (
    PARAGRAPH,
    READOUT,
    count_polls,
    deck_d1,
    double_click_bar,
    drag_bar,
    element_starting_with,
    focus_bar,
    markers_in,
    open_editor,
    point_bar,
    style_in_file,
    undo_disabled,
    wait_polls,
    width_page,
    write_fixture,
)

pytestmark = needs_chromium

__all__ = ["width_page"]

A = "Chiffres clés du trimestre"
H = "Objectifs"
J = "Hors charte"
H_STYLE = "max-width: 40em;color:#525252;font-size:10px"
CHANGED = "Changé"
DOT_COLOR = "() => getComputedStyle(document.getElementById('toolbar-status')).color"
SAVES = "() => window.__widthSaves"
SAVES_DONE = "() => saveCount"
OVERLAY_SHOWN = "() => getComputedStyle(document.getElementById('update-overlay')).display"
CANCEL = (
    "() => document.getElementById('width-bar')"
    ".dispatchEvent(new PointerEvent('pointercancel', { pointerId: 1, bubbles: true }))"
)
RELEASE_CAPTURE = "() => document.getElementById('width-bar').releasePointerCapture(1)"
# Null-safe: polled while the reloaded iframe is still parsing, when the node does not exist yet.
FRAME_TEXT = (
    "(sel) => document.getElementById('content-frame').contentDocument?.querySelector(sel)?.textContent ?? null"
)
BLOCK_WIDTH = (
    "(sel) => document.getElementById('content-frame').contentDocument.querySelector(sel).getBoundingClientRect().width"
)
SAVE_ERROR = re.compile(r"Save failed: \S+")
FRAME_WINDOW = "document.getElementById('content-frame').contentWindow"
PROBE = f"() => {FRAME_WINDOW}.__probe"


@pytest.fixture(autouse=True)
def fast_poll(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Poll every 100 ms, so three failed polls take about 300 ms (DEC-011)."""
    monkeypatch.setenv("HTMLEDITOR_POLL_INTERVAL", "100")
    config_module.reset_settings_cache()
    yield
    monkeypatch.delenv("HTMLEDITOR_POLL_INTERVAL")
    config_module.reset_settings_cache()


def _served(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> ServedDeck:
    return serve_deck(write_fixture(tmp_path, deck_d1()))


def _width(page: Page, selector: str) -> float:
    return float(page.evaluate(BLOCK_WIDTH, selector))


def _press_and_move(page: Page, selector: str, dx: float) -> tuple[float, float]:
    """Press the block's width bar and move ``dx`` screen pixels right, button held; return the press point."""
    bar = point_bar(page, selector)
    x, y = bar["x"] + bar["width"] / 2, bar["y"] + bar["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y)
    return x, y


def _agent_writes(deck: ServedDeck, old: str, new: str) -> None:
    """Rewrite the file as an agent would, with an mtime the editor cannot have seen."""
    source = deck.path.read_text(encoding="utf-8")
    assert old in source
    deck.path.write_text(source.replace(old, new, 1), encoding="utf-8")
    later = time.time() + 10
    os.utime(deck.path, (later, later))


def _expect_notice(page: Page, selector: str, text: str | re.Pattern[str]) -> None:
    """The notice is shown (a hidden notice keeps its text, so the text alone proves nothing) and reads ``text``."""
    notice = page.locator(selector)
    expect(notice).to_be_visible()
    expect(notice).to_contain_text(text)


def _type_at_end(page: Page, selector: str, text: str) -> None:
    page.frame_locator("#content-frame").locator(selector).click()
    page.keyboard.press("End")
    page.keyboard.type(text)


def _slide_rows(html: str, styles: dict[str, str]) -> list[str]:
    """Every element of the slides, as name, attributes and own text; the runtime `active` class left out.

    ``styles`` maps the start of a paragraph's text to the style it is given before the rows are read.
    """
    soup = BeautifulSoup(html, "html.parser")
    for text, style in styles.items():
        found = [tag for tag in soup.find_all("p") if tag.get_text().strip().startswith(text)]
        found[-1]["style"] = style
    rows = []
    for slide in soup.find_all(attrs={"data-type": "slide"}):
        for tag in [slide, *slide.find_all(True)]:
            attrs = {
                k: " ".join(c for c in v if c != "active") if isinstance(v, list) else v for k, v in tag.attrs.items()
            }
            own = "".join(tag.find_all(string=True, recursive=False)).strip()
            rows.append(f"{tag.name} {sorted(attrs.items())} {own!r}")
    return rows


def _px_outside_styles(html: str) -> list[str]:
    """Text or attribute values holding `px`, outside a style attribute and outside style and script elements."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["style", "script"]):
        tag.decompose()
    found = [str(s).strip() for s in soup.find_all(string=True) if "px" in s]
    for tag in soup.find_all(True):
        found.extend(f"{tag.name}[{k}]" for k, v in tag.attrs.items() if k != "style" and "px" in str(v))
    return found


def test_width_failures_nothing_of_the_editor_saved(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-017: drag A to 650, Right on A, reset H, Undo, Redo, reload: only A's and H's styles differ from D1."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)

    drag_bar(page, PARAGRAPH["A"], 47)
    wait_for_file(page, deck.path, "max-width:650px")
    focus_bar(page, PARAGRAPH["A"])
    page.keyboard.press("ArrowRight")
    wait_for_file(page, deck.path, "max-width:660px")
    double_click_bar(page, PARAGRAPH["H"])
    wait_until(
        page, lambda: style_in_file(deck.path, H), lambda s: s == "color:#525252; font-size:10px", what="H reset"
    )
    page.click("#undo-btn")
    wait_until(page, lambda: style_in_file(deck.path, H), lambda s: s == H_STYLE, what="H undone")
    page.click("#redo-btn")
    wait_until(
        page, lambda: style_in_file(deck.path, H), lambda s: s == "color:#525252; font-size:10px", what="H redone"
    )
    open_editor(page, deck.port)

    saved = deck.path.read_text(encoding="utf-8")
    expected = {A: "max-width:660px", H: "color:#525252; font-size:10px"}
    assert _slide_rows(saved, {}) == _slide_rows(deck_d1(), expected)
    assert len(BeautifulSoup(saved, "html.parser").find_all(True)) == len(
        BeautifulSoup(deck_d1(), "html.parser").find_all(True)
    ), "an element was added or removed"
    assert markers_in(deck.path) == []
    assert _px_outside_styles(saved) == []


def test_width_failures_autosave_during_drag_keeps_old_width(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-018: the typing save that lands during the drag writes J typed and A at 600; the release writes 650."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)

    _type_at_end(page, PARAGRAPH["J"], "!")
    x, y = _press_and_move(page, PARAGRAPH["A"], 100)
    assert page.evaluate(READOUT) == "700 px"
    # The hold: until the typing save lands (the spec's 2 s hold).
    wait_for_file(page, deck.path, f"{J}!")
    assert style_in_file(deck.path, A) == "max-width:600px"
    assert page.evaluate(READOUT) == "700 px", "the drag ended during the hold"
    # Pressing the bar blurs J, so its save starts before the preview: one more save runs with the preview at 700.
    done = int(page.evaluate(SAVES_DONE))
    page.evaluate("() => saveContent()")
    wait_for_js(page, SAVES_DONE, done + 1, what="the save during the drag done")
    assert style_in_file(deck.path, A) == "max-width:600px"
    assert _width(page, PARAGRAPH["A"]) == 700, "the preview is not back after the save"

    page.mouse.move(x + 50, y)
    assert page.evaluate(READOUT) == "650 px"
    page.mouse.up()
    wait_for_file(page, deck.path, "max-width:650px")
    assert style_in_file(deck.path, A) == "max-width:650px"
    assert element_starting_with(deck.path.read_text(encoding="utf-8"), J).get_text().strip() == f"{J}!"


def test_width_failures_cancelled_drag_changes_nothing(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-019: a pointercancel, then a capture lost without pointerup: A is 600 again, nothing saved, no Undo."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    before = deck.path.read_text(encoding="utf-8")
    open_editor(page, deck.port)

    _press_and_move(page, PARAGRAPH["A"], 100)
    assert page.evaluate(READOUT) == "700 px"
    page.evaluate(CANCEL)
    assert _width(page, PARAGRAPH["A"]) == 600
    assert page.evaluate(READOUT) is None
    page.mouse.up()

    x, y = _press_and_move(page, PARAGRAPH["A"], 100)
    assert page.evaluate(READOUT) == "700 px"
    page.evaluate(RELEASE_CAPTURE)
    # lostpointercapture is dispatched with the next pointer event, here a move with the button still down.
    page.mouse.move(x + 101, y)
    assert _width(page, PARAGRAPH["A"]) == 600
    assert page.evaluate(READOUT) is None
    page.mouse.up()

    settle(page)
    assert deck.path.read_text(encoding="utf-8") == before
    assert page.evaluate(SAVES) == 0
    assert _width(page, PARAGRAPH["A"]) == 600
    assert undo_disabled(page)


def test_width_failures_file_changed_during_drag(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-026: the agent writes the file during the drag; the release meets the conflict notice, disk kept."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)

    page.evaluate(f"() => {{ {FRAME_WINDOW}.__probe = 1; }}")
    count_polls(page)
    x, y = _press_and_move(page, PARAGRAPH["A"], 100)
    wait_for_js(page, "() => selfSaving", False, what="no save in flight")
    _agent_writes(deck, f">{J}<", f">{CHANGED}<")
    # Observed by answered polls, not lastMtime: lastMtime no longer moves during a drag (DEC-008 stale view fix).
    wait_polls(page)
    page.mouse.move(x + 50, y)
    assert page.evaluate(READOUT) == "650 px"
    page.mouse.up()

    _expect_notice(page, "#save-conflict", CONFLICT_TEXT)
    wait_for_js(page, SAVES_DONE, 1, what="the release save answered")
    assert page.evaluate(PROBE) == 1, "the frame reloaded during the drag"
    saved = deck.path.read_text(encoding="utf-8")
    assert f">{CHANGED}<" in saved
    assert style_in_file(deck.path, A) == "max-width:600px"


def test_width_failures_drag_ended_without_save_shows_agent_write(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """DEC-008: an agent write during a drag that ends without a save (release at the original value, press with no
    move, pointercancel) is shown once the drag ends, by the next poll; nothing is saved."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)
    count_polls(page)

    def back_to_start(x: float, y: float) -> None:
        page.mouse.move(x, y)
        assert page.evaluate(READOUT) == "600 px"
        page.mouse.up()

    def cancel(_x: float, _y: float) -> None:
        page.evaluate(CANCEL)
        page.mouse.up()

    endings: list[tuple[str, float, Callable[[float, float], None]]] = [
        ("release at the original value", 100, back_to_start),
        ("press with no move", 0, lambda _x, _y: page.mouse.up()),
        ("pointercancel", 100, cancel),
    ]
    for n, (ending, dx, end) in enumerate(endings, 1):
        written = f"{CHANGED} {n}"
        previous = J if n == 1 else f"{CHANGED} {n - 1}"
        x, y = _press_and_move(page, PARAGRAPH["A"], dx)
        _agent_writes(deck, f">{previous}<", f">{written}<")
        wait_polls(page)
        assert page.evaluate(FRAME_TEXT, PARAGRAPH["J"]) == previous, f"{ending}: reloaded during the drag"
        end(x, y)
        wait_until(
            page,
            lambda: page.evaluate(FRAME_TEXT, PARAGRAPH["J"]),
            lambda text, shown=written: text == shown,
            what=f"{ending}: the agent's text shown after the drag",
        )
        assert page.evaluate(SAVES) == 0, f"{ending}: a save was sent"
        open_editor(page, deck.port)
        count_polls(page)
    assert style_in_file(deck.path, A) == "max-width:600px"


def test_width_failures_server_unreachable(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-027: server stopped, A dragged to 650: error notice, pending, 650 on screen, then connection lost."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)
    stop_http_server()

    seen = drag_bar(page, PARAGRAPH["A"], 47)

    assert seen[-2] == "650 px", f"readouts while moving: {seen}"
    _expect_notice(page, "#save-error", SAVE_ERROR)
    wait_for_js(page, DOT_COLOR, PENDING_DOT_COLOR, what="the status dot pending")
    assert _width(page, PARAGRAPH["A"]) == 650
    _expect_notice(page, "#connection-lost", LOST_TEXT)
    assert page.evaluate(DOT_COLOR) == PENDING_DOT_COLOR
    assert style_in_file(deck.path, A) == "max-width:600px"


def test_width_failures_typing_before_drag_kept(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-032: `!` typed at the end of A, then at once A dragged to 650: both saved."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)

    _type_at_end(page, PARAGRAPH["A"], "!")
    seen = drag_bar(page, PARAGRAPH["A"], 47)

    assert seen[-2] == "650 px", f"readouts while moving: {seen}"
    saved = wait_for_file(page, deck.path, "max-width:650px")
    a = element_starting_with(saved, A)
    assert a.get_text().strip() == f"{A}!"
    assert a.get("style") == "max-width:650px"


def test_width_failures_reload_during_drag(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-036: an agent update ends during the drag: J `Changé` and A 600 shown, nothing saved, no Undo."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)

    _press_and_move(page, PARAGRAPH["A"], 100)
    assert page.evaluate(READOUT) == "700 px"
    get_state().set_update_flag(True)
    try:
        wait_for_js(page, OVERLAY_SHOWN, "flex", what="the update overlay shown")
        assert page.evaluate(READOUT) is None, "the agent update did not cancel the drag"
        _agent_writes(deck, f">{J}<", f">{CHANGED}<")
    finally:
        get_state().set_update_flag(False)
    wait_until(page, lambda: page.evaluate(FRAME_TEXT, PARAGRAPH["J"]), lambda t: t == CHANGED, what="J reloaded")
    page.mouse.up()

    settle(page)
    assert page.evaluate(FRAME_TEXT, PARAGRAPH["J"]) == CHANGED
    page.evaluate(f"() => {FRAME_WINDOW}.goToSlide(1)")  # the reloaded deck opens on its first slide
    assert _width(page, PARAGRAPH["A"]) == 600
    assert style_in_file(deck.path, A) == "max-width:600px"
    assert page.evaluate(SAVES) == 0
    assert undo_disabled(page)


def test_width_failures_reset_with_server_unreachable(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-039: reset while the server is stopped stays pending; once back, the next save writes A unstyled."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)
    stop_http_server()

    double_click_bar(page, PARAGRAPH["A"])

    wait_until(page, lambda: _width(page, PARAGRAPH["A"]), lambda w: w == 800, what="A 800 wide")
    _expect_notice(page, "#save-error", SAVE_ERROR)
    wait_for_js(page, DOT_COLOR, PENDING_DOT_COLOR, what="the status dot pending")
    assert style_in_file(deck.path, A) == "max-width:600px"

    start_http_server(str(deck.path), port=deck.port, host="127.0.0.1")
    _type_at_end(page, PARAGRAPH["J"], "!")
    wait_for_file(page, deck.path, f"{J}!")
    assert style_in_file(deck.path, A) is None
