"""E2E tests for SPEC-0004: a background autosave must not touch the work in progress.

Bug: ``saveContent()`` in ``editor.js`` removed the ``contenteditable``
attribute from every editable element, the focused one included, to serialize
the page. The browser then moved focus to ``<body>`` and the keystrokes typed
after each autosave (800 ms after the last one) were lost.

Real browser tests, same harness pattern as ``test_undo_redo_e2e.py``: a real
``ThreadingHTTPServer`` plus a real headless Chromium via pytest-playwright.
"""

from __future__ import annotations

import platform
import socket
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route

from mcp_htmleditor import config as config_module
from mcp_htmleditor import templates as templates_module
from mcp_htmleditor.http_server import start_http_server, stop_http_server

REPO_ROOT = Path(__file__).resolve().parents[1]
TITLE = "Titre du document"
HEADING = "Introduction"
SAVE_WAIT_MS = 1500  # > the 800 ms typing debounce plus the POST round trip
TITLE_SELECTOR = 'h1[data-editable~="text"]'
HEADING_SELECTOR = 'h2[data-editable~="text"]'
SAVED_DOT_COLOR = "rgb(66, 190, 101)"


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


@dataclass(frozen=True)
class ServedDoc:
    path: Path
    url: str


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_state: None) -> Iterator[ServedDoc]:
    """Serve a copy of the 'doc' bootstrap and yield its path on disk and its editor URL."""
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", str(REPO_ROOT / "templates"))
    config_module.reset_settings_cache()
    doc = tmp_path / "doc.html"
    doc.write_text(templates_module.template_path("doc").read_text(encoding="utf-8"), encoding="utf-8")
    port = _free_port()
    start_http_server(str(doc), port=port)
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    else:
        pytest.fail("HTTP server did not start in time")
    try:
        yield ServedDoc(path=doc, url=f"http://127.0.0.1:{port}/")
    finally:
        stop_http_server()


def _open_in_edit_mode(page: Page, served: ServedDoc) -> None:
    page.goto(served.url)
    page.wait_for_function(
        "() => { const d = document.getElementById('content-frame').contentDocument;"
        " return d && d.querySelector('h1'); }"
    )
    page.click("#edit-mode-btn")
    page.wait_for_timeout(150)


def _frame_eval(page: Page, body: str) -> object:
    """Evaluate ``body`` with ``doc`` bound to the iframe document."""
    return page.evaluate(f"() => {{ const doc = document.getElementById('content-frame').contentDocument; {body} }}")


def _zone_text(page: Page, selector: str) -> str:
    """Text of an editable zone, without the editor's drag handle glyph."""
    text = _frame_eval(
        page,
        f"const c = doc.querySelector('{selector}').cloneNode(true);"
        " c.querySelectorAll('._mcp_drag_handle').forEach(n => n.remove());"
        " return c.textContent;",
    )
    return str(text)


def _is_focused(page: Page, selector: str) -> bool:
    return bool(_frame_eval(page, f"return doc.activeElement === doc.querySelector('{selector}');"))


def _click_end(page: Page, selector: str) -> None:
    page.frame_locator("#content-frame").locator(selector).click()
    page.keyboard.press("End")


