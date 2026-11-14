"""US-0055 (SPEC-0010): the Ask AI panel and the requests side list of the editor.

Real browser tests: a real ``ThreadingHTTPServer`` plus a real headless Chromium. The requests are
read back through ``RequestService`` (the same service the MCP ``list_requests`` tool calls).
"""

from __future__ import annotations

import html.parser
import shutil
import subprocess
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page

from mcp_htmleditor import config
from mcp_htmleditor.request_service import RequestService
from mcp_htmleditor.request_store import RequestStore
from tests.browser_wait import wait_until
from tests.conftest import ServedDeck, needs_chromium

STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "mcp_htmleditor" / "static"
SCRIPT = STATIC_DIR / "editor-requests.js"
EXPECTED_ORDER = [
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
XSS_TEXT = "<img src=x onerror=window.__xss=1>"


def _service() -> RequestService:
    return RequestService(RequestStore(config.state_dir()))


def _stored(deck: ServedDeck) -> list[object]:
    return list(_service().list_requests(deck.path))


def _open(page: Page, deck: ServedDeck) -> None:
    page.goto(f"http://127.0.0.1:{deck.port}/")
    page.wait_for_function(
        "() => { const d = document.getElementById('content-frame').contentDocument;"
        " return d && d.querySelector('[data-type=\"slide\"]') && document.getElementById('requests-heading')"
        " && document.getElementById('requests-heading').textContent.startsWith('Requests ('); }"
    )


def _select_slide(page: Page, index: int) -> None:
    """Show slide ``index`` and click its title, as the person does."""
    page.evaluate(f"() => document.getElementById('content-frame').contentWindow.goToSlide({index})")
    page.frame_locator("#content-frame").locator(f"#slide-{index} .slide-h1").click()


def _open_panel(page: Page) -> None:
    page.click("#ask-ai-btn")
    page.wait_for_selector("#ask-ai-panel", state="visible")


def _queue(page: Page, text: str, message: str | None = None) -> str:
    """Type ``text`` in the open panel, queue it and return the panel message."""
    page.fill("#ask-ai-text", text)
    page.click("#ask-ai-queue")
    if message is None:
        page.wait_for_function(
            "() => document.getElementById('ask-ai-message').textContent !== ''"
            " && !document.getElementById('ask-ai-queue').disabled"
        )
    return page.text_content("#ask-ai-message") or ""


def _wait_heading(page: Page, text: str) -> None:
    page.wait_for_function("(t) => document.getElementById('requests-heading').textContent === t", arg=text)


def _lines(page: Page) -> list[str]:
    return [
        " ".join((node.text_content() or "").split())
        for node in page.query_selector_all("#requests-list li .request-text")
    ]


@needs_chromium
def test_e2e_001_queue_a_request(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    _select_slide(page, 3)
    assert not page.is_visible("#ask-ai-panel")
    _open_panel(page)
    assert page.text_content("#ask-ai-slide") == "Slide: slide-3"
    assert page.get_attribute("label[for=ask-ai-text]", "for") == "ask-ai-text"
    assert page.text_content("label[for=ask-ai-text]") == "Describe the change"
    assert page.text_content("#ask-ai-queue") == "Queue request"

    assert _queue(page, "Shorten the title") == "Request R-0001 queued"

    assert page.input_value("#ask-ai-text") == ""
    _wait_heading(page, "Requests (1)")
    assert _lines(page) == ["R-0001 pending slide-3 Shorten the title"]
    assert page.text_content("#requests-list li[data-request-id='R-0001'] button.request-delete") == "Delete"
    assert page.get_attribute("#ask-ai-message", "role") == "status"


@needs_chromium
def test_current_slide_defaults_to_the_first_slide(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    _open_panel(page)
    assert page.text_content("#ask-ai-slide") == "Slide: slide-0"


@needs_chromium
def test_opening_the_panel_does_not_autofocus_the_text(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    _open_panel(page)
    assert page.evaluate("() => document.activeElement && document.activeElement.id") != "ask-ai-text"
    page.click("#ask-ai-btn")
    assert not page.is_visible("#ask-ai-panel")


@needs_chromium
def test_slide_none_when_the_file_has_no_slide(
    page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    folder = tmp_path / "plain"
    folder.mkdir()
    path = folder / "plain.html"
    path.write_text("<!DOCTYPE html><html><body><p>x</p></body></html>", encoding="utf-8")
    deck = serve_deck(path)
    page.goto(f"http://127.0.0.1:{deck.port}/")
    page.wait_for_selector("#requests-heading", state="attached")
    _open_panel(page)
    assert page.text_content("#ask-ai-slide") == "Slide: none"
    assert _queue(page, "Say hello") == "Request R-0001 queued"
    _wait_heading(page, "Requests (1)")
    assert _lines(page) == ["R-0001 pending - Say hello"]
    assert _service().list_requests(path)[0].slide is None


@needs_chromium
@pytest.mark.parametrize("blank", ["", "   "])
def test_e2e_008_empty_request(page: Page, served_deck: ServedDeck, blank: str) -> None:
    _open(page, served_deck)
    _open_panel(page)
    assert _queue(page, blank) == "Write a request first"
    assert _stored(served_deck) == []


@needs_chromium
def test_e2e_009_too_long(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    _open_panel(page)
    message = _queue(page, "a" * 4001)
    assert message == "Request too long (max 4000 characters)"
    assert page.input_value("#ask-ai-text") == "a" * 4001
    assert _stored(served_deck) == []


@needs_chromium
def test_e2e_010_too_many_pending(page: Page, served_deck: ServedDeck) -> None:
    service = _service()
    for index in range(49):
        service.queue(served_deck.path, f"seed {index}", None)
    _open(page, served_deck)
    _wait_heading(page, "Requests (49)")
    _open_panel(page)
    assert _queue(page, "the fiftieth") == "Request R-0050 queued"
    _wait_heading(page, "Requests (50)")
    assert _queue(page, "one more") == "Too many pending requests (max 50)"
    assert page.input_value("#ask-ai-text") == "one more"
    assert page.text_content("#requests-heading") == "Requests (50)"
    assert len(page.query_selector_all("#requests-list li")) == 50
    assert len(_stored(served_deck)) == 50


@needs_chromium
def test_e2e_020_storage_failure(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    _open_panel(page)
    store = RequestStore(config.state_dir())
    directory = store.record_dir(served_deck.path)
    directory.parent.mkdir(parents=True, exist_ok=True)
    directory.write_text("a regular file where the directory belongs", encoding="utf-8")
    with pytest.raises(OSError) as expected:
        directory.mkdir(parents=True, exist_ok=True)
    assert str(expected.value)

    message = _queue(page, "x")

    assert message == f"Could not queue the request: {expected.value}"
    assert page.input_value("#ask-ai-text") == "x"
    directory.unlink()
    assert _stored(served_deck) == []


@needs_chromium
def test_e2e_021_ids_are_never_reused(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck)
    _open_panel(page)
    assert _queue(page, "first") == "Request R-0001 queued"
    _wait_heading(page, "Requests (1)")
    assert _queue(page, "second") == "Request R-0002 queued"
    _wait_heading(page, "Requests (2)")

    page.click("#requests-toggle")
    page.click("#requests-list li[data-request-id='R-0002'] button.request-delete")
    _wait_heading(page, "Requests (1)")
    assert _lines(page) == ["R-0001 pending slide-0 first"]

    assert _queue(page, "third") == "Request R-0003 queued"
    _wait_heading(page, "Requests (2)")
    assert [r.id for r in _service().list_requests(served_deck.path)] == ["R-0001", "R-0003"]  # type: ignore[attr-defined]


@needs_chromium
def test_delete_failure_shows_the_server_error_and_keeps_the_request(page: Page, served_deck: ServedDeck) -> None:
    _service().queue(served_deck.path, "keep me", "slide-1")
    _open(page, served_deck)
    _wait_heading(page, "Requests (1)")
    page.route(
        "**/requests/delete",
        lambda route: route.fulfill(status=200, content_type="application/json", body='{"ok": false, "error": "boom"}'),
    )
    page.click("#requests-toggle")
    page.click("#requests-list li[data-request-id='R-0001'] button.request-delete")
    page.wait_for_function("() => document.getElementById('ask-ai-message').textContent !== ''")
    assert page.text_content("#ask-ai-message") == "Could not delete the request: boom"
    assert page.is_visible("#ask-ai-panel")
    assert _lines(page) == ["R-0001 pending slide-1 keep me"]


@needs_chromium
def test_e2e_022_accents_and_line_breaks(page: Page, served_deck: ServedDeck) -> None:
    text = "Mettre « Résumé » en gras\npuis centrer"
    _open(page, served_deck)
    _open_panel(page)
    assert _queue(page, text) == "Request R-0001 queued"
    (request,) = _service().list_requests(served_deck.path)
    assert request.instruction == text
    assert request.title == "Mettre « Résumé » en gras puis centrer"


@needs_chromium
def test_e2e_026_boundary_sizes(page: Page, served_deck: ServedDeck) -> None:
    service = _service()
    for index in range(49):
        service.queue(served_deck.path, f"seed {index}", None)
    _open(page, served_deck)
    _wait_heading(page, "Requests (49)")
    _open_panel(page)
    assert _queue(page, "b" * 4000) == "Request R-0050 queued"
    _wait_heading(page, "Requests (50)")
    assert _queue(page, "c" * 4000) == "Too many pending requests (max 50)"
    assert len(_stored(served_deck)) == 50


@needs_chromium
def test_ut_d02_agent_text_is_data(page: Page, served_deck: ServedDeck) -> None:
    _service().queue(served_deck.path, XSS_TEXT, None)
    _open(page, served_deck)
    _wait_heading(page, "Requests (1)")
    assert _lines(page) == [f"R-0001 pending - {XSS_TEXT}"]
    assert page.evaluate("() => typeof window.__xss") == "undefined"
    assert page.query_selector("#requests-list img") is None


@needs_chromium
def test_skipped_request_shows_its_reason(page: Page, served_deck: ServedDeck) -> None:
    service = _service()
    service.queue(served_deck.path, "Do it", "slide-2")
    service.complete(served_deck.path, "R-0001", "skipped", "Not possible")
    _open(page, served_deck)
    page.click("#requests-toggle")
    page.wait_for_selector("#requests-list li")
    assert _lines(page) == ["R-0001 skipped slide-2 Do it Not possible"]
    assert page.text_content("#requests-heading") == "Requests (0)"


@needs_chromium
def test_requests_toggle_opens_and_closes_the_side_list(page: Page, served_deck: ServedDeck) -> None:
    """SPEC-0022 FR-1: closed by default, aria in sync, label carries the pending count, frame takes the width."""
    _service().queue(served_deck.path, "one", None)
    _service().queue(served_deck.path, "two", None)
    page.set_viewport_size({"width": 1600, "height": 900})
    _open(page, served_deck)
    _wait_heading(page, "Requests (2)")
    assert page.text_content("#requests-badge") == "(2)"
    assert page.get_attribute("#requests-toggle", "aria-label") == "Requests (2)"
    assert page.inner_text("#requests-toggle").strip() == "(2)"
    assert page.get_attribute("#requests-toggle", "aria-controls") == "requests-side"
    assert page.get_attribute("#requests-toggle", "aria-expanded") == "false"
    assert not page.is_visible("#requests-side")
    assert page.evaluate("() => document.getElementById('content-frame').getBoundingClientRect().width") == 1600

    page.click("#requests-toggle")
    assert page.is_visible("#requests-side")
    assert page.get_attribute("#requests-toggle", "aria-expanded") == "true"
    assert page.evaluate("() => document.getElementById('content-frame').getBoundingClientRect().width") == 1300

    page.click("#requests-toggle")
    assert not page.is_visible("#requests-side")
    assert page.get_attribute("#requests-toggle", "aria-expanded") == "false"

    page.click("#ask-ai-btn")
    page.fill("#ask-ai-text", "three")
    page.click("#ask-ai-queue")
    page.wait_for_function("() => document.getElementById('requests-badge').textContent === '(3)'")


@needs_chromium
def test_side_list_is_hidden_in_fullscreen_and_iframe_is_narrowed(page: Page, served_deck: ServedDeck) -> None:
    page.set_viewport_size({"width": 1600, "height": 900})
    _open(page, served_deck)
    page.click("#requests-toggle")
    assert page.is_visible("#requests-side")
    assert page.evaluate("() => document.getElementById('content-frame').getBoundingClientRect().width") == 1300
    page.click("#present-btn")
    wait_until(
        page, lambda: page.is_visible("#requests-side"), lambda visible: not visible, what="#requests-side hidden"
    )
    assert not page.is_visible("#requests-side")
    page.keyboard.press("Escape")
    wait_until(page, lambda: page.is_visible("#requests-side"), lambda visible: visible, what="#requests-side visible")
    assert page.is_visible("#requests-side")


def test_ut_d01_script_syntax_and_size() -> None:
    assert len(SCRIPT.read_text(encoding="utf-8").splitlines()) <= 500
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["node", "--check", str(SCRIPT)],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


class _ScriptCollector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        source = dict(attrs).get("src")
        if tag == "script" and source:
            self.sources.append(source.rsplit("/", 1)[-1])


def test_ut_d03_script_order(served_deck: ServedDeck) -> None:
    base = f"http://127.0.0.1:{served_deck.port}"
    with urllib.request.urlopen(f"{base}/") as response:  # noqa: S310 - local test URL
        parser = _ScriptCollector()
        parser.feed(response.read().decode("utf-8"))
    assert parser.sources == EXPECTED_ORDER
    with urllib.request.urlopen(f"{base}/static/editor-requests.js") as response:  # noqa: S310 - local test URL
        assert response.status == 200
        assert "no-store" in (response.headers.get("Cache-Control") or "")
