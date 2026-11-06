"""Exploit and non regression tests for SPEC-0013 US-0078: the wait bound, the idle close and the send side bound.

Bug (BUG-002): the editor server had no socket timeout, so a client declaring 100 bytes and sending one, a client
that never sent its request line and a client that never read an answer each held a handler thread forever. The
end to end tests run a real server with ``http_deadline.WAIT_SECONDS`` shortened to 1 second (BR-022) and talk to it
through raw sockets; "unchanged" is checked on ``deck.html`` and its folder, "no traceback" on the log records and on
the process stderr (where ``socketserver`` prints an unhandled handler error).
"""

from __future__ import annotations

import contextlib
import importlib
import json
import logging
import re
import socket
import threading
import time
import tomllib
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.conftest import ServedDeck
from tests.deck_support import BOOTSTRAP, run_cli
from tests.http_support import HEADER_END, RawReply, _parse

SECRET = "ORIGINAL-SECRET"  # noqa: S105 - a marker, not a credential
WAIT = 1.0
TOTAL = 4.0
CLOSE_MARGIN = 10.0  # generating a 27 MB export is CPU bound: 5.5 s measured at load average 22, the wait is 1 s
TIMEOUT_BODY = {"error": "Request timeout"}
LOGGER = "mcp_htmleditor.http_server"
Serve = Callable[[Path], ServedDeck]


def deadline_module() -> ModuleType:
    return importlib.import_module("mcp_htmleditor.http_deadline")


