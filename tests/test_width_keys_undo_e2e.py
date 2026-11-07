"""SPEC-0015 keyboard steps, reset and undo of a width (US-0090).

E2E-008, 009, 010, 011, 012, 013, 014, 015, 016, 020, 030, 037, 038 and 040, in real headless Chromium against a
real editor server. One page is shared by the module and one server is started per test (DEC-011); to keep the
suite inside its time cap, each test runs several spec scenarios in turn on the same fixture, every scenario marked
by its spec id and asserting on the file on disk.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

from tests.browser_wait import settle, wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.test_undo_redo_e2e import MOD
from tests.width_support import (
    PARAGRAPH,
    SAVED_DOT_COLOR,
    deck_d1,
    double_click_bar,
    drag_bar,
    focus_bar,
    open_editor,
    point_bar,
    redo_disabled,
    style_in_file,
    undo_disabled,
    width_page,
    write_fixture,
)

pytestmark = needs_chromium

__all__ = ["width_page"]

A = "Chiffres clés du trimestre"
B = "Note de synthèse"
H = "Objectifs"
I = "Mini"  # noqa: E741  # the spec's own letter for paragraph I
J = "Hors charte"
K = "Large"
TOOLTIP = "Glisser pour régler la largeur, double clic pour revenir à la largeur du modèle"
DOT_COLOR = "() => getComputedStyle(document.getElementById('toolbar-status')).color"
SAVES = "() => window.__widthSaves"
BAR_FOCUS = (
    "() => { const b = document.getElementById('width-bar');"
    " return [document.activeElement && document.activeElement.id, getComputedStyle(b).outlineStyle]; }"
)


def _served(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> ServedDeck:
    return serve_deck(write_fixture(tmp_path, deck_d1()))


def _style_becomes(page: Page, deck: ServedDeck, text: str, expected: str | None) -> None:
    """Wait until the style of the paragraph starting with ``text`` reads ``expected`` in the file."""
    wait_until(
        page,
        lambda: style_in_file(deck.path, text),
        lambda style: style == expected,
        what=f"the style of {text!r} reading {expected!r}",
    )


def _saves(page: Page) -> int:
    return int(page.evaluate(SAVES))


def _wait_saves(page: Page, count: int) -> None:
    wait_for_js(page, SAVES, count, what=f"{count} saves sent")
    wait_for_js(page, DOT_COLOR, SAVED_DOT_COLOR, what="the status dot saved")


def _block_width(page: Page, selector: str) -> float:
    return float(
        page.evaluate(
            "(sel) => document.getElementById('content-frame').contentDocument.querySelector(sel)"
            ".getBoundingClientRect().width",
            selector,
        )
    )


def _undo(page: Page, deck: ServedDeck, text: str, expected: str | None) -> None:
    page.click("#undo-btn")
    _style_becomes(page, deck, text, expected)


def test_width_keys_undo_keyboard_steps(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-030 name, tooltip and focus; E2E-008 keyboard steps and undo; E2E-016 redo cleared; E2E-038 K."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)

    # E2E-030: tooltip, accessible name, focus with a visible outline after a click, then Right works.
    point_bar(page, PARAGRAPH["A"])
    assert page.get_attribute("#width-bar", "title") == TOOLTIP
    assert page.get_by_role("separator", name="Largeur du texte").count() == 1
    focus_bar(page, PARAGRAPH["A"])
    active, outline = page.evaluate(BAR_FOCUS)
    assert active == "width-bar"
    assert outline != "none", "the focused bar shows a visible outline"

    # E2E-008: Right, Shift+Right, Left, each saved; three Undo bring back 600.
    page.keyboard.press("ArrowRight")
    _style_becomes(page, deck, A, "max-width:610px")
    _wait_saves(page, 1)
    page.keyboard.press("Shift+ArrowRight")
    _style_becomes(page, deck, A, "max-width:660px")
    _wait_saves(page, 2)
    page.keyboard.press("ArrowLeft")
    _style_becomes(page, deck, A, "max-width:650px")
    _wait_saves(page, 3)
    _undo(page, deck, A, "max-width:660px")
    _undo(page, deck, A, "max-width:610px")
    _undo(page, deck, A, "max-width:600px")
    assert undo_disabled(page)

    # E2E-016: Redo enabled, a new Right on A clears it.
    assert not redo_disabled(page)
    focus_bar(page, PARAGRAPH["A"])
    page.keyboard.press("ArrowRight")
    _style_becomes(page, deck, A, "max-width:610px")
    wait_until(page, lambda: redo_disabled(page), bool, what="Redo disabled")

    # E2E-038: K (max-width:1250px) is 800 wide in its column: Right starts from 800.
    focus_bar(page, PARAGRAPH["K"])
    page.keyboard.press("ArrowRight")
    _style_becomes(page, deck, K, "max-width:810px")


def test_width_keys_undo_nothing_saved(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-009 key at the bound, E2E-020 press without move, E2E-012 reset without width, E2E-037 other keys.

    One wait for absence covers the four: after them the file is byte identical, one save only was sent, and a
    single Undo empties the history, so none of them recorded an undo step.
    """
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)
    assert undo_disabled(page)

    # E2E-009: I is 85 wide; Left gives 80.
    focus_bar(page, PARAGRAPH["I"])
    page.keyboard.press("ArrowLeft")
    _style_becomes(page, deck, I, "max-width:80px")
    _wait_saves(page, 1)
    at_bound = deck.path.read_bytes()

    page.keyboard.press("ArrowLeft")  # E2E-009: a second Left at the bound
    focus_bar(page, PARAGRAPH["A"])  # E2E-020: press and release without moving
    double_click_bar(page, PARAGRAPH["B"])  # E2E-012: B has no inline width, twice
    double_click_bar(page, PARAGRAPH["B"])
    focus_bar(page, PARAGRAPH["A"])  # E2E-037: other keys keep their usual effect
    for key in ("ArrowUp", "ArrowDown", "a", "Enter"):
        page.keyboard.press(key)
    settle(page)
    assert deck.path.read_bytes() == at_bound
    assert _saves(page) == 1

    # E2E-009: one Undo brings back 85 and Undo is then disabled.
    _undo(page, deck, I, "max-width:85px")
    wait_until(page, lambda: undo_disabled(page), bool, what="Undo disabled")


