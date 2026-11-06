"""One stdio session with a child process, every line read bounded (SPEC-0014 BR-014, DEC-010).

A daemon reader thread pushes each line of the child's stdout into a queue and ``read_message`` waits on that queue
for at most ``LINE_TIMEOUT_SECONDS``. ``select`` on the descriptor is not used: a text mode pipe buffers ahead, so it
can miss a line already buffered. Tests shorten the bound with
``monkeypatch.setattr(stdio_support, "LINE_TIMEOUT_SECONDS", 1.0)``; the constant is read through the module at each
call, which is the only seam.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import TracebackType
from typing import IO, Any

import pytest

LINE_TIMEOUT_SECONDS: float = 30.0
REAP_TIMEOUT_SECONDS = 10
SILENT_CHILD = [sys.executable, "-c", "import time; time.sleep(3600)"]
CLOSED_MESSAGE = "the server closed stdout before answering"
CLIENT_INFO = {"name": "t", "version": "0"}


def mcp_command() -> list[str]:
    return [sys.executable, "-m", "mcp_htmleditor", "mcp"]


def silence_message() -> str:
    return f"the server did not answer within {LINE_TIMEOUT_SECONDS:g} s"


def request(request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def initialize_requests() -> list[dict[str, Any]]:
    params = {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": CLIENT_INFO}
    return [request(1, "initialize", params), {"jsonrpc": "2.0", "method": "notifications/initialized"}]


def tool_request(request_id: int, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return request(request_id, "tools/call", {"name": name, "arguments": arguments})


class StdioSession:
    """A child process driven over JSON lines; leaving the ``with`` block kills and reaps it."""

    def __init__(self, command: Sequence[str], *, cwd: Path, env: Mapping[str, str] | None = None) -> None:
        self._process = subprocess.Popen(  # noqa: S603  command built by the tests, no shell
            list(command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=cwd,
            env=dict(os.environ if env is None else env),
        )
        assert self._process.stdin is not None
        assert self._process.stdout is not None
        self._stdin: IO[str] = self._process.stdin
        self._lines: queue.Queue[str] = queue.Queue()
        self._messages: list[dict[str, Any]] = []
        reader = threading.Thread(target=self._pump, args=(self._process.stdout,), daemon=True)
        reader.start()

    def __enter__(self) -> StdioSession:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._kill_and_reap()

    @property
    def messages(self) -> list[dict[str, Any]]:
        return self._messages

    @property
    def process(self) -> subprocess.Popen[str]:
        return self._process

    def send(self, message: dict[str, Any]) -> None:
        self._stdin.write(json.dumps(message) + "\n")
        self._stdin.flush()

    def read_message(self) -> dict[str, Any]:
        """One line of the child's stdout as JSON; a silent child is killed and the test fails (BR-014)."""
        try:
            line = self._lines.get(timeout=LINE_TIMEOUT_SECONDS)
        except queue.Empty:
            self._kill_and_reap()
            pytest.fail(silence_message())
        assert line, CLOSED_MESSAGE
        message: dict[str, Any] = json.loads(line)  # a stray text line fails here
        self._messages.append(message)
        return message

    def read_until(self, wanted_ids: set[int]) -> None:
        while not wanted_ids <= {m.get("id") for m in self._messages}:
            self.read_message()

    def initialize(self) -> None:
        for message in initialize_requests():
            self.send(message)
        self.read_until({1})

    def call_tool(self, request_id: int, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.send(tool_request(request_id, name, arguments))
        while True:
            message = self.read_message()
            if message.get("id") == request_id:
                result: dict[str, Any] = message["result"]
                return result

    def _pump(self, stdout: IO[str]) -> None:
        for line in stdout:
            self._lines.put(line)
        self._lines.put("")

    def _kill_and_reap(self) -> None:
        self._process.kill()
        self._process.wait(timeout=REAP_TIMEOUT_SECONDS)


def run_session(
    requests: Sequence[dict[str, Any]],
    wanted_ids: set[int],
    *,
    command: Sequence[str] | None = None,
    cwd: Path,
    env: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Send every request at once, read until every wanted id was answered, return all messages read."""
    with StdioSession(command or mcp_command(), cwd=cwd, env=env) as session:
        for message in requests:
            session.send(message)
        session.read_until(wanted_ids)
        return session.messages
