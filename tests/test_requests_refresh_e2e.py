"""US-0056 (SPEC-0010): the side list follows the agent through the existing status poll.

Real browser tests: a real server polled every 250 ms, a real headless Chromium, and the agent side is the
in process MCP client (``call_tool``). The request log (``page.on("request")``) proves the list is fetched
only when the revision differs.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, expect

from mcp_htmleditor import config
from mcp_htmleditor.request_service import RequestService
from mcp_htmleditor.request_store import RequestStore
from mcp_htmleditor.state import get_state
from tests.browser_wait import settle, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import call_tool, deck_ei, write_deck

POLL_MS = 250
TITLE = "Shorten the title"


def _queue(deck: ServedDeck, text: str = TITLE, slide: str = "slide-3") -> None:
    RequestService(RequestStore(config.state_dir())).queue(deck.path, text, slide)


def _open(page: Page, deck: ServedDeck, expected_heading: str) -> list[str]:
    """Open the editor with a 250 ms poll; return the live log of ``METHOD /path`` API requests."""
    get_state().poll_interval = POLL_MS
    log: list[str] = []

    def record(request: object) -> None:
        url = request.url  # type: ignore[attr-defined]
        path = "/" + url.split("/", 3)[3].split("?")[0]
        if path in ("/status", "/requests", "/requests/delete"):
            log.append(f"{request.method} {path}")  # type: ignore[attr-defined]

    page.on("request", record)
    page.goto(f"http://127.0.0.1:{deck.port}/")
    expect(page.locator("#requests-heading")).to_have_text(expected_heading, timeout=5000)
    return log


def _await_first_poll(page: Page, log: list[str]) -> None:
    """Wait until the editor has polled ``GET /status`` at least once."""
    wait_until(page, lambda: log.count("GET /status"), lambda count: count >= 1, what="the first GET /status")


def _complete(deck: ServedDeck, status: str, reason: str | None = None) -> None:
    arguments = {"file": str(deck.path), "id": "R-0001", "status": status}
    if reason is not None:
        arguments["reason"] = reason
    ok, data = call_tool("complete_request", **arguments)
    assert ok, data
    assert data == {"ok": True, "id": "R-0001", "status": status}


@needs_chromium
def test_e2e_003_complete_as_done(page: Page, served_deck: ServedDeck) -> None:
    _queue(served_deck)
    _open(page, served_deck, "Requests (1)")
    expect(page.locator("#requests-list li .request-text")).to_have_text(f"R-0001 pending slide-3 {TITLE}")

    _complete(served_deck, "done")

    expect(page.locator("#requests-list li .request-text")).to_have_text(f"R-0001 done slide-3 {TITLE}", timeout=2000)
    expect(page.locator("#requests-heading")).to_have_text("Requests (0)", timeout=2000)


@needs_chromium
def test_e2e_004_complete_as_skipped(page: Page, served_deck: ServedDeck) -> None:
    _queue(served_deck)
    _open(page, served_deck, "Requests (1)")

    _complete(served_deck, "skipped", "Title is already short")

    expect(page.locator("#requests-list li .request-text")).to_have_text(
        f"R-0001 skipped slide-3 {TITLE} Title is already short", timeout=2000
    )


@needs_chromium
def test_e2e_027_editor_refresh_without_reload(page: Page, served_deck: ServedDeck) -> None:
    _queue(served_deck)
    _open(page, served_deck, "Requests (1)")
    url = page.url
    page.evaluate("() => { window.__marker = 'kept'; }")

    _complete(served_deck, "done")

    expect(page.locator("#requests-list li .request-text")).to_contain_text("R-0001 done", timeout=2000)
    assert page.url == url
    assert page.evaluate("() => window.__marker") == "kept"


@needs_chromium
def test_ut_e01_no_fetch_while_nothing_changes(page: Page, served_deck: ServedDeck) -> None:
    _queue(served_deck)
    log = _open(page, served_deck, "Requests (1)")
    _await_first_poll(page, log)
    status_before = log.count("GET /status")
    requests_before = log.count("GET /requests")

    page.wait_for_timeout(2600)  # pacing: measurement window, the polling period is what is counted

    assert log.count("GET /status") - status_before >= 10
    assert log.count("GET /requests") == requests_before


@needs_chromium
def test_ut_e02_no_extra_fetch_after_the_users_own_action(page: Page, served_deck: ServedDeck) -> None:
    log = _open(page, served_deck, "Requests (0)")
    _await_first_poll(page, log)
    page.click("#ask-ai-btn")
    page.fill("#ask-ai-text", TITLE)
    mark = len(log)

    page.click("#ask-ai-queue")
    expect(page.locator("#requests-heading")).to_have_text("Requests (1)", timeout=2000)
    page.wait_for_timeout(3 * POLL_MS + 400)  # pacing: measurement window, three polling periods

    since = log[mark:]
    assert since.count("POST /requests") == 1
    assert since.count("GET /requests") == 1
    assert since.index("GET /requests") > since.index("POST /requests")


@needs_chromium
def test_agent_change_while_the_page_holds_an_older_revision_is_picked_up_once(
    page: Page, served_deck: ServedDeck
) -> None:
    """After the agent completes, exactly one extra GET /requests, then silence again."""
    _queue(served_deck)
    log = _open(page, served_deck, "Requests (1)")
    _await_first_poll(page, log)
    mark = len(log)

    _complete(served_deck, "done")
    expect(page.locator("#requests-heading")).to_have_text("Requests (0)", timeout=2000)
    wait_until(page, lambda: log[mark:].count("GET /requests"), lambda count: count >= 1, what="the GET /requests")
    settle(page)

    assert log[mark:].count("GET /requests") == 1


@needs_chromium
def test_switching_the_served_file_to_a_lower_revision_refreshes_the_list(
    page: Page, served_deck: ServedDeck, tmp_path: Path
) -> None:
    """open_file keeps the page (and its held revision); deck B sits at a lower revision than deck A."""
    _queue(served_deck, "Alpha one")
    _queue(served_deck, "Alpha two")
    _open(page, served_deck, "Requests (2)")
    other = tmp_path / "other"
    other.mkdir()
    deck_b = Path(write_deck(other / "b.html", deck_ei()))
    _queue(ServedDeck(path=deck_b, port=served_deck.port), "Bravo only")

    ok, data = call_tool("open_file", file=str(deck_b))
    assert ok, data

    expect(page.locator("#requests-heading")).to_have_text("Requests (1)", timeout=2 * POLL_MS + 1500)
    expect(page.locator("#requests-list li .request-text")).to_have_text("R-0001 pending slide-3 Bravo only")
