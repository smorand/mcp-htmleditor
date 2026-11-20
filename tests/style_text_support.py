"""Fixture and helpers of the style text tests of SPEC-0020: Deck S and the live attribute text of an element.

Deck S is the D1 deck of ``tests/width_support.py`` with author styles on slide 2 that a lossy rewrite would damage
(``cursor``, ``outline``, comments holding ``;`` and ``'``), a ``<html>`` style that names ``--fs-scale`` inside a
comment, and a declarative diagram on slide 3.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from tests.conftest import ServedDeck
from tests.width_support import PARAGRAPHS, deck_d1, write_fixture

HTML_STYLE = "color:#161616 /* x;--fs-scale:9 */"
AUTHOR_STYLES = {
    "J": ("cursor:pointer;color:#0F62FE", "Hors charte"),
    "I": ("outline:1px solid #FF0000;font-weight:600", "Mini"),
    "P": ("color:red /* a;b */;font-weight:600", "Agent"),
    "K": ("color:red /* it's */;max-width:600px", "Large"),
    "H": ("/* note */ max-width:600px;color:#525252", "Objectifs"),
}
DIAGRAM = (
    '<div data-type="arch-diagram" style="position:relative; width:100%; height:200px;"><div data-type="arch-row">'
    '<div data-type="arch-node" data-id="n1" data-label="Serveur MCP" style="outline:1px dashed #8D8D8D;'
    'background:#EDF5FF">Serveur MCP</div>'
    '<div data-type="arch-node" data-id="n2" data-label="Base">Base</div></div></div>\n'
)
OLD_DIAGRAM_START = '        <div data-type="arch-diagram"'
OLD_DIAGRAM_END = "        </div>\n"


def deck_s(*, html_style: str | None = HTML_STYLE, replace: dict[str, tuple[str, str]] | None = None) -> str:
    """Deck S (spec section 4); ``replace`` overrides the style and text of paragraphs by letter."""
    html = deck_d1()
    styles = {**AUTHOR_STYLES, **(replace or {})}
    for letter, old_style, old_text in PARAGRAPHS:
        if letter in styles:
            style, text = styles[letter]
            old = f'<p data-editable="text" style="{old_style}">{old_text}</p>'
            assert old in html, letter
            html = html.replace(old, f'<p data-editable="text" style="{style}">{text}</p>', 1)
    start = html.index(OLD_DIAGRAM_START)
    end = html.index(OLD_DIAGRAM_END, start) + len(OLD_DIAGRAM_END)
    html = html[:start] + "        " + DIAGRAM + html[end:]
    if html_style is not None:
        html = html.replace(
            '<html lang="fr" data-doc-type="presentation">',
            f'<html lang="fr" data-doc-type="presentation" style="{html_style}">',
            1,
        )
    return html


def serve_deck_s(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], **kwargs: object) -> ServedDeck:
    return serve_deck(write_fixture(tmp_path, deck_s(**kwargs)))  # type: ignore[arg-type]


def live_style(page: Page, selector: str) -> str | None:
    """The ``style`` attribute text of a framed element as the document shows it now."""
    return page.evaluate(
        "(sel) => { const d = document.getElementById('content-frame').contentDocument;"
        " return d.querySelector(sel).getAttribute('style'); }",
        selector,
    )


def slide_in_file(path: Path, slide_id: str) -> str:
    """The markup of the slide ``slide_id`` as saved on disk."""
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    slide = soup.find(id=slide_id)
    assert slide is not None, slide_id
    return str(slide)


def type_in_first_paragraph(page: Page, selector: str, text: str) -> None:
    """Click at the end of a framed paragraph and type ``text`` (the autosave then writes the file)."""
    page.frame_locator("#content-frame").locator(selector).click()
    page.keyboard.press("End")
    page.keyboard.type(text)


GANTT_OLD = 'style="left:0%; width:25%; background:#0f62fe;"'
GANTT_NEW = 'style="left:0%; width:25%; background:#0F62FE"'
N2_STYLE = "position:absolute; left:10%; top:10%; width:20%; height:20%"
LEGACY_DIAGRAM = (
    '<div data-type="arch-diagram" style="width:100%; height:200px;">'
    '<div data-type="arch-node" data-label="Ancien" data-shape="box" '
    'style="position:absolute; left:10%; top:10%; width:20%;">Ancien</div></div>\n'
)


def deck_s2(*, html_style: str | None = "color:#161616") -> str:
    """Deck S2 (SPEC-0030): Deck S plus a Gantt task with an uppercase colour, a styled ``n2``, a legacy diagram."""
    html = deck_s(html_style=html_style)
    end = html.index(DIAGRAM) + len(DIAGRAM)
    html = html[:end] + "        " + LEGACY_DIAGRAM + html[end:]
    assert GANTT_OLD in html
    html = html.replace(GANTT_OLD, GANTT_NEW, 1)
    old_n2 = '<div data-type="arch-node" data-id="n2" data-label="Base">Base</div>'
    assert old_n2 in html
    styled = f'<div data-type="arch-node" data-id="n2" data-label="Base" style="{N2_STYLE}">Base</div>'
    return html.replace(old_n2, styled, 1)


def serve_deck_s2(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], **kwargs: object) -> ServedDeck:
    return serve_deck(write_fixture(tmp_path, deck_s2(**kwargs)))  # type: ignore[arg-type]
