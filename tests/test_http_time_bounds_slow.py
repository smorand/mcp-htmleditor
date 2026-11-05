"""Real value checks of SPEC-0013 US-0079: the 30 second wait bound and the 5 minute total bound.

These tests take minutes, so they carry the ``slow`` marker and the default run deselects them (``addopts`` in
``pyproject.toml``). Run them with ``make test ARGS='-m slow'``. They use the real bounds: nothing is monkeypatched.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from mcp_htmleditor import http_deadline
from tests.conftest import ServedDeck
from tests.test_http_time_bounds import (
    LOGGER,
    SECRET,
    TIMEOUT_BODY,
    Timed,
    folder_state,
    open_and_send,
    read_to_end,
    stalled_post,
    write_secret_deck,
)

pytestmark = pytest.mark.slow

Serve = Callable[[Path], ServedDeck]


@pytest.fixture
def deck(tmp_path: Path, serve_deck: Serve) -> ServedDeck:
    assert http_deadline.WAIT_SECONDS == 30.0
    assert http_deadline.TOTAL_SECONDS == 300.0
    folder = tmp_path / "work"
    folder.mkdir()
    return serve_deck(write_secret_deck(folder))


def long_read(conn: Timed, seconds: float) -> Timed:
    conn.sock.settimeout(seconds)
    return read_to_end(conn)


def get(port: int) -> bytes:
    return f"GET /content HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode("ascii")


def test_time_bounds_slow_bt_003_stalled_body_is_answered_and_released(deck: ServedDeck) -> None:
    before = folder_state(deck.path)
    conn = long_read(open_and_send(deck.port, stalled_post(deck.port)), 45.0)
    reply = conn.reply()

    assert reply.status == 408, reply.raw[:300]
    assert json.loads(reply.body) == TIMEOUT_BODY
    assert reply.closed
    assert conn.first_byte is not None
    assert 30.0 <= conn.first_byte - conn.last_sent <= 35.0
    assert folder_state(deck.path) == before


def test_time_bounds_slow_bt_015_stalled_connections_do_not_block_others(deck: ServedDeck) -> None:
    before = folder_state(deck.path)
    stalled = [open_and_send(deck.port, stalled_post(deck.port)) for _ in range(20)]
    readers = [threading.Thread(target=long_read, args=(conn, 50.0)) for conn in stalled]
    for reader in readers:
        reader.start()
    first = read_to_end(open_and_send(deck.port, get(deck.port)))
    time.sleep(35.0)
    second = read_to_end(open_and_send(deck.port, get(deck.port)))
    for reader in readers:
        reader.join(timeout=60)

    for normal in (first, second):
        assert normal.reply().status == 200
        assert SECRET.encode() in normal.reply().body
    for conn in stalled:
        reply = conn.reply()
        assert reply.status == 408, reply.raw[:300]
        assert json.loads(reply.body) == TIMEOUT_BODY
        assert reply.closed
    assert folder_state(deck.path) == before


def test_time_bounds_slow_bt_022_progressing_slow_upload_is_not_cut(deck: ServedDeck) -> None:
    body = b'{"html":"<!DOCTYPE html><html><p>SLOW</p></html>"}'.ljust(60)
    assert len(body) == 60
    head = (
        f"POST /content HTTP/1.1\r\nHost: 127.0.0.1:{deck.port}\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n\r\n"
    ).encode("ascii")
    conn = open_and_send(deck.port, head)
    for start in range(0, len(body), 10):
        if start:
            time.sleep(10.0)  # 5 gaps: 50 seconds in total, every gap far under the 30 second wait
        conn.sock.sendall(body[start : start + 10])
    conn.last_sent = time.monotonic()
    reply = long_read(conn, 10.0).reply()

    assert reply.status == 200, reply.raw[:300]
    payload = json.loads(reply.body)
    assert payload["ok"] is True
    assert isinstance(payload["mtime"], float)
    assert "<p>SLOW</p>" in deck.path.read_text(encoding="utf-8")


def test_time_bounds_slow_bt_023_idle_connection_closed(deck: ServedDeck, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER)
    time.sleep(1.0)  # let the readiness probe of serve_deck end before counting records
    caplog.clear()
    idle = long_read(open_and_send(deck.port, b""), 45.0)
    assert idle.closed
    assert idle.chunks == []
    assert idle.ended is not None
    assert 30.0 <= idle.ended - idle.last_sent <= 35.0
    assert [r for r in caplog.records if r.name == LOGGER] == []

    partial = long_read(open_and_send(deck.port, b"GET /con"), 45.0)
    reply = partial.reply()
    assert reply.status == 408, reply.raw[:300]
    assert json.loads(reply.body) == TIMEOUT_BODY
    assert partial.first_byte is not None
    assert 30.0 <= partial.first_byte - partial.last_sent <= 35.0
    warnings = [r.getMessage() for r in caplog.records if r.name == LOGGER and r.levelno >= logging.WARNING]
    assert warnings == ["Refused - -: Request timeout"]


def test_time_bounds_slow_bt_040_trickling_request_is_cut_by_the_total_bound(
    deck: ServedDeck, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER)
    time.sleep(1.0)
    caplog.clear()
    before = folder_state(deck.path)
    head = (
        f"POST /content HTTP/1.1\r\nHost: 127.0.0.1:{deck.port}\r\nContent-Type: application/json\r\n"
        "Content-Length: 100\r\n\r\n"
    ).encode("ascii")
    conn = open_and_send(deck.port, head)
    started = conn.last_sent
    conn.sock.settimeout(1.0)
    answered = False
    while not answered and time.monotonic() - started < 310.0:
        try:
            conn.sock.sendall(b"{")
        except OSError:
            break  # the server already answered and closed
        slot_end = time.monotonic() + 20.0
        while time.monotonic() < slot_end and not answered:
            try:
                chunk = conn.sock.recv(65536)
            except TimeoutError:
                continue
            answered = True
            if chunk:
                conn.first_byte = time.monotonic()
                conn.chunks.append(chunk)
    long_read(conn, 10.0)
    reply = conn.reply()

    assert reply.status == 408, reply.raw[:300]
    assert json.loads(reply.body) == TIMEOUT_BODY
    assert reply.closed
    assert conn.first_byte is not None
    assert 300.0 <= conn.first_byte - started <= 305.0
    warnings = [r.getMessage() for r in caplog.records if r.name == LOGGER and r.levelno >= logging.WARNING]
    assert warnings == ["Refused POST /content: Request timeout"]
    assert folder_state(deck.path) == before
