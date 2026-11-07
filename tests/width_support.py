"""Shared fixtures and helpers of the text width bar browser tests (SPEC-0015, DEC-011).

Fixture decks are generated from the Carbon bootstrap (spec 9.0). One Chromium page is shared by every
test of a module (``width_page``); each test starts its own editor server, writes its fixture, then
opens the editor on it with ``open_editor``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from bs4 import BeautifulSoup, Tag
from playwright.sync_api import Browser, Page

from tests.browser_wait import wait_for_js, wait_until

REPO_ROOT = Path(__file__).resolve().parents[1]
CARBON_BOOTSTRAP = REPO_ROOT / "templates" / "bootstrap" / "slides-empty.html"
VIEWPORT = {"width": 1280, "height": 900}
SAVED_DOT_COLOR = "rgb(66, 190, 101)"
ONE_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
SCALED_SLIDE_STYLE = "<style>.slide{transform:scale(0.5);transform-origin:top left}</style>"

PARAGRAPHS = (
    ("A", "max-width:600px", "Chiffres clés du trimestre"),
    ("B", "color:#0F62FE;font-weight:600", 'Note de synthèse <span class="tag-blue">Nouveau</span>'),
    ("H", "max-width: 40em;color:#525252;font-size:10px", "Objectifs"),
    ("I", "max-width:85px", "Mini"),
    ("J", "color:#123456", "Hors charte"),
    ("K", "max-width:1250px", "Large"),
    ("P", "max-width:50%", "Agent"),
    ("Q", "background:url(data:image/png;base64,AAA);color:#123456", "Fond"),
)
# CSS selector (inside the framed document) of each paragraph of D1, by its spec letter.
PARAGRAPH = {
    letter: f'.slide-body p[data-editable="text"]:nth-of-type({n})' for n, (letter, _, _) in enumerate(PARAGRAPHS, 1)
}

SAVE_COUNTER_SCRIPT = """
(() => {
  window.__widthSaves = 0;
  const send = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    const method = ((init && init.method) || 'GET').toUpperCase();
    if (method === 'POST' && url.pathname === '/content') window.__widthSaves++;
    return send(input, init);
  };
})();
"""
FRAME_READY = (
    "() => { const f = document.getElementById('content-frame');"
    " const d = f && f.contentDocument; return !!d && d.readyState === 'complete' && !!d.querySelector('#slide-1'); }"
)
SLIDE_2_SHOWN = (
    "() => { const d = document.getElementById('content-frame').contentDocument;"
    " return d.querySelector('#slide-1').classList.contains('active'); }"
)
EDITABLE = (
    "() => { const d = document.getElementById('content-frame').contentDocument;"
    " const p = d.querySelector('.slide-body p[data-editable]'); return !!p && p.isContentEditable; }"
)
# editor.js wires the edit button after its first /status answer, in the task that writes the file name.
EDIT_BUTTON_WIRED = "() => document.getElementById('toolbar-filename').textContent !== '\u2014'"
READOUT = "() => { const r = document.getElementById('width-readout'); return r && !r.hidden ? r.textContent : null; }"


def _slide(index: int, title: str, body: str) -> str:
    return (
        f'    <article class="slide" id="slide-{index}" data-type="slide" data-id="slide-{index}"'
        f' data-title="{title}">\n'
        '      <div class="slide-header">\n'
        f'        <h1 class="slide-h1" data-editable="text">{title}</h1>\n'
        "      </div>\n"
        f'      <div class="slide-body">\n{body}      </div>\n'
        "    </article>\n"
    )


def _slide_2_body() -> str:
    paragraphs = "".join(
        f'          <p data-editable="text" style="{style}">{text}</p>\n' for _, style, text in PARAGRAPHS
    )
    return (
        '        <div style="width:800px">\n'
        f"{paragraphs}"
        '          <ul data-editable="text"><li>Premier point</li><li>Second point</li></ul>\n'
        '          <table data-type="table"><thead><tr><th>Indicateur</th></tr></thead>'
        "<tbody><tr><td>Valeur A1</td></tr></tbody></table>\n"
        f'          <img alt="logo" src="data:image/png;base64,{ONE_PIXEL_PNG}">\n'
        "        </div>\n"
    )


def _slide_3_body() -> str:
    return (
        '        <div data-type="arch-diagram" style="position:relative; width:100%; height:200px;">\n'
        '          <div data-type="arch-node" class="arch-node" data-label="Serveur MCP" data-shape="box" '
        'style="position:absolute; left:10%; top:10%; width:20%; height:20%;">Serveur MCP</div>\n'
        "        </div>\n"
        '        <div data-type="gantt"><div class="gantt-row"><div class="gantt-track">'
        '<div data-type="gantt-task" class="gantt-bar" data-label="Cadrage" data-start="2026-01" data-end="2026-03" '
        'style="left:0%; width:25%; background:#0f62fe;">Cadrage</div></div></div></div>\n'
        '        <div data-type="annotated-image" style="position:relative;">'
        f'<img alt="graphique" src="data:image/png;base64,{ONE_PIXEL_PNG}" style="width:100%; display:block;">'
        '<div data-type="annotation" data-x="10" data-y="10" style="position:absolute; left:10%; top:10%;">Pic</div>'
        "</div>\n"
    )


def deck_d1() -> str:
    """D1 (spec 9.0): the Carbon bootstrap grown to three slides, slide 2 holding the paragraphs A to Q."""
    html = CARBON_BOOTSTRAP.read_text(encoding="utf-8")
    first_end = html.index("</article>") + len("</article>")
    slides = _slide(1, "Largeurs", _slide_2_body()) + _slide(2, "Objets", _slide_3_body())
    html = html[:first_end] + "\n\n" + slides + html[first_end:]
    html = html.replace("const TOTAL = 1;", "const TOTAL = 3;", 1)
    return html.replace(
        '"Titre de la présentation",\n', '"Titre de la présentation",\n    "Largeurs",\n    "Objets",\n', 1
    )


def deck_d3() -> str:
    """D3: D1 whose template shows every slide at half size."""
    return deck_d1().replace("</head>", SCALED_SLIDE_STYLE + "\n</head>", 1)


def deck_d2() -> str:
    """D2 (spec 9.0): a Perso document, title `Rapport Q1`, `Paragraphe 1` to `Paragraphe 40`, the first 500 wide."""
    html = (REPO_ROOT / "templates" / "bootstrap" / "document-perso-empty.html").read_text(encoding="utf-8")
    start = html.index('<h1 class="doc-title"')
    end = html.index("</article>")
    title = '<h1 class="doc-title" data-editable="text">Rapport Q1</h1>\n'
    paragraphs = "".join(
        f'<p data-editable="text"{' style="max-width:500px"' if n == 1 else ""}>Paragraphe {n}</p>\n'
        for n in range(1, 41)
    )
    return html[:start] + title + paragraphs + html[end:]


def deck_m1() -> str:
    """M1 (spec 9.0): the mail bootstrap as is."""
    return (REPO_ROOT / "templates" / "bootstrap" / "mail-empty.html").read_text(encoding="utf-8")


def deck_w1() -> str:
    """W1 (spec 9.0): the website bootstrap as is."""
    return (REPO_ROOT / "templates" / "bootstrap" / "website-empty.html").read_text(encoding="utf-8")


def write_fixture(folder: Path, text: str) -> Path:
    """Write ``text`` as ``deck.html`` in ``folder`` and return its path."""
    path = folder / "deck.html"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def width_page(browser: Browser) -> Iterator[Page]:
    """One Chromium page shared by the tests of a module, window 1280 by 900, saves counted."""
    context = browser.new_context(viewport=VIEWPORT)  # type: ignore[arg-type]  # ViewportSize is a TypedDict
    page = context.new_page()
    page.add_init_script(SAVE_COUNTER_SCRIPT)
    yield page
    context.close()


def show_slide_2(page: Page, port: int) -> None:
    """Open the editor on the served file and show slide 2."""
    page.goto(f"http://127.0.0.1:{port}/")
    wait_for_js(page, FRAME_READY, True, what="the framed deck loaded")
    page.evaluate("() => document.getElementById('content-frame').contentWindow.goToSlide(1)")
    wait_for_js(page, SLIDE_2_SHOWN, True, what="slide 2 shown")


def open_editor(page: Page, port: int) -> None:
    """Open the editor, show slide 2 and turn edit mode on."""
    show_slide_2(page, port)
    wait_for_js(page, EDIT_BUTTON_WIRED, True, what="the edit button wired")
    page.click("#edit-mode-btn")
    wait_for_js(page, EDITABLE, True, what="edit mode on")


DOCUMENT_READY = (
    "() => { const d = document.getElementById('content-frame').contentDocument;"
    " return !!d && d.readyState === 'complete' && !!d.querySelector('[data-editable]'); }"
)
DOCUMENT_EDITABLE = (
    "() => { const d = document.getElementById('content-frame').contentDocument;"
    " const e = d && d.querySelector('[data-editable~=\"text\"]'); return !!e && e.isContentEditable; }"
)


def open_document(page: Page, port: int) -> None:
    """Open the editor on a document, a mail or a website (no slides) and turn edit mode on."""
    page.goto(f"http://127.0.0.1:{port}/")
    wait_for_js(page, DOCUMENT_READY, True, what="the framed document loaded")
    wait_for_js(page, EDIT_BUTTON_WIRED, True, what="the edit button wired")
    page.click("#edit-mode-btn")
    wait_for_js(page, DOCUMENT_EDITABLE, True, what="edit mode on")


def block_box(page: Page, selector: str) -> dict[str, float]:
    """Rectangle of a framed element in the shell page's coordinates."""
    box = page.evaluate(
        """(sel) => {
          const frame = document.getElementById('content-frame');
          const f = frame.getBoundingClientRect();
          const r = frame.contentDocument.querySelector(sel).getBoundingClientRect();
          return { x: f.left + r.left, y: f.top + r.top, width: r.width, height: r.height };
        }""",
        selector,
    )
    return {key: float(value) for key, value in box.items()}


