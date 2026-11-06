"""A stop releases the port: in process lifecycle, the connection registry, and ``serve`` on Ctrl+C (SPEC-0014).

Ordering trick used by every test that needs a connection accepted before the stop: the serving loop accepts
connections in arrival order, so once a request opened after a connection was answered (or reached its route), the
earlier connection was accepted too. A connection still in the listen backlog at the stop would be reset by the
kernel instead of being closed by the server, which is not what these tests observe.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from mcp_htmleditor import http_server
from mcp_htmleditor.http_connections import ConnectionRegistry
from mcp_htmleditor.http_server import is_server_running, start_http_server, stop_http_server

from . import stdio_support
from .http_support import exchange, json_body

REPO = Path(__file__).resolve().parents[1]
DOC_BOOTSTRAP = REPO / "templates" / "bootstrap" / "document-empty.html"
STOP_BOUND_SECONDS = 2.0
READ_TIMEOUT_SECONDS = 5.0
RESTARTS = 20
PORT_ATTEMPTS = 5
LAST_HTML = "<!DOCTYPE html><html><body><p>LAST</p></body></html>"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_on_free_port(doc: Path) -> int:
    """Start on a port the OS just reported free; retry on a fresh one when another process took it meanwhile.

    ``free_port`` closes its probe before the server binds, so any process (a parallel test run, an outgoing
    connection given the same ephemeral port) can take the port in between: an explicit port never falls back,
    the start raises ``OSError`` instead. Only that collision is retried; the result is still checked exactly.
    """
    for _ in range(PORT_ATTEMPTS - 1):
        port = free_port()
        try:
            started = start_http_server(str(doc), port=port, host="127.0.0.1")
        except OSError as exc:
            if "already in use" not in str(exc):
                raise
            continue
        assert started == (True, port)
        return port
    port = free_port()
    assert start_http_server(str(doc), port=port, host="127.0.0.1") == (True, port)
    return port


def health(port: int) -> int | None:
    reply = exchange(port, f"GET /health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode())
    return reply.status


def read_to_end(sock: socket.socket, timeout: float = STOP_BOUND_SECONDS) -> bytes:
    """Everything the server sends until it closes; ``TimeoutError`` when it keeps the connection open."""
    sock.settimeout(timeout)
    chunks: list[bytes] = []
    while chunk := sock.recv(65536):
        chunks.append(chunk)
    return b"".join(chunks)


def wait_handlers_gone(before: set[threading.Thread]) -> list[threading.Thread]:
    """Threads started since ``before`` still alive after the stop bound (handler and serving threads)."""
    deadline = time.monotonic() + STOP_BOUND_SECONDS
    while (left := [t for t in threading.enumerate() if t not in before]) and time.monotonic() < deadline:
        time.sleep(0.05)
    return left


def timed_stop() -> float:
    started = time.monotonic()
    stop_http_server()
    return time.monotonic() - started


def save_request(port: int, html: str) -> bytes:
    body = json.dumps({"html": html}).encode("utf-8")
    head = (
        f"POST /content HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n\r\n"
    )
    return head.encode("ascii") + body


@pytest.fixture
def lifecycle_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_state: None) -> Iterator[Path]:
    """Spec section 4 conventions; returns ``D``, a copy of the ``doc`` bootstrap; the server is stopped at the end."""
    monkeypatch.setenv("HTMLEDITOR_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HTMLEDITOR_HOST", "127.0.0.1")
    monkeypatch.setenv("BROWSER", "true")
    doc = tmp_path / "doc.html"
    shutil.copyfile(DOC_BOOTSTRAP, doc)
    yield doc
    stop_http_server()


# ---------------------------------------------------------------------------
# BT-010, BT-011, BT-012
# ---------------------------------------------------------------------------


def test_stop_refuses_new_connections(lifecycle_env: Path) -> None:
    """SPEC-0014/BT-010: after the stop a connect is refused, the idle connection sees end of stream."""
    before = set(threading.enumerate())
    port = start_on_free_port(lifecycle_env)
    idle = socket.create_connection(("127.0.0.1", port), timeout=READ_TIMEOUT_SECONDS)
    try:
        assert health(port) == 200  # the idle connection was accepted before this one

        elapsed = timed_stop()

        assert elapsed < STOP_BOUND_SECONDS
        with pytest.raises(ConnectionRefusedError):
            socket.create_connection(("127.0.0.1", port), timeout=1)
        assert read_to_end(idle) == b""
        assert not is_server_running()
        assert wait_handlers_gone(before) == []
    finally:
        idle.close()


def test_received_request_is_answered_across_the_stop(lifecycle_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SPEC-0014/BT-011: a save already received gets its 200, a request line alone gets nothing."""
    port = start_on_free_port(lifecycle_env)
    reached, release = threading.Event(), threading.Event()
    original = http_server.write_save

    def held_write(target: Path, request: http_server.SaveRequest) -> float:
        reached.set()
        release.wait(READ_TIMEOUT_SECONDS)
        return original(target, request)

    monkeypatch.setattr(http_server, "write_save", held_write)
    line_only = socket.create_connection(("127.0.0.1", port), timeout=READ_TIMEOUT_SECONDS)
    saving = socket.create_connection(("127.0.0.1", port), timeout=READ_TIMEOUT_SECONDS)
    try:
        saving.sendall(save_request(port, LAST_HTML))
        line_only.sendall(b"POST /content HTTP/1.1\r\n")
        assert reached.wait(READ_TIMEOUT_SECONDS), "the save never reached its write step"

        elapsed = timed_stop()
        release.set()

        assert elapsed < STOP_BOUND_SECONDS  # BR-005: the stop did not wait for the save in progress
        answer = read_to_end(saving, READ_TIMEOUT_SECONDS)
        status_line, _, _ = answer.partition(b"\r\n")
        assert status_line.split(b" ")[1] == b"200", answer
        payload = json.loads(answer.partition(b"\r\n\r\n")[2])
        assert payload["ok"] is True
        assert isinstance(payload["mtime"], int | float)
        assert "<p>LAST</p>" in lifecycle_env.read_text(encoding="utf-8")
        assert read_to_end(line_only) == b""
    finally:
        release.set()
        saving.close()
        line_only.close()