@pytest.fixture
def short_bounds(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The test seam of BR-022: the module constants, shortened for this test only."""
    module = deadline_module()
    monkeypatch.setattr(module, "WAIT_SECONDS", WAIT)
    monkeypatch.setattr(module, "TOTAL_SECONDS", TOTAL)
    return module


def write_secret_deck(folder: Path, tail: str = "") -> Path:
    html = (BOOTSTRAP / "slides-empty.html").read_text(encoding="utf-8")
    html = re.sub(r"<title>.*?</title>", f"<title>{SECRET}</title>", html, count=1)
    html = html.replace("</body>", f"</body>{tail}")
    path = folder / "deck.html"
    path.write_text(html, encoding="utf-8")
    return path


@pytest.fixture
def deck(tmp_path: Path, serve_deck: Serve, short_bounds: ModuleType) -> ServedDeck:
    folder = tmp_path / "work"
    folder.mkdir()
    return serve_deck(write_secret_deck(folder))


@dataclass
class Timed:
    """A raw connection: what it sent, when its last byte left, and what came back and when."""

    sock: socket.socket
    last_sent: float = 0.0
    first_byte: float | None = None
    ended: float | None = None
    closed: bool = False
    chunks: list[bytes] = field(default_factory=list)

    def reply(self) -> RawReply:
        raw = b"".join(self.chunks)
        status, headers, body = _parse(raw)
        elapsed = (self.ended or time.monotonic()) - self.last_sent
        return RawReply(status=status, headers=headers, body=body, raw=raw, elapsed=elapsed, closed=self.closed)


def open_and_send(port: int, data: bytes) -> Timed:
    sock = socket.create_connection(("127.0.0.1", port), timeout=6.0)
    if data:
        sock.sendall(data)
    return Timed(sock=sock, last_sent=time.monotonic())


def read_to_end(conn: Timed) -> Timed:
    """Read until the server closes (or 6 seconds of silence), recording when the first byte and the end came."""
    try:
        while chunk := conn.sock.recv(65536):
            if conn.first_byte is None:
                conn.first_byte = time.monotonic()
            conn.chunks.append(chunk)
        conn.closed = True
    except ConnectionResetError:
        conn.closed = True
    except TimeoutError:
        conn.closed = False
    conn.ended = time.monotonic()
    conn.sock.close()
    return conn


def stalled_post(port: int) -> bytes:
    return (
        f"POST /content HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\n"
        "Content-Length: 100\r\n\r\n{"
    ).encode("ascii")


def assert_timed_out(conn: Timed) -> None:
    reply = conn.reply()
    assert reply.status == 408, reply.raw[:300]
    assert json.loads(reply.body) == TIMEOUT_BODY
    assert reply.closed
    assert conn.first_byte is not None
    assert WAIT - 0.05 <= conn.first_byte - conn.last_sent <= 3.0


def assert_no_traceback(caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]) -> None:
    assert not any("Traceback" in r.getMessage() or r.exc_info for r in caplog.records)
    out, err = capfd.readouterr()
    assert "Traceback" not in out + err


def folder_state(path: Path) -> tuple[bytes, list[str]]:
    return path.read_bytes(), sorted(entry.name for entry in path.parent.iterdir())


# ---------------------------------------------------------------------------
# End to end, short bounds (default suite)
# ---------------------------------------------------------------------------


def test_time_bounds_bt_042_stalled_bodies_are_answered_and_released(
    deck: ServedDeck, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    before = folder_state(deck.path)
    stalled = [open_and_send(deck.port, stalled_post(deck.port)) for _ in range(5)]
    readers = [threading.Thread(target=read_to_end, args=(conn,)) for conn in stalled]
    for reader in readers:
        reader.start()
    time.sleep(0.2)
    normal = read_to_end(
        open_and_send(deck.port, f"GET /content HTTP/1.1\r\nHost: 127.0.0.1:{deck.port}\r\n\r\n".encode())
    )
    for reader in readers:
        reader.join(timeout=8)

    assert normal.reply().status == 200
    assert SECRET.encode() in normal.reply().body
    assert normal.ended is not None
    for conn in stalled:
        assert_timed_out(conn)
        assert conn.first_byte is not None
        assert normal.ended < conn.first_byte
    assert folder_state(deck.path) == before
    assert_no_traceback(caplog, capfd)
    for command in ("serve", "new"):
        stdout, _, code = run_cli(command, "--help")
        assert code == 0
        assert "timeout" not in stdout.lower()


def test_time_bounds_bt_043_idle_and_partial_connections(
    deck: ServedDeck, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER)
    time.sleep(WAIT + 0.5)  # let the readiness probe of serve_deck end before counting records
    caplog.clear()
    idle = open_and_send(deck.port, b"")
    idle_reader = threading.Thread(target=read_to_end, args=(idle,))
    idle_reader.start()
    idle_reader.join(timeout=8)

    assert idle.closed
    assert idle.chunks == []
    assert idle.ended is not None
    assert WAIT - 0.05 <= idle.ended - idle.last_sent <= 3.0
    assert [r for r in caplog.records if r.name == LOGGER] == []

    partial = read_to_end(open_and_send(deck.port, b"GET /con"))
    assert_timed_out(partial)
    warnings = [r.getMessage() for r in caplog.records if r.name == LOGGER and r.levelno >= logging.WARNING]
    assert warnings == ["Refused - -: Request timeout"]
    assert_no_traceback(caplog, capfd)


def test_time_bounds_bt_045_progressing_upload_is_not_cut(deck: ServedDeck) -> None:
    # The spec says "padded to 60 bytes", but the literal object is already 63 bytes: padded to 70 instead, so it is
    # still sent 10 bytes at a time, 0.5 seconds apart, in 3.5 seconds (under the total bound T).
    body = b'{"html":"<!DOCTYPE html><html><body><p>SLOW</p></body></html>"}'.ljust(70)
    assert len(body) == 70
    head = (
        f"POST /content HTTP/1.1\r\nHost: 127.0.0.1:{deck.port}\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n\r\n"
    ).encode("ascii")
    conn = open_and_send(deck.port, head)
    for start in range(0, len(body), 10):
        time.sleep(0.5)
        conn.sock.sendall(body[start : start + 10])
    conn.last_sent = time.monotonic()
    reply = read_to_end(conn).reply()

    assert reply.status == 200, reply.raw[:300]
    payload = json.loads(reply.body)
    assert payload["ok"] is True
    assert isinstance(payload["mtime"], float)
    assert "<p>SLOW</p>" in deck.path.read_text(encoding="utf-8")


def test_time_bounds_bt_046_client_not_reading_is_released(
    tmp_path: Path,
    serve_deck: Serve,
    short_bounds: ModuleType,
    caplog: pytest.LogCaptureFixture,
    capfd: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "work"
    folder.mkdir()
    big = serve_deck(write_secret_deck(folder, tail="<!--" + "x" * (16 * 1024 * 1024) + "-->"))
    before = folder_state(big.path)
    time.sleep(WAIT + 0.3)  # let the readiness probe of serve_deck end before counting threads
    threads_before = handler_threads()
    conn = open_and_send(big.port, f"GET /content HTTP/1.1\r\nHost: 127.0.0.1:{big.port}\r\n\r\n".encode())
    time.sleep(4.0)
    reply = read_to_end(conn).reply()

    assert reply.closed
    assert reply.raw.startswith(b"HTTP/1.0 200")
    assert HEADER_END in reply.raw
    assert len(reply.body) < len(before[0])
    assert wait_threads_ended(threads_before) == set()
    health = read_to_end(
        open_and_send(big.port, f"GET /health HTTP/1.1\r\nHost: 127.0.0.1:{big.port}\r\n\r\n".encode())
    )
    assert health.reply().status == 200
    assert folder_state(big.path) == before
    assert_no_traceback(caplog, capfd)


def test_time_bounds_bt_044_trickling_request_is_cut_by_the_total_bound(
    deck: ServedDeck, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    """One byte every 0.6 seconds under a 1 second wait is never silent, yet the 4 second total ends it."""
    caplog.set_level(logging.WARNING, logger=LOGGER)
    time.sleep(WAIT + 0.5)  # let the readiness probe of serve_deck end before counting records
    caplog.clear()
    before = folder_state(deck.path)
    head = (
        f"POST /content HTTP/1.1\r\nHost: 127.0.0.1:{deck.port}\r\nContent-Type: application/json\r\n"
        "Content-Length: 100\r\n\r\n"
    ).encode("ascii")
    conn = open_and_send(deck.port, head)
    started = conn.last_sent
    conn.sock.settimeout(0.05)
    try:
        while conn.first_byte is None and time.monotonic() - started < TOTAL + 2.5:
            with contextlib.suppress(OSError):  # the server may already have answered and closed
                conn.sock.sendall(b"{")
            time.sleep(0.6)
            try:
                chunk = conn.sock.recv(65536)
            except TimeoutError:
                continue
            if chunk:
                conn.first_byte = time.monotonic()
                conn.chunks.append(chunk)
    finally:
        conn.sock.settimeout(6.0)
    read_to_end(conn)
    reply = conn.reply()

    assert reply.status == 408, reply.raw[:300]
    assert json.loads(reply.body) == TIMEOUT_BODY
    assert reply.closed
    assert conn.first_byte is not None
    assert TOTAL <= conn.first_byte - started <= TOTAL + 2.0
    warnings = [r.getMessage() for r in caplog.records if r.name == LOGGER and r.levelno >= logging.WARNING]
    assert warnings == ["Refused POST /content: Request timeout"]
    assert folder_state(deck.path) == before
    assert_no_traceback(caplog, capfd)


def test_time_bounds_header_and_request_line_stalls_name_the_request(
    deck: ServedDeck, caplog: pytest.LogCaptureFixture
) -> None:
    """A stall inside the header block is refused with the method and path of the request line already read."""
    caplog.set_level(logging.WARNING, logger=LOGGER)
    before = folder_state(deck.path)
    conn = read_to_end(
        open_and_send(deck.port, f"POST /content HTTP/1.1\r\nHost: 127.0.0.1:{deck.port}\r\nCont".encode())
    )
    assert_timed_out(conn)
    assert "Refused POST /content: Request timeout" in [r.getMessage() for r in caplog.records if r.name == LOGGER]
    assert folder_state(deck.path) == before


def test_time_bounds_client_closing_early_is_quiet(
    deck: ServedDeck, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    """A client that sends half a body and closes gets nothing written and leaves no traceback."""
    before = folder_state(deck.path)
    sock = socket.create_connection(("127.0.0.1", deck.port), timeout=3)
    sock.sendall(stalled_post(deck.port))
    sock.close()
    time.sleep(0.5)
    health = read_to_end(
        open_and_send(deck.port, f"GET /health HTTP/1.1\r\nHost: 127.0.0.1:{deck.port}\r\n\r\n".encode())
    )
    assert health.reply().status == 200
    assert health.reply().raw.startswith(b"HTTP/1.0 200")  # one request per connection, no keep alive
    assert folder_state(deck.path) == before
    assert_no_traceback(caplog, capfd)


# ---------------------------------------------------------------------------
# Units of http_deadline (support coverage)
# ---------------------------------------------------------------------------


@pytest.fixture
def pair() -> Iterator[tuple[socket.socket, socket.socket]]:
    server, client = socket.socketpair()
    yield server, client
    server.close()
    client.close()


def reader_over(server: socket.socket) -> Any:
    module = deadline_module()
    return module.DeadlineReader(server.makefile("rb"), server)


def send_later(sock: socket.socket, parts: list[bytes], gap: float) -> threading.Thread:
    def run() -> None:
        for part in parts:
            time.sleep(gap)
            sock.sendall(part)

    thread = threading.Thread(target=run)
    thread.start()
    return thread


def test_time_bounds_unit_readline_joins_a_line_sent_in_two_parts(pair: tuple[socket.socket, socket.socket]) -> None:
    server, client = pair
    reader = reader_over(server)
    sender = send_later(client, [b"GET / HT", b"TP/1.1\r\nHost"], 0.05)
    assert reader.readline(65537) == b"GET / HTTP/1.1\r\n"
    sender.join()
    assert reader.bytes_received == 16


def test_time_bounds_unit_readline_honours_its_limit(pair: tuple[socket.socket, socket.socket]) -> None:
    server, client = pair
    reader = reader_over(server)
    client.sendall(b"abcdef\n")
    assert reader.readline(4) == b"abcd"
    assert reader.readline() == b"ef\n"


def test_time_bounds_unit_read_collects_bytes_sent_one_at_a_time(pair: tuple[socket.socket, socket.socket]) -> None:
    server, client = pair
    reader = reader_over(server)
    sender = send_later(client, [bytes([c]) for c in b"hello!"], 0.02)
    assert reader.read(5) == b"hello"
    sender.join()


def test_time_bounds_unit_progress_restarts_the_wait(
    pair: tuple[socket.socket, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    """One byte every 0.15 seconds under a 0.3 second wait: never cut, although the whole read takes longer."""
    module = deadline_module()
    monkeypatch.setattr(module, "WAIT_SECONDS", 0.3)
    server, client = pair
    reader = reader_over(server)
    sender = send_later(client, [bytes([c]) for c in b"abcd"], 0.15)
    assert reader.read(4) == b"abcd"
    sender.join()


def test_time_bounds_unit_silence_raises_request_timeout(
    pair: tuple[socket.socket, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    module = deadline_module()
    monkeypatch.setattr(module, "WAIT_SECONDS", 0.2)
    server, client = pair
    reader = reader_over(server)
    with pytest.raises(module.RequestTimeout) as nothing:
        reader.readline()
    assert nothing.value.has_bytes is False
    with pytest.raises(module.RequestTimeout):  # the timed out socket file refuses any further read
        reader.read(1)

    other = reader_over(client)
    server.sendall(b"x")
    with pytest.raises(module.RequestTimeout) as partial:
        other.readline()
    assert partial.value.has_bytes is True


def test_time_bounds_unit_end_of_stream_and_close(pair: tuple[socket.socket, socket.socket]) -> None:
    server, client = pair
    reader = reader_over(server)
    client.sendall(b"ab")
    client.shutdown(socket.SHUT_WR)
    assert reader.read() == b"ab"
    assert reader.readline() == b""
    assert reader.read(3) == b""
    assert reader.closed is False
    reader.close()
    assert reader.closed is True


def test_time_bounds_unit_reset_is_not_a_timeout(pair: tuple[socket.socket, socket.socket]) -> None:
    """An error of a socket that never timed out is the client's close, passed on unchanged."""
    module = deadline_module()

    class Broken:
        def peek(self, size: int = 0) -> bytes:
            raise ConnectionResetError("reset")

    server, _ = pair
    reader = module.DeadlineReader(Broken(), server)
    with pytest.raises(ConnectionResetError):
        reader.readline()


def test_time_bounds_unit_writer_sends_everything_to_a_reader(pair: tuple[socket.socket, socket.socket]) -> None:
    module = deadline_module()
    server, client = pair
    data = bytes(range(256)) * 782  # 200 192 bytes, several chunks
    data = data[:200_000]
    received: list[bytes] = []

    def drain() -> None:
        total = 0
        while total < len(data):
            chunk = client.recv(65536)
            received.append(chunk)
            total += len(chunk)

    reader = threading.Thread(target=drain)
    reader.start()
    writer = module.DeadlineWriter(server)
    assert writer.write(data) == 200_000
    writer.flush()
    reader.join(timeout=5)
    assert b"".join(received) == data
    assert writer.closed is False
    writer.close()
    assert writer.closed is True


def test_time_bounds_unit_writer_gives_up_on_a_peer_that_never_reads(
    pair: tuple[socket.socket, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    module = deadline_module()
    monkeypatch.setattr(module, "WAIT_SECONDS", 0.2)
    server, _ = pair
    writer = module.DeadlineWriter(server)
    started = time.monotonic()
    with pytest.raises(module.ResponseTimeout):
        writer.write(b"x" * (16 * 1024 * 1024))
    assert time.monotonic() - started < 2.0
    started = time.monotonic()
    with pytest.raises(module.ResponseTimeout):  # a later write of the same answer fails at once
        writer.write(b"y")
    assert time.monotonic() - started < 0.1


def test_time_bounds_unit_request_timeout_is_not_a_timeout_error() -> None:
    module = deadline_module()
    error = module.RequestTimeout(has_bytes=True)
    assert not isinstance(error, TimeoutError)
    assert not isinstance(error, OSError)
    assert error.has_bytes is True
    assert module.WAIT_SECONDS == 30.0
    assert module.TOTAL_SECONDS == 300.0


# ---------------------------------------------------------------------------
# Review fixes: export answers to a client not reading, failures before the headers reach the wire, thread release
# ---------------------------------------------------------------------------

HANDLER_THREAD = "process_request_thread"  # the target name ThreadingHTTPServer gives each handler thread


def handler_threads() -> set[int]:
    return {t.ident or 0 for t in threading.enumerate() if HANDLER_THREAD in t.name}


def wait_threads_ended(before: set[int], timeout: float = 5.0) -> set[int]:
    """Handler threads started since ``before`` that are still alive after at most ``timeout`` seconds."""
    deadline = time.monotonic() + timeout
    while (left := handler_threads() - before) and time.monotonic() < deadline:
        time.sleep(0.05)
    return left


def write_incompressible_png(path: Path, side: int = 3000) -> None:
    """A valid RGB PNG of ``side`` x ``side`` random pixels, stored uncompressed (about 27 MB for 3000)."""
    import os
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    row = side * 3
    raw = os.urandom(row * side)
    scan = b"".join(b"\x00" + raw[i * row : (i + 1) * row] for i in range(side))
    header = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
    body = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(scan, 0))
    path.write_bytes(body + chunk(b"IEND", b""))


@pytest.mark.parametrize("kind", ["pptx", "docx"])
def test_time_bounds_export_to_a_client_not_reading_is_quiet(
    kind: str,
    tmp_path: Path,
    serve_deck: Serve,
    short_bounds: ModuleType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """DEC-015: an export answer the client stops reading is a DEBUG close, never an ERROR nor a second answer."""
    import shutil

    if kind == "docx" and shutil.which("pandoc") is None:
        pytest.skip("pandoc not installed")
    folder = tmp_path / "work"
    folder.mkdir()
    write_incompressible_png(folder / "big.png")
    tail = '<article class="slide" data-type="slide" data-id="slide-1" data-title="Big"><img src="big.png"></article>'
    if kind == "docx":
        tail = '<article data-type="document"><p>Big</p><img src="big.png"></article>'
    big = serve_deck(write_secret_deck(folder, tail=tail))
    time.sleep(WAIT + 0.3)  # let the readiness probe of serve_deck end
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    caplog.clear()
    before = handler_threads()
    conn = open_and_send(big.port, f"GET /export/{kind} HTTP/1.1\r\nHost: 127.0.0.1:{big.port}\r\n\r\n".encode())
    deadline = time.monotonic() + WAIT + CLOSE_MARGIN
    while not any("Connection closed while answering" in r.getMessage() for r in caplog.records):
        assert time.monotonic() < deadline, [r.getMessage() for r in caplog.records]
        time.sleep(0.05)
    assert wait_threads_ended(before, CLOSE_MARGIN) == set()
    conn.sock.close()

    ours = [r for r in caplog.records if r.name == LOGGER]
    assert [r.getMessage() for r in ours if r.levelno >= logging.ERROR] == []
    closed = [r for r in ours if r.getMessage().startswith("Connection closed while answering")]
    assert [(r.levelno, r.getMessage()) for r in closed] == [
        (logging.DEBUG, "Connection closed while answering: ResponseTimeout")
    ]
    health = read_to_end(
        open_and_send(big.port, f"GET /health HTTP/1.1\r\nHost: 127.0.0.1:{big.port}\r\n\r\n".encode())
    )
    assert health.reply().status == 200


def route_failing(after_flush: bool) -> Callable[[Any], None]:
    def route(handler: Any) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/plain")
        if after_flush:
            handler.end_headers()
        raise RuntimeError("boom")

    return route


def test_time_bounds_failure_before_headers_flushed_is_answered_500(
    deck: ServedDeck, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """BR-009: headers still buffered never reached the wire, so the catch-all discards them and answers 500."""
    from mcp_htmleditor import http_server

    monkeypatch.setattr(http_server._EditorHandler, "_serve_status", route_failing(after_flush=False))
    caplog.set_level(logging.ERROR, logger=LOGGER)
    conn = read_to_end(
        open_and_send(deck.port, f"GET /status HTTP/1.1\r\nHost: 127.0.0.1:{deck.port}\r\n\r\n".encode())
    )
    reply = conn.reply()

    assert reply.status == 500, reply.raw[:300]
    assert json.loads(reply.body) == {"error": "boom"}
    assert reply.raw.count(b"HTTP/1.") == 1
    assert b"text/plain" not in reply.raw
    assert [r.getMessage() for r in caplog.records if r.name == LOGGER] == ["Request failed: GET /status: RuntimeError"]


def test_time_bounds_failure_after_headers_flushed_sends_no_second_status(
    deck: ServedDeck, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mcp_htmleditor import http_server

    monkeypatch.setattr(http_server._EditorHandler, "_serve_status", route_failing(after_flush=True))
    conn = read_to_end(
        open_and_send(deck.port, f"GET /status HTTP/1.1\r\nHost: 127.0.0.1:{deck.port}\r\n\r\n".encode())
    )
    reply = conn.reply()

    assert reply.status == 200
    assert reply.raw.count(b"HTTP/1.") == 1
    assert reply.closed


def test_time_bounds_content_disposition_fits_any_file_name() -> None:
    """An export of a file named outside latin-1 gets a header that encodes, instead of a failed answer."""
    from mcp_htmleditor.http_server import content_disposition

    header = content_disposition('Présentation "été" 😀.pptx')
    header.encode("latin-1")
    assert header == (
        'attachment; filename="Pr_sentation __t__ _.pptx"; '
        "filename*=UTF-8''Pr%C3%A9sentation%20%22%C3%A9t%C3%A9%22%20%F0%9F%98%80.pptx"
    )
    assert content_disposition("deck.pptx") == "attachment; filename=\"deck.pptx\"; filename*=UTF-8''deck.pptx"


class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_time_bounds_unit_total_bound_cuts_a_request_that_keeps_progressing(
    pair: tuple[socket.socket, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bytes keep arriving inside the wait, but once TOTAL_SECONDS passed since the first byte the next read ends."""
    module = deadline_module()
    monkeypatch.setattr(module, "WAIT_SECONDS", 30.0)
    monkeypatch.setattr(module, "TOTAL_SECONDS", 300.0)
    server, client = pair
    clock = FakeClock()
    reader = module.DeadlineReader(server.makefile("rb"), server, clock)
    client.sendall(b"abc")
    assert reader.read(1) == b"a"
    clock.now = 299.9
    assert reader.read(1) == b"b"
    clock.now = 300.0
    with pytest.raises(module.RequestTimeout) as cut:
        reader.read(1)  # "c" is already buffered: the bound still applies
    assert cut.value.has_bytes is True
    with pytest.raises(module.RequestTimeout):
        reader.readline()


def test_time_bounds_unit_total_bound_shortens_the_wait(
    pair: tuple[socket.socket, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With 0.3 seconds left of the total, a silent peer is cut after 0.3 seconds, not after the 30 second wait."""
    module = deadline_module()
    monkeypatch.setattr(module, "WAIT_SECONDS", 30.0)
    monkeypatch.setattr(module, "TOTAL_SECONDS", 300.0)
    server, client = pair
    clock = FakeClock()
    reader = module.DeadlineReader(server.makefile("rb"), server, clock)
    client.sendall(b"x")
    assert reader.read(1) == b"x"
    clock.now = 299.7
    started = time.monotonic()
    with pytest.raises(module.RequestTimeout) as cut:
        reader.read(1)
    assert cut.value.has_bytes is True
    assert time.monotonic() - started < 2.0


def test_time_bounds_unit_total_bound_does_not_apply_before_the_first_byte(
    pair: tuple[socket.socket, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The total is measured from the first byte: an idle connection is only ever cut by the wait."""
    module = deadline_module()
    monkeypatch.setattr(module, "WAIT_SECONDS", 0.2)
    monkeypatch.setattr(module, "TOTAL_SECONDS", 1.0)
    server, _client = pair
    clock = FakeClock()
    clock.now = 10_000.0
    reader = module.DeadlineReader(server.makefile("rb"), server, clock)
    with pytest.raises(module.RequestTimeout) as idle:
        reader.readline()
    assert idle.value.has_bytes is False


def test_time_bounds_unit_total_bound_is_measured_from_the_first_byte_not_the_line(
    pair: tuple[socket.socket, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first byte starts the clock even when it is not yet a complete request line."""
    module = deadline_module()
    monkeypatch.setattr(module, "WAIT_SECONDS", 30.0)
    monkeypatch.setattr(module, "TOTAL_SECONDS", 300.0)
    server, client = pair
    clock = FakeClock()
    clock.now = 50.0
    reader = module.DeadlineReader(server.makefile("rb"), server, clock)
    client.sendall(b"GE")
    assert reader.read(2) == b"GE"
    clock.now = 350.0  # 300 seconds after the first byte
    client.sendall(b"T / HTTP/1.1\r\n")
    with pytest.raises(module.RequestTimeout):
        reader.readline()


def test_time_bounds_unit_writer_ignores_the_total_bound(
    pair: tuple[socket.socket, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The total covers receiving the request: sending the answer is bounded by the wait per chunk only."""
    module = deadline_module()
    monkeypatch.setattr(module, "TOTAL_SECONDS", 0.0)
    server, client = pair
    assert module.DeadlineWriter(server).write(b"answer") == 6
    assert client.recv(16) == b"answer"


def test_time_bounds_slow_marker_is_registered_and_deselected_by_default() -> None:
    """DEC-017: the real value tests are marked slow, the marker is registered and the default run deselects it."""
    root = Path(__file__).resolve().parent.parent
    options = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]
    assert any(marker.startswith("slow:") for marker in options["markers"])
    assert options["addopts"] == "-m 'not slow'"
    slow = importlib.import_module("tests.test_http_time_bounds_slow")
    assert slow.pytestmark.name == "slow"