def test_width_keys_undo_reset(width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    """E2E-013 Delete and Backspace, E2E-010 double click on A, E2E-011 reset keeps H's other declarations."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)

    paragraphs = "() => document.getElementById('content-frame').contentDocument.querySelectorAll('p').length"
    count = page.evaluate(paragraphs)

    # E2E-013: Delete on A's focused bar, Backspace on I's.
    focus_bar(page, PARAGRAPH["A"])
    page.keyboard.press("Delete")
    _style_becomes(page, deck, A, None)
    focus_bar(page, PARAGRAPH["I"])
    page.keyboard.press("Backspace")
    _style_becomes(page, deck, I, None)
    assert page.evaluate(paragraphs) == count, "Delete and Backspace on the bar remove no block"

    # E2E-010: A back to max-width:600px by Undo, then a double click gives the template's width back.
    _undo(page, deck, I, "max-width:85px")
    _undo(page, deck, A, "max-width:600px")
    double_click_bar(page, PARAGRAPH["A"])
    _style_becomes(page, deck, A, None)
    wait_for_js(page, DOT_COLOR, SAVED_DOT_COLOR, what="the status dot saved")
    assert _block_width(page, PARAGRAPH["A"]) == 800

    # E2E-011: the other declarations of H are kept, joined with '; '.
    double_click_bar(page, PARAGRAPH["H"])
    _style_becomes(page, deck, H, "color:#525252; font-size:10px")


def test_width_keys_undo_redo_drag(width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    """E2E-014 undo and redo a drag, E2E-015 the shortcut reverts typing first, E2E-040 reload empties history."""
    page = width_page
    deck = _served(tmp_path, serve_deck)
    open_editor(page, deck.port)

    # E2E-014: drag A to 650, Undo gives 600 (and 600 wide), Redo gives 650, both saved.
    drag_bar(page, PARAGRAPH["A"], 47)
    _style_becomes(page, deck, A, "max-width:650px")
    _wait_saves(page, 1)
    _undo(page, deck, A, "max-width:600px")
    _wait_saves(page, 2)
    wait_until(page, lambda: _block_width(page, PARAGRAPH["A"]), lambda width: width == 600, what="A 600 wide")
    page.click("#redo-btn")
    _style_becomes(page, deck, A, "max-width:650px")
    _wait_saves(page, 3)

    # E2E-015: type '!' at the end of J, then the shortcut once, caret still in J: the typing goes, not the width.
    j = page.frame_locator("#content-frame").locator(PARAGRAPH["J"])
    j.click()
    page.keyboard.press("End")
    page.keyboard.type("!")
    wait_until(page, j.inner_text, lambda text: text == f"{J}!", what="J typed")
    page.keyboard.press(f"{MOD}+z")
    wait_until(page, j.inner_text, lambda text: text == J, what="J reverted")
    # A structural undo would have moved the width step to Redo at once: Redo still disabled shows the shortcut went
    # to the typing, not to the width.
    assert redo_disabled(page)
    assert style_in_file(deck.path, A) == "max-width:650px"
    assert (
        page.evaluate(
            "() => getComputedStyle(document.getElementById('content-frame').contentDocument"
            f".querySelector('{PARAGRAPH['A']}')).maxWidth"
        )
        == "650px"
    )

    # E2E-040: a reload empties the history, A stays 650 in the file.
    open_editor(page, deck.port)
    assert undo_disabled(page)
    assert style_in_file(deck.path, A) == "max-width:650px"