def test_restart_loop_on_the_same_port(lifecycle_env: Path) -> None:
    """SPEC-0014/BT-012: start, idle connection, stop, 20 times on one port."""
    port = start_on_free_port(lifecycle_env)
    idles: list[socket.socket] = []  # every idle connection stays open across the next start
    try:
        for restart in range(RESTARTS):
            if restart:  # the first start is done above; every later one must get this exact port back
                assert start_http_server(str(lifecycle_env), port=port, host="127.0.0.1") == (True, port)
            idles.append(socket.create_connection(("127.0.0.1", port), timeout=READ_TIMEOUT_SECONDS))
            assert health(port) == 200
            stop_http_server()
    finally:
        for idle in idles:
            idle.close()


# ---------------------------------------------------------------------------
# Support tests: other paths at the stop
# ---------------------------------------------------------------------------


def test_stop_with_no_server_changes_nothing(lifecycle_env: Path) -> None:
    """SPEC-0014/BR-006 in process: no exception, still not running, and a second stop is the same."""
    stop_http_server()
    stop_http_server()

    assert not is_server_running()


def test_body_in_transit_at_the_stop_is_answered(lifecycle_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """DEC-006: headers complete, body still coming at the stop: the request is busy and answered 200."""
    port = start_on_free_port(lifecycle_env)
    begun = threading.Event()
    original = ConnectionRegistry.begin_request

    def observed_begin(self: ConnectionRegistry, sock: socket.socket) -> bool:
        accepted = original(self, sock)
        begun.set()
        return accepted

    monkeypatch.setattr(ConnectionRegistry, "begin_request", observed_begin)
    data = save_request(port, LAST_HTML)
    split = data.index(b"\r\n\r\n") + 4 + 10
    sock = socket.create_connection(("127.0.0.1", port), timeout=READ_TIMEOUT_SECONDS)
    try:
        sock.sendall(data[:split])
        assert begun.wait(READ_TIMEOUT_SECONDS), "the headers were never parsed"

        assert timed_stop() < STOP_BOUND_SECONDS
        sock.sendall(data[split:])

        answer = read_to_end(sock, READ_TIMEOUT_SECONDS)
        assert answer.split(b" ")[1] == b"200", answer
        assert "<p>LAST</p>" in lifecycle_env.read_text(encoding="utf-8")
    finally:
        sock.close()


def test_get_answered_normally_before_any_stop(lifecycle_env: Path) -> None:
    """A request on a running server is still answered and closed as before (no registry side effect)."""
    port = start_on_free_port(lifecycle_env)

    reply = exchange(port, f"GET /health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode())

    assert reply.status == 200
    assert reply.closed
    assert json_body(reply)["status"] == "ok"


# ---------------------------------------------------------------------------
# ConnectionRegistry over socket pairs
# ---------------------------------------------------------------------------


@pytest.fixture
def pairs() -> Iterator[list[tuple[socket.socket, socket.socket]]]:
    made: list[tuple[socket.socket, socket.socket]] = []
    yield made
    for ours, peer in made:
        ours.close()
        peer.close()


def new_pair(pairs: list[tuple[socket.socket, socket.socket]]) -> tuple[socket.socket, socket.socket]:
    ours, peer = socket.socketpair()
    peer.settimeout(STOP_BOUND_SECONDS)
    pairs.append((ours, peer))
    return ours, peer


def test_close_idle_shuts_idle_sockets_and_leaves_busy_ones(pairs: list[tuple[socket.socket, socket.socket]]) -> None:
    registry = ConnectionRegistry()
    idle, idle_peer = new_pair(pairs)
    busy, busy_peer = new_pair(pairs)
    registry.add(idle)
    registry.add(busy)
    assert registry.begin_request(busy)

    assert registry.close_idle() == 1

    assert registry.closing
    assert idle_peer.recv(10) == b""
    busy.sendall(b"answer")
    assert busy_peer.recv(10) == b"answer"
    assert registry.end_request(busy)  # closing: the caller closes the connection


def test_begin_request_refused_after_close_idle(pairs: list[tuple[socket.socket, socket.socket]]) -> None:
    registry = ConnectionRegistry()
    ours, _ = new_pair(pairs)
    registry.add(ours)
    assert not registry.closing

    registry.close_idle()

    assert not registry.begin_request(ours)


def test_end_request_while_running_keeps_the_connection(pairs: list[tuple[socket.socket, socket.socket]]) -> None:
    registry = ConnectionRegistry()
    ours, _ = new_pair(pairs)
    registry.add(ours)
    assert registry.begin_request(ours)

    assert not registry.end_request(ours)
    assert registry.close_idle() == 1  # idle again after its request


def test_add_after_close_idle_shuts_at_once(pairs: list[tuple[socket.socket, socket.socket]]) -> None:
    registry = ConnectionRegistry()
    registry.close_idle()
    late, late_peer = new_pair(pairs)

    registry.add(late)

    assert late_peer.recv(10) == b""


def test_remove_unknown_socket_does_nothing(pairs: list[tuple[socket.socket, socket.socket]]) -> None:
    registry = ConnectionRegistry()
    ours, peer = new_pair(pairs)

    registry.remove(ours)
    registry.add(ours)
    registry.remove(ours)

    assert registry.close_idle() == 0
    ours.sendall(b"x")
    assert peer.recv(1) == b"x"  # a removed socket is never shut


def test_close_idle_with_peer_already_gone_does_not_raise(
    pairs: list[tuple[socket.socket, socket.socket]], caplog: pytest.LogCaptureFixture
) -> None:
    registry = ConnectionRegistry()
    ours, peer = new_pair(pairs)
    registry.add(ours)
    peer.close()
    caplog.set_level("DEBUG", logger="mcp_htmleditor.http_connections")

    assert registry.close_idle() == 1

    assert "Connection already closed: OSError" in caplog.text


# ---------------------------------------------------------------------------
# DEC-017: serve on Ctrl+C
# ---------------------------------------------------------------------------


def default_sigint() -> None:
    """Child side, before exec: Python only raises ``KeyboardInterrupt`` when SIGINT is not ignored at startup,
    and a test run launched from a background shell job inherits SIGINT ignored."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)


class ServeRun:
    """A ``mcp-htmleditor serve`` child process with its stdout pumped into a queue (``None`` marks the end)."""

    def __init__(self, doc: Path, env: dict[str, str], port: int) -> None:
        self.port = port
        # --no-browser: a SIGINT landing during the browser launch, before the wait loop, would exit 1
        command = [sys.executable, "-m", "mcp_htmleditor", "serve", str(doc), "--port", str(port), "--no-browser"]
        self.process = subprocess.Popen(  # noqa: S603  command built by the test, no shell
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=REPO,
            env=env,
            preexec_fn=default_sigint,  # noqa: PLW1509  only resets one signal disposition
        )
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.seen: list[str] = []
        assert self.process.stdout is not None
        stdout = self.process.stdout

        def pump() -> None:
            for line in stdout:
                self.lines.put(line)
            self.lines.put(None)

        self.reader = threading.Thread(target=pump, daemon=True)
        self.reader.start()

    def serving(self) -> bool:
        """Wait for the ``Serving on`` line; False when the process ended first (its port was taken)."""
        while not any("Serving on" in line for line in self.seen):
            line = self.lines.get(timeout=stdio_support.LINE_TIMEOUT_SECONDS)
            if line is None:
                self.process.wait(timeout=10)
                return False
            self.seen.append(line)
        return True

    def drain(self) -> list[str]:
        self.reader.join(READ_TIMEOUT_SECONDS)  # stdout ends with the process
        while not self.lines.empty():
            if (line := self.lines.get_nowait()) is not None:
                self.seen.append(line)
        return self.seen


def serve_on_free_port(doc: Path, env: dict[str, str]) -> ServeRun:
    """Like ``start_on_free_port`` for a child ``serve``: a port taken between probe and bind ends the child early."""
    for _ in range(PORT_ATTEMPTS):
        run = ServeRun(doc, env, free_port())
        if run.serving():
            return run
    pytest.fail(f"serve could not bind a free port in {PORT_ATTEMPTS} attempts")


def test_serve_stops_on_ctrl_c_and_releases_the_port(tmp_path: Path) -> None:
    doc = tmp_path / "doc.html"
    shutil.copyfile(DOC_BOOTSTRAP, doc)
    env = {
        **os.environ,
        "HTMLEDITOR_STATE_DIR": str(tmp_path / "state"),
        "HTMLEDITOR_HOST": "127.0.0.1",
        "BROWSER": "true",
        "PYTHONUNBUFFERED": "1",
    }
    run = serve_on_free_port(doc, env)
    port, process = run.port, run.process
    try:
        assert health(port) == 200

        process.send_signal(signal.SIGINT)

        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
    seen = run.drain()
    assert any("Stopping server." in line for line in seen), seen
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("127.0.0.1", port), timeout=1)
