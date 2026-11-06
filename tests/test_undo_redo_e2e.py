"""E2E tests for structural undo/redo (Ctrl+Z / Ctrl+Shift+Z) in editor.js.

Real browser tests, same pattern as test_fullscreen_e2e.py: a real
ThreadingHTTPServer plus a real headless Chromium via pytest-playwright.
Unit tests cannot cover this: the whole feature lives in browser-only APIs
(contenteditable, document.write, pointer events, keyboard shortcuts).

Scope under test: structural DOM mutations that have zero native undo today
- arch-node drag reposition, image insert via drag-drop, table row add,
slide insert/delete, document block insert/reorder. Plain contenteditable
text edits are deliberately NOT covered here: they already have a working
native undo stack, this suite only proves OUR stack behaves correctly for
what native undo does not cover, and that it does not fire when focus is in
an actively-edited text zone.
"""

from __future__ import annotations

import platform
import re
import socket
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page

from mcp_htmleditor import config as config_module
from mcp_htmleditor import templates as templates_module
from mcp_htmleditor.http_server import start_http_server, stop_http_server
from tests.browser_wait import LATE_SAVE_MS, apply_save_delay, settle, wait_until

REPO_ROOT = Path(__file__).resolve().parents[1]

# Cross-platform Ctrl/Cmd for Playwright's keyboard.press() modifier names.
MOD = "Meta" if platform.system() == "Darwin" else "Control"


def _chromium_cache_dir() -> Path:
    home = Path.home()
    if platform.system() == "Darwin":
        return home / "Library" / "Caches" / "ms-playwright"
    return home / ".cache" / "ms-playwright"


HAS_CHROMIUM = any(_chromium_cache_dir().glob("chromium-*"))
needs_chromium = pytest.mark.skipif(
    not HAS_CHROMIUM,
    reason="Playwright Chromium is not installed; run `make sync`",
)


@pytest.fixture(params=[0, LATE_SAVE_MS], ids=["prompt", "late"])
def save_delay(request: pytest.FixtureRequest, page: Page) -> int:
    """Answer every ``POST /content`` at once (0) or ``LATE_SAVE_MS`` late (BR-011)."""
    delay = int(request.param)
    apply_save_delay(page, delay)
    return delay


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _deck_with_arch_diagram(tmp_path: Path) -> Path:
    """Grow the Carbon bootstrap's single slide with a 1-node arch-diagram.

    Reuses the bootstrap's own arch-node CSS (already embedded, see
    skill/types/arch-diagram.md), just adds a positioned node to drag.
    """
    src = templates_module.template_path("carbon")
    html = src.read_text(encoding="utf-8")
    diagram = (
        '<div data-type="arch-diagram" style="position:relative; width:100%; height:200px;">'
        '<div data-type="arch-node" class="arch-node" data-label="Service A" data-shape="box" '
        'data-x="10.0" data-y="10.0" data-width="20.0" data-height="15.0" '
        'style="position:absolute; left:10.0%; top:10.0%; width:20.0%; height:15.0%; '
        'border:2px solid #0f62fe; background:#edf5ff;">Service A</div>'
        "</div>"
    )
    match = re.search(r'(<div class="slide-body"[^>]*>)(.*?)(</div>)\s*<div class="slide-footer">', html, re.S)
    if not match:
        pytest.fail("templates/bootstrap/slides-empty.html shape changed, update this fixture")
    html = html.replace(match.group(0), match.group(1) + diagram + match.group(3) + '\n  <div class="slide-footer">', 1)
    out = tmp_path / "deck.html"
    out.write_text(html, encoding="utf-8")
    return out


def _plain_document(tmp_path: Path) -> Path:
    """Copy the plain 'doc' bootstrap as-is: has a title (h1) and a body
    paragraph (p), both top-level blocks of the article, ideal for block
    insert/reorder tests."""
    src = templates_module.template_path("doc")
    out = tmp_path / "doc.html"
    out.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return out


def _document_with_table(tmp_path: Path) -> Path:
    """'doc' bootstrap plus a 1-row data-type="table" for row/col context-menu tests."""
    src = templates_module.template_path("doc")
    html = src.read_text(encoding="utf-8")
    table = (
        '<table data-type="table"><thead><tr><th>A</th><th>B</th></tr></thead>'
        "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
    )
    html = html.replace("</article>", table + "</article>")
    out = tmp_path / "doc-table.html"
    out.write_text(html, encoding="utf-8")
    return out


