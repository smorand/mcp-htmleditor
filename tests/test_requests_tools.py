"""SPEC-0010 US-0053: the ``list_requests`` and ``complete_request`` tools and ``RequestService.complete``.

Requests are queued over a real editor server (``POST /requests``) or through the service; tools run through an
in process ``fastmcp.Client`` (``call_tool``). A tool error must be the service message with no ``error: `` prefix.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

import pytest

from mcp_htmleditor import config
from mcp_htmleditor.mcp_server import registered_tool_names
from mcp_htmleditor.request_service import RequestError, RequestService
from mcp_htmleditor.request_store import RequestStore
from mcp_htmleditor.skill_audit import listed_tools
from tests.conftest import ServedDeck

from .deck_support import call_tool, run_cli
from .test_requests_core import QUEUED_FORMAT, make_deck, post, queue_over_http

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "skill" / "core.md"
NOT_BLANK = "A reason is required to skip a request"


@pytest.fixture
def deck(tmp_path: Path) -> Path:
    return make_deck(tmp_path)


@pytest.fixture
def service() -> RequestService:
    return RequestService(RequestStore(config.state_dir()))


def queue_many(service: RequestService, deck: Path, count: int) -> None:
    for number in range(count):
        service.queue(deck, f"request {number + 1}", None)


def statuses(service: RequestService, deck: Path) -> list[str]:
    return [request.status for request in service.list_requests(deck)]


# ---------------------------------------------------------------------------
# E2E-002, E2E-013, E2E-014, E2E-023, E2E-025
# ---------------------------------------------------------------------------


def test_e2e_002_list_requests_returns_the_queued_request(served_deck: ServedDeck) -> None:
    assert queue_over_http(served_deck, "Shorten the title", "slide-3")[0] == 200
    ok, result = call_tool("list_requests", file=str(served_deck.path))
    assert ok
    assert list(result) == ["file", "requests"]
    assert result["file"] == str(served_deck.path.resolve())
    [request] = result["requests"]
    assert QUEUED_FORMAT.match(request.pop("queued"))
    assert request == {
        "id": "R-0001",
        "slide": "slide-3",
        "position": 4,
        "title": "Shorten the title",
        "instruction": "Shorten the title",
        "status": "pending",
        "reason": None,
    }
    assert list(request) == ["id", "slide", "position", "title", "instruction", "status", "reason"]


def test_e2e_013_invalid_status_is_the_product_message_not_a_schema_error(served_deck: ServedDeck) -> None:
    queue_over_http(served_deck, "Shorten the title")
    ok, message = call_tool("complete_request", file=str(served_deck.path), id="R-0001", status="finished")
    assert (ok, message) == (False, "Status must be done or skipped")
    ok, result = call_tool("list_requests", file=str(served_deck.path))
    assert [r["status"] for r in result["requests"]] == ["pending"]


def test_e2e_014_already_completed(served_deck: ServedDeck) -> None:
    queue_over_http(served_deck, "Shorten the title")
    ok, result = call_tool("complete_request", file=str(served_deck.path), id="R-0001", status="done")
    assert (ok, result) == (True, {"ok": True, "id": "R-0001", "status": "done"})
    ok, message = call_tool(
        "complete_request", file=str(served_deck.path), id="R-0001", status="skipped", reason="no longer needed"
    )
    assert (ok, message) == (False, "Request R-0001 is already done")
    ok, result = call_tool("list_requests", file=str(served_deck.path))
    assert [r["status"] for r in result["requests"]] == ["done"]


def test_e2e_023_two_files_have_two_queues(
    tmp_path: Path, served_deck: ServedDeck, monkeypatch: pytest.MonkeyPatch
) -> None:
    deck2 = make_deck(served_deck.path.parent, "deck2.html")
    queue_over_http(served_deck, "Shorten the title")
    ok, result = call_tool("list_requests", file=str(deck2))
    assert (ok, result["requests"]) == (True, [])
    ok, result = call_tool("list_requests", file=str(served_deck.path))
    assert ok
    assert len(result["requests"]) == 1
    monkeypatch.chdir(served_deck.path.parent)
    assert run_cli("requests", "deck2.html") == ("No requests for deck2.html\n", "", 0)


def test_e2e_025_completion_after_deletion(served_deck: ServedDeck) -> None:
    queue_over_http(served_deck, "Shorten the title")
    assert post(served_deck, "/requests/delete", {"id": "R-0001"})[0] == 200
    ok, message = call_tool("complete_request", file=str(served_deck.path), id="R-0001", status="done")
    assert (ok, message) == (False, 'Unknown request id "R-0001". Valid ids: none')


# ---------------------------------------------------------------------------
# UT-B01..B05
# ---------------------------------------------------------------------------


def test_ut_b01_done_ignores_a_reason_and_skipped_keeps_it_untrimmed(service: RequestService, deck: Path) -> None:
    queue_many(service, deck, 2)
    done = service.complete(deck, "R-0001", "done", "ignored")
    assert (done.status, done.reason) == ("done", None)
    skipped = service.complete(deck, "R-0002", "skipped", "  Title is already short  ")
    assert (skipped.status, skipped.reason) == ("skipped", "  Title is already short  ")
    assert [(r.status, r.reason) for r in service.list_requests(deck)] == [
        ("done", None),
        ("skipped", "  Title is already short  "),
    ]


@pytest.mark.parametrize("reason", ["   ", "\u3000", "\t\n\u00a0", "", None])
def test_ut_b01_skipped_needs_a_non_blank_reason(service: RequestService, deck: Path, reason: str | None) -> None:
    queue_many(service, deck, 1)
    with pytest.raises(RequestError) as caught:
        service.complete(deck, "R-0001", "skipped", reason)
    assert (caught.value.kind, caught.value.message) == ("invalid", NOT_BLANK)
    assert statuses(service, deck) == ["pending"]


def test_ut_b01_a_control_character_that_is_not_white_space_is_a_reason(service: RequestService, deck: Path) -> None:
    queue_many(service, deck, 1)
    assert service.complete(deck, "R-0001", "skipped", "\x1f").reason == "\x1f"


def test_ut_b01_a_long_reason_is_kept(service: RequestService, deck: Path) -> None:
    queue_many(service, deck, 1)
    reason = "x" * 10_000
    assert service.complete(deck, "R-0001", "skipped", reason).reason == reason


def test_ut_b02_check_order_in_the_service(service: RequestService, deck: Path) -> None:
    queue_many(service, deck, 1)
    service.complete(deck, "R-0001", "done", None)
    queue_many(service, deck, 1)
    cases = [
        ("R-9", "finished", None, 'Unknown request id "R-9". Valid ids: R-0001, R-0002', "not_found"),
        ("R-0002", "finished", None, "Status must be done or skipped", "invalid"),
        ("R-0002", "skipped", None, NOT_BLANK, "invalid"),
        ("R-0001", "skipped", None, NOT_BLANK, "invalid"),
        ("R-0001", "skipped", "why", "Request R-0001 is already done", "conflict"),
        ("R-0001", "done", None, "Request R-0001 is already done", "conflict"),
    ]
    for request_id, status, reason, message, kind in cases:
        with pytest.raises(RequestError) as caught:
            service.complete(deck, request_id, status, reason)
        assert (caught.value.message, caught.value.kind) == (message, kind)


def test_ut_b02_already_skipped_names_the_current_status(service: RequestService, deck: Path) -> None:
    queue_many(service, deck, 1)
    service.complete(deck, "R-0001", "skipped", "no")
    with pytest.raises(RequestError, match=r"^Request R-0001 is already skipped$"):
        service.complete(deck, "R-0001", "done", None)


def test_ut_b02_check_order_through_the_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ok, message = call_tool("complete_request", file="ghost.html", id="R-9", status="finished")
    assert (ok, message) == (False, "File not found: ghost.html")
    deck = make_deck(tmp_path)
    ok, message = call_tool("complete_request", file=str(deck), id="R-9", status="finished")
    assert (ok, message) == (False, 'Unknown request id "R-9". Valid ids: none')


def test_ut_b03_valid_ids_skip_deleted_ones_oldest_first(service: RequestService, deck: Path) -> None:
    queue_many(service, deck, 3)
    service.delete(deck, "R-0002")
    with pytest.raises(RequestError) as caught:
        service.complete(deck, "R-9", "done", None)
    assert (caught.value.kind, caught.value.message) == (
        "not_found",
        'Unknown request id "R-9". Valid ids: R-0001, R-0003',
    )


def test_ut_b03_a_completed_request_is_still_a_valid_id(service: RequestService, deck: Path) -> None:
    queue_many(service, deck, 2)
    service.complete(deck, "R-0001", "done", None)
    with pytest.raises(RequestError, match=r"Valid ids: R-0001, R-0002$"):
        service.complete(deck, "nope", "done", None)


def test_ut_b04_tool_errors_carry_the_file_as_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert call_tool("list_requests", file="ghost.html") == (False, "File not found: ghost.html")
    assert call_tool("list_requests", file="./ghost.html") == (False, "File not found: ./ghost.html")
    assert call_tool("complete_request", file="./ghost.html", id="R-1", status="done") == (
        False,
        "File not found: ./ghost.html",
    )


def test_ut_b04_storage_error_has_no_prefix(deck: Path) -> None:
    store = RequestStore(config.state_dir())
    RequestService(store).queue(deck, "one", None)
    (store.record_dir(deck) / "record.json").write_bytes(b"{not json")
    ok, message = call_tool("list_requests", file=str(deck))
    assert not ok
    assert message.startswith("Requests record of ")
    assert not message.startswith("error: ")
    ok, message = call_tool("complete_request", file=str(deck), id="R-0001", status="done")
    assert not ok
    assert message.startswith("Requests record of ")


def test_ut_b04_missing_reason_for_skipped_through_the_tool(deck: Path, service: RequestService) -> None:
    queue_many(service, deck, 1)
    assert call_tool("complete_request", file=str(deck), id="R-0001", status="skipped") == (False, NOT_BLANK)
    ok, result = call_tool("complete_request", file=str(deck), id="R-0001", status="skipped", reason=" why ")
    assert (ok, result) == (True, {"ok": True, "id": "R-0001", "status": "skipped"})
    assert service.list_requests(deck)[0].reason == " why "


def test_ut_b05_skill_audit_sees_the_two_tools() -> None:
    text = CORE.read_text(encoding="utf-8")
    assert {"list_requests", "complete_request"} <= set(listed_tools(text))
    assert {"list_requests", "complete_request"} <= set(registered_tool_names())
    stdout, _, code = run_cli("skill-audit")
    assert code == 0
    assert not [
        line
        for line in stdout.splitlines()
        if "PROBLEM" in line and re.search(r"list_requests|complete_request|tool", line)
    ]


# ---------------------------------------------------------------------------
# Atomicity: completion runs under the store lock
# ---------------------------------------------------------------------------


def test_completion_and_queue_in_parallel_lose_nothing(service: RequestService, deck: Path) -> None:
    queue_many(service, deck, 10)
    errors: list[BaseException] = []

    def complete_all() -> None:
        try:
            for number in range(1, 11):
                service.complete(deck, f"R-{number:04d}", "done", None)
        except BaseException as exc:
            errors.append(exc)

    def queue_more() -> None:
        try:
            for number in range(10):
                service.queue(deck, f"later {number}", None)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=complete_all), threading.Thread(target=queue_more)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    requests = service.list_requests(deck)
    assert len(requests) == 20
    assert [r.status for r in requests[:10]] == ["done"] * 10
    assert [r.status for r in requests[10:]] == ["pending"] * 10
    assert len({r.id for r in requests}) == 20
