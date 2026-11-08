"""E2E tests for SPEC-0004: a background autosave must not touch the work in progress.

Bug: ``saveContent()`` in ``editor-save.js`` removed the ``contenteditable``
attribute from every editable element, the focused one included, to serialize
the page. The browser then moved focus to ``<body>`` and the keystrokes typed
after each autosave (800 ms after the last one) were lost.

Real browser tests, same harness pattern as ``test_undo_redo_e2e.py``: a real
``ThreadingHTTPServer`` plus a real headless Chromium via pytest-playwright.
"""

from __future__ import annotations

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
from tests.browser_wait import (
    LATE_SAVE_MS,
    OBSERVE_BOUND_SECONDS,
    apply_save_delay,
    settle,
    wait_for_file,
    wait_for_js,
    wait_until,
)
from tests.conftest import needs_chromium

REPO_ROOT = Path(__file__).resolve().parents[1]
TITLE = "Titre du document"
HEADING = "Introduction"
TITLE_SELECTOR = 'h1[data-editable~="text"]'
HEADING_SELECTOR = 'h2[data-editable~="text"]'
SHORT_BOUND_SECONDS = 2.0
SAVED_DOT_COLOR = "rgb(66, 190, 101)"
DOT_COLOR_EXPRESSION = "() => getComputedStyle(document.getElementById('toolbar-status')).color"
TITLE_EDITABLE_EXPRESSION = (
    "() => { const d = document.getElementById('content-frame').contentDocument;"
    f" const h = d && d.querySelector('{TITLE_SELECTOR}'); return !!h && h.isContentEditable; }}"
)


# Only these tests failed RED with a late save (.implement/US-0084-red.log); the others run prompt only.
LATE_SAVE_TESTS = frozenset(
    {
        "test_typing_after_autosave_stays_in_the_zone",
        "test_leaving_a_zone_keeps_focus_in_the_next_zone",
        "test_several_saves_lose_nothing",
        "test_saved_file_has_no_editing_markers",
    }
)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "save_delay" in metafunc.fixturenames:
        late = metafunc.function.__name__ in LATE_SAVE_TESTS
        delays, ids = ([0, LATE_SAVE_MS], ["prompt", "late"]) if late else ([0], ["prompt"])
        metafunc.parametrize("save_delay", delays, ids=ids, indirect=True)


@pytest.fixture
def save_delay(request: pytest.FixtureRequest, page: Page) -> Iterator[int]:
    """Answer every ``POST /content`` at once (0) or ``LATE_SAVE_MS`` late (BR-011)."""
    delay = int(request.param)
    apply_save_delay(page, delay)
    yield delay
    page.unroute_all(behavior="ignoreErrors")


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
    wait_for_js(page, TITLE_EDITABLE_EXPRESSION, True, what="the title zone editable")


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
def test_typing_after_autosave_stays_in_the_zone(page: Page, served: ServedDoc, save_delay: int) -> None:
    """BT-001: reproduction of BUG-001."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("AAA")
    wait_for_file(page, served.path, f"{TITLE}AAA")
    page.keyboard.type("BBB")

    assert f"{TITLE}AAA" in served.path.read_text(encoding="utf-8")
    assert _zone_text(page, TITLE_SELECTOR) == f"{TITLE}AAABBB"
    assert _is_focused(page, TITLE_SELECTOR)


@needs_chromium
def test_caret_offset_survives_a_save(page: Page, served: ServedDoc, save_delay: int) -> None:
    """BT-010."""
    _open_in_edit_mode(page, served)
    page.frame_locator("#content-frame").locator(TITLE_SELECTOR).click()
    page.keyboard.press("Home")
    for _ in range(5):
        page.keyboard.press("ArrowRight")
    page.keyboard.type("X")
    wait_for_file(page, served.path, "TitreX du document")
    page.keyboard.type("Y")

    assert _zone_text(page, TITLE_SELECTOR) == "TitreXY du document"


@needs_chromium
def test_selection_survives_a_save(page: Page, served: ServedDoc, save_delay: int) -> None:
    """BT-011."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    for _ in range(8):
        page.keyboard.press("Shift+ArrowLeft")
    page.keyboard.type("Z")
    page.keyboard.press("Shift+ArrowLeft")
    wait_for_file(page, served.path, "Titre du Z")
    page.keyboard.type("W")

    assert _zone_text(page, TITLE_SELECTOR) == "Titre du W"


