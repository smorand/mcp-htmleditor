"""Shared fixtures and helpers of the presentation pointer browser tests (SPEC-0017, DEC-017).

Deck P (spec 9.0) is generated from the IBM Carbon starting point, so it carries whatever pointer block,
Pointeur control and L line the bootstrap carries. One Chromium page at 1600 by 900 is shared by every test
of a module (``pointer_file_page``); each test reopens Deck P as a ``file://`` URL with ``open_deck_p``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, Page

from tests.browser_wait import wait_until

REPO_ROOT = Path(__file__).resolve().parents[1]
CARBON_BOOTSTRAP = REPO_ROOT / "templates" / "bootstrap" / "slides-empty.html"
WIDTH, HEIGHT = 1600, 900
VIEWPORT = {"width": WIDTH, "height": HEIGHT}
PDF_DATES = re.compile(rb"/(?:CreationDate|ModDate) \([^)]*\)")
# The slides' `fadein` restarts on each print and is rasterized at whatever opacity it reached, so two prints of
# the same page differ; the print helper stills every animation first, the same way for every print compared.
STILL_ANIMATIONS = """
() => {
  if (document.getElementById('pointer-test-still')) return;
  const style = document.createElement('style');
  style.id = 'pointer-test-still';
  style.textContent = '*, *::before, *::after { animation: none !important; }';
  document.head.appendChild(style);
}
"""

# Slide 1 keeps its centre (slide pixel 480, 270, screen point 800, 450 at 1600 by 900) empty: its body is
# two 380 px columns, 200 px apart.
SLIDE_1_BODY = """
        <div style="display:flex; justify-content:space-between; height:100%">
          <div style="width:380px; display:flex; flex-direction:column; gap:12px">
            <p data-editable="text">Plain <strong>paragraph</strong></p>
            <div class="cds-tile" id="tile-a"><div class="tile-title">Tile A</div></div>
            <div class="cds-tile" id="tile-b"><div class="tile-title">Tile B</div></div>
            <table id="table-p" style="border-collapse:collapse">
              <tr><td style="border-bottom:1px solid #8d8d8d; padding:4px">Row 1</td>
                  <td style="border-bottom:1px solid #8d8d8d; padding:4px">One</td></tr>
              <tr><td style="border-bottom:1px solid #8d8d8d; padding:4px">Row 2</td>
                  <td style="border-bottom:1px solid #8d8d8d; padding:4px">Two</td></tr>
            </table>
          </div>
          <div style="width:380px; display:flex; flex-direction:column; gap:12px">
            <a id="link-docs" href="#docs">Docs</a>
            <button id="btn-count" type="button" onclick="this.textContent = 'Count 1'">Count</button>
            <label>Note <input id="note" type="text"></label>
            <svg id="drawing" width="200" height="80" viewBox="0 0 200 80">
              <rect x="4" y="4" width="80" height="60" fill="#0f62fe"></rect>
              <circle cx="150" cy="40" r="30" fill="#198038"></circle>
            </svg>
          </div>
        </div>
"""
SLIDE_2_BODY = """
        <p data-editable="text" style="color:#f4f4f4">Dark paragraph</p>
        <div class="cds-tile" id="edge-tile" style="position:absolute; left:0; top:300px; width:200px">Edge tile</div>
"""
SLIDE_3_BODY = """
        <div id="panel" style="position:absolute; left:5%; top:5%; width:90%; height:90%; background:#e0e0e0">
          <p data-editable="text">Last</p>
        </div>