def _start(tmp_path_file: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", str(REPO_ROOT / "templates"))
    config_module.reset_settings_cache()
    port = _free_port()
    start_http_server(str(tmp_path_file), port=port)
    base_url = f"http://127.0.0.1:{port}/"
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    else:
        pytest.fail("HTTP server did not start in time")
    return base_url


@pytest.fixture
def arch_deck_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_state: None) -> Iterator[str]:
    deck = _deck_with_arch_diagram(tmp_path)
    try:
        yield _start(deck, monkeypatch)
    finally:
        stop_http_server()


@pytest.fixture
def doc_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_state: None) -> Iterator[str]:
    doc = _plain_document(tmp_path)
    try:
        yield _start(doc, monkeypatch)
    finally:
        stop_http_server()


@pytest.fixture
def table_doc_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_state: None) -> Iterator[str]:
    doc = _document_with_table(tmp_path)
    try:
        yield _start(doc, monkeypatch)
    finally:
        stop_http_server()


def _inner(page: Page, js_expression: str) -> object:
    """Evaluate a JS expression with `doc` bound to the iframe's contentDocument."""
    return page.evaluate(
        f"() => {{ const doc = document.getElementById('content-frame').contentDocument; return ({js_expression}); }}"
    )


SLIDE_COUNT = "doc.querySelectorAll('article[data-type=slide]').length"
IMAGE_COUNT = "doc.querySelectorAll('img').length"
ROW_COUNT = "doc.querySelectorAll('table tbody tr').length"
BLOCK_COUNT = "doc.querySelector('article').children.length"
BLOCK_ORDER = "[...doc.querySelector('article').children].map(c => c.tagName)"


def _await_inner(page: Page, js_expression: str, holds: Callable[[object], bool], *, what: str) -> object:
    """Observe `_inner(js_expression)` until `holds` is true (BR-008); return the value that held."""
    return wait_until(page, lambda: _inner(page, js_expression), holds, what=what)


def _await_count(page: Page, js_expression: str, expected: int, *, what: str) -> object:
    """Observe a count until it equals `expected`; the caller's assertion then reads the value that held."""
    return _await_inner(page, js_expression, lambda value: value == expected, what=what)


def _press_undo_redo(page: Page, keys: str) -> None:
    """Press an undo or redo shortcut, then wait until the restored document is rewired.

    The DOM is rewritten at once but `onFrameLoad` re-registers the keydown handler on the new document
    only when its `load` event fires (`restoringFromUndo` goes back to false then): a shortcut pressed
    before that is lost, as it would be for a user acting within the same few milliseconds.
    """
    page.keyboard.press(keys)
    wait_until(
        page,
        lambda: page.evaluate("() => restoringFromUndo"),
        lambda restoring: restoring is False,
        what="restored document rewired",
    )


def _enable_edit_mode(page: Page) -> None:
    page.click("#edit-mode-btn")
    wait_until(
        page,
        lambda: page.evaluate("() => getComputedStyle(document.getElementById('undo-btn')).display"),
        lambda display: display != "none",
        what="undo button displayed",
    )


@needs_chromium
def test_undo_redo_buttons_hidden_outside_edit_mode(page: Page, arch_deck_server: str, save_delay: int) -> None:
    page.goto(arch_deck_server, wait_until="networkidle")
    assert page.evaluate("() => getComputedStyle(document.getElementById('undo-btn')).display") == "none"
    _enable_edit_mode(page)
    assert page.evaluate("() => getComputedStyle(document.getElementById('undo-btn')).display") != "none"
    assert page.is_disabled("#undo-btn")  # nothing to undo yet


