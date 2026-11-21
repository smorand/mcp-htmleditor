"""SPEC-0031 (US-0169): a declarative diagram edit stays undoable after the layout run.

BT-001 to BT-005. After an edge is created (or a node added) the server rewrites the file with the recomputed
positions and the page reloads it; the undo and redo history must survive that reload, and an agent write must still
empty it. Real headless Chromium against a real editor server; the second channel is the file on disk.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

from tests.browser_wait import wait_for_file, wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.style_text_support import serve_deck_s
from tests.test_style_text_marks_e2e import SHOW_SLIDE_3, SLIDE_3_SHOWN, _open_slide_3, _start_connect
from tests.width_support import PARAGRAPH, drag_bar, open_editor, width_page

pytestmark = needs_chromium

__all__ = ["width_page"]

FRAME = "document.getElementById('content-frame').contentDocument"
EDGE_LAID_OUT = (
    f"() => {{ const d = {FRAME}; return d.querySelectorAll('[data-type=\"arch-edge\"]').length === 1"
    " && /left:/.test(d.querySelector('[data-id=\"n1\"]').getAttribute('style') || ''); }"
)
EDGES = f"() => {FRAME}.querySelectorAll('[data-type=\"arch-edge\"]').length"
UNDO_DISABLED = "() => document.getElementById('undo-btn').disabled"
REDO_DISABLED = "() => document.getElementById('redo-btn').disabled"
ADD_ENTRY = "＋ Ajouter nœud (rangée existante ou nouvelle)"


def _create_edge(page: Page, deck: ServedDeck) -> None:
    """Create the edge n1 to n2 (label accepted empty) and wait until the layout run has reloaded the page."""
    page.once("dialog", lambda dialog: dialog.accept(""))
    _start_connect(page)
    page.frame_locator("#content-frame").locator('[data-id="n2"]').dispatch_event("click")
    wait_for_file(page, deck.path, 'data-type="arch-edge"')
    wait_for_js(page, EDGE_LAID_OUT, True, what="the diagram reloaded with its recomputed positions")


def _edges_in_file(path: Path) -> int:
    return path.read_text(encoding="utf-8").count('data-type="arch-edge"')


def test_bt001_the_undo_button_stays_enabled_after_an_edge_is_created(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    _open_slide_3(width_page, deck)

    _create_edge(width_page, deck)

    assert width_page.evaluate(UNDO_DISABLED) is False


def test_bt002_undo_removes_the_edge_and_redo_brings_it_back(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    _open_slide_3(width_page, deck)
    _create_edge(width_page, deck)

    width_page.click("#undo-btn")
    wait_until(width_page, lambda: _edges_in_file(deck.path), lambda n: n == 0, what="the edge undone in the file")
    wait_for_js(width_page, EDGES, 0, what="the edge undone in the page")
    assert width_page.evaluate(REDO_DISABLED) is False

    width_page.click("#redo-btn")
    wait_until(width_page, lambda: _edges_in_file(deck.path), lambda n: n == 1, what="the edge redone in the file")
    wait_for_js(width_page, EDGES, 1, what="the edge redone in the page")


def test_bt003_undo_of_a_node_added_to_a_declarative_diagram(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    width_page.once("dialog", lambda dialog: dialog.accept("Cache"))
    _open_slide_3(width_page, deck)

    width_page.frame_locator("#content-frame").locator('[data-type="arch-diagram"]:has([data-type="arch-row"])').click(
        button="right", position={"x": 5, "y": 150}
    )
    width_page.locator(f'#_editor_ctx_host div:text-is("{ADD_ENTRY}")').click()
    wait_for_file(width_page, deck.path, 'data-label="Cache"')
    wait_for_js(
        width_page,
        f"() => /left:/.test({FRAME}.querySelector('[data-label=\"Cache\"]').getAttribute('style') || '')",
        True,
        what="the diagram reloaded with its recomputed positions",
    )

    width_page.click("#undo-btn")

    wait_until(
        width_page,
        lambda: "Cache" in deck.path.read_text(encoding="utf-8").split("</article>", 3)[2],
        lambda present: not present,
        what="the node undone in the file",
    )
    wait_for_js(
        width_page, f"() => !!{FRAME}.querySelector('[data-label=\"Cache\"]')", False, what="undone in the page"
    )


def test_bt004_an_agent_write_still_empties_the_history(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    _open_slide_3(width_page, deck)
    _create_edge(width_page, deck)
    assert width_page.evaluate(UNDO_DISABLED) is False

    deck.path.write_text(
        deck.path.read_text(encoding="utf-8").replace(">Objets<", ">ObjetsAgent<", 1), encoding="utf-8"
    )
    later = time.time() + 10
    os.utime(deck.path, (later, later))

    wait_for_js(
        width_page,
        f"() => {{ const d = {FRAME}; return !!d && !!d.body && d.body.textContent.includes('ObjetsAgent'); }}",
        True,
        what="the agent write shown",
    )
    assert width_page.evaluate(UNDO_DISABLED) is True


def test_bt005_the_earlier_history_is_kept(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    open_editor(width_page, deck.port)
    drag_bar(width_page, PARAGRAPH["A"], 47)
    wait_for_file(width_page, deck.path, "max-width:650px")
    width_page.evaluate(SHOW_SLIDE_3)
    wait_for_js(width_page, SLIDE_3_SHOWN, True, what="slide 3 shown")
    _create_edge(width_page, deck)

    width_page.click("#undo-btn")
    wait_until(width_page, lambda: _edges_in_file(deck.path), lambda n: n == 0, what="the edge undone")
    assert width_page.evaluate(UNDO_DISABLED) is False
    width_page.click("#undo-btn")

    wait_for_file(width_page, deck.path, 'style="max-width:600px">Chiffres')
