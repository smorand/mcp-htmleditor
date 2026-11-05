"""Exploit and non regression tests for SPEC-0013 US-0072: the length of the ``POST /arch-layout`` body.

Bug (BUG-002): the layout route converted ``Content-Length`` with ``int()`` and read that many bytes, so ``abc``,
``-5`` or a 20 digit value closed the connection with a traceback and a declared body that never came held the
handler. Every request is a raw socket exchange; "unchanged" is checked on ``deck.html``, not on the answer.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page

from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import BOOTSTRAP
from tests.http_support import RawReply, exchange, json_body

SECRET = "ORIGINAL-SECRET"  # noqa: S105 - a marker, not a credential
DIAGRAM = (
    '<div data-type="arch-diagram" data-diagram-id="d1"><div data-type="arch-row" data-row="0">'
    '<div data-type="arch-node" data-id="a" data-label="A"></div>'
    '<div data-type="arch-node" data-id="b" data-label="B"></div></div></div>'
)
INVALID = {"error": "Invalid Content-Length"}
TOO_LARGE = {"error": "Request too large"}
PROMPT = 2.0
Serve = Callable[[Path], ServedDeck]


@pytest.fixture
def deck(tmp_path: Path, serve_deck: Serve) -> ServedDeck:
    folder = tmp_path / "work"
    folder.mkdir()
    html = (BOOTSTRAP / "slides-empty.html").read_text(encoding="utf-8")
    html = re.sub(r"<title>.*?</title>", f"<title>{SECRET}</title>", html, count=1)
    html = html.replace("</body>", f"{DIAGRAM}\n</body>")
    path = folder / "deck.html"
    path.write_text(html, encoding="utf-8")
    return serve_deck(path)


def post_layout(deck: ServedDeck, headers: list[str], body: bytes = b"") -> RawReply:
    lines = [f"Host: 127.0.0.1:{deck.port}", *headers]
    head = "POST /arch-layout HTTP/1.1\r\n" + "".join(f"{line}\r\n" for line in lines) + "\r\n"
    return exchange(deck.port, head.encode("iso-8859-1") + body, timeout=PROMPT)


def assert_refused(reply: RawReply, status: int, payload: dict[str, str]) -> None:
    assert reply.status == status, reply.raw[:300]
    assert json_body(reply) == payload
    assert reply.elapsed < PROMPT


def assert_untouched(deck: ServedDeck, before: bytes, caplog: pytest.LogCaptureFixture) -> None:
    after = deck.path.read_bytes()
    assert after == before
    assert b"data-x" not in after
    assert not any("Traceback" in r.getMessage() or r.exc_info for r in caplog.records)


def test_bt_002_invalid_layout_length_is_answered(deck: ServedDeck, caplog: pytest.LogCaptureFixture) -> None:
    """BT-002 and the BR-013 log line: the literal payload of BUG-002."""
    before = deck.path.read_bytes()
    caplog.set_level(logging.WARNING, logger="mcp_htmleditor.http_server")
    mark = len(caplog.records)

    reply = post_layout(deck, ["Content-Length: abc"])

    assert_refused(reply, 400, INVALID)
    assert_untouched(deck, before, caplog)
    new = [r for r in caplog.records[mark:] if r.name == "mcp_htmleditor.http_server"]
    assert [r.getMessage() for r in new] == ["Refused POST /arch-layout: Invalid Content-Length"]


@pytest.mark.parametrize(
    ("value", "status", "payload"),
    [("-5", 400, INVALID), ("99999999999999999999", 413, TOO_LARGE)],
)
def test_bt_013_negative_and_huge_layout_lengths(
    deck: ServedDeck, caplog: pytest.LogCaptureFixture, value: str, status: int, payload: dict[str, str]
) -> None:
    """BT-013."""
    before = deck.path.read_bytes()
    caplog.set_level(logging.WARNING, logger="mcp_htmleditor.http_server")

    assert_refused(post_layout(deck, [f"Content-Length: {value}"]), status, payload)
    assert_untouched(deck, before, caplog)


def test_bt_014_declared_large_layout_body_is_refused_without_waiting(
    deck: ServedDeck, caplog: pytest.LogCaptureFixture
) -> None:
    """BT-014: 2 000 000 declared, nothing sent."""
    before = deck.path.read_bytes()
    caplog.set_level(logging.WARNING, logger="mcp_htmleditor.http_server")

    assert_refused(post_layout(deck, ["Content-Length: 2000000"]), 413, TOO_LARGE)
    assert_untouched(deck, before, caplog)


@pytest.mark.parametrize(
    ("headers", "body"),
    [
        ([], b""),
        (["Content-Length: 0"], b""),
        (["Content-Length: 007"], b'{"a":1}'),
        (["Content-Length: 1048576"], b"x" * 1_048_576),
    ],
)
def test_bt_021_layout_length_boundaries_served(deck: ServedDeck, headers: list[str], body: bytes) -> None:
    """BT-021: the first four cases."""
    reply = post_layout(deck, headers, body)

    assert reply.status == 200, reply.raw[:300]
    payload = json_body(reply)
    assert payload["ok"] is True
    assert {"diagrams_updated", "warnings"} <= payload.keys()


def test_bt_021_one_byte_above_the_cap(deck: ServedDeck) -> None:
    """BT-021: the last case."""
    before = deck.path.read_bytes()

    assert_refused(post_layout(deck, ["Content-Length: 1048577"]), 413, TOO_LARGE)
    assert deck.path.read_bytes() == before


@needs_chromium
def test_bt_029_bundled_editor_layout_call_still_works(page: Page, deck: ServedDeck) -> None:
    """BT-029: the editor's own call, no body and no content type."""
    page.goto(f"http://127.0.0.1:{deck.port}/")
    status = page.evaluate("() => fetch('/arch-layout', {method: 'POST'}).then(r => r.status)")

    assert status == 200
    html = deck.path.read_text(encoding="utf-8")
    assert len(re.findall(r'data-id="[ab]"[^>]*data-x=|data-x="[^"]*"[^>]*data-id="[ab]"', html)) == 2
