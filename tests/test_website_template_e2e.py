"""E2E — 'website' template: no export buttons, tab switch works, doc block UI reused.

Real browser test (same ThreadingHTTPServer + headless Chromium pattern as
test_fullscreen_e2e.py / test_undo_redo_e2e.py): a unit test cannot see what
CSS `display` editor.js actually computed on the export buttons, or whether a
real click event on a `.site-tab` button reaches its `onclick` handler
without being intercepted by contenteditable focus handling.
"""

from __future__ import annotations

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


def _chromium_installed() -> bool:
    import platform

    home = Path.home()
    cache = (
        home / "Library" / "Caches" / "ms-playwright"
        if platform.system() == "Darwin"
        else home / ".cache" / "ms-playwright"
    )
    return any(cache.glob("chromium-*"))


needs_chromium = pytest.mark.skipif(
    not _chromium_installed(), reason="Playwright Chromium is not installed; run `make sync`"
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def website_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_state: None) -> Iterator[str]:
    """Serve the real 'website' bootstrap over HTTP and yield its base URL."""
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", str(REPO_ROOT / "templates"))
    config_module.reset_settings_cache()

    src = templates_module.template_path("website")
    site = tmp_path / "site.html"
    site.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    port = _free_port()
    start_http_server(str(site), port=port)
    base_url = f"http://127.0.0.1:{port}/"

    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    else:
        pytest.fail("HTTP server did not start in time")

    try:
        yield base_url
    finally:
        stop_http_server()


def _inner(page: Page, js_expression: str) -> object:
    return page.evaluate(
        f"() => {{ const doc = document.getElementById('content-frame').contentDocument; return ({js_expression}); }}"
    )


@needs_chromium
def test_website_has_no_export_buttons_but_keeps_doc_block_ui(page: Page, website_server: str) -> None:
    """A website gets the document block/drag UI but neither PPTX nor DOCX export."""
    page.goto(website_server, wait_until="networkidle")
    page.wait_for_selector("#content-frame")

    assert page.eval_on_selector("#export-pptx-btn", "el => getComputedStyle(el).display") == "none"
    assert page.eval_on_selector("#export-docx-btn", "el => getComputedStyle(el).display") == "none"

    page.click("#edit-mode-btn")
    page.wait_for_timeout(200)

    assert page.eval_on_selector("#export-pptx-btn", "el => getComputedStyle(el).display") == "none"
    assert page.eval_on_selector("#export-docx-btn", "el => getComputedStyle(el).display") == "none"
    assert page.eval_on_selector("#toolbar-doc-actions", "el => getComputedStyle(el).display") != "none"


@needs_chromium
def test_website_tabs_switch_on_click_in_and_out_of_edit_mode(page: Page, website_server: str) -> None:
    """Clicking a .site-tab switches the active panel, in and out of edit mode.

    The click bubbles from the nested ``<span data-editable>`` up to the
    ``<button onclick=...>`` (normal DOM event bubbling), so the tab always
    switches. In edit mode the browser may ALSO drop an editing caret into
    the clicked span, same as clicking any other ``[data-editable]`` text —
    that is expected, not a defect this template needs to suppress.
    """
    page.goto(website_server, wait_until="networkidle")
    page.wait_for_selector("#content-frame")

    def active_panel() -> object:
        return _inner(page, "doc.querySelector('.site-tabpanel.active').id")

    frame = page.frame_locator("#content-frame")

    assert active_panel() == "tab-1"
    frame.locator(".site-tab").nth(1).click()
    assert active_panel() == "tab-2"

    page.click("#edit-mode-btn")
    page.wait_for_timeout(200)
    frame.locator(".site-tab").nth(2).click()
    assert active_panel() == "tab-3"
