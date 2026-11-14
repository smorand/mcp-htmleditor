"""Request loop additions: ``position`` and filters on ``list_requests``, and the ``clear_requests`` wipe."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_htmleditor import config
from mcp_htmleditor.request_service import RequestError, RequestService
from mcp_htmleditor.request_store import RequestStore

from .deck_support import call_tool, run_cli


def slide(slide_id: str) -> str:
    return f'<section data-type="slide" data-id="{slide_id}" data-title="{slide_id}"><h1>{slide_id}</h1></section>'


def write_deck(path: Path, ids: list[str]) -> None:
    body = "".join(slide(i) for i in ids)
    path.write_text(f'<!DOCTYPE html><html data-doc-type="presentation"><body>{body}</body></html>', encoding="utf-8")


@pytest.fixture
def service() -> RequestService:
    return RequestService(RequestStore(config.state_dir()))


@pytest.fixture
def deck(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "deck.html"
    write_deck(path, ["a", "b", "c"])
    return path


def positions(deck: Path, **filters: str) -> list[tuple[str, int | None]]:
    ok, result = call_tool("list_requests", file=str(deck), **filters)
    assert ok, result
    return [(r["id"], r["position"]) for r in result["requests"]]


def test_position_follows_reorder_and_deletion(deck: Path, service: RequestService) -> None:
    service.queue(deck, "one", "c")
    service.queue(deck, "two", "a")
    service.queue(deck, "three", None)
    service.queue(deck, "four", "ghost")
    assert positions(deck) == [("R-0001", 3), ("R-0002", 1), ("R-0003", None), ("R-0004", None)]
    write_deck(deck, ["c", "a", "b"])
    assert positions(deck)[:2] == [("R-0001", 1), ("R-0002", 2)]
    write_deck(deck, ["b", "a"])
    assert positions(deck)[:2] == [("R-0001", None), ("R-0002", 2)]


def test_position_is_not_stored(deck: Path, service: RequestService) -> None:
    service.queue(deck, "one", "c")
    assert not hasattr(service.list_requests(deck)[0], "position")


def test_position_none_for_a_document(tmp_path: Path, service: RequestService) -> None:
    path = tmp_path / "doc.html"
    path.write_text("<!DOCTYPE html><html><body><p>x</p></body></html>", encoding="utf-8")
    service.queue(path, "one", "a")
    assert positions(path) == [("R-0001", None)]


def test_filters(deck: Path, service: RequestService) -> None:
    service.queue(deck, "one", "a")
    service.queue(deck, "two", "b")
    service.queue(deck, "three", "a")
    service.complete(deck, "R-0003", "done", None)
    assert positions(deck, slide="a") == [("R-0001", 1), ("R-0003", 1)]
    assert positions(deck, status="pending") == [("R-0001", 1), ("R-0002", 2)]
    assert positions(deck, slide="a", status="done") == [("R-0003", 1)]
    assert positions(deck, slide="zz") == []


def test_invalid_status(deck: Path, service: RequestService) -> None:
    ok, message = call_tool("list_requests", file=str(deck), status="open")
    assert not ok
    assert "Status must be pending, done or skipped" in str(message)
    assert run_cli("requests", "deck.html", "--status", "open") == (
        "",
        "error: Status must be pending, done or skipped\n",
        1,
    )
    with pytest.raises(RequestError):
        service.list_positioned(deck, None, "open")


def test_cli_line_and_filters(deck: Path, service: RequestService) -> None:
    service.queue(deck, "one", "b")
    service.queue(deck, "two", None)
    service.queue(deck, "three", "ghost")
    assert run_cli("requests", "deck.html") == (
        "R-0001  pending  b  2  one\nR-0002  pending  -  -  two\nR-0003  pending  ghost  -  three\n",
        "",
        0,
    )
    assert run_cli("requests", "deck.html", "--slide", "b") == ("R-0001  pending  b  2  one\n", "", 0)
    assert run_cli("requests", "deck.html", "--status", "done")[0] == "No requests for deck.html\n"


def seed(deck: Path, service: RequestService) -> None:
    for text in ("one", "two", "three"):
        service.queue(deck, text, None)
    service.complete(deck, "R-0001", "done", None)
    service.complete(deck, "R-0002", "skipped", "no")


def test_clear_finished_keeps_pending(deck: Path, service: RequestService) -> None:
    seed(deck, service)
    assert service.clear(deck, "finished") == 2
    assert [r.id for r in service.list_requests(deck)] == ["R-0003"]


def test_clear_all(deck: Path, service: RequestService) -> None:
    seed(deck, service)
    assert service.clear(deck, "all") == 3
    assert service.list_requests(deck) == []


def test_clear_nothing_keeps_the_revision(deck: Path, service: RequestService) -> None:
    service.queue(deck, "one", None)
    before = service.revision(deck)
    assert service.clear(deck, "finished") == 0
    assert service.revision(deck) == before
    assert service.clear(deck, "all") == 1
    assert service.revision(deck) == before + 1


def test_clear_bad_scope(deck: Path, service: RequestService) -> None:
    with pytest.raises(RequestError) as caught:
        service.clear(deck, "pending")
    assert caught.value.message == "Scope must be finished or all"


def test_clear_tool(deck: Path, service: RequestService) -> None:
    seed(deck, service)
    assert call_tool("clear_requests", file=str(deck)) == (True, {"ok": True, "removed": 2})
    assert call_tool("clear_requests", file=str(deck), scope="all") == (True, {"ok": True, "removed": 1})
    ok, message = call_tool("clear_requests", file=str(deck), scope="x")
    assert not ok
    assert "Scope must be finished or all" in str(message)
    ok, message = call_tool("clear_requests", file=str(deck.parent / "nope.html"))
    assert not ok
    assert "File not found" in str(message)


def test_clear_cli(deck: Path, service: RequestService) -> None:
    seed(deck, service)
    assert run_cli("request-clear", "deck.html") == ("removed 2\n", "", 0)
    assert run_cli("request-clear", "deck.html") == ("removed 0\n", "", 0)
    assert run_cli("request-clear", "deck.html", "--all") == ("removed 1\n", "", 0)
    assert run_cli("request-clear", "nope.html")[2] == 1
