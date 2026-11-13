"""US-0058 (SPEC-0010): the editor lists the AI suggestions and ``Apply`` turns one into a pending request.

Browser tests drive a real server polled every 250 ms and a headless Chromium; the agent side is the in process
MCP client. Unit tests drive ``RequestService`` and the HTTP route with ``http.client``.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page, Route, expect

from mcp_htmleditor import config
from mcp_htmleditor.request_service import RequestError, RequestService
from mcp_htmleditor.request_store import RequestStore
from mcp_htmleditor.state import get_state
from tests.browser_wait import settle, wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import call_tool, run_cli
from tests.test_requests_core import EVIL_ORIGIN, call, make_deck, post
from tests.test_review_write import S1_LINE, S2_LINE, s2, suggestion

POLL_MS = 250
INSTRUCTION = "Tighten the agenda. Cut to 5 lines"
XSS_TEXT = "<img src=x onerror=window.__xss=1>"


def s1() -> dict[str, Any]:
    return suggestion(1, slide="slide-1")


def _service() -> RequestService:
    return RequestService(RequestStore(config.state_dir()))


def _write_review(deck: ServedDeck, items: list[dict[str, Any]]) -> None:
    ok, data = call_tool("write_review", file=str(deck.path), suggestions=items)  # type: ignore[arg-type]
    assert ok, data
    assert data == {"ok": True, "count": len(items)}


def _open(page: Page, deck: ServedDeck, heading: str) -> None:
    get_state().poll_interval = POLL_MS
    page.goto(f"http://127.0.0.1:{deck.port}/")
    expect(page.locator("#suggestions-heading")).to_have_text(heading, timeout=5000)
    page.click("#requests-toggle")


def _row(page: Page, suggestion_id: str) -> Any:
    return page.locator(f'#suggestions-list li[data-suggestion-id="{suggestion_id}"]')


# ---------------------------------------------------------------------------
# E2E
# ---------------------------------------------------------------------------


@needs_chromium
def test_e2e_006_write_and_show_a_review(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck, "AI suggestions (0)")
    items = [suggestion(1), s2()]

    _write_review(served_deck, items)

    expect(page.locator("#suggestions-heading")).to_have_text("AI suggestions (2)", timeout=2000)
    for item in items:
        row = _row(page, item["id"])
        expect(row.locator(".suggestion-title")).to_have_text(item["title"])
        expect(row.locator(".suggestion-why")).to_have_text(item["why"])
        expect(row.locator("button.suggestion-apply")).to_have_text("Apply")
        expect(row.locator("button.suggestion-apply")).to_be_enabled()
    stdout, _, code = run_cli("review", str(served_deck.path))
    assert code == 0
    assert stdout == S1_LINE + S2_LINE


@needs_chromium
def test_e2e_007_apply_a_suggestion(page: Page, served_deck: ServedDeck) -> None:
    _write_review(served_deck, [s1(), s2()])
    _open(page, served_deck, "AI suggestions (2)")

    _row(page, "s1").locator("button.suggestion-apply").click()

    expect(page.locator("#ask-ai-message")).to_have_text("Request R-0001 queued", timeout=2000)
    expect(page.locator("#requests-list li .request-text")).to_have_text(
        f"R-0001 pending slide-1 {INSTRUCTION}", timeout=2000
    )
    expect(_row(page, "s1").locator("button.suggestion-apply")).to_have_text("Applied", timeout=2000)
    expect(_row(page, "s1").locator("button.suggestion-apply")).to_be_disabled()
    expect(_row(page, "s2").locator("button.suggestion-apply")).to_have_text("Apply")
    ok, data = call_tool("list_requests", file=str(served_deck.path))
    assert ok, data
    assert [item["instruction"] for item in data["requests"]] == [INSTRUCTION]


@needs_chromium
def test_e2e_019_apply_twice(page: Page, served_deck: ServedDeck) -> None:
    _write_review(served_deck, [s1()])
    _open(page, served_deck, "AI suggestions (1)")
    stale = page.context.new_page()
    stale.goto(f"http://127.0.0.1:{served_deck.port}/")
    expect(stale.locator("#suggestions-heading")).to_have_text("AI suggestions (1)", timeout=5000)
    stale.click("#requests-toggle")

    def block_requests_fetch(route: Route) -> None:
        if route.request.method == "GET":
            route.abort()
        else:
            route.continue_()

    stale.route("**/requests", block_requests_fetch)
    _row(page, "s1").locator("button.suggestion-apply").click()
    expect(_row(page, "s1").locator("button.suggestion-apply")).to_have_text("Applied", timeout=2000)
    expect(_row(page, "s1").locator("button.suggestion-apply")).to_be_disabled()

    expect(_row(stale, "s1").locator("button.suggestion-apply")).to_have_text("Apply")
    _row(stale, "s1").locator("button.suggestion-apply").click()

    expect(stale.locator("#ask-ai-message")).to_have_text("Suggestion s1 was already applied", timeout=2000)
    assert len(_service().list_requests(served_deck.path)) == 1


@needs_chromium
def test_e2e_024_new_review_replaces_the_old_one(page: Page, served_deck: ServedDeck) -> None:
    _write_review(served_deck, [s1()])
    _open(page, served_deck, "AI suggestions (1)")
    _row(page, "s1").locator("button.suggestion-apply").click()
    expect(page.locator("#requests-list li")).to_have_count(1, timeout=2000)

    _write_review(served_deck, [suggestion(3, id="n1", title="Name the owner")])

    expect(page.locator("#suggestions-heading")).to_have_text("AI suggestions (1)", timeout=2000)
    expect(page.locator("#suggestions-list li")).to_have_count(1)
    expect(_row(page, "n1").locator(".suggestion-title")).to_have_text("Name the owner")
    expect(page.locator("#requests-list li .request-text")).to_have_text(f"R-0001 pending slide-1 {INSTRUCTION}")


@needs_chromium
def test_ut_g05_suggestion_text_is_data(page: Page, served_deck: ServedDeck) -> None:
    _write_review(served_deck, [suggestion(1, why=XSS_TEXT, title=XSS_TEXT[:60])])
    _open(page, served_deck, "AI suggestions (1)")

    expect(_row(page, "s1").locator(".suggestion-why")).to_have_text(XSS_TEXT)
    wait_until(
        page,
        lambda: page.locator("#suggestions-list li").count(),
        lambda count: count == 1,
        what="one rendered suggestion row",
    )
    settle(page)
    assert page.evaluate("() => window.__xss") is None
    assert page.locator("#suggestions-list img").count() == 0


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


@pytest.fixture
def deck(tmp_path: Path) -> Path:
    return make_deck(tmp_path)


@pytest.fixture
def service() -> RequestService:
    return _service()


def _text_suggestion(title_length: int, change_length: int) -> dict[str, Any]:
    return suggestion(1, title="t" * title_length, change="c" * change_length)


def _refusal(service: RequestService, deck: Path, suggestion_id: str) -> RequestError:
    with pytest.raises(RequestError) as caught:
        service.apply_suggestion(deck, suggestion_id)
    return caught.value


def _fill_queue(service: RequestService, deck: Path) -> None:
    for number in range(50):
        service.queue(deck, f"r{number}", None)


def _assert_untouched(service: RequestService, deck: Path, requests_before: list[Any]) -> None:
    assert [item.applied for item in service.read_review(deck)] == [False]
    assert service.list_requests(deck) == requests_before


def test_ut_g01_apply_creates_the_request_and_marks_the_suggestion(service: RequestService, deck: Path) -> None:
    service.write_review(deck, [s1(), s2()])

    request = service.apply_suggestion(deck, "s1")

    assert (request.id, request.slide, request.instruction, request.status, request.reason) == (
        "R-0001",
        "slide-1",
        INSTRUCTION,
        "pending",
        None,
    )
    assert request.title == INSTRUCTION
    assert [(item.id, item.applied) for item in service.read_review(deck)] == [("s1", True), ("s2", False)]
    assert service.list_requests(deck) == [request]


def test_ut_g01_unknown_id_with_and_without_a_review(service: RequestService, deck: Path) -> None:
    error = _refusal(service, deck, "x9")
    assert (error.kind, error.message) == ("not_found", "Suggestion x9 no longer exists")
    service.write_review(deck, [s1()])
    error = _refusal(service, deck, "x9")
    assert (error.kind, error.message) == ("not_found", "Suggestion x9 no longer exists")


def test_ut_g01_already_applied_outranks_the_queue_limit(service: RequestService, deck: Path) -> None:
    service.write_review(deck, [s1()])
    service.apply_suggestion(deck, "s1")
    for number in range(49):
        service.queue(deck, f"r{number}", None)
    error = _refusal(service, deck, "s1")
    assert (error.kind, error.message) == ("conflict", "Suggestion s1 was already applied")
    assert sum(item.status == "pending" for item in service.list_requests(deck)) == 50


def test_ut_g01_and_g02_too_long_leaves_no_trace(service: RequestService, deck: Path) -> None:
    service.write_review(deck, [_text_suggestion(30, 3980)])
    error = _refusal(service, deck, "s1")
    assert (error.kind, error.message) == ("invalid", "Request too long (max 4000 characters)")
    _assert_untouched(service, deck, [])


def test_ut_g01_exactly_4000_is_accepted(service: RequestService, deck: Path) -> None:
    service.write_review(deck, [_text_suggestion(30, 3968)])
    assert len(service.apply_suggestion(deck, "s1").instruction) == 4000


def test_ut_g01_and_g02_too_many_pending_leaves_no_trace(service: RequestService, deck: Path) -> None:
    service.write_review(deck, [s1()])
    _fill_queue(service, deck)
    before = service.list_requests(deck)
    error = _refusal(service, deck, "s1")
    assert (error.kind, error.message) == ("conflict", "Too many pending requests (max 50)")
    _assert_untouched(service, deck, before)


def test_ut_g02_storage_failure_keeps_everything(service: RequestService, deck: Path) -> None:
    service.write_review(deck, [s1()])
    store = RequestStore(config.state_dir())
    directory = store.record_dir(deck)
    directory.rename(directory.with_name("requests-moved"))
    directory.write_text("a regular file where the directory belongs")

    error = _refusal(service, deck, "s1")

    assert error.kind == "storage"
    assert error.message.startswith("Could not queue the request: ")


def test_ut_g03_slide_is_kept_as_is(service: RequestService, deck: Path) -> None:
    service.write_review(deck, [suggestion(1, slide="slide-99"), s2()])
    assert service.apply_suggestion(deck, "s1").slide == "slide-99"
    assert service.apply_suggestion(deck, "s2").slide is None


def test_apply_bumps_the_revision_once(service: RequestService, deck: Path) -> None:
    service.write_review(deck, [s1()])
    before = service.revision(deck)
    service.apply_suggestion(deck, "s1")
    assert service.revision(deck) == before + 1


def test_concurrent_apply_creates_exactly_one_request(service: RequestService, deck: Path) -> None:
    service.write_review(deck, [s1()])
    outcomes: list[str] = []
    barrier = threading.Barrier(6)

    def attempt() -> None:
        barrier.wait()
        try:
            service.apply_suggestion(deck, "s1")
            outcomes.append("ok")
        except RequestError as exc:
            outcomes.append(exc.message)

    threads = [threading.Thread(target=attempt) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count("ok") == 1
    assert outcomes.count("Suggestion s1 was already applied") == 5
    assert len(service.list_requests(deck)) == 1


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def test_ut_g04_http_mapping(served_deck: ServedDeck) -> None:
    service = _service()
    service.write_review(served_deck.path, [s1(), suggestion(2, id="long", title="t" * 30, change="c" * 3980)])

    status, body = post(served_deck, "/review/apply", {"id": "s1"})
    assert status == 200
    assert body["ok"] is True
    assert body["request"]["instruction"] == INSTRUCTION
    assert set(body["request"]) == {"id", "slide", "title", "queued", "instruction", "status", "reason"}
    assert post(served_deck, "/review/apply", {"id": "s9"}) == (
        404,
        {"ok": False, "error": "Suggestion s9 no longer exists"},
    )
    assert post(served_deck, "/review/apply", {"id": "s1"}) == (
        409,
        {"ok": False, "error": "Suggestion s1 was already applied"},
    )
    assert post(served_deck, "/review/apply", {"id": "long"}) == (
        400,
        {"ok": False, "error": "Request too long (max 4000 characters)"},
    )
    invalid = (400, {"ok": False, "error": "Invalid request body"})
    for payload in ([], {"id": 5}, {}):
        assert post(served_deck, "/review/apply", payload) == invalid
    status, _, _ = call(served_deck, "POST", "/review/apply", b'{"id":"s1"}', {"Content-Type": "text/plain"})
    assert status == 415
    assert len(service.list_requests(served_deck.path)) == 1


def test_ut_g04_too_many_pending_is_a_409(served_deck: ServedDeck) -> None:
    service = _service()
    service.write_review(served_deck.path, [s1()])
    _fill_queue(service, served_deck.path)
    assert post(served_deck, "/review/apply", {"id": "s1"}) == (
        409,
        {"ok": False, "error": "Too many pending requests (max 50)"},
    )


@pytest.mark.parametrize("headers", [{"Origin": EVIL_ORIGIN}, {"Host": "evil.example"}])
def test_ut_g04_the_gate_runs_before_the_route(served_deck: ServedDeck, headers: dict[str, str]) -> None:
    service = _service()
    service.write_review(served_deck.path, [s1()])
    status, _, _ = call(served_deck, "POST", "/review/apply", b'{"id":"s1"}', headers)
    assert status == 403
    assert service.list_requests(served_deck.path) == []
    assert [item.applied for item in service.read_review(served_deck.path)] == [False]


def test_ut_g04_storage_error_is_a_500(served_deck: ServedDeck) -> None:
    service = _service()
    service.write_review(served_deck.path, [s1()])
    directory = RequestStore(config.state_dir()).record_dir(served_deck.path)
    directory.rename(directory.with_name("requests-moved"))
    directory.write_text("in the way")

    status, body = post(served_deck, "/review/apply", {"id": "s1"})

    assert status == 500
    assert body["ok"] is False
    assert body["error"].startswith("Could not queue the request: ")
