"""Tests for the /health payload of the editor HTTP server."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp_htmleditor import state as state_module
from mcp_htmleditor.http_server import health_payload
from mcp_htmleditor.version import __version__
from tests.conftest import ServedDeck
from tests.http_support import exchange, json_body

SERVE = Callable[[Path], ServedDeck]
KEYS = {"ok", "status", "pid", "file", "page", "port", "version", "started", "uptime_seconds"}


def test_health_reports_status_and_version(fresh_state: state_module.EditorState) -> None:
    """Without a file loaded, /health still answers ok with the version."""
    payload = health_payload()

    assert payload["status"] == "ok"
    assert payload["version"] == __version__
    assert payload["file"] is None
    assert payload["page"] is None
    assert payload["port"] == 7842
    assert set(payload) == KEYS


def test_health_reports_the_served_file(fresh_state: state_module.EditorState, html_file: Path) -> None:
    """Once a file is loaded, /health names it and its port."""
    fresh_state.set_file(str(html_file))
    fresh_state.port = 9001

    payload = health_payload()

    assert payload["file"] == str(html_file.resolve())
    assert payload["page"] == "doc.html"
    assert payload["port"] == 9001
    assert payload["status"] == "ok"


def test_version_is_a_non_empty_string() -> None:
    """The version placeholder is replaced at build time, never empty."""
    assert isinstance(__version__, str)
    assert __version__


def test_health_started_and_uptime(fresh_state: state_module.EditorState) -> None:
    """``started`` is a UTC ISO time and the uptime a non negative int."""
    payload = health_payload()

    assert payload["ok"] is True
    assert payload["pid"] == os.getpid()
    assert datetime.fromisoformat(payload["started"]).utcoffset().total_seconds() == 0
    assert isinstance(payload["uptime_seconds"], int)
    assert payload["uptime_seconds"] >= 0


def _get(deck: ServedDeck, path: str, host: str | None = None, method: str = "GET") -> tuple[int | None, bytes]:
    host_line = host if host is not None else f"127.0.0.1:{deck.port}"
    reply = exchange(deck.port, f"{method} {path} HTTP/1.1\r\nHost: {host_line}\r\n\r\n".encode())
    return reply.status, reply.body


def _payload(deck: ServedDeck) -> dict[str, Any]:
    request = f"GET /health HTTP/1.1\r\nHost: 127.0.0.1:{deck.port}\r\n\r\n".encode()
    return json_body(exchange(deck.port, request))


def test_health_over_http(served_deck: ServedDeck) -> None:
    """The live route answers the documented shape with this process pid and the loaded file."""
    status, body = _get(served_deck, "/health")
    payload = _payload(served_deck)

    assert status == 200
    assert set(payload) == KEYS
    assert payload["pid"] == os.getpid()
    assert payload["file"] == str(served_deck.path.resolve())
    assert payload["page"] == "deck.html"
    assert payload["port"] == served_deck.port
    assert payload["version"] == __version__
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", payload["started"])
    assert payload["uptime_seconds"] >= 0
    assert body.startswith(b"{")


def test_health_is_open_to_any_host_unlike_status(served_deck: ServedDeck) -> None:
    """/health skips the header gate (health checks, SPEC-0005 BT-016); /status keeps it."""
    assert _get(served_deck, "/health", host="attacker.example")[0] == 200
    assert _get(served_deck, "/status", host="attacker.example")[0] == 403


def test_health_method_rules_and_unknown_paths(served_deck: ServedDeck) -> None:
    """POST is gated then unknown (404), OPTIONS 405, HEAD 501, a sub path falls to the file route (404)."""
    assert _get(served_deck, "/health", method="POST")[0] == 404
    assert _get(served_deck, "/health", host="attacker.example", method="POST")[0] == 403
    assert _get(served_deck, "/health", method="OPTIONS")[0] == 405
    assert _get(served_deck, "/health", method="HEAD")[0] == 501
    assert _get(served_deck, "/health/x")[0] == 404


def test_health_writes_nothing(served_deck: ServedDeck, isolate_state_dir: Path) -> None:
    """Calls leave the state dir and the deck unchanged."""

    def snapshot() -> dict[str, tuple[int, int]]:
        files = [*isolate_state_dir.rglob("*"), served_deck.path]
        return {str(f): (f.stat().st_mtime_ns, f.stat().st_size) for f in files if f.is_file()}

    before = snapshot()
    for _ in range(3):
        assert _get(served_deck, "/health")[0] == 200
    assert snapshot() == before


def test_health_without_file_over_http(serve_deck: SERVE, tmp_path: Path) -> None:
    """A server whose state holds no file reports null ``file`` and ``page``."""
    deck = serve_deck(tmp_path / "x.html")
    state_module.get_state().current_file = None
    payload = _payload(deck)

    assert payload["file"] is None
    assert payload["page"] is None
