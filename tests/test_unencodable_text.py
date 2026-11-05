"""Exploit tests for SPEC-0013 US-0074 (BUG-003): patch and record writers given text UTF-8 cannot hold.

JSON allows ``"\\ud800"``; the writers decoded it, failed to encode it and printed a traceback or raised
``UnicodeEncodeError``. Every payload below holds the escape as six ASCII characters. "Unchanged" is checked on the
file bytes, its folder (no temporary file), its history, the review and the request record (bytes and revision).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor import config
from tests.conftest import ServedDeck
from tests.deck_support import BOOTSTRAP, call_tool, run_cli
from tests.http_support import exchange, json_body

REPO = Path(__file__).resolve().parents[1]
SECRET = "ORIGINAL-SECRET"  # noqa: S105 - a marker, not a credential
UNENCODABLE = "Text cannot be encoded as UTF-8"
REFUSED = (f"error: {UNENCODABLE}\n", 1)
SET_TITLE = '[{"op":"set_text","id":"slide-0","selector":"h1","text":"T\\ud800"}]'
SLIDE = '<article class="slide" data-type="slide" data-id="slide-9" data-title="T\\ud800"><h1>X\\ud800</h1></article>'


@dataclass(frozen=True)
class Frozen:
    deck_bytes: bytes
    folder: list[str]
    history: str


def tree(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.exists() else []


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {str(p): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()} if root.exists() else {}


@pytest.fixture
def deck(tmp_path: Path) -> Path:
    path = tmp_path / "work" / "deck.html"
    path.parent.mkdir(parents=True)
    html = (BOOTSTRAP / "slides-empty.html").read_text(encoding="utf-8")
    path.write_text(re.sub(r"<title>.*?</title>", f"<title>{SECRET}</title>", html, count=1), encoding="utf-8")
    return path


def freeze(deck: Path) -> Frozen:
    history, _, code = run_cli("history", str(deck))
    assert code == 0
    return Frozen(deck.read_bytes(), sorted(entry.name for entry in deck.parent.iterdir()), history)


def ops_file(tmp_path: Path, raw: str) -> Path:
    path = tmp_path / "ops" / "ops.json"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(raw.encode("ascii"))
    return path


def assert_unchanged(deck: Path, before: Frozen) -> None:
    assert freeze(deck) == before
    assert before.history == f"No history for {deck}\n"
    assert SECRET in deck.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# BT-016, BT-017, BT-036: patch
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flags", [(), ("--dry-run",)])
def test_bt_016_patch_command_refuses_a_lone_surrogate(tmp_path: Path, deck: Path, flags: tuple[str, ...]) -> None:
    ops = ops_file(tmp_path, SET_TITLE)
    before = freeze(deck)
    stdout, stderr, code = run_cli("patch", str(deck), "--ops", str(ops), *flags)
    assert (stdout, stderr, code) == ("", *REFUSED)
    assert "Traceback" not in stderr
    assert_unchanged(deck, before)


def test_bt_017_patch_tool_refuses_a_lone_surrogate(deck: Path) -> None:
    before = freeze(deck)
    ops = json.loads(SET_TITLE)
    assert call_tool("patch", file=str(deck), ops=ops) == (False, UNENCODABLE)
    assert call_tool("patch", file=str(deck), ops=ops, dry_run=True) == (False, UNENCODABLE)  # type: ignore[arg-type]
    assert_unchanged(deck, before)


@pytest.mark.parametrize(
    "operation",
    [
        f'{{"op":"replace_slide","id":"slide-0","html":"{SLIDE.replace(chr(34), chr(92) + chr(34))}"}}',
        f'{{"op":"insert_slide","after":"slide-0","html":"{SLIDE.replace(chr(34), chr(92) + chr(34))}"}}',
    ],
)
def test_bt_036_slide_replacement_and_insertion_refuse_a_lone_surrogate(
    tmp_path: Path, deck: Path, operation: str
) -> None:
    raw = f"[{operation}]"
    ops = ops_file(tmp_path, raw)
    before = freeze(deck)
    stdout, stderr, code = run_cli("patch", str(deck), "--ops", str(ops))
    assert (stdout, stderr, code) == ("", *REFUSED)
    assert "Traceback" not in stderr
    assert call_tool("patch", file=str(deck), ops=json.loads(raw)) == (False, UNENCODABLE)
    assert_unchanged(deck, before)


def test_whole_patch_is_refused_when_only_a_later_operation_is_unencodable(tmp_path: Path, deck: Path) -> None:
    raw = '[{"op":"set_text","id":"slide-0","selector":"h1","text":"Fine"},' + SET_TITLE[1:]
    before = freeze(deck)
    assert run_cli("patch", str(deck), "--ops", str(ops_file(tmp_path, raw))) == ("", *REFUSED)
    assert_unchanged(deck, before)


# ---------------------------------------------------------------------------
# BT-018: review writes
# ---------------------------------------------------------------------------

REVIEW = '[{"id":"a","slide":null,"title":"t\\ud800","why":"w","change":"c"}]'


@pytest.mark.parametrize("field", ["id", "slide", "title", "why", "change"])
def test_bt_018_review_writes_refuse_a_lone_surrogate_in_any_field(tmp_path: Path, deck: Path, field: str) -> None:
    suggestion: dict[str, Any] = {"id": "a", "slide": None, "title": "t", "why": "w", "change": "c"}
    suggestion[field] = "x\ud800"
    state = config.state_dir()
    folder_before, state_before = tree(deck.parent), tree_bytes(state)
    assert call_tool("write_review", file=str(deck), suggestions=[suggestion]) == (False, UNENCODABLE)
    path = tmp_path / "ops" / "rev.json"
    path.parent.mkdir()
    path.write_bytes(json.dumps([suggestion]).encode("ascii"))  # json.dumps escapes the surrogate
    stdout, stderr, code = run_cli("review", str(deck), "--write", str(path))
    assert (stdout, stderr, code) == ("", *REFUSED)
    assert "Traceback" not in stderr
    assert run_cli("review", str(deck)) == (f"No review for {deck}\n", "", 0)
    assert tree(deck.parent) == folder_before
    assert tree_bytes(state) == state_before


def test_bt_018_literal_payload(tmp_path: Path, deck: Path) -> None:
    path = tmp_path / "ops" / "rev.json"
    path.parent.mkdir()
    path.write_bytes(REVIEW.encode("ascii"))
    state_before = tree_bytes(config.state_dir())
    assert run_cli("review", str(deck), "--write", str(path)) == ("", *REFUSED)
    assert call_tool("write_review", file=str(deck), suggestions=json.loads(REVIEW)) == (False, UNENCODABLE)
    assert tree_bytes(config.state_dir()) == state_before


def test_shape_messages_keep_precedence_over_the_encodability_check(deck: Path) -> None:
    assert call_tool("write_review", file=str(deck), suggestions="x\ud800") == (  # type: ignore[arg-type]
        False,
        "Review must be a list of suggestions",
    )
    missing = [{"id": "a\ud800", "slide": None, "title": "t", "why": "w"}]
    assert call_tool("write_review", file=str(deck), suggestions=missing) == (
        False,
        'Suggestion 1: missing field "change"',
    )


# ---------------------------------------------------------------------------
# BT-019: request completion
# ---------------------------------------------------------------------------


def requests_of(served: ServedDeck) -> dict[str, Any]:
    reply = exchange(served.port, f"GET /requests HTTP/1.1\r\nHost: 127.0.0.1:{served.port}\r\n\r\n".encode())
    body: dict[str, Any] = json_body(reply)
    return body


def queue_two(served: ServedDeck) -> None:
    for text in ("one", "two"):
        body = json.dumps({"instruction": text}).encode()
        head = (
            f"POST /requests HTTP/1.1\r\nHost: 127.0.0.1:{served.port}\r\n"
            f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
        )
        assert exchange(served.port, head.encode() + body).status == 200


def test_bt_019_request_completion_refuses_an_unencodable_reason(tmp_path: Path, served_deck: ServedDeck) -> None:
    queue_two(served_deck)
    deck = str(served_deck.path)
    listed, state = requests_of(served_deck), config.state_dir()
    state_before = tree_bytes(state)
    assert listed["revision"] == 2
    assert call_tool("complete_request", file=deck, id="R-0001", status="skipped", reason="because \ud800") == (
        False,
        UNENCODABLE,
    )
    assert call_tool("complete_request", file=deck, id="R-0001", status="done", reason="because \ud800") == (
        False,
        UNENCODABLE,
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO / "src"),
        "HTMLEDITOR_STATE_DIR": str(state),
        "HTMLEDITOR_LOG_DIR": str(tmp_path / "logs"),
        "HTMLEDITOR_CACHE_DIR": str(tmp_path / "cache"),
    }
    argv = [sys.executable, "-m", "mcp_htmleditor", "request-skip", deck.encode(), b"R-0002", b"--reason", b"bad \xff"]
    done = subprocess.run(argv, env=env, capture_output=True, timeout=120, cwd=REPO, check=False)  # type: ignore[call-overload]  # noqa: S603
    assert (done.stdout, done.stderr.decode(), done.returncode) == (b"", f"error: {UNENCODABLE}\n", 1)
    assert b"Traceback" not in done.stderr
    assert requests_of(served_deck) == listed
    assert [r["status"] for r in listed["requests"]] == ["pending", "pending"]
    assert tree_bytes(state) == state_before


def test_the_reason_is_checked_before_the_store_is_read(deck: Path) -> None:
    assert call_tool("complete_request", file=str(deck), id="R-0099", status="finished", reason="\ud800") == (
        False,
        UNENCODABLE,
    )


# ---------------------------------------------------------------------------
# BT-030, BT-032: non regression
# ---------------------------------------------------------------------------


def test_bt_030_valid_unicode_is_still_written(tmp_path: Path, deck: Path) -> None:
    raw = '[{"op":"set_text","id":"slide-0","selector":"h1","text":"T\\ud83d\\ude00\\u0000\\u00e9"}]'
    stdout, stderr, code = run_cli("patch", str(deck), "--ops", str(ops_file(tmp_path, raw)))
    assert (stderr, code) == ("", 0)
    assert json.loads(stdout)["changed"] is True
    assert "T\U0001f600\x00\u00e9".encode() in deck.read_bytes()
    review = [{"id": "a", "slide": None, "title": "t\U0001f600", "why": "w\x00", "change": "é"}]
    assert call_tool("write_review", file=str(deck), suggestions=review) == (True, {"ok": True, "count": 1})


def test_bt_032_http_request_routes_keep_their_message(served_deck: ServedDeck) -> None:
    queue_two(served_deck)
    before = requests_of(served_deck)
    for route, body in (
        ("/requests", b'{"instruction":"\\ud800"}'),
        ("/requests/delete", b'{"id":"\\ud800"}'),
        ("/review/apply", b'{"id":"\\ud800"}'),
    ):
        head = (
            f"POST {route} HTTP/1.1\r\nHost: 127.0.0.1:{served_deck.port}\r\n"
            f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
        )
        reply = exchange(served_deck.port, head.encode() + body)
        assert reply.status == 400
        assert json_body(reply) == {"ok": False, "error": "Invalid request body"}
    assert requests_of(served_deck) == before
