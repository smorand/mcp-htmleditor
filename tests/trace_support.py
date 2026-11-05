"""Subprocess driver for the trace tests (SPEC-0013 DEC-016).

The tracer provider is process global and settable once, and ``tests/test_tracing.py`` owns the one of the test
process. A traced run therefore happens in a child interpreter with its own log, cache and state folders under
``tmp_path``: it calls ``configure_tracing()`` and ``setup_logging()``, runs the tool through an in process
``fastmcp.Client`` (or starts the editor server), flushes the provider and reports the outcome as JSON.
Arguments holding lone surrogates travel as JSON with ``ensure_ascii=True`` so the escapes survive.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.http_support import exchange

REPO = Path(__file__).resolve().parents[1]
TRACE_FILE = "mcp-htmleditor-otel.log"
PORT_TOKEN = b"%PORT%"
TIMEOUT = 120

_PRELUDE = """
import json, sys
from mcp_htmleditor.logging_config import setup_logging
from mcp_htmleditor.tracing import configure_tracing
setup_logging()
configure_tracing()
from opentelemetry import trace


def flush():
    trace.get_tracer_provider().force_flush()
"""

_TOOL_SCRIPT = (
    _PRELUDE
    + """
import asyncio
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp_htmleditor.mcp_server import mcp

tool, arguments = json.loads(sys.argv[1]), json.loads(sys.argv[2])


async def session():
    async with Client(mcp) as client:
        try:
            result = await client.call_tool(tool, arguments)
        except ToolError as exc:
            return {"ok": False, "data": str(exc)}
        return {"ok": True, "data": result.data}


outcome = asyncio.run(session())
flush()
print(json.dumps(outcome))
"""
)

_SERVER_SCRIPT = (
    _PRELUDE
    + """
from mcp_htmleditor.http_server import start_http_server, stop_http_server

start_http_server(sys.argv[1], port=int(sys.argv[2]))
sys.stdin.read()
stop_http_server()
flush()
"""
)


@dataclass(frozen=True)
class TracedRun:
    ok: bool  # tool outcome: True with data, False with the tool error text
    data: Any
    stdout: str
    stderr: str
    trace_lines: list[str]  # the local trace file read as strict UTF-8, split in lines ([] with OTLP)
    log_text: str = ""  # the application log file read as strict UTF-8


def run_traced_tool(
    tmp_path: Path, tool: str, arguments: dict[str, Any], *, env: dict[str, str] | None = None
) -> TracedRun:
    """Call ``tool`` in a child interpreter with tracing configured, and collect what it wrote."""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter, repository script
        [sys.executable, "-c", _TOOL_SCRIPT, json.dumps(tool), json.dumps(arguments, ensure_ascii=True)],
        env=_environment(tmp_path, env),
        cwd=REPO,
        capture_output=True,
        timeout=TIMEOUT,
        check=False,
    )
    stdout = completed.stdout.decode("utf-8")
    outcome = json.loads(stdout.strip().splitlines()[-1]) if completed.returncode == 0 else {"ok": None, "data": None}
    return TracedRun(
        ok=outcome["ok"],
        data=outcome["data"],
        stdout=stdout,
        stderr=completed.stderr.decode("utf-8"),
        trace_lines=_trace_lines(tmp_path),
        log_text=_log_text(tmp_path),
    )


def run_traced_server(tmp_path: Path, served: Path, raw_requests: list[bytes]) -> TracedRun:
    """Serve ``served`` in a child interpreter, send each raw request, then stop it.

    ``%PORT%`` in a request is replaced by the port of the server. ``data`` holds the status of each answer.
    """
    port = _free_port()
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter, repository script
        [sys.executable, "-c", _SERVER_SCRIPT, str(served), str(port)],
        env=_environment(tmp_path, None),
        cwd=REPO,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_listening(process, port)
        statuses = [exchange(port, request.replace(PORT_TOKEN, str(port).encode())).status for request in raw_requests]
    finally:
        stdout, stderr = process.communicate(input=b"", timeout=TIMEOUT)
    return TracedRun(
        ok=process.returncode == 0,
        data=statuses,
        stdout=stdout.decode("utf-8"),
        stderr=stderr.decode("utf-8"),
        trace_lines=_trace_lines(tmp_path),
        log_text=_log_text(tmp_path),
    )


def _environment(tmp_path: Path, extra: dict[str, str] | None) -> dict[str, str]:
    base = {key: value for key, value in os.environ.items() if not key.startswith("HTMLEDITOR_")}
    base.update(
        PYTHONPATH=str(REPO / "src"),
        HTMLEDITOR_LOG_DIR=str(tmp_path / "logs"),
        HTMLEDITOR_STATE_DIR=str(tmp_path / "state"),
        HTMLEDITOR_CACHE_DIR=str(tmp_path / "cache"),
    )
    base.update(extra or {})
    return base


def _trace_lines(tmp_path: Path) -> list[str]:
    path = tmp_path / "logs" / TRACE_FILE
    if not path.exists():
        return []
    return [line for line in path.read_bytes().decode("utf-8").split("\n") if line]


def _log_text(tmp_path: Path) -> str:
    path = tmp_path / "logs" / "mcp-htmleditor.log"
    return path.read_bytes().decode("utf-8") if path.exists() else ""


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_listening(process: subprocess.Popen[bytes], port: int) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"editor server exited early with {process.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError("editor server did not start in time")
