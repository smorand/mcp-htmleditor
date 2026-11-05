"""SPEC-0010 US-0057: ``write_review`` (tool and command), ``review`` (command) and the service rules behind them.

Tools run through ``call_tool`` (in process ``fastmcp.Client``), commands through ``run_cli`` (separate streams,
tracing stubbed). A tool error must be the service message with no ``error: `` prefix.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor import config
from mcp_htmleditor.request_service import RequestError, RequestService
from mcp_htmleditor.request_store import RequestStore
from mcp_htmleditor.skill_audit import listed_tools

from .deck_support import call_tool, run_cli
from .test_requests_core import make_deck

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "skill" / "core.md"
S1_LINE = "s1  slide-2  Tighten the agenda\n"
S2_LINE = "s2  -  Add a closing slide\n"


def suggestion(number: int, **changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": f"s{number}",
        "slide": "slide-2",
        "title": "Tighten the agenda",
        "why": "The agenda has 8 lines",
        "change": "Cut to 5 lines",
    }
    return {**base, **changes}


def s2() -> dict[str, Any]:
    return suggestion(
        2, slide=None, title="Add a closing slide", why="The deck ends abruptly", change="Add a thank you slide"
    )


def two() -> list[dict[str, Any]]:
    return [suggestion(1), s2()]


def without(item: dict[str, Any], key: str) -> dict[str, Any]:
    return {name: value for name, value in item.items() if name != key}


@pytest.fixture
def deck(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return make_deck(tmp_path)


@pytest.fixture
def service() -> RequestService:
    return RequestService(RequestStore(config.state_dir()))


def write_json(folder: Path, name: str, payload: object) -> Path:
    path = folder / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def stored_ids(service: RequestService, deck: Path) -> list[str]:
    return [item.id for item in service.read_review(deck)]


# ---------------------------------------------------------------------------
# E2E-015 to E2E-018
# ---------------------------------------------------------------------------


def test_e2e_015_too_many_suggestions(deck: Path, service: RequestService) -> None:
    service.write_review(deck, two())
    seven = [suggestion(n) for n in range(1, 8)]
    ok, message = call_tool("write_review", file=str(deck), suggestions=seven)
    assert (ok, message) == (False, "At most 6 suggestions")
    assert run_cli("review", "deck.html") == (S1_LINE + S2_LINE, "", 0)
    write_json(deck.parent, "seven.json", seven)
    assert run_cli("review", "deck.html", "--write", "seven.json") == ("", "error: At most 6 suggestions\n", 1)
    assert run_cli("review", "deck.html") == (S1_LINE + S2_LINE, "", 0)


def test_e2e_016_title_too_long(deck: Path) -> None:
    long_title = [suggestion(1), suggestion(2, title="t" * 61)]
    message = "Suggestion 2: title is longer than 60 characters"
    assert call_tool("write_review", file=str(deck), suggestions=long_title) == (False, message)
    write_json(deck.parent, "long.json", long_title)
    assert run_cli("review", "deck.html", "--write", "long.json") == ("", f"error: {message}\n", 1)
    assert run_cli("review", "deck.html") == ("No review for deck.html\n", "", 0)
    exact = [suggestion(1), suggestion(2, title="t" * 60)]
    assert call_tool("write_review", file=str(deck), suggestions=exact) == (True, {"ok": True, "count": 2})


def test_e2e_017_missing_field_and_duplicate_id(deck: Path) -> None:
    cases = [
        ([suggestion(1), s2(), without(suggestion(3), "change")], 'Suggestion 3: missing field "change"'),
        ([suggestion(1), suggestion(2, id="s1")], 'Suggestion 2: duplicate id "s1"'),
    ]
    for position, (review, message) in enumerate(cases):
        assert call_tool("write_review", file=str(deck), suggestions=review) == (False, message)
        write_json(deck.parent, f"case{position}.json", review)
        assert run_cli("review", "deck.html", "--write", f"case{position}.json") == ("", f"error: {message}\n", 1)


def test_e2e_018_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    message = "File not found: ghost.html"
    assert run_cli("requests", "ghost.html") == ("", f"error: {message}\n", 1)
    assert call_tool("list_requests", file="ghost.html") == (False, message)
    assert call_tool("complete_request", file="ghost.html", id="R-0001", status="done") == (False, message)
    assert call_tool("write_review", file="ghost.html", suggestions=[suggestion(1)]) == (False, message)
    assert run_cli("review", "ghost.html") == ("", f"error: {message}\n", 1)
    assert run_cli("review", "ghost.html", "--write", "s.json") == ("", f"error: {message}\n", 1)


def test_independent_test_two_valid_suggestions(deck: Path) -> None:
    assert call_tool("write_review", file=str(deck), suggestions=two()) == (True, {"ok": True, "count": 2})
    assert run_cli("review", "deck.html") == (S1_LINE + S2_LINE, "", 0)


# ---------------------------------------------------------------------------
# UT-F01 to UT-F07
# ---------------------------------------------------------------------------


def message_of(service: RequestService, deck: Path, raw: object) -> str:
    with pytest.raises(RequestError) as caught:
        service.write_review(deck, raw)
    assert caught.value.kind == "invalid"
    return caught.value.message


def test_ut_f01_check_order(deck: Path, service: RequestService) -> None:
    faulty = [without(suggestion(n), "why") for n in range(1, 8)]
    assert message_of(service, deck, faulty) == "At most 6 suggestions"
    missing_then_long = [suggestion(1), without(suggestion(2), "why"), suggestion(3, title="t" * 61)]
    assert message_of(service, deck, missing_then_long) == 'Suggestion 2: missing field "why"'
    both = [without(suggestion(1, title="t" * 61), "why")]
    assert message_of(service, deck, both) == 'Suggestion 1: missing field "why"'
    long_and_duplicate = [suggestion(1), suggestion(2, id="s1", title="t" * 61)]
    assert message_of(service, deck, long_and_duplicate) == "Suggestion 2: title is longer than 60 characters"
    in_field_order = [{"id": "s1", "slide": 3, "title": "", "why": "", "change": ""}]
    assert message_of(service, deck, in_field_order) == 'Suggestion 1: missing field "slide"'


def test_ut_f02_field_rules(deck: Path, service: RequestService) -> None:
    assert service.write_review(deck, [suggestion(1, slide=None)]) == 1
    cases: list[tuple[object, str]] = [
        ([suggestion(1, slide=3)], 'Suggestion 1: missing field "slide"'),
        ([without(suggestion(1), "slide")], 'Suggestion 1: missing field "slide"'),
        ([suggestion(1, why="  \u3000 ")], 'Suggestion 1: missing field "why"'),
        ([suggestion(1, id="")], 'Suggestion 1: missing field "id"'),
        ([suggestion(1, title=None)], 'Suggestion 1: missing field "title"'),
        ([suggestion(1, change=5)], 'Suggestion 1: missing field "change"'),
        (["s1"], 'Suggestion 1: missing field "id"'),
        ({}, "Review must be a list of suggestions"),
        (None, "Review must be a list of suggestions"),
    ]
    for raw, message in cases:
        assert message_of(service, deck, raw) == message
    assert stored_ids(service, deck) == ["s1"]
    assert service.write_review(deck, [suggestion(1, why="\x1c\x1d x")]) == 1
    assert service.write_review(deck, [{**suggestion(1), "extra": "kept?"}]) == 1
    [stored] = service.read_review(deck)
    assert not hasattr(stored, "extra")
    assert stored == replace(stored, applied=False)
    raw_record = next(Path(config.state_dir()).rglob("record.json")).read_text(encoding="utf-8")
    assert "extra" not in raw_record


def test_ut_f02_empty_review_is_stored_empty(deck: Path, service: RequestService) -> None:
    assert service.write_review(deck, []) == 0
    assert service.read_review(deck) == []
    assert RequestStore(config.state_dir()).read(deck).review == []


def test_ut_f03_applied_state_belongs_to_the_review(deck: Path, service: RequestService) -> None:
    service.write_review(deck, two())
    store = RequestStore(config.state_dir())

    def apply(record: Any) -> None:
        record.review = [replace(item, applied=item.id == "s1") for item in record.review]

    store.update(deck, "apply", apply)
    request = service.queue(deck, "from s1", "slide-2")
    assert [item.applied for item in service.read_review(deck)] == [True, False]
    service.write_review(deck, [suggestion(1)])
    [again] = service.read_review(deck)
    assert (again.id, again.applied) == ("s1", False)
    assert [item.id for item in service.list_requests(deck)] == [request.id]


def test_ut_f04_review_output(deck: Path, service: RequestService) -> None:
    assert run_cli("review", "deck.html") == ("No review for deck.html\n", "", 0)
    service.write_review(deck, two())
    assert run_cli("review", "deck.html") == (S1_LINE + S2_LINE, "", 0)
    service.write_review(deck, [])
    assert run_cli("review", "deck.html") == ("No review for deck.html\n", "", 0)


def test_ut_f05_write_sources_and_errors(deck: Path) -> None:
    write_json(deck.parent, "review.json", two())
    assert run_cli("review", "deck.html", "--write", "review.json") == ("Review written: 2 suggestions\n", "", 0)
    stdin = json.dumps(two())
    assert run_cli("review", "deck.html", "--write", "-", input=stdin) == ("Review written: 2 suggestions\n", "", 0)
    write_json(deck.parent, "one.json", [suggestion(1)])
    assert run_cli("review", "deck.html", "--write", "one.json") == ("Review written: 1 suggestions\n", "", 0)
    stdout, stderr, status = run_cli("review", "deck.html", "--write", "nope.json")
    assert (stdout, status) == ("", 1)
    assert stderr.startswith("error: Cannot read nope.json: ")
    assert len(stderr.strip()) > len("error: Cannot read nope.json: ")
    (deck.parent / "bad.json").write_text("{", encoding="utf-8")
    stdout, stderr, status = run_cli("review", "deck.html", "--write", "bad.json")
    assert (stdout, status) == ("", 1)
    assert stderr.startswith("error: Invalid JSON: ")
    assert len(stderr.strip()) > len("error: Invalid JSON: ")
    assert run_cli("review", "deck.html", "--write", "-", input="{}") == (
        "",
        "error: Review must be a list of suggestions\n",
        1,
    )
    stdout, stderr, status = run_cli("review", "deck.html", "--write", "-", input="{")
    assert (stdout, status) == ("", 1)
    assert stderr.startswith("error: Invalid JSON: ")


def test_ut_f06_storage_failure_keeps_the_old_review(deck: Path, service: RequestService) -> None:
    service.write_review(deck, [suggestion(1)])
    directory = RequestStore(config.state_dir()).record_dir(deck)
    moved = directory.with_name("requests-away")
    directory.rename(moved)
    directory.write_text("in the way", encoding="utf-8")
    try:
        with pytest.raises(RequestError) as caught:
            service.write_review(deck, two())
        assert caught.value.kind == "storage"
        assert caught.value.message.startswith("Could not write the review: ")
    finally:
        directory.unlink()
        shutil.move(str(moved), str(directory))
    assert stored_ids(service, deck) == ["s1"]


def test_ut_f07_skill_audit_lists_write_review() -> None:
    stdout, _, status = run_cli("skill-audit")
    assert status == 0, stdout
    assert "write_review" in listed_tools(CORE.read_text(encoding="utf-8"))
