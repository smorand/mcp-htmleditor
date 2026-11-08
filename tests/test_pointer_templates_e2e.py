"""The presentation pointer in every presentation template (SPEC-0017, US-0107, US-0109).

One module page at 1600 by 900 (DEC-017). E2E-036: the layout areas of the Euro-Information starting point are not
boxes. E2E-029: the 11 templates, each served in turn by one editor server (a second ``start_http_server`` call
switches the served file), pointed at, then exported as before. E2E-032: Deck S (a copy of the stacked
``presentation-standard.html``) opened directly, and a deck made from each starting point, served.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page

from mcp_htmleditor.http_server import start_http_server
from tests.browser_wait import wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import build_deck, write_deck
from tests.pointer_support import (
    DOC,
    FRAME_DOC,
    REPO_ROOT,
    deck_p_path,
    dispatch_key,
    leave_full_screen,
    next_frames,
    open_deck_p,
    pointer_file_page,
    pointer_state,
    present_served,
    present_with,
    wait_presenting,
    wait_ringed,
    wait_slide_settled,
    wait_state,
)
from tests.test_export_golden import (
    EXAMPLE_CARBON_COMPLETE,
    EXAMPLE_CARBON_COMPLETE_FILE,
    GOLDEN_FILE,
    TEMPLATES,
    slide_hashes,
)

__all__ = ["deck_p_path", "pointer_file_page"]

EI_PARAGRAPH = "EI paragraph"
# The middle of the right half of the white inner frame, to the right of the one short paragraph.
INNER_EMPTY_SPOT = (
    f"() => {{ const r = ({FRAME_DOC}).querySelector('#slide-1 .slide-inner').getBoundingClientRect();"
    " return [r.left + r.width * 0.8, r.top + r.height * 0.6]; }"
)


STACKED_SCALE = 1.25  # a 1280 by 720 slide in a 1600 by 900 window
CONTROLS_GAP = 8  # page pixels between Pointeur and Présenter
DOT_SLIDE_PIXELS = 18
SCREEN_CENTRE = (800, 450)
# The headline of the current slide, whatever the template: the first title element in document order.
HEADLINE = "h1, h2, .slide-h1, .slide-cover-title, .med-cover-title, .slide-section-title"
CURRENT = '[data-type="slide"].active, [data-type="slide"][data-fs-current]'
HEADLINE_CENTRE = (
    "([doc, sel, cur]) => { const slide = doc.querySelector(cur); const el = slide.querySelector(sel);"
    " const r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }"
)
# The editor page, once its first /status answer named the served file and the deck's document is complete.
SERVED_READY = (
    "name => { const f = document.getElementById('content-frame'); const d = f && f.contentDocument;"
    " return document.getElementById('toolbar-filename').textContent.trim() === name"
    " && !!d && d.readyState === 'complete' && !!d.querySelector('[data-type=\"slide\"]'); }"
)
POINTER_SHOWN = "() => { const b = document.getElementById('pointer-btn'); return !!b && b.offsetWidth > 0; }"
# Both stacked controls: rect, shown or not.
STACKED_CONTROLS = """
() => [document.getElementById('btn-pointer'), document.getElementById('btn-present')].map(el => {
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return {left: r.left, right: r.right, top: r.top, bottom: r.bottom,
          shown: getComputedStyle(el).display !== 'none' && r.width > 0};
})
"""
# Starting point: (key, its headline's selector).
STARTING_POINTS = (("carbon", ".slide-h1"), ("ei", ".slide-cover-title"), ("medical", ".med-cover-title"))
ELEVEN = (*TEMPLATES, EXAMPLE_CARBON_COMPLETE)
# build_deck retitles the Carbon cover to ``<strong>Cover</strong>``; the starting point's own headline also holds
# plain text after its bold part, the shape kept here (a headline whose text is all inside inline children is not
# a text block for the pointer's rule FR-NEW-005).
CARBON_HEADLINE = ("<strong>Cover</strong>", "<strong>Cover</strong> de la présentation")


def ei_deck() -> str:
    """A deck made from the ``ei`` starting point: a cover, one content slide holding a paragraph and no tile."""
    deck = build_deck("ei", ("Cover", "Content", "Closing"))
    return deck.replace("<p>Texte de Content.</p>", f"<p>{EI_PARAGRAPH}</p>", 1)


@pytest.fixture
def served_ei(tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]) -> ServedDeck:
    return serve_deck(Path(write_deck(tmp_path / "deck-ei.html", ei_deck())))


def click_and_read(page: Page, x: float, y: float) -> int:
    """Click the screen point, let the deck's frame loop see it, return the number of rings shown."""
    page.mouse.click(x, y)
    next_frames(page, FRAME_DOC)
    return int(pointer_state(page, FRAME_DOC)["rings"])