@needs_chromium
def test_undo_redo_arch_node_reposition(page: Page, arch_deck_server: str, save_delay: int) -> None:
    """Drag an arch-node, then Ctrl+Z restores its original data-x/data-y, Ctrl+Shift+Z redoes it."""
    page.goto(arch_deck_server, wait_until="networkidle")
    _enable_edit_mode(page)

    node_sel = '[data-type="arch-node"]'
    original_x = _inner(page, f"doc.querySelector('{node_sel}').dataset.x")
    original_y = _inner(page, f"doc.querySelector('{node_sel}').dataset.y")
    assert original_x == "10.0"

    box = _inner(
        page,
        f"(() => {{ const r = doc.querySelector('{node_sel}').getBoundingClientRect();"
        " const f = document.getElementById('content-frame').getBoundingClientRect();"
        " return [f.left + r.left + r.width/2, f.top + r.top + r.height/2]; })()",
    )
    assert isinstance(box, list)
    start_x, start_y = box

    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(start_x + 120, start_y + 60, steps=5)
    page.mouse.up()

    node_x = f"doc.querySelector('{node_sel}').dataset.x"
    moved_x = _await_inner(page, node_x, lambda x: x != original_x, what="node x after the drag")
    assert moved_x != original_x, "drag did not move the node"

    page.click("#content-frame")  # focus the iframe so Playwright's key events land there
    _press_undo_redo(page, f"{MOD}+z")

    restored_x = _await_inner(page, node_x, lambda x: x == original_x, what="node x after undo")
    restored_y = _inner(page, f"doc.querySelector('{node_sel}').dataset.y")
    assert restored_x == original_x
    assert restored_y == original_y

    _press_undo_redo(page, f"{MOD}+Shift+z")
    redone_x = _await_inner(page, node_x, lambda x: x == moved_x, what="node x after redo")
    assert redone_x == moved_x


@needs_chromium
def test_undo_redo_slide_insert_and_delete(page: Page, arch_deck_server: str, save_delay: int) -> None:
    page.goto(arch_deck_server, wait_until="networkidle")
    _enable_edit_mode(page)

    assert _inner(page, SLIDE_COUNT) == 1

    page.click("#btn-insert-after")
    page.wait_for_selector("#slide-picker .picker-card")
    page.click("#slide-picker .picker-card")
    assert _await_count(page, SLIDE_COUNT, 2, what="slides after insert") == 2

    page.click("#content-frame")
    _press_undo_redo(page, f"{MOD}+z")
    assert _await_count(page, SLIDE_COUNT, 1, what="slides after undo") == 1

    _press_undo_redo(page, f"{MOD}+Shift+z")
    assert _await_count(page, SLIDE_COUNT, 2, what="slides after redo") == 2


@needs_chromium
def test_undo_does_not_fire_inside_active_text_editing(page: Page, doc_server: str, save_delay: int) -> None:
    """Typing then Ctrl+Z inside a contenteditable zone must NOT touch our
    structural stack: it must be a no-op from our side (native browser undo
    handles it, or does nothing if disabled under automation), never restore
    a structural snapshot while the user is mid-sentence."""
    page.goto(doc_server, wait_until="networkidle")
    _enable_edit_mode(page)

    block_count_before = _inner(page, BLOCK_COUNT)

    # Do ONE structural op first, so the stack is non-empty.
    page.click("#btn-insert-block-after")
    page.wait_for_selector("#block-picker .picker-card")
    page.click("#block-picker .picker-card")
    block_count_after_insert = _await_inner(
        page, BLOCK_COUNT, lambda count: count != block_count_before, what="blocks after insert"
    )

    # Now focus the title (contenteditable) and type.
    _inner(page, "doc.querySelector('h1').focus()")
    page.keyboard.type(" extra")
    _await_inner(page, "doc.querySelector('h1').textContent", lambda text: "extra" in str(text), what="typed title")

    page.keyboard.press(f"{MOD}+z")  # nothing to rewire: the shortcut must be left to the browser
    settle(page)  # BR-010: an undo that would wrongly fire has had its time before the absence is asserted

    # The structural snapshot must still be there (undo stack untouched by a
    # keystroke fired while focus is inside a live contenteditable region).
    assert _inner(page, BLOCK_COUNT) == block_count_after_insert


@needs_chromium
def test_undo_redo_document_block_insert(page: Page, doc_server: str, save_delay: int) -> None:
    page.goto(doc_server, wait_until="networkidle")
    _enable_edit_mode(page)

    before = _inner(page, BLOCK_COUNT)

    page.click("#btn-insert-block-after")
    page.wait_for_selector("#block-picker .picker-card")
    page.click("#block-picker .picker-card")
    after_insert = _await_count(page, BLOCK_COUNT, before + 1, what="blocks after insert")
    assert after_insert == before + 1

    page.click("#content-frame")
    _press_undo_redo(page, f"{MOD}+z")
    assert _await_count(page, BLOCK_COUNT, before, what="blocks after undo") == before

    _press_undo_redo(page, f"{MOD}+Shift+z")
    assert _await_count(page, BLOCK_COUNT, after_insert, what="blocks after redo") == after_insert


