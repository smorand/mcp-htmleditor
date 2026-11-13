"""DT-004 and DT-012 (SPEC-0012): editor scripts are served uncached, ordered, valid and unique."""

from __future__ import annotations

import platform
import re
import shutil
import socket
import subprocess
import time
import urllib.request
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page

from mcp_htmleditor.http_server import start_http_server, stop_http_server

STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "mcp_htmleditor" / "static"

EXPECTED_SCRIPT_ORDER = [
    "slide-layouts.js",
    "doc-blocks.js",
    "editor-undo.js",
    "editor-edit.js",
    "editor-format.js",
    "editor-menus.js",
    "editor-save.js",
    "editor-slides.js",
    "editor-blocks.js",
    "editor-drag.js",
    "editor-width.js",
    "editor-requests.js",
    "editor-notes.js",
    "editor.js",
]
EDITOR_SCRIPTS = [name for name in EXPECTED_SCRIPT_ORDER if name.startswith("editor")]
FUNCTION_DEFINITION = re.compile(r"^(?:async )?function ([A-Za-z0-9_$]+)\(", re.MULTILINE)
SCRIPT_TAG = re.compile(r'<script\s+src="/static/([^"]+)"\s*></script>')


def _chromium_cache_dir() -> Path:
    home = Path.home()
    if platform.system() == "Darwin":
        return home / "Library" / "Caches" / "ms-playwright"
    return home / ".cache" / "ms-playwright"


needs_chromium = pytest.mark.skipif(
    not any(_chromium_cache_dir().glob("chromium-*")),
    reason="Playwright Chromium is not installed; run `make sync`",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def running_server(html_file: Path, reset_state: None) -> Iterator[str]:
    """Serve `html_file` over a real HTTP server and yield its base URL."""
    port = _free_port()
    start_http_server(str(html_file), port=port)
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    else:
        pytest.fail("HTTP server did not start in time")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        stop_http_server()


@pytest.mark.parametrize("script", EDITOR_SCRIPTS)
def test_editor_script_is_served_uncached(running_server: str, script: str) -> None:
    """DT-004: every editor*.js answers 200 with Cache-Control: no-store."""
    with urllib.request.urlopen(f"{running_server}/static/{script}") as response:  # noqa: S310 - local test URL
        assert response.status == 200
        assert "no-store" in (response.headers.get("Cache-Control") or "")


def test_editor_html_lists_scripts_in_order(running_server: str) -> None:
    """DT-012: the served editor page loads the thirteen scripts in the DR-006 order."""
    with urllib.request.urlopen(f"{running_server}/") as response:  # noqa: S310 - local test URL
        html = response.read().decode("utf-8")
    assert SCRIPT_TAG.findall(html) == EXPECTED_SCRIPT_ORDER


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize("script", sorted(path.name for path in STATIC_DIR.glob("*.js")))
def test_static_script_passes_node_check(script: str) -> None:
    """DT-012: every static script is syntactically valid."""
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["node", "--check", str(STATIC_DIR / script)],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_no_global_function_is_defined_twice() -> None:
    """DT-012: no top level function name is defined in two static scripts (or twice in one)."""
    names: Counter[str] = Counter()
    for path in STATIC_DIR.glob("*.js"):
        names.update(FUNCTION_DEFINITION.findall(path.read_text(encoding="utf-8")))
    assert {name: count for name, count in names.items() if count > 1} == {}


@needs_chromium
def test_editor_page_loads_without_page_error(running_server: str, page: Page) -> None:
    """DT-012: a real Chromium loads the editor page and records no page error."""
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{running_server}/")
    page.wait_for_function("typeof performUndo === 'function'", timeout=10000)
    assert errors == []
