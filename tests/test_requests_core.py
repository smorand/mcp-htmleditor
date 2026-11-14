"""SPEC-0010 US-0052: request store, queue endpoints and the ``requests`` command.

Service level tests drive ``RequestStore`` and ``RequestService`` in process (and from child processes for the
lock); HTTP tests use a real editor server through ``http.client`` so ``Host``, ``Origin`` and ``Content-Length``
are sent verbatim; command line tests use ``click.testing`` with separate streams.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import logging
import os
import re
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor import config, request_store
from mcp_htmleditor import state as state_module
from mcp_htmleditor.request_service import RequestError, RequestService, build_request_service
from mcp_htmleditor.request_store import Record, RequestStore
from mcp_htmleditor.state import get_state
from tests.conftest import ServedDeck
from tests.deck_support import run_cli

REPO = Path(__file__).resolve().parents[1]
REQUEST_KEYS = ["id", "slide", "title", "queued", "instruction", "status", "reason"]
QUEUED_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
EVIL_ORIGIN = "https://evil.example"
FIXED_NOW = datetime(2026, 11, 3, 10, 15, 0, tzinfo=UTC)


def make_deck(folder: Path, name: str = "deck.html") -> Path:
    path = folder / name
    path.write_text("<!DOCTYPE html><html><body><p>x</p></body></html>", encoding="utf-8")
    return path


@pytest.fixture
def deck(tmp_path: Path) -> Path:
    return make_deck(tmp_path)


@pytest.fixture
def store() -> RequestStore:
    return RequestStore(config.state_dir())


@pytest.fixture
def service(store: RequestStore) -> RequestService:
    return RequestService(store)


def record_bytes(store: RequestStore, file: Path) -> bytes:
    return (store.record_dir(file) / "record.json").read_bytes()


def expected_key(file: Path) -> str:
    return hashlib.sha256(os.path.realpath(file).encode("utf-8")).hexdigest()[:32]


def seed_next_id(store: RequestStore, file: Path, value: int) -> None:
    def change(record: Record) -> None:
        record.next_id = value

    store.update(file, "seed", change)


def set_status(store: RequestStore, file: Path, index: int, status: str) -> None:
    def change(record: Record) -> None:
        record.requests[index] = replace(record.requests[index], status=status)

    store.update(file, "complete", change)


# ---------------------------------------------------------------------------
# UT-A01: store round trip and unreadable record
# ---------------------------------------------------------------------------


def test_ut_a01_round_trip_keeps_the_text_and_writes_utf8(deck: Path, store: RequestStore) -> None:
    typed = "Mettre « Résumé » en gras\r\npuis centrer"
    RequestService(store).queue(deck, typed, "slide-3")
    stored = RequestService(RequestStore(config.state_dir())).list_requests(deck)
    assert [r.instruction for r in stored] == [typed]
    raw = record_bytes(store, deck)
    assert "Résumé".encode() in raw
    assert b"\\u00e9" not in raw
    assert store.record_dir(deck) == config.state_dir() / "files" / expected_key(deck) / "requests"


def test_record_dir_is_the_spec_0009_per_file_directory(deck: Path, store: RequestStore) -> None:
    assert store.record_dir(deck) == state_module._file_dir(str(deck)) / "requests"


def test_record_has_the_documented_shape(deck: Path, store: RequestStore, service: RequestService) -> None:
    service.queue(deck, "Shorten", "slide-1")
    data = json.loads(record_bytes(store, deck))
    assert list(data) == ["version", "file", "revision", "next_id", "requests", "review"]
    assert data["version"] == 1
    assert data["file"] == os.path.realpath(deck)
    assert (data["revision"], data["next_id"], data["review"]) == (1, 2, None)
    assert list(data["requests"][0]) == REQUEST_KEYS
    assert (store.record_dir(deck) / "record.lock").read_bytes() == b""


@pytest.mark.parametrize("broken", [b"{not json", b"[]", b'{"version":2}', b'{"version":1,"next_id":"x"}', b"\xff\xfe"])
def test_ut_a01_unreadable_record_raises_and_is_never_reset(
    deck: Path, store: RequestStore, service: RequestService, broken: bytes
) -> None:
    service.queue(deck, "first", None)
    path = store.record_dir(deck) / "record.json"
    path.write_bytes(broken)
    for call in (lambda: service.list_requests(deck), lambda: service.queue(deck, "again", None)):
        with pytest.raises(RequestError) as caught:
            call()
        assert caught.value.kind == "storage"
        assert caught.value.message.startswith("Requests record of ")
        assert "is unreadable: " in caught.value.message
        assert str(caught.value) == caught.value.message
    assert path.read_bytes() == broken


def test_read_of_an_absent_record_is_empty_and_creates_nothing(deck: Path, store: RequestStore) -> None:
    assert store.read(deck) == Record()
    assert store.revision(deck) == 0
    assert not config.state_dir().exists()


def test_revision_of_an_unreadable_record_is_zero_and_logs(
    deck: Path, store: RequestStore, service: RequestService, caplog: pytest.LogCaptureFixture
) -> None:
    service.queue(deck, "secret instruction text", None)
    (store.record_dir(deck) / "record.json").write_bytes(b"{not json")
    with caplog.at_level(logging.WARNING):
        assert store.revision(deck) == 0
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert "secret instruction text" not in caplog.text


# ---------------------------------------------------------------------------
# Update semantics (DEC-011, DEC-016): revision only on a real change, nothing written on failure
# ---------------------------------------------------------------------------


def test_update_bumps_the_revision_only_when_the_record_changes(deck: Path, store: RequestStore) -> None:
    assert store.update(deck, "noop", lambda record: 41) == 41
    assert not (store.record_dir(deck) / "record.json").exists()
    seed_next_id(store, deck, 5)
    first = record_bytes(store, deck)
    assert store.read(deck).revision == 1
    store.update(deck, "noop", lambda record: None)
    assert record_bytes(store, deck) == first
    assert store.read(deck).revision == 1


def test_update_that_raises_writes_nothing(deck: Path, store: RequestStore, service: RequestService) -> None:
    service.queue(deck, "one", None)
    before = record_bytes(store, deck)

    def change(record: Record) -> None:
        record.next_id = 99
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        store.update(deck, "fail", change)
    assert record_bytes(store, deck) == before


def test_review_none_is_distinct_from_an_empty_review(deck: Path, store: RequestStore) -> None:
    def clear(record: Record) -> None:
        record.review = []

    store.update(deck, "review", clear)
    assert store.read(deck).review == []
    assert json.loads(record_bytes(store, deck))["review"] == []


def test_update_span_names_the_operation_and_never_the_text(
    deck: Path, store: RequestStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def spy(name: str, attributes: dict[str, Any] | None = None) -> Iterator[None]:
        seen.append((name, dict(attributes or {})))
        yield

    monkeypatch.setattr(request_store, "trace_span", spy)
    RequestService(store).queue(deck, "private words", None)
    assert [name for name, _ in seen] == ["requests.update"]
    attributes = seen[0][1]
    assert "queue" in attributes.values()
    assert str(store.record_dir(deck) / "record.json") in attributes.values()
    assert "private words" not in json.dumps(attributes)


def test_storage_failure_does_not_log_the_instruction(
    deck: Path, store: RequestStore, service: RequestService, caplog: pytest.LogCaptureFixture
) -> None:
    store.record_dir(deck).parent.mkdir(parents=True)
    store.record_dir(deck).write_text("in the way")
    with caplog.at_level(logging.DEBUG), pytest.raises(RequestError):
        service.queue(deck, "do not leak this sentence", None)
    assert "do not leak this sentence" not in caplog.text


# ---------------------------------------------------------------------------
# UT-A02: processes and threads, no lost request, no duplicate id
# ---------------------------------------------------------------------------

CHILD_SCRIPT = (
    "import sys\n"
    "from pathlib import Path\n"
    "from mcp_htmleditor.request_service import build_request_service\n"
    "service = build_request_service()\n"
    "file = Path(sys.argv[1])\n"
    "for i in range(15):\n"
    "    service.queue(file, f'child {i}', None)\n"
)


def test_ut_a02_three_processes_lose_nothing_and_never_duplicate(deck: Path, store: RequestStore) -> None:
    env = {**os.environ, "HTMLEDITOR_STATE_DIR": str(config.state_dir()), "PYTHONPATH": str(REPO / "src")}
    children = [
        subprocess.Popen([sys.executable, "-c", CHILD_SCRIPT, str(deck)], env=env, cwd=REPO)  # noqa: S603
        for _ in range(2)
    ]
    service = build_request_service()
    for i in range(15):
        service.queue(deck, f"parent {i}", None)
    assert [child.wait(timeout=120) for child in children] == [0, 0]
    ids = [r.id for r in service.list_requests(deck)]
    assert len(ids) == 45
    assert ids == sorted(set(ids))
    assert ids == [f"R-{n:04d}" for n in range(1, 46)]
    assert json.loads(record_bytes(store, deck))["next_id"] == 46


def test_threads_lose_nothing_and_never_duplicate(deck: Path, service: RequestService) -> None:
    def work(tag: int) -> None:
        for i in range(10):
            RequestService(RequestStore(config.state_dir())).queue(deck, f"t{tag} {i}", None)

    threads = [threading.Thread(target=work, args=(tag,)) for tag in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    ids = [r.id for r in service.list_requests(deck)]
    assert ids == [f"R-{n:04d}" for n in range(1, 41)]


# ---------------------------------------------------------------------------
# UT-A03: rule order and limits
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "blank",
    ["", "   ", "\u3000", "\u00a0", " " * 4001, "\u0085\u2028\u2029\u202f\u205f\u1680\u200a"],
    ids=["empty", "spaces", "ideographic", "nbsp", "4001-spaces", "mixed"],
)
def test_ut_a03_blank_is_refused_before_the_length(service: RequestService, deck: Path, blank: str) -> None:
    with pytest.raises(RequestError) as caught:
        service.queue(deck, blank, None)
    assert (caught.value.kind, caught.value.message) == ("invalid", "Write a request first")


def test_a_control_character_that_is_not_white_space_is_not_blank(service: RequestService, deck: Path) -> None:
    assert service.queue(deck, "\u001f", None).instruction == "\u001f"


def test_ut_a03_length_limit(service: RequestService, deck: Path) -> None:
    assert service.queue(deck, "a" * 4000, None).instruction == "a" * 4000
    with pytest.raises(RequestError) as caught:
        service.queue(deck, "a" * 4001, None)
    assert (caught.value.kind, caught.value.message) == ("invalid", "Request too long (max 4000 characters)")


def test_ut_a03_pending_limit_counts_pending_only(store: RequestStore, service: RequestService, deck: Path) -> None:
    for i in range(50):
        service.queue(deck, f"r{i}", None)
    with pytest.raises(RequestError) as caught:
        service.queue(deck, "one too many", None)
    assert (caught.value.kind, caught.value.message) == ("conflict", "Too many pending requests (max 50)")
    set_status(store, deck, 0, "done")
    assert service.queue(deck, "now it fits", None).id == "R-0051"


def test_refusals_leave_the_record_untouched(store: RequestStore, service: RequestService, deck: Path) -> None:
    service.queue(deck, "one", None)
    before = record_bytes(store, deck)
    for bad in ("  ", "a" * 4001):
        with pytest.raises(RequestError):
            service.queue(deck, bad, None)
    assert record_bytes(store, deck) == before


# ---------------------------------------------------------------------------
# UT-A04: storage failure seam
# ---------------------------------------------------------------------------


def test_ut_a04_storage_failure_message_is_the_oserror_text(
    store: RequestStore, service: RequestService, deck: Path
) -> None:
    store.record_dir(deck).parent.mkdir(parents=True)
    store.record_dir(deck).write_text("a regular file where the directory belongs")
    with pytest.raises(OSError) as expected:
        store.record_dir(deck).mkdir(parents=True, exist_ok=True)
    with pytest.raises(RequestError) as caught:
        service.queue(deck, "x", None)
    assert caught.value.kind == "storage"
    assert caught.value.message == f"Could not queue the request: {expected.value}"
    assert str(expected.value)
    assert not (store.record_dir(deck) / "record.json").exists()
    with pytest.raises(RequestError) as deleted:
        service.delete(deck, "R-0001")
    assert deleted.value.kind == "storage"
    assert deleted.value.message.startswith("Could not delete the request: ")


def test_a_failed_atomic_write_is_a_storage_error_and_keeps_the_record(
    store: RequestStore, service: RequestService, deck: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.queue(deck, "one", None)
    before = record_bytes(store, deck)

    def refuse(source: str, destination: str) -> None:
        raise PermissionError(13, "Permission denied")

    with monkeypatch.context() as patch:
        patch.setattr("mcp_htmleditor.fileio.replace_file", refuse)
        with pytest.raises(RequestError) as caught:
            service.queue(deck, "two", None)
    assert caught.value.kind == "storage"
    assert caught.value.message.startswith("Could not queue the request: ")
    assert record_bytes(store, deck) == before
    assert [p.name for p in store.record_dir(deck).iterdir() if p.name.endswith(".tmp")] == []


# ---------------------------------------------------------------------------
# UT-A05: title and id formatting
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("instruction", "title"),
    [
        ("a\r\nb", "a b"),
        ("a\n\nb", "a  b"),
        ("a\rb", "a b"),
        (" hi", " hi"),
        ("x" * 70, "x" * 60),
        ("x" * 59 + "😀" + "yyyy", "x" * 59 + "😀"),
    ],
)
def test_ut_a05_titles(service: RequestService, deck: Path, instruction: str, title: str) -> None:
    request = service.queue(deck, instruction, None)
    assert request.title == title
    assert request.instruction == instruction
    assert len(request.title) <= 60


def test_ut_a05_ids_go_past_r_9999_and_next_id_never_decreases(
    store: RequestStore, service: RequestService, deck: Path
) -> None:
    seed_next_id(store, deck, 9999)
    assert [service.queue(deck, "x", None).id, service.queue(deck, "y", None).id] == ["R-9999", "R-10000"]
    service.delete(deck, "R-10000")
    assert service.queue(deck, "z", None).id == "R-10001"


def test_ut_a05_queued_comes_from_the_injected_clock_inside_the_lock(store: RequestStore, deck: Path) -> None:
    request = RequestService(store, clock=lambda: FIXED_NOW).queue(deck, "x", None)
    assert request.queued == "2026-11-03T10:15:00Z"
    assert QUEUED_FORMAT.match(RequestService(store).queue(deck, "y", None).queued)


def test_slide_is_stored_as_given_without_checking_the_file(service: RequestService, deck: Path) -> None:
    assert service.queue(deck, "x", "no-such-slide").slide == "no-such-slide"
    assert service.queue(deck, "y", None).slide is None
    assert service.list_requests(deck)[0].status == "pending"
    assert service.list_requests(deck)[0].reason is None


# ---------------------------------------------------------------------------
# Service helpers
# ---------------------------------------------------------------------------


def test_require_file_resolves_and_names_the_file_as_typed(
    tmp_path: Path, deck: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mcp_htmleditor.request_service import require_file

    monkeypatch.chdir(tmp_path)
    assert require_file("deck.html") == deck.resolve()
    with pytest.raises(RequestError) as caught:
        require_file("ghost.html")
    assert (caught.value.kind, caught.value.message) == ("not_found", "File not found: ghost.html")
    with pytest.raises(RequestError):
        require_file(str(tmp_path))


def test_snapshot_gathers_revision_pending_requests_and_suggestions(
    store: RequestStore, service: RequestService, deck: Path
) -> None:
    service.queue(deck, "one", None)
    service.queue(deck, "two", None)
    set_status(store, deck, 0, "done")
    snapshot = service.snapshot(deck)
    assert snapshot.revision == 3
    assert snapshot.pending == 1
    assert [r.id for r in snapshot.requests] == ["R-0001", "R-0002"]
    assert snapshot.suggestions == []


def test_delete_of_an_unknown_id_is_a_noop(store: RequestStore, service: RequestService, deck: Path) -> None:
    service.queue(deck, "one", None)
    before = record_bytes(store, deck)
    service.delete(deck, "R-0009")
    assert record_bytes(store, deck) == before


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def call(
    served: ServedDeck,
    method: str,
    route: str,
    body: bytes = b"",
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any], http.client.HTTPResponse]:
    """Send one request with exactly the given headers (Host and Origin included) and decode the JSON answer."""
    sent = {"Content-Type": "application/json", "Content-Length": str(len(body))} | (headers or {})
    conn = http.client.HTTPConnection("127.0.0.1", served.port, timeout=60)
    try:
        conn.putrequest(method, route, skip_host="Host" in sent, skip_accept_encoding=True)
        for name, value in sent.items():
            conn.putheader(name, value)
        conn.endheaders(body)
        response = conn.getresponse()
        raw = response.read()
        return response.status, json.loads(raw) if raw else {}, response
    finally:
        conn.close()


def post(served: ServedDeck, route: str, payload: object) -> tuple[int, dict[str, Any]]:
    status, data, _ = call(served, "POST", route, json.dumps(payload).encode("utf-8"))
    return status, data


def queue_over_http(served: ServedDeck, instruction: str, slide: str | None = None) -> tuple[int, dict[str, Any]]:
    return post(served, "/requests", {"instruction": instruction, "slide": slide})


# ---------------------------------------------------------------------------
# UT-A06: HTTP queue and list
# ---------------------------------------------------------------------------


def test_ut_a06_post_then_get(served_deck: ServedDeck) -> None:
    status, body = queue_over_http(served_deck, "Shorten the title", "slide-3")
    assert status == 200
    assert body["ok"] is True
    request = body["request"]
    assert list(request) == REQUEST_KEYS
    assert QUEUED_FORMAT.match(request.pop("queued"))
    assert request == {
        "id": "R-0001",
        "slide": "slide-3",
        "title": "Shorten the title",
        "instruction": "Shorten the title",
        "status": "pending",
        "reason": None,
    }
    status, listing, _ = call(served_deck, "GET", "/requests")
    assert status == 200
    assert list(listing) == ["revision", "pending", "requests", "suggestions"]
    assert (listing["revision"], listing["pending"], listing["suggestions"]) == (1, 1, [])
    assert [r["id"] for r in listing["requests"]] == ["R-0001"]
    assert list(listing["requests"][0]) == REQUEST_KEYS


def test_ut_a06_slide_may_be_absent_or_null(served_deck: ServedDeck) -> None:
    assert post(served_deck, "/requests", {"instruction": "no slide key"})[1]["request"]["slide"] is None


def test_ut_a06_content_type_must_be_json(served_deck: ServedDeck) -> None:
    status, body, _ = call(served_deck, "POST", "/requests", b'{"instruction":"x"}', {"Content-Type": "text/plain"})
    assert (status, body) == (415, {"error": "unsupported content type"})
    status, body, _ = call(
        served_deck, "POST", "/requests", b'{"instruction":"x"}', {"Content-Type": "application/json; charset=utf-8"}
    )
    assert status == 200


def test_ut_a06_body_errors(served_deck: ServedDeck) -> None:
    assert call(served_deck, "POST", "/requests", b"{")[:2] == (400, {"error": "Invalid JSON body"})
    assert call(served_deck, "POST", "/requests", b"")[:2] == (400, {"error": "Invalid JSON body"})
    assert served_deck.request("POST", "/requests", content_length="abc").status == 400
    bad_length = served_deck.request("POST", "/requests", content_length="abc")
    assert bad_length.body == {"error": "Invalid Content-Length"}
    too_large = served_deck.request("POST", "/requests", content_length="1048577", send_body=False)
    assert (too_large.status, too_large.body) == (413, {"error": "Request too large"})
    invalid = {"ok": False, "error": "Invalid request body"}
    for payload in (
        [],
        {"instruction": 5, "slide": None},
        {"instruction": "x", "slide": 3},
        {"slide": None},
        "text",
        None,
    ):
        assert post(served_deck, "/requests", payload) == (400, invalid)
    assert post(served_deck, "/requests/delete", {"id": 5}) == (400, invalid)
    assert post(served_deck, "/requests/delete", {}) == (400, invalid)
    assert post(served_deck, "/requests/delete", []) == (400, invalid)
    assert call(served_deck, "GET", "/requests")[1]["requests"] == []


def test_ut_a06_text_the_record_cannot_hold_is_an_invalid_body(served_deck: ServedDeck) -> None:
    invalid = (400, {"ok": False, "error": "Invalid request body"})
    assert call(served_deck, "POST", "/requests", b'{"instruction":"\\ud800"}')[:2] == invalid
    assert call(served_deck, "POST", "/requests", b'{"instruction":"x","slide":"\\udfff"}')[:2] == invalid
    assert call(served_deck, "POST", "/requests/delete", b'{"id":"\\ud800"}')[:2] == invalid
    assert call(served_deck, "POST", "/requests", b'{"instruction":"\xff"}')[:2] == (
        400,
        {"error": "Invalid JSON body"},
    )


def test_ut_a06_a_body_of_exactly_one_mebibyte_is_read(served_deck: ServedDeck) -> None:
    padding = " " * (1_048_576 - len(b'{"instruction":"x","pad":""}'))
    body = ('{"instruction":"x","pad":"' + padding + '"}').encode()
    assert len(body) == 1_048_576
    assert call(served_deck, "POST", "/requests", body)[0] == 200


def test_ut_a06_rule_errors(served_deck: ServedDeck) -> None:
    assert queue_over_http(served_deck, "  \u3000 ") == (400, {"ok": False, "error": "Write a request first"})
    assert queue_over_http(served_deck, "a" * 4001) == (
        400,
        {"ok": False, "error": "Request too long (max 4000 characters)"},
    )
    for i in range(50):
        assert queue_over_http(served_deck, f"r{i}")[0] == 200
    assert queue_over_http(served_deck, "one more") == (
        409,
        {"ok": False, "error": "Too many pending requests (max 50)"},
    )


def test_ut_a06_storage_error_is_a_500(served_deck: ServedDeck, store: RequestStore) -> None:
    store.record_dir(served_deck.path).parent.mkdir(parents=True, exist_ok=True)
    store.record_dir(served_deck.path).write_text("in the way")
    status, body = queue_over_http(served_deck, "x")
    assert status == 500
    assert body["ok"] is False
    assert body["error"].startswith("Could not queue the request: ")
    status, body, _ = call(served_deck, "GET", "/requests")
    assert status == 500
    assert body["error"].startswith("Requests record of ")


def test_unreadable_record_is_a_500_on_get_and_status_revision_is_zero(
    served_deck: ServedDeck, store: RequestStore
) -> None:
    queue_over_http(served_deck, "x")
    (store.record_dir(served_deck.path) / "record.json").write_bytes(b"{not json")
    status, body, _ = call(served_deck, "GET", "/requests")
    assert status == 500
    assert body["error"].startswith("Requests record of ")
    assert "is unreadable: " in body["error"]
    assert served_deck.status()["requests_revision"] == 0


def test_ut_a06_no_file_loaded(served_deck: ServedDeck) -> None:
    get_state().current_file = None
    assert call(served_deck, "GET", "/requests")[:2] == (404, {"error": "No file loaded"})
    assert call(served_deck, "POST", "/requests", b'{"instruction":"x"}')[:2] == (404, {"error": "No file loaded"})
    assert call(served_deck, "POST", "/requests/delete", b'{"id":"R-0001"}')[:2] == (404, {"error": "No file loaded"})
    assert served_deck.status()["requests_revision"] == 0


def test_the_trailing_slash_get_route_and_unknown_methods(served_deck: ServedDeck) -> None:
    assert call(served_deck, "GET", "/requests/")[0] == 200
    assert call(served_deck, "POST", "/requests/other", b"{}")[0] == 404
    assert call(served_deck, "GET", "/requests/delete")[0] == 404


# ---------------------------------------------------------------------------
# UT-A07: SPEC-0005 gate on the new routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("headers", [{"Origin": EVIL_ORIGIN}, {"Host": "evil.example"}])
@pytest.mark.parametrize(
    ("method", "route"), [("GET", "/requests"), ("POST", "/requests"), ("POST", "/requests/delete")]
)
def test_ut_a07_the_gate_runs_before_the_new_routes(
    served_deck: ServedDeck, method: str, route: str, headers: dict[str, str]
) -> None:
    body = b'{"instruction":"x","id":"R-0001"}' if method == "POST" else b""
    status, _, _ = call(served_deck, method, route, body, headers)
    assert status == 403
    assert not list(config.state_dir().rglob("requests"))


def test_ut_a07_options_is_still_405(served_deck: ServedDeck) -> None:
    status, _, response = call(served_deck, "OPTIONS", "/requests")
    assert status == 405
    assert response.getheader("Allow") == "GET, POST"


# ---------------------------------------------------------------------------
# UT-A08: delete
# ---------------------------------------------------------------------------


def test_ut_a08_delete_unknown_is_a_noop_then_a_real_delete(served_deck: ServedDeck) -> None:
    queue_over_http(served_deck, "one")
    queue_over_http(served_deck, "two")
    assert post(served_deck, "/requests/delete", {"id": "R-0009"}) == (200, {"ok": True})
    listing = call(served_deck, "GET", "/requests")[1]
    assert (listing["revision"], len(listing["requests"])) == (2, 2)
    assert post(served_deck, "/requests/delete", {"id": "R-0002"}) == (200, {"ok": True})
    listing = call(served_deck, "GET", "/requests")[1]
    assert (listing["revision"], [r["id"] for r in listing["requests"]]) == (3, ["R-0001"])
    assert queue_over_http(served_deck, "three")[1]["request"]["id"] == "R-0003"


def test_ut_a08_a_delete_frees_a_slot_at_the_pending_limit(served_deck: ServedDeck, service: RequestService) -> None:
    for i in range(50):
        service.queue(served_deck.path, f"r{i}", None)
    assert queue_over_http(served_deck, "too many")[0] == 409
    assert post(served_deck, "/requests/delete", {"id": "R-0007"}) == (200, {"ok": True})
    assert queue_over_http(served_deck, "fits now")[0] == 200


def test_delete_storage_error_is_a_500(served_deck: ServedDeck, store: RequestStore) -> None:
    store.record_dir(served_deck.path).parent.mkdir(parents=True, exist_ok=True)
    store.record_dir(served_deck.path).write_text("in the way")
    status, body = post(served_deck, "/requests/delete", {"id": "R-0001"})
    assert status == 500
    assert body["ok"] is False
    assert body["error"].startswith("Could not delete the request: ")


# ---------------------------------------------------------------------------
# UT-A09: requests command, isolation and aliases
# ---------------------------------------------------------------------------


def test_ut_a09_lists_oldest_first(
    tmp_path: Path, deck: Path, service: RequestService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service.queue(deck, "Shorten the title", "slide-3")
    service.queue(deck, "Fix footer", None)
    out, err, code = run_cli("requests", "deck.html")
    assert (out, err, code) == (
        "R-0001  pending  slide-3  -  Shorten the title\nR-0002  pending  -  -  Fix footer\n",
        "",
        0,
    )


def test_ut_a09_other_file_and_missing_file(
    tmp_path: Path, deck: Path, service: RequestService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service.queue(deck, "x", None)
    make_deck(tmp_path, "deck2.html")
    assert run_cli("requests", "deck2.html") == ("No requests for deck2.html\n", "", 0)
    assert run_cli("requests", "ghost.html") == ("", "error: File not found: ghost.html\n", 1)


def test_ut_a09_symlink_shares_the_record_and_a_rename_starts_empty(
    tmp_path: Path, deck: Path, service: RequestService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service.queue(deck, "Shorten the title", "slide-3")
    service.queue(deck, "Fix footer", None)
    (tmp_path / "alias.html").symlink_to(deck)
    out, _, code = run_cli("requests", "alias.html")
    assert (out, code) == ("R-0001  pending  slide-3  -  Shorten the title\nR-0002  pending  -  -  Fix footer\n", 0)
    deck.rename(tmp_path / "moved.html")
    assert run_cli("requests", "moved.html")[0] == "No requests for moved.html\n"


def test_the_command_shows_every_status_and_a_storage_error(
    tmp_path: Path, deck: Path, store: RequestStore, service: RequestService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service.queue(deck, "a\nb", "s1")
    set_status(store, deck, 0, "done")
    assert run_cli("requests", "deck.html")[0] == "R-0001  done  s1  -  a b\n"
    (store.record_dir(deck) / "record.json").write_bytes(b"{not json")
    out, err, code = run_cli("requests", "deck.html")
    assert out == ""
    assert err.startswith("error: Requests record of ")
    assert code == 1


# ---------------------------------------------------------------------------
# UT-A10: requests_revision and no file next to the deck
# ---------------------------------------------------------------------------


def test_ut_a10_requests_revision_follows_the_record(served_deck: ServedDeck) -> None:
    before = served_deck.status()
    assert before["requests_revision"] == 0
    assert {"mtime", "update_in_progress", "update_expires_in", "filename", "poll_interval", "port"} <= set(before)
    queue_over_http(served_deck, "one")
    assert served_deck.status()["requests_revision"] == 1
    post(served_deck, "/requests/delete", {"id": "R-0001"})
    assert served_deck.status()["requests_revision"] == 2
    assert sorted(entry.name for entry in served_deck.path.parent.iterdir()) == ["deck.html"]


def test_requests_of_two_files_are_kept_apart(tmp_path: Path, service: RequestService) -> None:
    first, second = make_deck(tmp_path, "a.html"), make_deck(tmp_path, "b.html")
    service.queue(first, "for a", None)
    assert service.list_requests(second) == []
    assert service.queue(second, "for b", None).id == "R-0001"
    assert [r.instruction for r in service.list_requests(first)] == ["for a"]
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["a.html", "b.html"]


def test_build_request_service_uses_the_configured_state_directory(deck: Path) -> None:
    build_request_service().queue(deck, "x", None)
    assert (config.state_dir() / "files" / expected_key(deck) / "requests" / "record.json").is_file()