@needs_chromium
def test_pointer_ei_layout_areas_are_not_boxes(pointer_file_page: Page, served_ei: ServedDeck) -> None:
    """E2E-036."""
    page = pointer_file_page
    present_served(page, served_ei.port)
    dispatch_key(page, "ArrowRight")
    wait_state(page, lambda s: s["current"] == 1, "the content slide shown", FRAME_DOC)
    wait_slide_settled(page, FRAME_DOC)

    x, y = page.evaluate(INNER_EMPTY_SPOT)
    assert click_and_read(page, x, y) == 0, "the white inner frame was ringed"

    page_number = page.evaluate(
        f"() => {{ const r = ({FRAME_DOC}).querySelector('#slide-1 .slide-foot-page').getBoundingClientRect();"
        " return [r.left + r.width / 2, r.top + r.height / 2]; }"
    )
    assert click_and_read(page, *page_number) == 0, "the footer's page number was ringed"

    paragraph = page.evaluate(
        f"() => {{ const r = ({FRAME_DOC}).querySelector('#slide-1 .slide-body p').getBoundingClientRect();"
        " return [r.left + r.width / 2, r.top + r.height / 2]; }"
    )
    page.mouse.click(*paragraph)
    wait_ringed(page, "#slide-1 .slide-body p", FRAME_DOC)


def baseline() -> dict[str, dict[str, str]]:
    """DEC-012: the golden slide XML hashes of the 11 templates, captured before SPEC-0017."""
    golden: dict[str, dict[str, str]] = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    golden[EXAMPLE_CARBON_COMPLETE] = json.loads(EXAMPLE_CARBON_COMPLETE_FILE.read_text(encoding="utf-8"))
    return golden


def serve_in_turn(serve_deck: Callable[[Path], ServedDeck]) -> Callable[[Path], int]:
    """Serve the first file with a new editor server, switch the same server to each later file (DEC-017)."""
    ports: list[int] = []

    def serve(path: Path) -> int:
        if not ports:
            ports.append(serve_deck(path).port)
        else:
            start_http_server(str(path))
        return ports[0]

    return serve


def open_editor(page: Page, port: int, name: str) -> None:
    """Open the editor page on the served ``name``; return once its deck is loaded and its Pointeur control shown."""
    leave_full_screen(page)
    page.goto(f"http://127.0.0.1:{port}/")
    wait_until(page, lambda: page.evaluate(SERVED_READY, name), bool, what=f"the editor serving {name}")
    wait_until(page, lambda: page.evaluate(POINTER_SHOWN), bool, what=f"{name}: the editor's Pointeur control shown")


def headline_centre(page: Page, doc: str, selector: str = HEADLINE) -> list[float]:
    centre: list[float] = page.evaluate(f"([sel, cur]) => ({HEADLINE_CENTRE})([{doc}, sel, cur])", [selector, CURRENT])
    return centre


def point_and_ring(page: Page, doc: str) -> None:
    """The mouse over the slide's centre shows the dot; a click on the headline shows one ring."""
    page.mouse.move(*SCREEN_CENTRE)
    wait_state(page, lambda s: s["dot"] is not None, "the dot shown", doc)
    page.mouse.click(*headline_centre(page, doc))
    wait_state(page, lambda s: s["rings"] == 1, "a ring shown", doc)


