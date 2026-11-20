"""SPEC-0020 (US-0164): width actions and the presenting strip read CSS comments as comments.

BT-012 to BT-016 and BT-023. Real headless Chromium against a real editor server; one page per module, one server
per test; every assertion on a saved style reads the file on disk.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from tests.browser_wait import wait_for_file
from tests.conftest import ServedDeck, needs_chromium
from tests.style_text_support import HTML_STYLE, serve_deck_s, type_in_first_paragraph
from tests.width_support import PARAGRAPH, drag_bar, open_editor, point_bar, style_in_file, width_page

pytestmark = needs_chromium

__all__ = ["width_page"]


def _html_style(path: Path) -> str | None:
    html = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser").find("html")
    assert html is not None
    style = html.get("style")
    return None if style is None else str(style)


def test_bt012_a_width_action_on_a_comment_holding_a_semicolon(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    open_editor(width_page, deck.port)

    drag_bar(width_page, PARAGRAPH["P"], -153)

    wait_for_file(width_page, deck.path, "max-width:650px")
    assert style_in_file(deck.path, "Agent") == "color:red /* a;b */; font-weight:600; max-width:650px"


def test_bt013_a_quote_in_a_comment_does_not_hide_the_width(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    open_editor(width_page, deck.port)

    drag_bar(width_page, PARAGRAPH["K"], 47)

    wait_for_file(width_page, deck.path, "max-width:650px")
    assert style_in_file(deck.path, "Large") == "color:red /* it's */; max-width:650px"


def test_bt014_a_width_named_after_a_comment_is_replaced(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    open_editor(width_page, deck.port)

    drag_bar(width_page, PARAGRAPH["H"], 47)

    wait_for_file(width_page, deck.path, "max-width:650px")
    assert style_in_file(deck.path, "Objectifs") == "color:#525252; max-width:650px"


def test_bt023_a_comment_opener_inside_parentheses_is_not_a_comment(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck, replace={"Q": ("background:url(a/*b);max-width:600px", "Fond")})
    open_editor(width_page, deck.port)

    drag_bar(width_page, PARAGRAPH["Q"], 47)

    wait_for_file(width_page, deck.path, "max-width:650px")
    assert style_in_file(deck.path, "Fond") == "background:url(a/*b); max-width:650px"


def test_bt015_reset_keeps_a_comment(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    open_editor(width_page, deck.port)
    bar = point_bar(width_page, PARAGRAPH["K"])

    width_page.mouse.dblclick(bar["x"] + bar["width"] / 2, bar["y"] + bar["height"] / 2)

    wait_for_file(width_page, deck.path, "/* it's */\">Large")
    assert style_in_file(deck.path, "Large") == "color:red /* it's */"


def test_bt016_the_presenting_strip_keeps_a_comment_that_names_the_scale(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    open_editor(width_page, deck.port)

    type_in_first_paragraph(width_page, PARAGRAPH["A"], "X")

    wait_for_file(width_page, deck.path, "Chiffres clés du trimestreX")
    assert _html_style(deck.path) == HTML_STYLE


def test_bt016_the_scale_name_is_case_sensitive(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck, html_style="color:#161616;--FS-SCALE:2")
    open_editor(width_page, deck.port)

    type_in_first_paragraph(width_page, PARAGRAPH["A"], "X")

    wait_for_file(width_page, deck.path, "Chiffres clés du trimestreX")
    assert _html_style(deck.path) == "color:#161616;--FS-SCALE:2"
