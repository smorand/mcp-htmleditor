"""Locks of the SPEC-0016 arbitrations: a missing pandoc fails the DOCX export, a stale server record is not adopted.

No product behavior changes here (DEC-012): BR-018 to BR-020 keep today's code, these tests make a later change
that swallows a missing pandoc, reloads a dead process's record or loses the status of an idle process fail.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from . import stdio_support
from .test_server_lifecycle import free_port

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO / "templates" / "bootstrap"
PANDOC_MISSING_STDERR = "error: pandoc not found in PATH: install pandoc to export to DOCX."
STALE_PORT = 7845
STALE_PID = 999999
STALE_POLL_INTERVAL = 5000
DEFAULT_POLL_INTERVAL = 1000
SERVER_BOUND_SECONDS = 20.0
OBSERVE_INTERVAL_SECONDS = 0.1
STOP_BOUND_SECONDS = 10
COMMAND_BOUND_SECONDS = 30


def child_env(tmp_path: Path, **extra: str) -> dict[str, str]:
    """Environment of a child process: state and templates under the test, loopback host, no inherited port."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("HTMLEDITOR_")}
    env.update(
        HTMLEDITOR_STATE_DIR=str(tmp_path / "state"),
        HTMLEDITOR_TEMPLATES_DIR=str(REPO / "templates"),
        HTMLEDITOR_HOST="127.0.0.1",
    )
    env.update(extra)
    return env


def server_record_path(state_dir: Path, deck: Path) -> Path:
    key = hashlib.sha256(str(deck.resolve()).encode("utf-8")).hexdigest()[:32]
    return state_dir / "files" / key / "server.json"


def read_status(port: int) -> dict[str, Any] | None:
    """``GET /status`` as JSON, or None while nothing answers on ``port`` yet."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=2) as reply:
            status: dict[str, Any] = json.load(reply)
            return status
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return None


def wait_for_status(port: int, server: subprocess.Popen[bytes]) -> dict[str, Any]:
    """Poll ``GET /status`` until the server answers, at most ``SERVER_BOUND_SECONDS``; fail if it exited."""
    deadline = time.monotonic() + SERVER_BOUND_SECONDS
    while time.monotonic() < deadline:
        assert server.poll() is None, f"serve exited early with status {server.returncode}"
        status = read_status(port)
        if status is not None:
            return status
        time.sleep(OBSERVE_INTERVAL_SECONDS)
    raise AssertionError(f"no answer on /status of port {port} within {SERVER_BOUND_SECONDS:g} s")


@pytest.fixture
def empty_path_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "no-tools"
    directory.mkdir()
    return directory


def test_docx_export_without_pandoc_fails_explicitly(tmp_path: Path, empty_path_dir: Path) -> None:
    """SPEC-0016/BT-022 (BR-018): no pandoc on PATH, exit 1, the documented message, no output file."""
    document = tmp_path / "doc.html"
    shutil.copy(BOOTSTRAP / "document-empty.html", document)
    output = tmp_path / "doc.docx"

    done = subprocess.run(  # noqa: S603  fixed argument list, no shell
        [sys.executable, "-m", "mcp_htmleditor", "export", "docx", str(document), str(output)],
        env=child_env(tmp_path, PATH=str(empty_path_dir)),
        capture_output=True,
        text=True,
        timeout=COMMAND_BOUND_SECONDS,
        check=False,
    )

    assert done.returncode == 1, done.stdout + done.stderr
    assert done.stderr.strip() == PANDOC_MISSING_STDERR
    assert not output.exists()


@pytest.fixture
def stale_record_server(tmp_path: Path) -> Iterator[tuple[subprocess.Popen[bytes], Path, int]]:
    """A ``serve`` child on a free port ``HTMLEDITOR_PORT`` for a deck whose server record came from a dead process."""
    deck = tmp_path / "deck.html"
    shutil.copy(BOOTSTRAP / "slides-empty.html", deck)
    deck = deck.resolve()
    record = server_record_path(tmp_path / "state", deck)
    record.parent.mkdir(parents=True)
    record.write_text(
        json.dumps({"file": str(deck), "port": STALE_PORT, "pid": STALE_PID, "poll_interval": STALE_POLL_INTERVAL}),
        encoding="utf-8",
    )
    port = free_port()
    server = subprocess.Popen(  # noqa: S603  fixed argument list, no shell
        [sys.executable, "-m", "mcp_htmleditor", "serve", str(deck), "--no-browser"],
        env=child_env(tmp_path, HTMLEDITOR_PORT=str(port)),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=tmp_path,
    )
    try:
        yield server, deck, port
    finally:
        server.terminate()
        try:
            server.wait(timeout=STOP_BOUND_SECONDS)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=STOP_BOUND_SECONDS)


def test_stale_server_record_is_not_adopted(
    tmp_path: Path, stale_record_server: tuple[subprocess.Popen[bytes], Path, int]
) -> None:
    """SPEC-0016/BT-023 (BR-019, BR-020): serve ignores a dead record, an idle process reports the live one."""
    server, deck, port = stale_record_server

    status = wait_for_status(port, server)
    assert status["port"] == port
    assert status["poll_interval"] == DEFAULT_POLL_INTERVAL
    assert status["filename"] == str(deck)

    last = json.loads((tmp_path / "state" / "last.json").read_text(encoding="utf-8"))
    assert last == {"file": str(deck)}
    requests = [*stdio_support.initialize_requests(), stdio_support.tool_request(2, "get_status", {})]
    messages = stdio_support.run_session(requests, {2}, cwd=tmp_path, env=child_env(tmp_path))
    reply = next(message for message in messages if message.get("id") == 2)
    reported: dict[str, Any] = reply["result"]["structuredContent"]
    assert reported["running"] is False
    assert reported["port"] == port
    assert reported["pid"] == server.pid
    assert reported["file"] == str(deck)
