"""SPEC-0020 (US-0163): a save and an undo snapshot keep every author style text as written.

BT-001, BT-010, BT-011, BT-020. Real headless Chromium against a real editor server; one page per module, one
server per test; every assertion on a saved style reads the file on disk.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

from tests.browser_wait import wait_for_file, wait_for_js
from tests.conftest import ServedDeck, needs_chromium
from tests.style_text_support import live_style, serve_deck_s, slide_in_file, type_in_first_paragraph
from tests.width_support import PARAGRAPH, drag_bar, markers_in, open_editor, style_in_file, width_page

pytestmark = needs_chromium

__all__ = ["width_page"]

J_STYLE = "cursor:pointer;color:#0F62FE"
I_STYLE = "outline:1px solid #FF0000;font-weight:600"


def test_bt001_a_typing_save_keeps_an_authors_cursor_and_outline(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    open_editor(width_page, deck.port)

    type_in_first_paragraph(width_page, PARAGRAPH["A"], "X")

    wait_for_file(width_page, deck.path, "Chiffres clés du trimestreX")
    saved = slide_in_file(deck.path, "slide-1")
    assert f'<p data-editable="text" style="{J_STYLE}">Hors charte</p>' in saved
    assert f'<p data-editable="text" style="{I_STYLE}">Mini</p>' in saved
    assert "rgb(" not in saved


def test_bt010_a_width_action_changes_only_its_texts_style(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    open_editor(width_page, deck.port)

    drag_bar(width_page, PARAGRAPH["A"], 47)

    wait_for_file(width_page, deck.path, "max-width:650px")
    assert style_in_file(deck.path, "Chiffres clés du trimestre") == "max-width:650px"
    assert style_in_file(deck.path, "Hors charte") == J_STYLE
    assert style_in_file(deck.path, "Mini") == I_STYLE


def test_bt011_undo_after_a_structural_action_restores_the_exact_texts(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    open_editor(width_page, deck.port)

    drag_bar(width_page, PARAGRAPH["A"], 47)
    wait_for_file(width_page, deck.path, "max-width:650px")
    assert live_style(width_page, PARAGRAPH["J"]) == J_STYLE
    width_page.click("#undo-btn")

    wait_for_js(
        width_page,
        "() => document.getElementById('content-frame').contentDocument.querySelector("
        f"{PARAGRAPH['A']!r}).getAttribute('style')",
        "max-width:600px",
        what="the width undone",
    )
    wait_for_file(width_page, deck.path, 'style="max-width:600px">Chiffres')
    assert style_in_file(deck.path, "Chiffres clés du trimestre") == "max-width:600px"
    assert style_in_file(deck.path, "Hors charte") == J_STYLE
    assert live_style(width_page, PARAGRAPH["J"]) == J_STYLE


def test_bt020_the_editors_own_look_is_still_not_saved(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    open_editor(width_page, deck.port)

    type_in_first_paragraph(width_page, PARAGRAPH["A"], "X")

    text = wait_for_file(width_page, deck.path, "Chiffres clés du trimestreX")
    assert markers_in(deck.path) == []
    assert "outline: 2px dashed" not in text