"""

# One snapshot of the pointer state of a document (DEC-017): pointer on, dot centre and diameter or null,
# ring rect or null, current slide index, full screen element tag, the current slide's computed cursor.
POINTER_STATE = """
doc => {
  const win = doc.defaultView;
  const slides = [...doc.querySelectorAll('[data-type="slide"]')];
  const slide = doc.querySelector('[data-type="slide"].active, [data-type="slide"][data-fs-current]') || slides[0];
  const shown = el => !!el && win.getComputedStyle(el).display !== 'none'
    && el.getBoundingClientRect().width > 0;
  const dotEl = doc.getElementById('deck-pointer-dot');
  const ringEl = doc.getElementById('deck-pointer-ring');
  let dot = null;
  if (shown(dotEl)) {
    const r = dotEl.getBoundingClientRect();
    dot = {x: r.left + r.width / 2, y: r.top + r.height / 2, d: r.width};
  }
  let ring = null;
  if (shown(ringEl)) {
    const r = ringEl.getBoundingClientRect();
    ring = {left: r.left, top: r.top, width: r.width, height: r.height};
  }
  return {
    on: doc.documentElement.hasAttribute('data-deck-pointer'),
    layer: !!doc.getElementById('deck-pointer-layer'),
    dot, ring,
    rings: doc.querySelectorAll('#deck-pointer-ring').length,
    current: slides.indexOf(slide),
    fullscreen: doc.fullscreenElement ? doc.fullscreenElement.tagName : null,
    cursor: win.getComputedStyle(slide).cursor,
  };
}
"""

PointerState = dict[str, Any]


def _slide(index: int, title: str, body: str, style: str = "") -> str:
    return (
        f'    <article class="slide" id="slide-{index}" data-type="slide" data-id="slide-{index}"'
        f' data-title="{title}"{style}>\n'
        f'      <div class="slide-body" style="position:relative">{body}      </div>\n'
        "    </article>\n"
    )


def deck_p() -> str:
    """Deck P (spec 9.0): the Carbon starting point grown to three slides."""
    html = CARBON_BOOTSTRAP.read_text(encoding="utf-8")
    start = html.index('<article class="slide active"')
    end = html.index("</article>") + len("</article>")
    first = (
        '<article class="slide active" id="slide-0" data-type="slide" data-id="slide-0" data-title="Pointer test">\n'
        '      <div class="slide-header" style="border-bottom:4px solid #0f62fe">\n'
        '        <h1 class="slide-h1" data-editable="text">Pointer test</h1>\n'
        "      </div>\n"
        f'      <div class="slide-body">{SLIDE_1_BODY}      </div>\n'
        "    </article>\n"
    )
    others = _slide(1, "Dark", SLIDE_2_BODY, ' style="background:#161616"') + _slide(2, "Last", SLIDE_3_BODY)
    html = html[:start] + first + others + html[end:]
    html = html.replace("const TOTAL = 1;", "const TOTAL = 3;", 1)
    return html.replace('"Titre de la présentation",\n', '"Pointer test",\n    "Dark",\n    "Last",\n', 1)


@pytest.fixture(scope="module")
def deck_p_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("deck-p") / "deck-p.html"
    path.write_text(deck_p(), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def pointer_file_page(browser: Browser) -> Iterator[Page]:
    """One Chromium page shared by the tests of a module, window 1600 by 900."""
    context = browser.new_context(viewport=VIEWPORT)  # type: ignore[arg-type]  # ViewportSize is a TypedDict
    page = context.new_page()
    yield page
    context.close()


def pointer_state(page: Page) -> PointerState:
    state: PointerState = page.evaluate(f"({POINTER_STATE})(document)")
    return state


def open_deck_p(page: Page, path: Path, width: int = WIDTH, height: int = HEIGHT) -> None:
    """Leave a full screen left by the previous test, size the window, load Deck P afresh."""
    if page.evaluate("!!document.fullscreenElement"):
        page.evaluate("document.exitFullscreen()")
        wait_until(
            page, lambda: page.evaluate("!!document.fullscreenElement"), lambda v: not v, what="full screen left"
        )
    page.set_viewport_size({"width": width, "height": height})
    page.goto(path.as_uri())


def wait_state(page: Page, holds: Any, what: str) -> PointerState:
    return wait_until(page, lambda: pointer_state(page), holds, what=what)


def wait_presenting(page: Page) -> PointerState:
    return wait_state(page, lambda s: s["fullscreen"] == "HTML", "the deck presented full screen")


def print_pdf_normalized(page: Page) -> bytes:
    """The page printed to PDF, animations stilled, its creation and modification dates removed (DEC-017)."""
    page.evaluate(STILL_ANIMATIONS)
    return PDF_DATES.sub(b"", page.pdf())
