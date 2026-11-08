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
from playwright.sync_api import Browser, CDPSession, Page

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
            <div class="cds-tile" id="tile-a"><div class="tile-title" data-editable="text">Tile A</div></div>
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
# The panel covers 90 % of the slide's area (the body's padding box is the slide's, 958 by 538 inside its border),
# so FR-NEW-005 rule 6 skips it.
SLIDE_3_BODY = """
        <div id="panel" style="position:absolute; left:0; top:5%; width:100%; height:90%; background:#e0e0e0">
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
    const cs = win.getComputedStyle(ringEl);
    ring = {left: r.left, top: r.top, width: r.width, height: r.height,
            border: parseFloat(cs.borderTopWidth), opacity: cs.opacity};
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
RingCheck = dict[str, Any]

DOC = "document"
FRAME_DOC = "document.getElementById('content-frame').contentDocument"
SCALE = WIDTH / 960
RING_GAP = 6  # slide pixels between the box and the ring's outer edge
RING_LINE = 3  # slide pixels of the ring's line

# The ring and the rect of one element of the deck, read together ("X ringed" compares the two).
RING_AROUND = """
(doc, sel) => {
  const rect = el => { if (!el) return null; const r = el.getBoundingClientRect();
    return {left: r.left, top: r.top, width: r.width, height: r.height}; };
  const ring = doc.getElementById('deck-pointer-ring');
  return {box: rect(doc.querySelector(sel)), ring: rect(ring),
          rings: doc.querySelectorAll('#deck-pointer-ring').length,
          still: !ring || ring.getAnimations().every(a => a.playState !== 'running')};
}
"""


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


POINTER_BLOCK = re.compile(r"<!-- deck-pointer:begin -->.*?<!-- deck-pointer:end -->\n?", re.DOTALL)
POINTER_CONTROL_LINE = re.compile(r'^[ \t]*<button[^\n]*id="btn-pointer"[^\n]*\n', re.MULTILINE)
POINTER_KEY_LINE = re.compile(r"^[ \t]*if \(\(e\.key === 'l'[^\n]*\n", re.MULTILINE)


def deck_o() -> str:
    """Deck O (spec 9.0, DEC-017): Deck P without the deck-pointer block, the Pointeur control and the L line."""
    html = deck_p()
    for pattern in (POINTER_BLOCK, POINTER_CONTROL_LINE, POINTER_KEY_LINE):
        html, count = pattern.subn("", html)
        if count != 1:
            raise AssertionError(f"Deck P changed shape: {pattern.pattern!r} matched {count} times")
    return html


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


@pytest.fixture(scope="module")
def pointer_touch_page(browser: Browser) -> Iterator[Page]:
    """A page on a screen taking touch and a mouse (E2E-026), window 1600 by 900."""
    context = browser.new_context(viewport=VIEWPORT, has_touch=True)  # type: ignore[arg-type]  # TypedDict
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="module")
def pointer_reduced_page(browser: Browser) -> Iterator[Page]:
    """A page whose system asks for reduced motion (E2E-027), window 1600 by 900."""
    context = browser.new_context(viewport=VIEWPORT, reduced_motion="reduce")  # type: ignore[arg-type]  # TypedDict
    page = context.new_page()
    yield page
    context.close()


def resize_presented(page: Page, width: int, height: int) -> CDPSession:
    """Resize a full screen window: Chromium refuses ``set_viewport_size`` then, so the viewport is emulated.

    The emulation lasts as long as the returned session: clear it there (``Emulation.clearDeviceMetricsOverride``).
    """
    session = page.context.new_cdp_session(page)
    session.send(
        "Emulation.setDeviceMetricsOverride",
        {"width": width, "height": height, "deviceScaleFactor": 0, "mobile": False},
    )
    return session


def present_served(page: Page, port: int) -> None:
    """Open the editor page on Deck P served at ``port``, present it with ``#present-btn``, turn the pointer on."""
    open_served(page, port)
    present_with(page, "#present-btn")
    wait_until(
        page,
        lambda: page.evaluate("document.activeElement.id"),
        lambda v: v == "content-frame",
        what="focus in the deck",
    )
    page.keyboard.press("l")
    wait_state(page, lambda s: s["on"], "pointer on", FRAME_DOC)


# editor.js wires its buttons after its first /status answer, in the task that writes the file name; the deck's
# scripts have run once its document is complete.
EDITOR_READY = (
    "() => { const f = document.getElementById('content-frame'); const d = f && f.contentDocument;"
    " return document.getElementById('toolbar-filename').textContent !== '\u2014'"
    " && !!d && d.readyState === 'complete' && !!d.querySelector('#slide-2'); }"
)
# SPEC-0016 DEC-002: headless Chromium keeps the keyboard focus in the iframe, so a key "typed with the focus in
# the editor page" is dispatched on the editor page's own document; returns defaultPrevented.
DISPATCH_KEY = (
    "k => { const e = new KeyboardEvent('keydown', {key: k, bubbles: true, cancelable: true});"
    " document.dispatchEvent(e); return e.defaultPrevented; }"
)
# The editor's Pointeur control: present in the toolbar, shown, and its place beside the present control.
POINTER_CONTROL = """
() => {
  const btn = document.getElementById('pointer-btn');
  const present = document.getElementById('present-btn');
  if (!btn) return {exists: false, shown: false};
  const r = btn.getBoundingClientRect(), p = present.getBoundingClientRect();
  return {exists: true, shown: getComputedStyle(btn).display !== 'none' && r.width > 0,
          afterPresent: present.nextElementSibling === btn, left: r.left, presentRight: p.right,
          title: btn.title, label: btn.getAttribute('aria-label'), text: btn.textContent.trim()};
}
"""


