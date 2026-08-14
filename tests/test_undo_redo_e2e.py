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
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page

from mcp_htmleditor import config as config_module
from mcp_htmleditor import templates as templates_module
from mcp_htmleditor.http_server import start_http_server, stop_http_server

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


def _enable_edit_mode(page: Page) -> None:
    page.click("#edit-mode-btn")
    page.wait_for_timeout(150)


@needs_chromium
def test_undo_redo_buttons_hidden_outside_edit_mode(page: Page, arch_deck_server: str) -> None:
    page.goto(arch_deck_server, wait_until="networkidle")
    assert page.evaluate("() => getComputedStyle(document.getElementById('undo-btn')).display") == "none"
    _enable_edit_mode(page)
    assert page.evaluate("() => getComputedStyle(document.getElementById('undo-btn')).display") != "none"
    assert page.is_disabled("#undo-btn")  # nothing to undo yet


@needs_chromium
def test_undo_redo_arch_node_reposition(page: Page, arch_deck_server: str) -> None:
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
    page.wait_for_timeout(300)

    moved_x = _inner(page, f"doc.querySelector('{node_sel}').dataset.x")
    assert moved_x != original_x, "drag did not move the node"

    page.click("#content-frame")  # focus the iframe so Playwright's key events land there
    page.keyboard.press(f"{MOD}+z")
    page.wait_for_timeout(300)

    restored_x = _inner(page, f"doc.querySelector('{node_sel}').dataset.x")
    restored_y = _inner(page, f"doc.querySelector('{node_sel}').dataset.y")
    assert restored_x == original_x
    assert restored_y == original_y

    page.keyboard.press(f"{MOD}+Shift+z")
    page.wait_for_timeout(300)
    redone_x = _inner(page, f"doc.querySelector('{node_sel}').dataset.x")
    assert redone_x == moved_x


@needs_chromium
def test_undo_redo_slide_insert_and_delete(page: Page, arch_deck_server: str) -> None:
    page.goto(arch_deck_server, wait_until="networkidle")
    _enable_edit_mode(page)

    assert _inner(page, "doc.querySelectorAll('article[data-type=\"slide\"]').length") == 1

    page.click("#btn-insert-after")
    page.wait_for_selector("#slide-picker .picker-card")
    page.click("#slide-picker .picker-card")
    page.wait_for_timeout(300)
    assert _inner(page, "doc.querySelectorAll('article[data-type=\"slide\"]').length") == 2

    page.click("#content-frame")
    page.keyboard.press(f"{MOD}+z")
    page.wait_for_timeout(300)
    assert _inner(page, "doc.querySelectorAll('article[data-type=\"slide\"]').length") == 1

    page.keyboard.press(f"{MOD}+Shift+z")
    page.wait_for_timeout(300)
    assert _inner(page, "doc.querySelectorAll('article[data-type=\"slide\"]').length") == 2


@needs_chromium
def test_undo_does_not_fire_inside_active_text_editing(page: Page, doc_server: str) -> None:
    """Typing then Ctrl+Z inside a contenteditable zone must NOT touch our
    structural stack: it must be a no-op from our side (native browser undo
    handles it, or does nothing if disabled under automation), never restore
    a structural snapshot while the user is mid-sentence."""
    page.goto(doc_server, wait_until="networkidle")
    _enable_edit_mode(page)

    # Do ONE structural op first, so the stack is non-empty.
    page.click("#btn-insert-block-after")
    page.wait_for_selector("#block-picker .picker-card")
    page.click("#block-picker .picker-card")
    page.wait_for_timeout(300)
    block_count_after_insert = _inner(page, "doc.querySelector('article').children.length")

    # Now focus the title (contenteditable) and type.
    _inner(page, "doc.querySelector('h1').focus()")
    page.keyboard.type(" extra")
    page.wait_for_timeout(200)

    page.keyboard.press(f"{MOD}+z")
    page.wait_for_timeout(300)

    # The structural snapshot must still be there (undo stack untouched by a
    # keystroke fired while focus is inside a live contenteditable region).
    assert _inner(page, "doc.querySelector('article').children.length") == block_count_after_insert


