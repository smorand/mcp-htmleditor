"""Exploit and non regression tests for SPEC-0013 US-0071: the header gate of the editor server.

Bug (BUG-001): the server read only the first ``Host``, ``Origin``, ``Content-Length`` or ``Content-Type`` line,
ignored ``Transfer-Encoding``, accepted ``Host: evil@127.0.0.1:P`` and judged a folded header with the fold inside.
A local non browser client could overwrite the document with a second ``Host`` line.

Every request is a raw socket exchange (``tests.http_support``) so the duplicated and folded lines reach the server
as written. "Unchanged" is checked on other channels than the answer: the bytes of ``deck.html``, its folder, its
history and its request record.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page

from tests.browser_wait import wait_for_js
from tests.conftest import ServedDeck, needs_chromium
from tests.deck_support import BOOTSTRAP, run_cli
from tests.http_support import RawReply, exchange, json_body

SECRET = "ORIGINAL-SECRET"  # noqa: S105 - a marker, not a credential
SAVE_BODY = b'{"html":"<html><body>PWNED</body></html>"}'
REQUEST_BODY = b'{"instruction":"PWNED"}'
DIAGRAM = (
    '<div data-type="arch-diagram" data-diagram-id="d1"><div data-type="arch-row" data-row="0">'
    '<div data-type="arch-node" data-id="a" data-label="A"></div>'
    '<div data-type="arch-node" data-id="b" data-label="B"></div></div></div>'
)
JSON_TYPE = "Content-Type: application/json"
FIRST_ZONE_EDITABLE_EXPRESSION = (
    "() => { const d = document.getElementById('content-frame').contentDocument;"
    " const h = d && d.querySelector('[data-editable~=\"text\"]'); return !!h && h.isContentEditable; }"
)
SAVED_DOT_EXPRESSION = "() => getComputedStyle(document.getElementById('toolbar-status')).color"
SAVED_DOT_COLOR = "rgb(66, 190, 101)"
Serve = Callable[[Path], ServedDeck]


@dataclass(frozen=True)
class Gate:
    deck: ServedDeck

    @property
    def port(self) -> int:
        return self.deck.port

    @property
    def local(self) -> str:
        return f"127.0.0.1:{self.deck.port}"

    def send(self, method: str, path: str, headers: list[str], body: bytes = b"") -> RawReply:
        """Send a request whose header lines are written exactly as given."""
        head = f"{method} {path} HTTP/1.1\r\n" + "".join(f"{line}\r\n" for line in headers) + "\r\n"
        return exchange(self.port, head.encode("iso-8859-1") + body)

    def revision(self) -> int:
        reply = self.send("GET", "/requests", [f"Host: {self.local}"])
        assert reply.status == 200
        return int(json_body(reply)["revision"])


@dataclass(frozen=True)
class Frozen:
    """Everything a refused request must leave alone."""

    deck_bytes: bytes
    folder: list[str]
    history: str
    revision: int


def freeze(gate: Gate) -> Frozen:
    deck = gate.deck.path
    history, _, code = run_cli("history", str(deck))
    assert code == 0
    return Frozen(
        deck_bytes=deck.read_bytes(),
        folder=sorted(entry.name for entry in deck.parent.iterdir()),
        history=history,
        revision=gate.revision(),
    )


def assert_frozen(gate: Gate, before: Frozen) -> None:
    after = freeze(gate)
    assert after.deck_bytes == before.deck_bytes
    assert b"PWNED" not in after.deck_bytes
    assert after.folder == before.folder
    assert after.history == before.history
    assert after.revision == before.revision


def assert_refused(reply: RawReply, error: str) -> None:
    assert reply.status == 400, reply.raw[:300]
    assert json_body(reply) == {"error": error}
    assert SECRET.encode() not in reply.raw


@pytest.fixture
def gate(tmp_path: Path, serve_deck: Serve) -> Gate:
    folder = tmp_path / "work"
    folder.mkdir()
    html = (BOOTSTRAP / "slides-empty.html").read_text(encoding="utf-8")
    html = re.sub(r"<title>.*?</title>", f"<title>{SECRET}</title>", html, count=1)
    html = html.replace("</body>", f"{DIAGRAM}\n</body>")
    path = folder / "deck.html"
    path.write_text(html, encoding="utf-8")
    return Gate(serve_deck(path))


def save_request(gate: Gate, headers: list[str], body: bytes = SAVE_BODY) -> RawReply:
    return gate.send("POST", "/content", headers, body)


# --- exploits: duplicated and ambiguous headers ------------------------------------------------------------


def test_bt_001_save_with_local_then_foreign_host(gate: Gate, caplog: pytest.LogCaptureFixture) -> None:
    """BT-001 and the BR-013 log line: the literal payload of BUG-001."""
    before = freeze(gate)
    caplog.set_level(logging.WARNING, logger="mcp_htmleditor.http_server")
    mark = len(caplog.records)

    reply = save_request(
        gate,
        [f"Host: {gate.local}", "Host: evil.example", JSON_TYPE, "Content-Length: 42"],
    )

    assert len(SAVE_BODY) == 42
    assert_frozen(gate, before)
    assert reply.status == 400
    assert json_body(reply) == {"error": "Duplicate Host header"}
    assert SECRET in gate.deck.path.read_text(encoding="utf-8")
    new = [r for r in caplog.records[mark:] if r.name == "mcp_htmleditor.http_server"]
    assert [r.getMessage() for r in new] == ["Refused POST /content: Duplicate Host header"]
    assert all(r.levelno == logging.WARNING and r.exc_info is None for r in new)
    assert not any("PWNED" in r.getMessage() or "evil.example" in r.getMessage() for r in new)


def test_bt_005_reverse_host_order_cannot_read(gate: Gate) -> None:
    """BT-005."""
    mtime = gate.deck.status()["mtime"]

    reply = gate.send("GET", "/content", [f"Host: {gate.local}", "Host: evil.example"])

    assert_refused(reply, "Duplicate Host header")
    status = gate.send("GET", "/status", [f"Host: {gate.local}"])
    assert json_body(status)["mtime"] == mtime


def test_bt_006_duplicated_origin(gate: Gate) -> None:
    """BT-006."""
    before = freeze(gate)
    headers = [
        f"Host: {gate.local}",
        f"Origin: http://{gate.local}",
        "Origin: https://evil.example",
        JSON_TYPE,
        "Content-Length: 42",
    ]

    assert_refused(save_request(gate, headers), "Duplicate Origin header")
    assert_frozen(gate, before)


def test_bt_007_duplicated_content_length_on_save(gate: Gate) -> None:
    """BT-007."""
    before = freeze(gate)
    headers = [f"Host: {gate.local}", JSON_TYPE, "Content-Length: 42", "Content-Length: 5"]

    assert_refused(save_request(gate, headers), "Duplicate Content-Length header")
    assert_frozen(gate, before)


def test_bt_008_duplicated_content_length_on_request_route(gate: Gate) -> None:
    """BT-008."""
    before = freeze(gate)
    headers = [f"Host: {gate.local}", JSON_TYPE, "Content-Length: 23", "Content-Length: 2"]

    reply = gate.send("POST", "/requests", headers, REQUEST_BODY)

    assert len(REQUEST_BODY) == 23
    assert_refused(reply, "Duplicate Content-Length header")
    listing = json_body(gate.send("GET", "/requests", [f"Host: {gate.local}"]))
    assert [r for r in listing["requests"] if "PWNED" in str(r)] == []
    stdout, _, _ = run_cli("requests", str(gate.deck.path))
    assert "PWNED" not in stdout
    assert_frozen(gate, before)


@pytest.mark.parametrize(("route", "body"), [("/content", SAVE_BODY), ("/requests", REQUEST_BODY)])
def test_bt_009_duplicated_content_type(gate: Gate, route: str, body: bytes) -> None:
    """BT-009."""
    before = freeze(gate)
    headers = [f"Host: {gate.local}", JSON_TYPE, "Content-Type: text/plain", f"Content-Length: {len(body)}"]

    assert_refused(gate.send("POST", route, headers, body), "Duplicate Content-Type header")
    assert_frozen(gate, before)


def test_bt_010_chunked_body(gate: Gate) -> None:
    """BT-010: with and without a Content-Length next to Transfer-Encoding."""
    before = freeze(gate)
    chunked = b"2a\r\n" + SAVE_BODY + b"\r\n0\r\n\r\n"
    headers = [f"Host: {gate.local}", JSON_TYPE, "Transfer-Encoding: chunked"]

    assert_refused(save_request(gate, headers, chunked), "Transfer-Encoding not supported")
    assert_frozen(gate, before)
    both = [f"Host: {gate.local}", JSON_TYPE, "Content-Length: 42", "Transfer-Encoding: chunked"]
    assert_refused(save_request(gate, both), "Transfer-Encoding not supported")
    assert_frozen(gate, before)


def test_bt_011_host_with_userinfo(gate: Gate) -> None:
    """BT-011."""
    assert_refused(gate.send("GET", "/content", [f"Host: evil@{gate.local}"]), "Invalid Host header")


def test_bt_012_folded_host(gate: Gate) -> None:
    """BT-012."""
    reply = gate.send("GET", "/content", [f"Host: {gate.local}\r\n evil.example"])

    assert_refused(reply, "Invalid header folding")


def test_bt_020_header_check_details(gate: Gate) -> None:
    """BT-020: casing, order of the checks, and the routes outside the gate."""
    before = freeze(gate)
    local = gate.local

    mixed = gate.send("GET", "/content", [f"host: {local}", f"HOST: {local}"])
    assert_refused(mixed, "Duplicate Host header")
    same = gate.send("GET", "/content", [f"Host: {local}", f"Host: {local}", "Origin: https://evil.example"])
    assert_refused(same, "Duplicate Host header")
    folded = save_request(
        gate, [f"Host: {local}", f"Host: {local}", "Origin: http://x\r\n y", JSON_TYPE, "Content-Length: 42"]
    )
    assert_refused(folded, "Invalid header folding")

    health = gate.send("GET", "/health", [f"Host: {local}", "Host: evil.example"])
    assert health.status == 200
    assert sorted(json_body(health)) == sorted(
        ["ok", "status", "pid", "file", "page", "port", "version", "started", "uptime_seconds"]
    )
    options = gate.send("OPTIONS", "/content", [f"Host: {local}", "Host: evil.example"])
    assert options.status == 405
    assert options.headers["allow"] == "GET, POST"
    assert options.body == b""
    no_host = gate.send("GET", "/content", [])
    assert no_host.status == 403
    assert json_body(no_host) == {"error": "forbidden host"}
    put = gate.send("PUT", "/content", [f"Host: {local}", "Host: evil.example"])
    assert put.status == 501

    assert_frozen(gate, before)


# --- BT-035: every protected route refuses each ambiguous header --------------------------------------------

POST_ROUTES: list[tuple[str, bytes]] = [
    ("/content", SAVE_BODY),
    ("/arch-layout", b"{}"),
    ("/requests", REQUEST_BODY),
    ("/requests/delete", b'{"id":"R-0001"}'),
    ("/review/apply", b'{"id":"a"}'),
]
GET_ROUTES = [
    "/",
    "/static/editor.js",
    "/content",
    "/content-frame",
    "/status",
    "/export/pptx",
    "/export/docx",
    "/requests",
    "/nope",
]
REVIEW = '[{"id":"a","slide":null,"title":"t","why":"w","change":"c"}]'


def header_blocks(local: str, length: int | None) -> list[tuple[list[str], str]]:
    """The six header blocks and their error; ``length`` is the body size of a POST route, None for a GET."""
    kind = [JSON_TYPE] if length is not None else []
    size = [f"Content-Length: {length}"] if length is not None else []
    return [
        ([f"Host: {local}", "Host: evil.example", *kind, *size], "Duplicate Host header"),
        (
            [f"Host: {local}", f"Origin: http://{local}", "Origin: https://evil.example", *kind, *size],
            "Duplicate Origin header",
        ),
        (
            [f"Host: {local}", *kind, f"Content-Length: {length or 0}", "Content-Length: 0"],
            "Duplicate Content-Length header",
        ),
        ([f"Host: {local}", JSON_TYPE, "Content-Type: text/plain", *size], "Duplicate Content-Type header"),
        ([f"Host: {local}", "Transfer-Encoding: chunked", *kind, *size], "Transfer-Encoding not supported"),
        ([f"Host: evil@{local}", *kind, *size], "Invalid Host header"),
    ]


@pytest.mark.parametrize(
    ("method", "route", "body"),
    [("POST", route, body) for route, body in POST_ROUTES] + [("GET", route, b"") for route in GET_ROUTES],
    ids=[f"POST {route}" for route, _ in POST_ROUTES] + [f"GET {route}" for route in GET_ROUTES],
)
def test_bt_035_every_route_refuses_each_ambiguous_header(
    gate: Gate, tmp_path: Path, method: str, route: str, body: bytes
) -> None:
    """BT-035: 14 routes x 6 header blocks, the document, the queue and the review stay as they were."""
    deck = gate.deck.path
    keep = b'{"instruction":"keep"}'
    queued = gate.send("POST", "/requests", [f"Host: {gate.local}", JSON_TYPE, f"Content-Length: {len(keep)}"], keep)
    assert queued.status == 200, queued.raw
    rev = tmp_path / "rev.json"
    rev.write_text(REVIEW, encoding="utf-8")
    _, _, code = run_cli("review", str(deck), "--write", str(rev))
    assert code == 0
    before = freeze(gate)
    files = sorted(entry.name for entry in tmp_path.rglob("*"))

    failures: list[str] = []
    for lines, error in header_blocks(gate.local, len(body) if method == "POST" else None):
        reply = gate.send(method, route, lines, body)
        if reply.status != 400 or reply.body[:1] != b"{" or json_body(reply) != {"error": error}:
            failures.append(f"{error!r} got {reply.status} {reply.raw[:120]!r}")
        elif SECRET.encode() in reply.raw or b"PK" in reply.raw:
            failures.append(f"{error!r} leaked content")
    assert failures == []

    assert_frozen(gate, before)
    assert b"data-x" not in deck.read_bytes()
    stdout, _, _ = run_cli("requests", str(deck))
    lines_out = stdout.strip().splitlines()
    assert len(lines_out) == 1
    assert re.match(r"R-0001\s+pending\s", lines_out[0])
    assert "keep" in lines_out[0]
    review_out, _, _ = run_cli("review", str(deck))
    assert review_out.startswith("a  ")
    assert sorted(entry.name for entry in tmp_path.rglob("*")) == files


# --- non regression --------------------------------------------------------------------------------------


def test_bt_026_single_headers_served_as_today(gate: Gate) -> None:
    """BT-026."""
    local = gate.local
    port = gate.port

    plain = gate.send("GET", "/content", [f"Host: {local}"])
    assert plain.status == 200
    assert SECRET.encode() in plain.body
    named = gate.send("GET", "/content", [f"Host: localhost:{port}", f"Origin: http://localhost:{port}"])
    assert named.status == 200
    assert SECRET.encode() in named.body

    page = b'{"html":"<!DOCTYPE html><html><body><p>X</p></body></html>"}'
    saved = save_request(
        gate,
        [f"Host: {local}", f"Origin: http://{local}", JSON_TYPE, f"Content-Length: {len(page)}"],
        page,
    )
    assert saved.status == 200
    answer: Any = json_body(saved)
    assert answer["ok"] is True
    assert isinstance(answer["mtime"], float)
    assert "<p>X</p>" in gate.deck.path.read_text(encoding="utf-8")


def test_bt_027_existing_messages_unchanged(gate: Gate) -> None:
    """BT-027."""
    local = gate.local
    sane = [f"Host: {local}", JSON_TYPE]

    def save_with(*lines: str, body: bytes = SAVE_BODY) -> RawReply:
        return save_request(gate, list(lines), body)

    bad_length = save_with(f"Host: {local}", JSON_TYPE, "Content-Length: abc")
    assert (bad_length.status, json_body(bad_length)) == (400, {"error": "Invalid Content-Length"})
    too_large = save_with(*sane, "Content-Length: 52428801", body=b"")
    assert (too_large.status, json_body(too_large)) == (413, {"error": "Request too large"})
    wrong_type = save_with(f"Host: {local}", "Content-Type: text/plain", "Content-Length: 42")
    assert (wrong_type.status, json_body(wrong_type)) == (415, {"error": "unsupported content type"})
    not_json = save_with(*sane, "Content-Length: 8", body=b"not json")
    assert (not_json.status, json_body(not_json)) == (400, {"error": "Invalid JSON body"})
    host = gate.send("GET", "/content", [f"Host: attacker.example:{gate.port}"])
    assert (host.status, json_body(host)) == (403, {"error": "forbidden host"})
    origin = gate.send("GET", "/content", [f"Host: {local}", "Origin: https://evil.example"])
    assert (origin.status, json_body(origin)) == (403, {"error": "forbidden origin"})


@needs_chromium
def test_bt_031_browser_editor_keeps_saving(page: Page, served_deck: ServedDeck) -> None:
    """BT-031: the editor of a real browser sends one of each header and still saves."""
    page.goto(f"http://127.0.0.1:{served_deck.port}/")
    page.wait_for_function(
        "() => { const d = document.getElementById('content-frame').contentDocument;"
        " return d && d.querySelector('[data-editable~=\"text\"]'); }"
    )
    page.click("#edit-mode-btn")
    wait_for_js(page, FIRST_ZONE_EDITABLE_EXPRESSION, True, what="the first text zone editable")
    page.frame_locator("#content-frame").locator('[data-editable~="text"]').first.click()
    page.keyboard.press("End")
    page.keyboard.type("AAA")
    # The Euro-Information deck already carries "AAA" in a base64 asset, so the file cannot show the save:
    # the status dot, pending from the keystroke, turns saved once the POST answered.
    wait_for_js(page, SAVED_DOT_EXPRESSION, SAVED_DOT_COLOR, what="the status dot saved")

    assert "AAA" in served_deck.path.read_text(encoding="utf-8")
