"""SPEC-0030 (US-0167): editor actions set one style declaration as text and keep the author's others.

BT-002 to BT-008: Gantt resize, positioning context of a diagram, arch node press and move, Undo. Real headless
Chromium against a real editor server; every assertion on a saved text reads the file on disk. The arch node is
pressed and moved with pointer events dispatched on it (a mouse press at its centre lands on the row around it).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from tests.browser_wait import wait_for_file, wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.style_text_support import N2_STYLE, live_style, serve_deck_s2, type_in_first_paragraph
from tests.width_support import PARAGRAPH, open_editor, width_page

pytestmark = needs_chromium

__all__ = ["width_page"]

TASK = '[data-type="gantt-task"]'
TASK_STYLE = "left:0%; width:25%; background:#0F62FE"
N1_STYLE = "outline:1px dashed #8D8D8D;background:#EDF5FF"
LEGACY = '[data-type="arch-diagram"]:not(:has([data-type="arch-row"]))'
SHOW_SLIDE_3 = "() => document.getElementById('content-frame').contentWindow.goToSlide(2)"
SLIDE_3_SHOWN = (
    "() => document.getElementById('content-frame').contentDocument.querySelector('#slide-2')"
    ".classList.contains('active')"
)
PRESS_AND_MOVE = """([id, dx, dy]) => {
  const d = document.getElementById('content-frame').contentDocument;
  const node = d.querySelector(`[data-id="${id}"]`);
  const r = node.getBoundingClientRect();
  const at = (type, x, y) => new PointerEvent(type, {button: 0, clientX: x, clientY: y, bubbles: true, pointerId: 1});
  node.dispatchEvent(at('pointerdown', r.left + 5, r.top + 5));
  if (dx || dy) d.dispatchEvent(at('pointermove', r.left + 5 + dx, r.top + 5 + dy));
  d.dispatchEvent(at('pointerup', r.left + 5 + dx, r.top + 5 + dy));
}"""


def _open_slide_3(page: Page, deck: ServedDeck, *, edit: bool = True) -> None:
    if edit:
        open_editor(page, deck.port)
    else:
        from tests.width_support import show_slide_2

        show_slide_2(page, deck.port)
    page.evaluate(SHOW_SLIDE_3)
    wait_for_js(page, SLIDE_3_SHOWN, True, what="slide 3 shown")


def _soup(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def _style(path: Path, **attributes: str) -> str | None:
    element = _soup(path).find(attrs=attributes)
    assert element is not None, attributes
    value = element.get("style")  # type: ignore[union-attr]
    return None if value is None else str(value)


def _task_style(path: Path) -> str | None:
    task = _soup(path).find(attrs={"data-type": "gantt-task"})
    assert task is not None
    value = task.get("style")
    return None if value is None else str(value)


def _menu(page: Page, label: str) -> None:
    page.locator(f'#_editor_ctx_host div:text-is("{label}")').click()


def _resize(page: Page, label: str) -> None:
    page.frame_locator("#content-frame").locator(TASK).first.click(button="right")
    _menu(page, label)


def test_bt002_gantt_resize_keeps_the_other_declarations(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s2(tmp_path, serve_deck)
    _open_slide_3(width_page, deck)

    _resize(width_page, "Agrandir (+20%)")

    wait_for_file(width_page, deck.path, "width:30.0%")
    assert _task_style(deck.path) == "left:0%; width:30.0%; background:#0F62FE"


def test_bt003_gantt_shrink(width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    deck = serve_deck_s2(tmp_path, serve_deck)
    _open_slide_3(width_page, deck)

    _resize(width_page, "Réduire (-20%)")

    wait_for_file(width_page, deck.path, "width:20.0%")
    assert _task_style(deck.path) == "left:0%; width:20.0%; background:#0F62FE"


def test_bt004_a_press_without_moving_writes_nothing(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s2(tmp_path, serve_deck)
    _open_slide_3(width_page, deck)

    # n2 already is position:absolute (a same value write changes nothing); n1 is not, so it shows the defect
    width_page.evaluate(PRESS_AND_MOVE, ["n1", 0, 0])
    width_page.evaluate(PRESS_AND_MOVE, ["n2", 0, 0])
    width_page.frame_locator("#content-frame").locator("#slide-2 .slide-h1").click()
    width_page.keyboard.press("End")
    width_page.keyboard.type("X")

    wait_for_file(width_page, deck.path, "ObjetsX")
    assert _style(deck.path, **{"data-id": "n2"}) == N2_STYLE
    assert _style(deck.path, **{"data-id": "n1"}) == N1_STYLE
    assert live_style(width_page, '[data-id="n1"]') == N1_STYLE
    assert live_style(width_page, '[data-id="n2"]') == N2_STYLE
    assert (
        width_page.evaluate(
            "() => document.getElementById('content-frame').contentDocument.querySelector('[data-id=\"n2\"]')"
            ".hasAttribute('contenteditable')"
        )
        is False
    )


def test_bt005_a_node_move_sets_only_its_position(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s2(tmp_path, serve_deck)
    _open_slide_3(width_page, deck)

    width_page.evaluate(PRESS_AND_MOVE, ["n1", 30, 0])
    width_page.evaluate(PRESS_AND_MOVE, ["n2", 30, 0])

    wait_until(
        width_page,
        lambda: (_style(deck.path, **{"data-id": "n1"}) or "", _style(deck.path, **{"data-id": "n2"}) or ""),
        lambda styles: (
            styles[0].startswith("outline:1px dashed #8D8D8D; background:#EDF5FF; position:absolute; left:")
            and "left:10%" not in styles[1]
        ),
        what="both moves saved",
    )
    n1 = _style(deck.path, **{"data-id": "n1"}) or ""
    n2 = _style(deck.path, **{"data-id": "n2"}) or ""
    assert n1.count("left:") == 1 and n1.count("top:") == 1 and n1.endswith("%")
    assert n2.startswith("position:absolute; left:") and n2.endswith("; width:20%; height:20%")
    assert n2.count("left:") == 1 and n2.count("top:") == 1


def test_bt006_the_legacy_diagram_becomes_relative_at_edit_mode_entry(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s2(tmp_path, serve_deck)
    _open_slide_3(width_page, deck)

    type_in_first_paragraph(width_page, "#slide-2 .slide-h1", "X")

    wait_for_file(width_page, deck.path, "ObjetsX")
    diagrams = _soup(deck.path).find_all(attrs={"data-type": "arch-diagram"})
    legacy = next(d for d in diagrams if not d.find(attrs={"data-type": "arch-row"}))
    assert legacy.get("style") == "width:100%; height:200px; position:relative"
    declarative = next(d for d in diagrams if d.find(attrs={"data-type": "arch-row"}))
    assert declarative.get("style") == "position:relative; width:100%; height:200px;"


def test_bt007_adding_a_node_to_a_static_legacy_diagram(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s2(tmp_path, serve_deck)
    width_page.once("dialog", lambda dialog: dialog.accept("NoeudAjoute"))
    _open_slide_3(width_page, deck, edit=False)

    width_page.frame_locator("#content-frame").locator(LEGACY).click(button="right", position={"x": 5, "y": 150})
    _menu(width_page, "＋ Ajouter nœud")

    wait_for_file(width_page, deck.path, ">NoeudAjoute<")
    diagrams = _soup(deck.path).find_all(attrs={"data-type": "arch-diagram"})
    legacy = next(d for d in diagrams if not d.find(attrs={"data-type": "arch-row"}))
    assert legacy.get("style") == "width:100%; height:200px; position:relative"


def test_bt008_undo_restores_the_exact_text(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s2(tmp_path, serve_deck)
    _open_slide_3(width_page, deck)
    _resize(width_page, "Agrandir (+20%)")
    wait_for_file(width_page, deck.path, "width:30.0%")

    width_page.click("#undo-btn")

    wait_until(width_page, lambda: _task_style(deck.path), lambda text: text == TASK_STYLE, what="the width undone")
    assert live_style(width_page, TASK) == TASK_STYLE
    assert PARAGRAPH["A"]