@needs_chromium
def test_undo_redo_document_block_insert(page: Page, doc_server: str) -> None:
    page.goto(doc_server, wait_until="networkidle")
    _enable_edit_mode(page)

    before = _inner(page, "doc.querySelector('article').children.length")

    page.click("#btn-insert-block-after")
    page.wait_for_selector("#block-picker .picker-card")
    page.click("#block-picker .picker-card")
    page.wait_for_timeout(300)
    after_insert = _inner(page, "doc.querySelector('article').children.length")
    assert after_insert == before + 1

    page.click("#content-frame")
    page.keyboard.press(f"{MOD}+z")
    page.wait_for_timeout(300)
    assert _inner(page, "doc.querySelector('article').children.length") == before

    page.keyboard.press(f"{MOD}+Shift+z")
    page.wait_for_timeout(300)
    assert _inner(page, "doc.querySelector('article').children.length") == after_insert


@needs_chromium
def test_undo_redo_image_insert_via_drop(page: Page, doc_server: str) -> None:
    """Image insert onto a specific editable (the drag-drop path in
    embedImageFile) uses insertAdjacentHTML, NOT execCommand: unlike the
    file-picker path, it does not push a step onto the browser's native
    contenteditable undo stack, which is exactly why this needs OUR stack.
    """
    page.goto(doc_server, wait_until="networkidle")
    _enable_edit_mode(page)

    before = _inner(page, "doc.querySelectorAll('img').length")
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
    page.wait_for_timeout(300)
    assert _inner(page, "doc.querySelectorAll('img').length") == 1

    page.click("#content-frame")
    page.keyboard.press(f"{MOD}+z")
    page.wait_for_timeout(300)
    assert _inner(page, "doc.querySelectorAll('img').length") == 0

    page.keyboard.press(f"{MOD}+Shift+z")
    page.wait_for_timeout(300)
    assert _inner(page, "doc.querySelectorAll('img').length") == 1


@needs_chromium
def test_undo_redo_table_row_add_via_context_menu(page: Page, table_doc_server: str) -> None:
    page.goto(table_doc_server, wait_until="networkidle")
    _enable_edit_mode(page)

    assert _inner(page, "doc.querySelectorAll('table tbody tr').length") == 1

    frame_el = page.frame_locator("#content-frame")
    frame_el.locator("table").first.click(button="right")
    page.wait_for_timeout(150)
    page.click("text=\uff0b Ajouter ligne")
    page.wait_for_timeout(300)
    assert _inner(page, "doc.querySelectorAll('table tbody tr').length") == 2

    page.click("#content-frame")
    page.keyboard.press(f"{MOD}+z")
    page.wait_for_timeout(300)
    assert _inner(page, "doc.querySelectorAll('table tbody tr').length") == 1

    page.keyboard.press(f"{MOD}+Shift+z")
    page.wait_for_timeout(300)
    assert _inner(page, "doc.querySelectorAll('table tbody tr').length") == 2


@needs_chromium
def test_undo_redo_document_block_reorder(page: Page, doc_server: str) -> None:
    page.goto(doc_server, wait_until="networkidle")
    _enable_edit_mode(page)

    order_before = _inner(page, "[...doc.querySelector('article').children].map(c => c.tagName)")
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
    page.wait_for_timeout(300)

    order_after = _inner(page, "[...doc.querySelector('article').children].map(c => c.tagName)")
    assert order_after != order_before, "drag-drop did not reorder the blocks"

    page.click("#content-frame")
    page.keyboard.press(f"{MOD}+z")
    page.wait_for_timeout(300)
    order_undone = _inner(page, "[...doc.querySelector('article').children].map(c => c.tagName)")
    assert order_undone == order_before

    page.keyboard.press(f"{MOD}+Shift+z")
    page.wait_for_timeout(300)
    order_redone = _inner(page, "[...doc.querySelector('article').children].map(c => c.tagName)")
    assert order_redone == order_after
