"""The editor shell and static assets must never be cached by the browser.

This is a live-editing tool: editor.html/editor.js/editor.css change between
sessions (bug fixes, new features) and the served document changes on every
save. Without an explicit no-store, an already-open tab (or even a plain
reload, since no ETag/Last-Modified validators are sent either) can keep
running stale JavaScript after a fix has been shipped and reinstalled - which
is exactly what broke the fullscreen fix for a real user in the field.
"""

from __future__ import annotations

import socket
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from mcp_htmleditor.http_server import start_http_server, stop_http_server


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def running_server(html_file: Path, reset_state: None) -> Iterator[str]:
    """Serve `html_file` over a real HTTP server and yield its base URL."""
    port = _free_port()
    start_http_server(str(html_file), port=port)
    base_url = f"http://127.0.0.1:{port}"
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


def _cache_control(url: str) -> str | None:
    with urllib.request.urlopen(url) as response:  # noqa: S310 - fixed http://127.0.0.1 test URL
        return response.headers.get("Cache-Control")


def test_editor_shell_is_never_cached(running_server: str) -> None:
    """GET / (editor.html) is served with Cache-Control: no-store."""
    cache_control = _cache_control(running_server + "/")
    assert cache_control is not None
    assert "no-store" in cache_control


def test_static_js_is_never_cached(running_server: str) -> None:
    """GET /static/editor.js is served with Cache-Control: no-store."""
    cache_control = _cache_control(running_server + "/static/editor.js")
    assert cache_control is not None
    assert "no-store" in cache_control


def test_content_frame_document_is_never_cached(running_server: str) -> None:
    """GET /content-frame (the served deck) is served with Cache-Control: no-store."""
    cache_control = _cache_control(running_server + "/content-frame")
    assert cache_control is not None
    assert "no-store" in cache_control