@needs_chromium
def test_leaving_a_zone_keeps_focus_in_the_next_zone(page: Page, served: ServedDoc, save_delay: int) -> None:
    """BT-012."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("A1")
    _click_end(page, HEADING_SELECTOR)
    page.keyboard.type("B1")

    assert _zone_text(page, HEADING_SELECTOR) == f"{HEADING}B1"
    assert _is_focused(page, HEADING_SELECTOR)
    wait_for_file(page, served.path, f"{TITLE}A1")
    assert f"{TITLE}A1" in served.path.read_text(encoding="utf-8")


@needs_chromium
def test_several_saves_lose_nothing(page: Page, served: ServedDoc, save_delay: int) -> None:
    """BT-013."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("1")
    page.wait_for_timeout(1000)  # pacing: spaces the three keystrokes so each one is saved on its own
    page.keyboard.type("2")
    page.wait_for_timeout(1000)  # pacing: same spacing, no result is asserted after it
    page.keyboard.type("3")
    wait_for_file(page, served.path, f"{TITLE}123")

    assert _zone_text(page, TITLE_SELECTOR) == f"{TITLE}123"
    assert f"{TITLE}123" in served.path.read_text(encoding="utf-8")


@needs_chromium
def test_failed_save_keeps_focus(page: Page, served: ServedDoc, save_delay: int) -> None:
    """BT-014."""

    def abort_saves(route: Route) -> None:
        if route.request.method == "POST":
            route.abort()
        else:
            route.continue_()

    failed_saves: list[str] = []
    page.on("requestfailed", lambda request: failed_saves.append(request.url))
    page.route("**/content", abort_saves)
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("Q")
    wait_until(page, lambda: len(failed_saves), lambda count: count >= 1, what="the aborted save attempt")
    page.keyboard.type("R")

    assert _zone_text(page, TITLE_SELECTOR) == f"{TITLE}QR"
    assert _is_focused(page, TITLE_SELECTOR)


@needs_chromium
def test_bounded_observation_reports_the_last_value(page: Page, served: ServedDoc) -> None:
    """BT-014 (SPEC-0014): an awaited save that never lands fails after the bound, with the file content."""
    page.route("**/content", lambda route: route.abort() if route.request.method == "POST" else route.continue_())
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("Q")
    started = time.monotonic()

    with pytest.raises(AssertionError) as raised:
        wait_for_file(page, served.path, f"{TITLE}Q", bound=SHORT_BOUND_SECONDS)

    assert OBSERVE_BOUND_SECONDS == 10.0  # the default bound; a short one keeps this test fast
    assert SHORT_BOUND_SECONDS <= time.monotonic() - started <= SHORT_BOUND_SECONDS + 2
    assert f">{TITLE}</h1>" in str(raised.value)


@needs_chromium
def test_saved_file_has_no_editing_markers(page: Page, served: ServedDoc, save_delay: int) -> None:
    """BT-020: non regression of SPEC-0001/FR-005."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("AAA")
    wait_for_file(page, served.path, f"{TITLE}AAA")
    page.keyboard.type("BBB")

    saved = served.path.read_text(encoding="utf-8")
    assert f"{TITLE}AAA" in saved
    assert "contenteditable" not in saved
    assert "_mcp_" not in saved


@needs_chromium
def test_self_save_does_not_reload_the_preview(page: Page, served: ServedDoc, save_delay: int) -> None:
    """BT-021: non regression of SPEC-0002/FR-008."""
    _open_in_edit_mode(page, served)
    page.evaluate("() => { document.getElementById('content-frame').contentWindow.__probe = 1; }")
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("AAA")
    wait_for_file(page, served.path, f"{TITLE}AAA")
    wait_for_js(page, DOT_COLOR_EXPRESSION, SAVED_DOT_COLOR, what="the status dot saved (the save answered)")
    settle(page)

    assert page.evaluate("() => document.getElementById('content-frame').contentWindow.__probe") == 1


@needs_chromium
def test_status_dot_returns_to_saved(page: Page, served: ServedDoc, save_delay: int) -> None:
    """BT-022: non regression of SPEC-0002/FR-007."""
    _open_in_edit_mode(page, served)
    _click_end(page, TITLE_SELECTOR)
    page.keyboard.type("AAA")
    wait_for_file(page, served.path, f"{TITLE}AAA")
    page.keyboard.type("BBB")
    wait_for_file(page, served.path, f"{TITLE}AAABBB")

    assert wait_for_js(page, DOT_COLOR_EXPRESSION, SAVED_DOT_COLOR, what="the status dot saved") == SAVED_DOT_COLOR
