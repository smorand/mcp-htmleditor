"""The agent tools across a stop, driven over stdio on a real ``mcp-htmleditor mcp`` process (SPEC-0014)."""

from __future__ import annotations

import json
import os
import shutil
import socket
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor.config import PORT_RANGE_END, PORT_RANGE_START

from .http_support import exchange
from .stdio_support import StdioSession, mcp_command

REPO = Path(__file__).resolve().parents[1]
DOC_BOOTSTRAP = REPO / "templates" / "bootstrap" / "document-empty.html"
STOP_BOUND_SECONDS = 2.0
PREFERRED_PORT = 7842
FASTMCP_PREFIX = "Error calling tool 'start_server': "  # added by FastMCP to every tool error, not by the server


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


PORT_ATTEMPTS = 5


def start_on_free_port(session: StdioSession, request_id: int, doc: str) -> dict[str, Any]:
    """``start_server`` on a port the OS just reported free, retried on a fresh one when another process took it.

    An explicit port never falls back, so a port taken between ``free_port`` and the bind is an "already in use"
    tool error, not a different port; only that error is retried, and the answer is still checked by the caller.
    """
    for attempt in range(PORT_ATTEMPTS):
        port = free_port()
        result = session.call_tool(request_id, "start_server", {"file": doc, "port": port})
        if result.get("isError") and "already in use" in error_text(result) and attempt < PORT_ATTEMPTS - 1:
            continue
        answer = payload(result)
        assert answer["port"] == port
        return answer
    raise AssertionError("unreachable")


def payload(result: dict[str, Any]) -> dict[str, Any]:
    """The JSON answer of a successful tool call."""
    assert not result.get("isError"), result
    value: dict[str, Any] = json.loads(result["content"][0]["text"])
    return value


def error_text(result: dict[str, Any]) -> str:
    assert result.get("isError"), result
    text: str = result["content"][0]["text"]
    return text


def health(port: int) -> int | None:
    return exchange(port, f"GET /health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode()).status


def copy_doc(path: Path) -> str:
    shutil.copyfile(DOC_BOOTSTRAP, path)
    return str(path)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[StdioSession]:
    env = {
        **os.environ,
        "HTMLEDITOR_STATE_DIR": str(tmp_path / "state"),
        "HTMLEDITOR_HOST": "127.0.0.1",
        "BROWSER": "true",
    }
    with StdioSession(mcp_command(), cwd=REPO, env=env) as started:
        started.initialize()
        yield started


def test_restart_on_the_same_port_with_a_tab_open(session: StdioSession, tmp_path: Path) -> None:
    """SPEC-0014/BT-001 (BUG-001 reproduction)."""
    doc = copy_doc(tmp_path / "doc.html")
    first = start_on_free_port(session, 2, doc)
    port = first["port"]
    assert first["started"] is True
    idle = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        assert health(port) == 200  # the idle connection was accepted before this one

        assert payload(session.call_tool(3, "stop_server", {})) == {"ok": True}
        stopped_at = time.monotonic()
        second = payload(session.call_tool(4, "start_server", {"file": doc, "port": port}))

        assert (second["ok"], second["started"], second["port"]) == (True, True, port)
        assert health(port) == 200
        idle.settimeout(max(0.01, stopped_at + STOP_BOUND_SECONDS - time.monotonic()))
        assert idle.recv(10) == b""
    finally:
        idle.close()
        session.call_tool(5, "stop_server", {})


def test_stop_twice_and_status(session: StdioSession, tmp_path: Path) -> None:
    """SPEC-0014/BT-013."""
    doc = copy_doc(tmp_path / "doc.html")
    assert start_on_free_port(session, 2, doc)["started"] is True

    assert payload(session.call_tool(3, "stop_server", {})) == {"ok": True}
    assert payload(session.call_tool(4, "stop_server", {})) == {"ok": True}
    assert payload(session.call_tool(5, "get_status", {}))["running"] is False


def test_stop_and_serve_as_today_without_connections(session: StdioSession, tmp_path: Path) -> None:
    """SPEC-0014/BT-020 (SPEC-0001/FR-009, FR-031)."""
    doc = copy_doc(tmp_path / "doc.html")
    other = copy_doc(tmp_path / "other.html")

    first = payload(session.call_tool(2, "start_server", {"file": doc}))
    second = payload(session.call_tool(3, "start_server", {"file": other}))
    stopped = payload(session.call_tool(4, "stop_server", {}))
    status = payload(session.call_tool(5, "get_status", {}))

    assert first["ok"] is True
    assert first["started"] is True
    assert first["port"] == PREFERRED_PORT or PORT_RANGE_START <= first["port"] <= PORT_RANGE_END
    assert (second["ok"], second["started"], second["port"], second["file"]) == (True, False, first["port"], other)
    assert stopped == {"ok": True}
    assert status["running"] is False


def test_explicit_port_taken_still_explained(session: StdioSession, tmp_path: Path) -> None:
    """SPEC-0014/BT-021 (SPEC-0001/FR-032): another process holds the port, without SO_REUSEADDR."""
    doc = copy_doc(tmp_path / "doc.html")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        port = int(holder.getsockname()[1])

        text = error_text(session.call_tool(2, "start_server", {"file": doc, "port": port}))

    assert text.startswith(FASTMCP_PREFIX), text
    assert text.removeprefix(FASTMCP_PREFIX).startswith(
        f"Port {port} is already in use (pass no --port to auto-pick a free one in {PORT_RANGE_START}-{PORT_RANGE_END}"
    ), text
