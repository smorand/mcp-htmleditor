"""SPEC-0015 E2E-021 to E2E-025, E2E-031, E2E-033 and E2E-043 (US-0091): where the width bar shows and hides.

Real headless Chromium against a real editor server. One page is shared by the module (DEC-011), one server
per test. The bar's `hidden` state and its rectangle are read right after each pointer action: show and hide are
synchronous in the event handlers (DEC-006). Saved results are read in the file.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from mcp_htmleditor.state import get_state
from tests.browser_wait import settle, wait_for_file, wait_for_js, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.width_support import (
    PARAGRAPH,
    bar_box,
    block_box,
    deck_d1,
    deck_d2,
    deck_m1,
    deck_w1,
    drag_bar,
    open_document,
    open_editor,
    point_bar,
    show_slide_2,
    style_in_file,
    width_page,
    write_fixture,
)

pytestmark = needs_chromium

__all__ = ["width_page"]

TOLERANCE = 2.0
FRAME_DOC = "document.getElementById('content-frame').contentDocument"
# Slide 2's table cells and slide 3's objects are text zones here, so only the excluded targets keep the bar away.
MAKE_ZONES = f"""() => {{
  const doc = {FRAME_DOC};
  doc.querySelectorAll('td, th, [data-type="arch-node"], [data-type="gantt-task"], [data-type="annotation"]')
    .forEach(el => el.setAttribute('data-editable', 'text'));
  const item = doc.querySelectorAll('.slide-body li')[0];
  item.insertAdjacentHTML('beforeend', '<img alt="inner" style="width:40px;height:40px"'
    + ' src="' + doc.querySelector('img[alt="logo"]').src + '">');
}}"""
GO_TO_SLIDE = "(n) => document.getElementById('content-frame').contentWindow.goToSlide(n)"
OVERLAY_SHOWN = "() => getComputedStyle(document.getElementById('update-overlay')).display"
# The shell reports the fullscreen framed document as its iframe.
FULLSCREEN = "() => document.fullscreenElement ? document.fullscreenElement.tagName : null"
SAVES = "() => window.__widthSaves"


def _served(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck], text: str) -> ServedDeck:
    return serve_deck(write_fixture(tmp_path, text))


def _point(page: Page, selector: str) -> None:
    """Move the pointer to the middle of a framed element."""
    box = block_box(page, selector)
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def _point_and_read(page: Page, selector: str) -> dict[str, float] | None:
    _point(page, selector)
    return bar_box(page)


def _assert_on_right_edge(bar: dict[str, float], block: dict[str, float]) -> None:
    assert abs(bar["x"] - (block["x"] + block["width"])) <= TOLERANCE, f"bar {bar} not on the edge of {block}"
    assert abs(bar["y"] - block["y"]) <= TOLERANCE, f"bar {bar} not at the top of {block}"
    assert abs(bar["height"] - block["height"]) <= TOLERANCE, f"bar {bar} not as tall as {block}"


def test_width_visibility_excluded_things(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-021: no bar on a cell, a header, an image, a diagram node, a Gantt task or an annotation."""
    deck = _served(tmp_path, serve_deck, deck_d1())
    open_editor(width_page, deck.port)
    width_page.evaluate(MAKE_ZONES)
    frame_slide = ".slide-body"

    for selector in (f"{frame_slide} td", f"{frame_slide} th", f"{frame_slide} li img[alt='inner']"):
        assert _point_and_read(width_page, selector) is None, f"a width bar shows on {selector}"
    width_page.evaluate(GO_TO_SLIDE, 2)
    for selector in ('[data-type="arch-node"]', '[data-type="gantt-task"]', '[data-type="annotation"]'):
        assert _point_and_read(width_page, f"#slide-2 {selector}") is None, f"a width bar shows on {selector}"
    width_page.evaluate(GO_TO_SLIDE, 1)

    bar = _point_and_read(width_page, f"{PARAGRAPH['B']} .tag-blue")
    assert bar is not None, "no bar on the word Nouveau"
    _assert_on_right_edge(bar, block_box(width_page, PARAGRAPH["B"]))