@needs_chromium
def test_undo_redo_image_insert_via_drop(page: Page, doc_server: str, save_delay: int) -> None:
    """Image insert onto a specific editable (the drag-drop path in
    embedImageFile) uses insertAdjacentHTML, NOT execCommand: unlike the
    file-picker path, it does not push a step onto the browser's native
    contenteditable undo stack, which is exactly why this needs OUR stack.
    """
    page.goto(doc_server, wait_until="networkidle")
    _enable_edit_mode(page)

    before = _inner(page, IMAGE_COUNT)
    assert before == 0

    # Exercise the exact code path drag-and-drop uses (embedImageFile with a
    # targetEl), without needing a real OS-level DataTransfer file drop.
    page.evaluate(
        """() => {
            const doc = document.getElementById('content-frame').contentDocument;
            const targetEl = doc.querySelector("[data-editable~='text']");
            const bytes = new Uint8Array([137,80,78,71,13,10,26,10]);
            const file = new File([bytes], 'tiny.png', { type: 'image/png' });
            window.embedImageFile(doc, file, targetEl);
        }"""
    )
    assert _await_count(page, IMAGE_COUNT, 1, what="images after insert") == 1

    page.click("#content-frame")
    _press_undo_redo(page, f"{MOD}+z")
    assert _await_count(page, IMAGE_COUNT, 0, what="images after undo") == 0

    _press_undo_redo(page, f"{MOD}+Shift+z")
    assert _await_count(page, IMAGE_COUNT, 1, what="images after redo") == 1


@needs_chromium
def test_undo_redo_table_row_add_via_context_menu(page: Page, table_doc_server: str, save_delay: int) -> None:
    page.goto(table_doc_server, wait_until="networkidle")
    _enable_edit_mode(page)

    assert _inner(page, ROW_COUNT) == 1

    frame_el = page.frame_locator("#content-frame")
    frame_el.locator("table").first.click(button="right")
    page.wait_for_selector("text=\uff0b Ajouter ligne", timeout=10_000)
    page.click("text=\uff0b Ajouter ligne")
    assert _await_count(page, ROW_COUNT, 2, what="rows after add") == 2

    page.click("#content-frame")
    _press_undo_redo(page, f"{MOD}+z")
    assert _await_count(page, ROW_COUNT, 1, what="rows after undo") == 1

    _press_undo_redo(page, f"{MOD}+Shift+z")
    assert _await_count(page, ROW_COUNT, 2, what="rows after redo") == 2


@needs_chromium
def test_undo_redo_document_block_reorder(page: Page, doc_server: str, save_delay: int) -> None:
    page.goto(doc_server, wait_until="networkidle")
    _enable_edit_mode(page)

    order_before = _inner(page, BLOCK_ORDER)
    assert isinstance(order_before, list)
    assert len(order_before) >= 2

    # Drag the SECOND block's handle above the FIRST block.
    handles = page.evaluate(
        "() => { const doc = document.getElementById('content-frame').contentDocument;"
        " return [...doc.querySelectorAll('._mcp_drag_handle')].length; }"
    )
    assert handles >= 2

    first_rect = _inner(
        page,
        "(() => { const doc = document.getElementById('content-frame'); "
        "const b = doc.contentDocument.querySelector('article').children[0].getBoundingClientRect();"
        "const f = doc.getBoundingClientRect(); return [f.left + b.left + 10, f.top + b.top + 5]; })()",
    )
    second_handle_rect = _inner(
        page,
        "(() => { const doc = document.getElementById('content-frame'); "
        "const h = doc.contentDocument.querySelectorAll('._mcp_drag_handle')[1].getBoundingClientRect();"
        "const f = doc.getBoundingClientRect(); return [f.left + h.left + h.width/2, f.top + h.top + h.height/2]; })()",
    )
    assert isinstance(first_rect, list) and isinstance(second_handle_rect, list)

    page.mouse.move(*second_handle_rect)
    page.mouse.down()
    page.mouse.move(first_rect[0], first_rect[1] - 5, steps=5)
    page.mouse.up()

    order_after = _await_inner(page, BLOCK_ORDER, lambda order: order != order_before, what="block order after drag")
    assert order_after != order_before, "drag-drop did not reorder the blocks"

    page.click("#content-frame")
    _press_undo_redo(page, f"{MOD}+z")
    order_undone = _await_inner(page, BLOCK_ORDER, lambda order: order == order_before, what="block order after undo")
    assert order_undone == order_before

    _press_undo_redo(page, f"{MOD}+Shift+z")
    order_redone = _await_inner(page, BLOCK_ORDER, lambda order: order == order_after, what="block order after redo")
    assert order_redone == order_after