def bar_box(page: Page) -> dict[str, float] | None:
    """Rectangle of the width bar, ``None`` when it is hidden."""
    box = page.evaluate(
        """() => { const b = document.getElementById('width-bar');
          if (!b || b.hidden) return null; const r = b.getBoundingClientRect();
          return { x: r.left, y: r.top, width: r.width, height: r.height }; }"""
    )
    return None if box is None else {key: float(value) for key, value in box.items()}


def drag_bar(page: Page, selector: str, dx: float, *, alt: bool = False, steps: int = 5) -> list[str]:
    """Point at a framed text block, drag its width bar ``dx`` screen pixels and let go.

    Return the readouts seen after each pointer move, the last one after the release (``None`` when hidden).
    """
    bar = point_bar(page, selector)
    start_x = bar["x"] + bar["width"] / 2
    y = bar["y"] + bar["height"] / 2
    page.mouse.move(start_x, y)
    seen: list[str] = []
    # Released in `finally`: a failure must not leave Alt or the button held on the module's shared page.
    if alt:
        page.keyboard.down("Alt")
    try:
        page.mouse.down()
        try:
            for step in range(1, steps + 1):
                page.mouse.move(start_x + dx * step / steps, y)
                seen.append(page.evaluate(READOUT))
        finally:
            page.mouse.up()
    finally:
        if alt:
            page.keyboard.up("Alt")
    seen.append(page.evaluate(READOUT))
    return seen