def open_served(page: Page, port: int) -> None:
    """Leave a full screen left by the previous test, size the window, open the editor page on the served deck."""
    leave_full_screen(page)
    page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
    page.goto(f"http://127.0.0.1:{port}/")
    wait_until(page, lambda: page.evaluate(EDITOR_READY), bool, what="the editor and its deck ready")


def present_with(page: Page, control: str) -> None:
    """Press an editor toolbar control that presents the served deck; return once it is full screen and still."""
    shown = page.evaluate(
        "([sel]) => { const b = document.querySelector(sel); return !!b && b.offsetWidth > 0; }", [control]
    )
    assert shown, f"{control} is not shown in the editor toolbar"
    page.click(control)
    wait_state(page, lambda s: s["fullscreen"] == "HTML", "the served deck presented", FRAME_DOC)
    wait_slide_settled(page, FRAME_DOC)


def dispatch_key(page: Page, key: str) -> bool:
    """A key typed while the focus is in the editor page (DISPATCH_KEY); the relay acts synchronously."""
    return bool(page.evaluate(DISPATCH_KEY, key))


def pointer_control(page: Page) -> dict[str, Any]:
    control: dict[str, Any] = page.evaluate(POINTER_CONTROL)
    return control


def pointer_state(page: Page, doc: str = DOC) -> PointerState:
    state: PointerState = page.evaluate(f"({POINTER_STATE})({doc})")
    return state


def ring_around(page: Page, selector: str, doc: str = DOC) -> RingCheck:
    """The ring state and the rect of the element ``selector`` of the deck's document, read in one go."""
    check: RingCheck = page.evaluate(f"([sel]) => ({RING_AROUND})({doc}, sel)", [selector])
    return check


def is_ringed(check: RingCheck, scale: float = SCALE) -> bool:
    """One ring shown whose outer edge lies 6 slide pixels (times ``scale``) +-1 screen pixel outside the box."""
    ring, box = check["ring"], check["box"]
    if check["rings"] != 1 or ring is None or box is None:
        return False
    gap = RING_GAP * scale
    edges = (
        box["left"] - ring["left"],
        box["top"] - ring["top"],
        ring["left"] + ring["width"] - box["left"] - box["width"],
        ring["top"] + ring["height"] - box["top"] - box["height"],
    )
    return all(abs(edge - gap) <= 1 for edge in edges)


def wait_ringed(page: Page, selector: str, doc: str = DOC, scale: float = SCALE) -> RingCheck:
    """Wait until ``selector`` is ringed and the ring's entrance animation is over: a rect read during the animation
    already passes ``is_ringed`` but differs by a pixel from the same ring read once it is still."""
    return wait_until(
        page,
        lambda: ring_around(page, selector, doc),
        lambda c: c["still"] and is_ringed(c, scale),
        what=f"{selector} ringed",
    )


def next_frames(page: Page, doc: str = DOC) -> None:
    """Return once the deck's document has drawn two more frames, so its frame loop has seen the last action."""
    page.evaluate(
        f"() => new Promise(r => {{ const w = ({doc}).defaultView;"
        " w.requestAnimationFrame(() => w.requestAnimationFrame(r)); })"
    )


def click_centre(page: Page, selector: str, doc: str = DOC) -> None:
    """Click the middle of ``selector`` of the deck's document at its screen place (the deck fills the page)."""
    box = page.evaluate(
        f"([sel]) => {{ const r = ({doc}).querySelector(sel).getBoundingClientRect();"
        " return [r.left + r.width / 2, r.top + r.height / 2]; }",
        [selector],
    )
    page.mouse.click(box[0], box[1])


def leave_full_screen(page: Page) -> None:
    """Leave a full screen left by the previous test of the module page."""
    if page.evaluate("!!document.fullscreenElement"):
        page.evaluate("document.exitFullscreen()")
        wait_until(
            page, lambda: page.evaluate("!!document.fullscreenElement"), lambda v: not v, what="full screen left"
        )


def open_deck_p(page: Page, path: Path, width: int = WIDTH, height: int = HEIGHT) -> None:
    """Leave a full screen left by the previous test, size the window, load Deck P afresh."""
    leave_full_screen(page)
    page.set_viewport_size({"width": width, "height": height})
    page.goto(path.as_uri())


def wait_state(page: Page, holds: Any, what: str, doc: str = DOC) -> PointerState:
    return wait_until(page, lambda: pointer_state(page, doc), holds, what=what)


def wait_presenting(page: Page) -> PointerState:
    return wait_state(page, lambda s: s["fullscreen"] == "HTML", "the deck presented full screen")


# True once the current slide is scaled to fit the window and its entrance animation is over, so the screen
# place of an element read now is where a click lands.
SLIDE_SETTLED = """
doc => {
  const win = doc.defaultView;
  const slide = doc.querySelector('[data-type="slide"].active, [data-type="slide"][data-fs-current]');
  if (!slide || !doc.fullscreenElement) return false;
  const fit = Math.min(win.innerWidth / slide.offsetWidth, win.innerHeight / slide.offsetHeight);
  const running = slide.getAnimations().some(a => a.playState === 'running');
  return !running && Math.abs(slide.getBoundingClientRect().width - fit * slide.offsetWidth) <= 1;
}
"""


def wait_slide_settled(page: Page, doc: str = DOC) -> None:
    wait_until(page, lambda: page.evaluate(f"({SLIDE_SETTLED})({doc})"), lambda v: v, what="the slide fitted and still")


def print_pdf_normalized(page: Page) -> bytes:
    """The page printed to PDF, animations stilled, its creation and modification dates removed (DEC-017)."""
    page.evaluate(STILL_ANIMATIONS)
    return PDF_DATES.sub(b"", page.pdf())