@needs_chromium
def test_typing_after_autosave_stays_in_the_zone(page: Page, served: ServedDoc) -> None:
    """BT-001: reproduction of BUG-001."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("AAA")
    page.wait_for_timeout(SAVE_WAIT_MS)
    page.keyboard.type("BBB")

    assert f"{TITLE}AAA" in served.path.read_text(encoding="utf-8")
    assert _zone_text(page, TITLE_SELECTOR) == f"{TITLE}AAABBB"
    assert _is_focused(page, TITLE_SELECTOR)


@needs_chromium
def test_caret_offset_survives_a_save(page: Page, served: ServedDoc) -> None:
    """BT-010."""
    _open_in_edit_mode(page, served)
    page.frame_locator("#content-frame").locator(TITLE_SELECTOR).click()
    page.keyboard.press("Home")
    for _ in range(5):
        page.keyboard.press("ArrowRight")
    page.keyboard.type("X")
    page.wait_for_timeout(SAVE_WAIT_MS)
    page.keyboard.type("Y")

    assert _zone_text(page, TITLE_SELECTOR) == "TitreXY du document"


@needs_chromium
def test_selection_survives_a_save(page: Page, served: ServedDoc) -> None:
    """BT-011."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    for _ in range(8):
        page.keyboard.press("Shift+ArrowLeft")
    page.keyboard.type("Z")
    page.keyboard.press("Shift+ArrowLeft")
    page.wait_for_timeout(SAVE_WAIT_MS)
    page.keyboard.type("W")

    assert _zone_text(page, TITLE_SELECTOR) == "Titre du W"


@needs_chromium
def test_leaving_a_zone_keeps_focus_in_the_next_zone(page: Page, served: ServedDoc) -> None:
    """BT-012."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("A1")
    _click_end(page, HEADING_SELECTOR)
    page.keyboard.type("B1")

    assert _zone_text(page, HEADING_SELECTOR) == f"{HEADING}B1"
    assert _is_focused(page, HEADING_SELECTOR)
    page.wait_for_timeout(SAVE_WAIT_MS)
    assert f"{TITLE}A1" in served.path.read_text(encoding="utf-8")


@needs_chromium
def test_several_saves_lose_nothing(page: Page, served: ServedDoc) -> None:
    """BT-013."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("1")
    page.wait_for_timeout(1000)
    page.keyboard.type("2")
    page.wait_for_timeout(1000)
    page.keyboard.type("3")
    page.wait_for_timeout(SAVE_WAIT_MS)

    assert _zone_text(page, TITLE_SELECTOR) == f"{TITLE}123"
    assert f"{TITLE}123" in served.path.read_text(encoding="utf-8")


@needs_chromium
def test_failed_save_keeps_focus(page: Page, served: ServedDoc) -> None:
    """BT-014."""

    def abort_saves(route: Route) -> None:
        if route.request.method == "POST":
            route.abort()
        else:
            route.continue_()

    page.route("**/content", abort_saves)
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("Q")
    page.wait_for_timeout(SAVE_WAIT_MS)
    page.keyboard.type("R")

    assert _zone_text(page, TITLE_SELECTOR) == f"{TITLE}QR"
    assert _is_focused(page, TITLE_SELECTOR)


@needs_chromium
def test_saved_file_has_no_editing_markers(page: Page, served: ServedDoc) -> None:
    """BT-020: non regression of SPEC-0001/FR-005."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("AAA")
    page.wait_for_timeout(SAVE_WAIT_MS)
    page.keyboard.type("BBB")

    saved = served.path.read_text(encoding="utf-8")
    assert f"{TITLE}AAA" in saved
    assert "contenteditable" not in saved
    assert "_mcp_" not in saved


@needs_chromium
def test_self_save_does_not_reload_the_preview(page: Page, served: ServedDoc) -> None:
    """BT-021: non regression of SPEC-0002/FR-008."""
    _open_in_edit_mode(page, served)
    page.evaluate("() => { document.getElementById('content-frame').contentWindow.__probe = 1; }")
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("AAA")
    page.wait_for_timeout(2500)

    assert page.evaluate("() => document.getElementById('content-frame').contentWindow.__probe") == 1


@needs_chromium
def test_status_dot_returns_to_saved(page: Page, served: ServedDoc) -> None:
    """BT-022: non regression of SPEC-0002/FR-007."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("AAA")
    page.wait_for_timeout(SAVE_WAIT_MS)
    page.keyboard.type("BBB")
    page.wait_for_timeout(SAVE_WAIT_MS)

    color = page.evaluate("() => getComputedStyle(document.getElementById('toolbar-status')).color")
    assert color == SAVED_DOT_COLOR
