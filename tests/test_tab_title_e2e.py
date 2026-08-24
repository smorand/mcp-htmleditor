"""Regression test: the browser tab shows the edited document's own <title>.

Bug: the editor shell (``static/editor.html``) has a hardcoded
``<title>HTML Editor</title>``. The actual document being edited is loaded
in a nested iframe (``/content-frame``), whose own ``<title>`` never
propagates to the parent tab on its own (iframe titles never affect the
outer tab). Two different files served on two different ports therefore
showed the exact same generic tab name, making them indistinguishable.

Fix: ``editor.js``'s ``onFrameLoad()`` now copies the iframe document's
``document.title`` onto the shell's own ``document.title`` on every load
(initial load, ``open_file`` switch, external agent rewrite), falling back
to the file name only when the document has no ``<title>``.
"""

from __future__ import annotations

import platform
import socket
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page

from mcp_htmleditor.http_server import start_http_server, stop_http_server


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


def _write_doc(path: Path, title: str, heading: str) -> Path:
    path.write_text(
        "<!DOCTYPE html>\n"
        '<html lang="fr" data-doc-type="document">\n'
        "<head><meta charset=\"UTF-8\"><title>" + title + "</title></head>\n"
        "<body><article data-type=\"document\">"
        '<h1 data-editable="text">' + heading + "</h1></article></body>\n"
        "</html>\n",
        encoding="utf-8",
    )
    return path


def _serve(path: Path) -> tuple[int, str]:
    port = _free_port()
    start_http_server(str(path), port=port)
    base_url = f"http://127.0.0.1:{port}/"
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    else:
        pytest.fail("HTTP server did not start in time")
    return port, base_url


@needs_chromium
def test_tab_title_reflects_document_title_not_filename(page: Page, tmp_path: Path) -> None:
    """The tab title must be the HTML document's own <title>, not the shell's
    hardcoded default and not the on-disk file name."""
    doc = _write_doc(tmp_path / "trame.html", "Rapport Trimestriel EI", "Contenu")
    _port, base_url = _serve(doc)
    try:
        page.goto(base_url, wait_until="networkidle")
        page.wait_for_selector("#content-frame")
        page.wait_for_function("document.title === 'Rapport Trimestriel EI'")
        assert page.title() == "Rapport Trimestriel EI"
        assert page.title() != "HTML Editor"
        assert page.title() != "trame.html"
    finally:
        stop_http_server()


@needs_chromium
def test_tab_title_differs_after_switching_to_a_different_file(page: Page, tmp_path: Path) -> None:
    """Regression for the reported bug: after switching the served file
    (mirrors ``open_file``/reload), the tab must show the NEW document's own
    title, never the previous file's title nor the generic shell default.

    Two independent ports serving two files at once (the real-world report)
    is exercised manually (see report), since the module-level HTTP server
    state only supports one active file per process (by design, see
    skill/README.md "Plusieurs presentations en parallele"). Switching the
    served file within one server covers the same code path: onFrameLoad()
    re-reading doc.title on every iframe load.
    """
    doc_a = _write_doc(tmp_path / "trame.html", "Rapport Q1 2026", "Contenu A")
    _port, base_url = _serve(doc_a)
    try:
        page.goto(base_url, wait_until="networkidle")
        page.wait_for_selector("#content-frame")
        page.wait_for_function("document.title === 'Rapport Q1 2026'")
        assert page.title() == "Rapport Q1 2026"

        doc_b = _write_doc(tmp_path / "autre.html", "Note de synthese", "Contenu B")
        from mcp_htmleditor.state import get_state

        get_state().current_file = str(doc_b)
        page.evaluate("() => { document.getElementById('content-frame').src = '/content-frame?' + Date.now(); }")
        page.wait_for_function("document.title === 'Note de synthese'")
        assert page.title() == "Note de synthese"
    finally:
        stop_http_server()


@needs_chromium
def test_tab_title_falls_back_to_filename_when_document_has_no_title(page: Page, tmp_path: Path) -> None:
    """Falls back to the file name (never the generic shell title) when the
    edited document has no <title> at all."""
    doc = tmp_path / "sans-titre.html"
    doc.write_text(
        "<!DOCTYPE html>\n<html data-doc-type=\"document\"><head><meta charset=\"UTF-8\"></head>"
        "<body><article data-type=\"document\"><p data-editable=\"text\">Sans titre</p></article></body></html>\n",
        encoding="utf-8",
    )
    _port, base_url = _serve(doc)
    try:
        page.goto(base_url, wait_until="networkidle")
        page.wait_for_selector("#content-frame")
        page.wait_for_function("document.title === 'sans-titre.html'")
        assert page.title() == "sans-titre.html"
    finally:
        stop_http_server()
