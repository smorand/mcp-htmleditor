"""SPEC-0020 (US-0165, US-0166): the editor's transient marks leave no trace in the author's style text.

Connect mode of a declarative diagram (BT-017, BT-018) and the image drop indicator (BT-019). Real headless Chromium
against a real editor server; every assertion on a saved text reads the file on disk.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from tests.browser_wait import wait_for_file, wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.style_text_support import live_style, serve_deck_s, type_in_first_paragraph
from tests.width_support import PARAGRAPH, open_editor, style_in_file, width_page

pytestmark = needs_chromium

__all__ = ["width_page"]

N1 = '[data-id="n1"]'
N1_STYLE = "outline:1px dashed #8D8D8D;background:#EDF5FF"
CONNECT_ENTRY = "➜ Créer une arête depuis ce nœud"
SHOW_SLIDE_3 = "() => document.getElementById('content-frame').contentWindow.goToSlide(2)"
SLIDE_3_SHOWN = (
    "() => document.getElementById('content-frame').contentDocument.querySelector('#slide-2')"
    ".classList.contains('active')"
)


def _open_slide_3(page: Page, deck: ServedDeck) -> None:
    open_editor(page, deck.port)
    page.evaluate(SHOW_SLIDE_3)
    wait_for_js(page, SLIDE_3_SHOWN, True, what="slide 3 shown")


def _start_connect(page: Page) -> None:
    page.frame_locator("#content-frame").locator(N1).click(button="right")
    page.locator(f'#_editor_ctx_host div:text-is("{CONNECT_ENTRY}")').click()


def _soup(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def _node_style(path: Path, node_id: str) -> str | None:
    node = _soup(path).find(attrs={"data-id": node_id})
    assert node is not None
    style = node.get("style")  # type: ignore[union-attr]
    return None if style is None else str(style)


def _body_style(path: Path) -> str | None:
    body = _soup(path).find("body")
    assert body is not None
    style = body.get("style")
    return None if style is None else str(style)


def test_bt017_connect_mode_a_save_during_the_mode_then_escape(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    _open_slide_3(width_page, deck)

    _start_connect(width_page)
    outline = wait_for_js(
        width_page,
        "() => getComputedStyle(document.getElementById('content-frame').contentDocument.querySelector("
        f"{N1!r})).outline",
        "rgb(15, 98, 254) solid 3px",
        what="the source node outlined",
    )
    width_page.frame_locator("#content-frame").locator("#slide-2 .slide-h1").click()
    width_page.keyboard.press("End")
    width_page.keyboard.type("X")
    text = wait_for_file(width_page, deck.path, "ObjetsX")

    assert outline == "rgb(15, 98, 254) solid 3px"
    assert _node_style(deck.path, "n1") == N1_STYLE
    assert _body_style(deck.path) is None
    assert "data-mcp-mark" not in text
    width_page.keyboard.press("Escape")
    wait_for_js(width_page, f"() => {live_style_expression(N1)} === {N1_STYLE!r}", True, what="n1 text back")
    assert live_style(width_page, N1) == N1_STYLE
    assert live_style(width_page, "body") is None


def live_style_expression(selector: str) -> str:
    return f"document.getElementById('content-frame').contentDocument.querySelector({selector!r}).getAttribute('style')"


def test_bt018_connect_mode_the_undo_snapshot_holds_no_mark(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """BT-018: the snapshot taken while the mode is active holds no mark; after the edge and the layout reload (the
    undo history survives it, SPEC-0031) Undo removes the edge and leaves the author's text and no mark. The target
    node receives a click event (a real mouse press lands on the row around the node here)."""
    deck = serve_deck_s(tmp_path, serve_deck)
    width_page.once("dialog", lambda dialog: dialog.accept(""))
    _open_slide_3(width_page, deck)

    _start_connect(width_page)
    wait_for_js(width_page, "() => !!archConnectSource", True, what="connect mode active")
    snapshot = str(
        width_page.evaluate("() => captureDomSnapshot(document.getElementById('content-frame').contentDocument)")
    )
    soup = BeautifulSoup(snapshot, "html.parser")
    assert soup.find(attrs={"data-mcp-mark": True}) is None  # the injected sheet's own rules name the attribute
    assert soup.find(attrs={"data-id": "n1"}).get("style") == N1_STYLE  # type: ignore[union-attr]
    assert "crosshair" not in " ".join(str(el.get("style")) for el in soup.find_all(style=True))
    assert soup.find(attrs={"data-id": "n1"}).get("style") == N1_STYLE  # type: ignore[union-attr]
    assert soup.find("body").get("style") is None  # type: ignore[union-attr]

    width_page.frame_locator("#content-frame").locator('[data-id="n2"]').dispatch_event("click")
    wait_for_file(width_page, deck.path, 'data-type="arch-edge"')
    wait_for_js(
        width_page,
        "() => /left:/.test(document.getElementById('content-frame').contentDocument"
        ".querySelector('[data-id=\"n1\"]').getAttribute('style') || '')",
        True,
        what="the diagram reloaded with its recomputed positions",
    )
    width_page.click("#undo-btn")
    wait_until(
        width_page,
        lambda: 'data-type="arch-edge"' in deck.path.read_text(encoding="utf-8"),
        lambda has_edge: not has_edge,
        what="the edge undone in the file",
    )

    text = deck.path.read_text(encoding="utf-8")
    style = _node_style(deck.path, "n1") or ""
    assert style.count("outline") == 1
    assert "outline:1px dashed #8D8D8D" in style
    assert "crosshair" not in text
    assert "data-mcp-mark" not in text
    assert _body_style(deck.path) is None


DRAG_OVER = """(el) => {
  const data = new DataTransfer();
  data.items.add(new File(['x'], 'a.png', {type: 'image/png'}));
  el.dispatchEvent(new DragEvent('dragover', {dataTransfer: data, bubbles: true, cancelable: true}));
}"""
DRAG_LEAVE = "(el) => el.dispatchEvent(new DragEvent('dragleave', {bubbles: true}))"
DROP_SHADOW = "rgb(15, 98, 254) 0px 0px 0px 3px inset"


def _shadow(page: Page, selector: str) -> str:
    return str(
        page.evaluate(
            "(sel) => getComputedStyle(document.getElementById('content-frame').contentDocument"
            ".querySelector(sel)).boxShadow",
            selector,
        )
    )


def test_bt019_the_drop_indicator_during_a_save_then_leave(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    deck = serve_deck_s(tmp_path, serve_deck)
    open_editor(width_page, deck.port)
    zone = width_page.frame_locator("#content-frame").locator(PARAGRAPH["J"])

    type_in_first_paragraph(width_page, PARAGRAPH["A"], "X")
    zone.evaluate(DRAG_OVER)
    over = _shadow(width_page, PARAGRAPH["J"])
    text = wait_for_file(width_page, deck.path, "Chiffres clés du trimestreX")  # the autosave, no dragleave yet
    zone.evaluate(DRAG_LEAVE)

    assert over == DROP_SHADOW
    assert style_in_file(deck.path, "Hors charte") == "cursor:pointer;color:#0F62FE"
    assert "data-mcp-mark" not in text
    wait_until(
        width_page, lambda: _shadow(width_page, PARAGRAPH["J"]), lambda shadow: shadow == "none", what="indicator gone"
    )
    assert live_style(width_page, PARAGRAPH["J"]) == "cursor:pointer;color:#0F62FE"


def test_bt019_the_authors_own_box_shadow_is_back_after_the_drag(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    own = "box-shadow:0 0 4px #FF0000"
    deck = serve_deck_s(tmp_path, serve_deck, replace={"J": (own, "Hors charte")})
    open_editor(width_page, deck.port)
    zone = width_page.frame_locator("#content-frame").locator(PARAGRAPH["J"])
    before = _shadow(width_page, PARAGRAPH["J"])

    zone.evaluate(DRAG_OVER)
    over = _shadow(width_page, PARAGRAPH["J"])
    zone.evaluate(DRAG_LEAVE)

    assert over == DROP_SHADOW
    assert before.startswith("rgb(255, 0, 0)")
    assert _shadow(width_page, PARAGRAPH["J"]) == before
    assert live_style(width_page, PARAGRAPH["J"]) == own