POLL_COUNTER_SCRIPT = """
(() => {
  if (window.__statusPolls !== undefined) return;
  window.__statusPolls = 0;
  const send = window.fetch;
  window.fetch = async (input, init) => {
    const response = await send(input, init);
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (url.pathname === '/status') window.__statusPolls++;
    return response;
  };
})()
"""


def count_polls(page: Page) -> None:
    """Count the editor's answered ``/status`` polls in ``window.__statusPolls`` (installed once per page load)."""
    page.evaluate(POLL_COUNTER_SCRIPT)


def wait_polls(page: Page, count: int = 3) -> None:
    """Wait until ``count`` more ``/status`` polls have been answered.

    The one in flight may predate the call and the counter moves before a poll is handled, so the default 3 means
    at least one poll that started after the call has been fully handled.
    """
    start = int(page.evaluate("() => window.__statusPolls"))
    wait_until(
        page,
        lambda: int(page.evaluate("() => window.__statusPolls")),
        lambda n: n >= start + count,
        what=f"{count} status polls answered",
    )


def element_starting_with(html: str, text: str) -> Tag:
    """The innermost element of ``html`` whose text starts with ``text``."""
    soup = BeautifulSoup(html, "html.parser")
    found = [tag for tag in soup.find_all(True) if tag.get_text().strip().startswith(text)]
    assert found, f"no element starting with {text!r}"
    return found[-1]


def style_in_file(path: Path, text: str) -> str | None:
    """The ``style`` attribute of the element of the file whose text starts with ``text``, ``None`` when absent."""
    style = element_starting_with(path.read_text(encoding="utf-8"), text).get("style")
    return None if style is None else str(style)


def markers_in(path: Path) -> list[str]:
    """Editing markers left in the file: ids, classes or attributes starting with ``_mcp``, ``contenteditable``, and
    the width bar's own ids. Empty when the file is clean (NFR-003)."""
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    found: list[str] = []
    for tag in soup.find_all(True):
        for name, value in tag.attrs.items():
            values = value if isinstance(value, list) else [value]
            if name.startswith("_mcp") or name == "contenteditable":
                found.append(f"{tag.name} attribute {name}")
            elif name == "id" and (str(value).startswith("_mcp") or value in ("width-bar", "width-readout")):
                found.append(f"{tag.name} id {value}")
            elif name == "class":
                found.extend(f"{tag.name} class {c}" for c in values if str(c).startswith("_mcp"))
    return found


def point_bar(page: Page, selector: str) -> dict[str, float]:
    """Point at a framed text block and return the rectangle of the width bar shown on it."""
    box = block_box(page, selector)
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    bar = bar_box(page)
    assert bar is not None, f"no width bar on {selector}"
    return bar


def focus_bar(page: Page, selector: str) -> None:
    """Point at a framed text block, then click its width bar, which takes the keyboard focus."""
    bar = point_bar(page, selector)
    page.mouse.click(bar["x"] + bar["width"] / 2, bar["y"] + bar["height"] / 2)


def double_click_bar(page: Page, selector: str) -> None:
    """Point at a framed text block, then double click its width bar."""
    bar = point_bar(page, selector)
    page.mouse.dblclick(bar["x"] + bar["width"] / 2, bar["y"] + bar["height"] / 2)


def undo_disabled(page: Page) -> bool:
    """True when the editor's Undo button is disabled."""
    return bool(page.evaluate("() => document.getElementById('undo-btn').disabled"))


def redo_disabled(page: Page) -> bool:
    """True when the editor's Redo button is disabled."""
    return bool(page.evaluate("() => document.getElementById('redo-btn').disabled"))
