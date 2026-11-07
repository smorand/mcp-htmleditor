"""SPEC-0015 E2E-001 to E2E-007 and E2E-042 (US-0089): drag the text width bar, one declaration saved.

Real headless Chromium against a real editor server. One page is shared by the module (DEC-011), one server
per test. Every assertion on the saved style reads the file on disk.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page

from tests.browser_wait import wait_for_file, wait_for_js
from tests.conftest import ServedDeck, needs_chromium
from tests.width_support import (
    PARAGRAPH,
    SAVED_DOT_COLOR,
    deck_d1,
    deck_d3,
    drag_bar,
    open_editor,
    show_slide_2,
    style_in_file,
    width_page,
    write_fixture,
)

pytestmark = needs_chromium

__all__ = ["width_page"]

DOT_COLOR = "() => getComputedStyle(document.getElementById('toolbar-status')).color"
SAVED_COUNT = "() => window.__widthSaves"
SAVE_DONE = "() => saveCount >= 1"


def _served(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], text: str) -> ServedDeck:
    return serve_deck(write_fixture(tmp_path, text))


def _block_width(page: Page, selector: str) -> float:
    return float(
        page.evaluate(
            "(sel) => document.getElementById('content-frame').contentDocument.querySelector(sel)"
            ".getBoundingClientRect().width",
            selector,
        )
    )


def test_width_drag_paragraph_saved(width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    """E2E-001: point at A, press the bar, move 47 px right, let go: `650 px` shown, `max-width:650px` saved."""
    deck = _served(tmp_path, serve_deck, deck_d1())
    open_editor(width_page, deck.port)

    seen = drag_bar(width_page, PARAGRAPH["A"], 47)

    assert seen[-2] == "650 px", f"readouts while moving: {seen}"
    assert seen[-1] is None, "the readout is gone after letting go"
    wait_for_file(width_page, deck.path, "max-width:650px")
    assert style_in_file(deck.path, "Chiffres clés du trimestre") == "max-width:650px"
    assert wait_for_js(width_page, DOT_COLOR, SAVED_DOT_COLOR, what="the status dot saved") == SAVED_DOT_COLOR
    show_slide_2(width_page, deck.port)
    assert _block_width(width_page, PARAGRAPH["A"]) == 650


def test_width_drag_alt_single_pixels(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-002: with Alt held, 47 px right gives `647 px` and `max-width:647px`."""
    deck = _served(tmp_path, serve_deck, deck_d1())
    open_editor(width_page, deck.port)

    seen = drag_bar(width_page, PARAGRAPH["A"], 47, alt=True)

    assert seen[-2] == "647 px", f"readouts while moving: {seen}"
    wait_for_file(width_page, deck.path, "max-width:647px")
    assert style_in_file(deck.path, "Chiffres clés du trimestre") == "max-width:647px"


def test_width_drag_lower_bound(width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    """E2E-003: 600 px left gives `80 px` and `max-width:80px`."""
    deck = _served(tmp_path, serve_deck, deck_d1())
    open_editor(width_page, deck.port)

    seen = drag_bar(width_page, PARAGRAPH["A"], -600)

    assert seen[-2] == "80 px", f"readouts while moving: {seen}"
    wait_for_file(width_page, deck.path, "max-width:80px")
    assert style_in_file(deck.path, "Chiffres clés du trimestre") == "max-width:80px"


def test_width_drag_upper_bound(width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    """E2E-004: window 2400 px wide, 900 px right gives `1280 px` and `max-width:1280px`."""
    deck = _served(tmp_path, serve_deck, deck_d1())
    width_page.set_viewport_size({"width": 2400, "height": 900})
    try:
        open_editor(width_page, deck.port)
        seen = drag_bar(width_page, PARAGRAPH["A"], 900)
    finally:
        width_page.set_viewport_size({"width": 1280, "height": 900})

    assert seen[-2] == "1280 px", f"readouts while moving: {seen}"
    wait_for_file(width_page, deck.path, "max-width:1280px")
    assert style_in_file(deck.path, "Chiffres clés du trimestre") == "max-width:1280px"


def test_width_drag_scaled_slide_pixels(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-005: on a slide shown at half size, 50 screen px right gives `max-width:700px`, not 650."""
    deck = _served(tmp_path, serve_deck, deck_d3())
    open_editor(width_page, deck.port)

    drag_bar(width_page, PARAGRAPH["A"], 50)

    wait_for_file(width_page, deck.path, "max-width:700px")
    assert style_in_file(deck.path, "Chiffres clés du trimestre") == "max-width:700px"


@pytest.mark.parametrize(
    "case",
    [
        ("B", "Note de synthèse", -153, "color:#0F62FE; font-weight:600; max-width:650px"),
        ("H", "Objectifs", 200, "color:#525252; font-size:10px; max-width:600px"),
        ("Q", "Fond", -153, "background:url(data:image/png;base64,AAA); color:#123456; max-width:650px"),
    ],
    ids=["E2E-006-colour-kept", "E2E-007-em-replaced", "E2E-042-semicolon-in-url"],
)
def test_width_drag_other_declarations_verbatim(
    width_page: Page,
    tmp_path: Path,
    serve_deck: Callable[[Path], ServedDeck],
    case: tuple[str, str, int, str],
) -> None:
    """E2E-006, E2E-007, E2E-042: the other declarations keep their exact text; the rest of the file is unchanged.

    The whole file save reformats the bootstrap (indentation, attribute order, the shown slide), so "before" is
    the file as the editor saves it right before the drag, not the fixture text.
    """
    letter, text, dx, expected = case
    deck = _served(tmp_path, serve_deck, deck_d1())
    open_editor(width_page, deck.port)
    width_page.evaluate("() => saveContent()")  # the file as the editor writes it before any width action
    wait_for_js(width_page, SAVED_COUNT, 1, what="the baseline save sent")
    wait_for_js(width_page, SAVE_DONE, True, what="the baseline save answered")
    baseline = deck.path.read_text(encoding="utf-8")
    original = style_in_file(deck.path, text)
    assert original is not None

    drag_bar(width_page, PARAGRAPH[letter], dx)

    saved = wait_for_file(width_page, deck.path, expected)
    assert style_in_file(deck.path, text) == expected
    assert "rgb(" not in saved
    assert saved == baseline.replace(f'style="{original}"', f'style="{expected}"', 1)