@needs_chromium
def test_pointer_leaves_every_template_pptx_export_unchanged(
    pointer_file_page: Page, serve_deck: Callable[[Path], ServedDeck], tmp_path: Path
) -> None:
    """E2E-029."""
    page = pointer_file_page
    page.set_viewport_size({"width": 1600, "height": 900})
    serve = serve_in_turn(serve_deck)
    golden = baseline()
    for template in ELEVEN:
        source = REPO_ROOT / template
        copy = tmp_path / source.name
        shutil.copyfile(source, copy)
        open_editor(page, serve(copy), copy.name)
        present_with(page, "#pointer-btn")
        wait_state(page, lambda s: s["on"], f"{template}: pointer on", FRAME_DOC)
        point_and_ring(page, FRAME_DOC)
        page.keyboard.press("Escape")
        wait_until(page, lambda: page.evaluate("!!document.fullscreenElement"), lambda v: not v, what="Escape left")
        next_frames(page)
        assert copy.read_bytes() == source.read_bytes(), f"{template}: the served copy changed"
        assert slide_hashes(template, tmp_path) == golden[template], f"{template}: direct export"
        assert slide_hashes(str(copy), tmp_path) == golden[template], f"{template}: export after pointing"


def present_and_step(page: Page, doc: str, headline: str, scale: float) -> None:
    """Point at the slide's centre, ring its headline, press Right: the next slide, the pointer on, no ring."""
    page.mouse.move(*SCREEN_CENTRE)
    wait_state(page, lambda s: s["dot"] is not None, "the dot shown", doc)
    page.mouse.click(*headline_centre(page, doc, headline))
    wait_ringed(page, ", ".join(f"{current} {headline}" for current in CURRENT.split(", ")), doc, scale)
    if doc == DOC:
        page.keyboard.press("ArrowRight")
    else:
        dispatch_key(page, "ArrowRight")
    wait_state(page, lambda s: s["current"] == 1, "the next slide shown", doc)
    next_frames(page, doc)
    after = pointer_state(page, doc)
    assert after["on"] and after["rings"] == 0, after


@needs_chromium
def test_pointer_stacked_deck_and_every_starting_point(
    pointer_file_page: Page, serve_deck: Callable[[Path], ServedDeck], tmp_path: Path
) -> None:
    """E2E-032."""
    page = pointer_file_page
    deck_s = tmp_path / "deck-s.html"
    shutil.copyfile(REPO_ROOT / "templates" / "reference" / "slides" / "presentation-standard.html", deck_s)
    open_deck_p(page, deck_s)
    pointer, present = page.evaluate(STACKED_CONTROLS)
    assert pointer is not None and pointer["shown"] and present["shown"], (pointer, present)
    assert abs(present["left"] - pointer["right"] - CONTROLS_GAP) <= 0.5, (pointer, present)
    assert abs(present["top"] - pointer["top"]) <= 0.5, (pointer, present)

    page.click("#btn-pointer")
    wait_presenting(page)
    wait_slide_settled(page)
    wait_state(page, lambda s: s["on"], "pointer on")
    assert not any(c["shown"] for c in page.evaluate(STACKED_CONTROLS)), "a stacked control shown while presenting"
    page.mouse.move(*SCREEN_CENTRE)
    dot = wait_state(page, lambda s: s["dot"] is not None, "the dot shown")["dot"]
    assert abs(dot["d"] - DOT_SLIDE_PIXELS * STACKED_SCALE) <= 1, dot
    present_and_step(page, DOC, "h1", STACKED_SCALE)

    serve = serve_in_turn(serve_deck)
    for key, headline in STARTING_POINTS:
        deck = build_deck(key, ("Cover", "Second")).replace(*CARBON_HEADLINE, 1)
        path = Path(write_deck(tmp_path / f"new-{key}.html", deck))
        open_editor(page, serve(path), path.name)
        present_with(page, "#pointer-btn")
        wait_state(page, lambda s: s["on"], f"{key}: pointer on", FRAME_DOC)
        present_and_step(page, FRAME_DOC, headline, 1600 / 960)
