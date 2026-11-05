"""Exploit tests for SPEC-0013 US-0073 (BUG-003): a save holding a lone surrogate.

JSON allows ``"\\ud800"``; the server decoded it, failed to encode it, closed the connection with no answer and
logged a traceback. Every request is a raw socket exchange; the bodies hold the escape as six ASCII characters.
"Unchanged" is checked on the file bytes, its folder (no temporary file), its history and the request revision.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.conftest import ServedDeck
from tests.deck_support import BOOTSTRAP, run_cli
from tests.http_support import RawReply, exchange, json_body

SECRET = "ORIGINAL-SECRET"  # noqa: S105 - a marker, not a credential
UNENCODABLE = "Text cannot be encoded as UTF-8"
LONE_HIGH = b'{"html":"<html>\\ud800"}'
JSON_TYPE = "Content-Type: application/json"
Serve = Callable[[Path], ServedDeck]


@dataclass(frozen=True)
class Frozen:
    deck_bytes: bytes
    folder: list[str]
    history: str
    revision: int


@dataclass(frozen=True)
class Editor:
    deck: ServedDeck

    @property
    def local(self) -> str:
        return f"127.0.0.1:{self.deck.port}"

    def post(self, route: str, body: bytes, headers: list[str] | None = None) -> RawReply:
        lines = headers if headers is not None else [f"Host: {self.local}", JSON_TYPE, f"Content-Length: {len(body)}"]
        head = f"POST {route} HTTP/1.1\r\n" + "".join(f"{line}\r\n" for line in lines) + "\r\n"
        return exchange(self.deck.port, head.encode("iso-8859-1") + body)

    def save(self, body: bytes) -> RawReply:
        return self.post("/content", body)

    def freeze(self) -> Frozen:
        path = self.deck.path
        history, _, code = run_cli("history", str(path))
        assert code == 0
        reply = exchange(self.deck.port, f"GET /requests HTTP/1.1\r\nHost: {self.local}\r\n\r\n".encode())
        return Frozen(
            deck_bytes=path.read_bytes(),
            folder=sorted(entry.name for entry in path.parent.iterdir()),
            history=history,
            revision=int(json_body(reply)["revision"]),
        )


def _write_deck(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    html = (BOOTSTRAP / "slides-empty.html").read_text(encoding="utf-8")
    path.write_text(re.sub(r"<title>.*?</title>", f"<title>{SECRET}</title>", html, count=1), encoding="utf-8")
    return path


@pytest.fixture
def editor(tmp_path: Path, serve_deck: Serve) -> Editor:
    return Editor(serve_deck(_write_deck(tmp_path / "work" / "deck.html")))


def assert_refused(reply: RawReply, error: str) -> None:
    assert reply.status == 400, reply.raw[:300]
    assert json_body(reply) == {"error": error}


def test_bt_004_lone_surrogate_save_gets_an_answer(editor: Editor, caplog: pytest.LogCaptureFixture) -> None:
    """BT-004: the literal payload of BUG-003."""
    before = editor.freeze()
    caplog.set_level(logging.WARNING, logger="mcp_htmleditor.http_server")

    reply = editor.save(LONE_HIGH)

    assert_refused(reply, UNENCODABLE)
    assert editor.freeze() == before
    assert "Traceback" not in caplog.text
    assert all(r.exc_info is None for r in caplog.records)
    assert SECRET in editor.deck.path.read_text(encoding="utf-8")


@pytest.mark.parametrize("body", [b'{"html":"<html>\\udc00"}', b'{"html":"<html>\\ud83dX</html>"}'])
def test_bt_024_variants(editor: Editor, body: bytes) -> None:
    """BT-024: a lone low surrogate and a split pair."""
    before = editor.freeze()
    assert_refused(editor.save(body), UNENCODABLE)
    assert editor.freeze() == before


def test_bt_024_refusal_outranks_the_template_check(tmp_path: Path, serve_deck: Serve) -> None:
    """BT-024: under templates/bootstrap/ the unencodable save is 400, not 403."""
    deck = Editor(serve_deck(_write_deck(tmp_path / "work" / "templates" / "bootstrap" / "deck.html")))
    before = deck.freeze()
    assert_refused(deck.save(LONE_HIGH), UNENCODABLE)
    assert deck.freeze() == before


def test_bt_025_refusal_log_lines(editor: Editor, caplog: pytest.LogCaptureFixture) -> None:
    """BT-025: exactly one warning per refusal, no body, no escape, no traceback."""
    caplog.set_level(logging.WARNING, logger="mcp_htmleditor.http_server")
    mark = len(caplog.records)
    body = b'{"html":"<html><body>PWNED</body></html>"}'

    editor.post(
        "/content", body, [f"Host: {editor.local}", "Host: evil.example", JSON_TYPE, f"Content-Length: {len(body)}"]
    )
    editor.post("/arch-layout", b"{}", [f"Host: {editor.local}", JSON_TYPE, "Content-Length: abc"])
    editor.save(LONE_HIGH)

    new = [r for r in caplog.records[mark:] if r.name == "mcp_htmleditor.http_server"]
    assert [r.getMessage() for r in new] == [
        "Refused POST /content: Duplicate Host header",
        "Refused POST /arch-layout: Invalid Content-Length",
        f"Refused POST /content: {UNENCODABLE}",
    ]
    assert all(r.levelno == logging.WARNING and r.exc_info is None for r in new)
    assert not any(x in r.getMessage() for r in new for x in ("PWNED", "\\ud800", "Traceback"))


@pytest.mark.parametrize("body", [b"[]", b'"text"', b'{"html": 5}'])
def test_bt_028_non_object_body_is_invalid_json(editor: Editor, body: bytes) -> None:
    """BT-028: non regression of the former BL-0015."""
    before = editor.freeze()
    assert_refused(editor.save(body), "Invalid JSON body")
    assert editor.freeze() == before


def test_valid_pair_and_nul_are_still_saved(editor: Editor) -> None:
    """BR-017: a valid pair and U+0000 are written as UTF-8."""
    reply = editor.save(b'{"html":"<html><body>\\ud83d\\ude00\\u0000</body></html>"}')
    assert reply.status == 200, reply.raw[:300]
    assert "😀\x00".encode() in editor.deck.path.read_bytes()