def test_width_visibility_not_outside_editing(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-022: no bar with edit mode off, in the fullscreen presentation, or while the update overlay shows."""
    deck = _served(tmp_path, serve_deck, deck_d1())
    show_slide_2(width_page, deck.port)
    assert _point_and_read(width_page, PARAGRAPH["A"]) is None, "a bar shows outside edit mode"

    wait_for_js(
        width_page, "() => document.getElementById('toolbar-filename').textContent !== '\u2014'", True, what="ready"
    )
    width_page.click("#edit-mode-btn")
    assert _point_and_read(width_page, PARAGRAPH["A"]) is not None, "edit mode on shows no bar"

    width_page.click("#present-btn")
    wait_for_js(width_page, FULLSCREEN, "IFRAME", what="the presentation in fullscreen")
    assert _point_and_read(width_page, PARAGRAPH["A"]) is None, "a bar shows in the fullscreen presentation"
    width_page.keyboard.press("Escape")
    wait_for_js(width_page, FULLSCREEN, None, what="fullscreen left")

    assert _point_and_read(width_page, PARAGRAPH["A"]) is not None, "the bar is back after fullscreen"
    get_state().set_update_flag(True)
    try:
        wait_for_js(width_page, OVERLAY_SHOWN, "flex", what="the update overlay shown")
        assert bar_box(width_page) is None, "the bar stays while the agent updates"
        assert _point_and_read(width_page, PARAGRAPH["A"]) is None, "a bar shows during an agent update"
    finally:
        get_state().set_update_flag(False)


def test_width_visibility_nested_list_item(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-023: the bar is on the list item only; dragging it to 300 writes the item's style alone."""
    deck = _served(tmp_path, serve_deck, deck_d1())
    open_editor(width_page, deck.port)
    item = ".slide-body li:nth-of-type(2)"
    box = block_box(width_page, item)

    bar = point_bar(width_page, item)
    _assert_on_right_edge(bar, box)
    seen = drag_bar(width_page, item, 300 - box["width"])

    assert seen[-2] == "300 px", f"readouts while moving: {seen}"
    wait_for_file(width_page, deck.path, "max-width:300px")
    assert style_in_file(deck.path, "Second point") == "max-width:300px"
    assert style_in_file(deck.path, "Premier point") is None
    assert BeautifulSoup(deck.path.read_text(encoding="utf-8"), "html.parser").select_one("ul").get("style") is None


def test_width_visibility_document_scrolled(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-024: the bar follows its paragraph on scroll; the reorder handle still moves it with its width."""
    deck = _served(tmp_path, serve_deck, deck_d2())
    open_document(width_page, deck.port)
    target = "article > p:nth-child(31)"  # title is child 1, so Paragraphe 30 is child 31
    width_page.evaluate(f"() => {FRAME_DOC}.querySelector('{target}').scrollIntoView({{block: 'center'}})")
    box = block_box(width_page, target)
    _assert_on_right_edge(point_bar(width_page, target), box)

    width_page.evaluate("() => document.getElementById('content-frame').contentWindow.scrollBy(0, -200)")
    moved = wait_until(
        width_page,
        lambda: block_box(width_page, target)["y"],
        lambda y: abs(y - box["y"]) > 100,
        what="the paragraph scrolled",
    )
    after = wait_until(
        width_page,
        lambda: bar_box(width_page),
        lambda b: b is not None and abs(b["y"] - moved) <= TOLERANCE,
        what="the bar following its paragraph",
    )
    assert after is not None
    _assert_on_right_edge(after, block_box(width_page, target))

    seen = drag_bar(width_page, target, 500 - box["width"])
    assert seen[-2] == "500 px", f"readouts while moving: {seen}"
    wait_until(
        width_page,
        lambda: style_in_file(deck.path, "Paragraphe 30"),
        lambda style: style == "max-width:500px",
        what="Paragraphe 30 saved at 500",
    )

    handle = width_page.evaluate(
        f"""() => {{ const d = {FRAME_DOC}; const f = document.getElementById('content-frame').getBoundingClientRect();
          const h = d.querySelectorAll('._mcp_drag_handle')[30].getBoundingClientRect();
          const above = d.querySelector('article > p:nth-child(30)').getBoundingClientRect();
          return {{ x: f.left + h.left + h.width / 2, y: f.top + h.top + h.height / 2,
                    toX: f.left + above.left + 10, toY: f.top + above.top + 2 }}; }}"""
    )
    width_page.mouse.move(handle["x"], handle["y"])
    width_page.mouse.down()
    width_page.mouse.move(handle["toX"], handle["toY"], steps=5)
    width_page.mouse.up()

    def order() -> list[str]:
        soup = BeautifulSoup(deck.path.read_text(encoding="utf-8"), "html.parser")
        return [p.get_text() for p in soup.select("article > p")][27:30]

    assert wait_until(
        width_page, order, lambda texts: texts == ["Paragraphe 28", "Paragraphe 30", "Paragraphe 29"], what="reorder"
    )
    assert style_in_file(deck.path, "Paragraphe 30") == "max-width:500px"


def test_width_visibility_bar_hides(width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> None:
    """E2E-025: the bar hides on an empty area, when the pointer leaves the frame and on a slide change."""
    deck = _served(tmp_path, serve_deck, deck_d1())
    open_editor(width_page, deck.port)

    assert _point_and_read(width_page, PARAGRAPH["A"]) is not None
    frame = width_page.evaluate(
        "() => { const r = document.getElementById('content-frame').getBoundingClientRect();"
        " return { x: r.left, y: r.top, width: r.width, height: r.height }; }"
    )
    width_page.mouse.move(frame["x"] + 4, frame["y"] + frame["height"] - 4)
    assert bar_box(width_page) is None, "the bar stays on an empty area"

    assert _point_and_read(width_page, PARAGRAPH["A"]) is not None
    width_page.mouse.move(frame["x"] + frame["width"] / 2, frame["y"] - 20)
    assert bar_box(width_page) is None, "the bar stays after the pointer left the frame"

    assert _point_and_read(width_page, PARAGRAPH["A"]) is not None
    width_page.evaluate("() => document.getElementById('content-frame').focus()")
    width_page.keyboard.press("ArrowRight")
    wait_for_js(
        width_page,
        f"() => {FRAME_DOC}.querySelector('#slide-2').classList.contains('active')",
        True,
        what="slide 3 shown",
    )
    assert bar_box(width_page) is None, "the bar stays after a slide change"


def test_width_visibility_mail_paragraph(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-031: the mail intro keeps every declaration in order, then `; max-width:400px`."""
    deck = _served(tmp_path, serve_deck, deck_m1())
    open_document(width_page, deck.port)
    intro = 'p[style*="text-align:justify"]'
    box = block_box(width_page, intro)

    seen = drag_bar(width_page, intro, 400 - box["width"])

    assert seen[-2] == "400 px", f"readouts while moving: {seen}"
    wait_for_file(width_page, deck.path, "max-width:400px")
    assert style_in_file(deck.path, "Redigez votre introduction") == (
        "margin:0; font-family:Helvetica,Arial,sans-serif; font-size:15px; line-height:1.6; color:#1a1a1a;"
        " text-align:justify; max-width:400px"
    )


def test_width_visibility_inline_label_in_control(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-033: the tab label is inline and its control is no text block, so no bar."""
    deck = _served(tmp_path, serve_deck, deck_w1())
    open_document(width_page, deck.port)

    assert _point_and_read(width_page, ".site-tab.active span") is None


def test_width_visibility_agent_write(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-043: an agent write reloads the document, the bar hides, and the editor saves nothing."""
    deck = _served(tmp_path, serve_deck, deck_d1())
    open_editor(width_page, deck.port)
    assert _point_and_read(width_page, PARAGRAPH["A"]) is not None
    saves = width_page.evaluate(SAVES)
    width_page.evaluate(f"() => {{ window.__oldDoc = {FRAME_DOC}; }}")

    deck.path.write_text(
        deck.path.read_text(encoding="utf-8").replace('max-width:600px">Chiffres', 'max-width:500px">Chiffres', 1)
    )
    wait_for_js(
        width_page,
        f"() => {{ const d = {FRAME_DOC}; const p = d && d.querySelector('{PARAGRAPH['A']}');"
        " return d !== window.__oldDoc && !!p && p.isContentEditable && p.style.maxWidth === '500px'; }",
        True,
        what="the document reloaded with the agent's width",
    )
    assert bar_box(width_page) is None, "the bar stays after the reload"
    width_page.evaluate(GO_TO_SLIDE, 1)

    bar = _point_and_read(width_page, PARAGRAPH["A"])
    assert bar is not None
    box = block_box(width_page, PARAGRAPH["A"])
    assert abs(box["width"] - 500) <= TOLERANCE
    _assert_on_right_edge(bar, box)
    settle(width_page)
    assert width_page.evaluate(SAVES) == saves, "the editor saved after the agent's write"
    assert style_in_file(deck.path, "Chiffres clés du trimestre") == "max-width:500px"
