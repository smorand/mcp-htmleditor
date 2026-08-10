"""MCP server for html-editor.

Exposes 6 tools for LLM agents to control the WYSIWYG editor. Every tool call is
traced as ``mcp.<tool>`` (see :mod:`.tracing`).
"""

from __future__ import annotations

import logging
import webbrowser
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .http_server import (
    is_server_running,
    start_http_server,
    stop_http_server,
)
from .state import get_state
from .tracing import trace_span

logger = logging.getLogger(__name__)

mcp: FastMCP = FastMCP("html-editor")


@mcp.tool()
def start_server(file: str, port: int | None = None) -> dict[str, Any]:
    """Start the WYSIWYG HTTP server for the given HTML file.

    Idempotent: if the server is already running in this MCP process, returns
    OK without restarting anything (only the served file is switched). Opens
    the browser automatically.

    Args:
        file: Absolute or relative path to the HTML file to edit.
        port: TCP port for the HTTP server. Omit it (default) to auto-pick a
            free port (preferred default, then 7840-7849): starting several
            independent ``mcp-htmleditor mcp`` processes, each editing its
            own file, then lets multiple presentations coexist without
            colliding on the same port. Pass an explicit port only when you
            need a specific one; it is used as-is and the call fails clearly
            if it is already taken.

    Returns:
        Dict with keys: ok, url, file, port, started (bool). `port` is the
        port actually bound, which may differ from the requested one when
        it was auto-picked.
    """
    abs_file = str(Path(file).resolve())
    state = get_state()

    with trace_span("mcp.start_server", {"file.path": abs_file}) as span:
        already_running = is_server_running() and state.current_file == abs_file

        if already_running:
            started, bound_port = False, state.port
        else:
            started, bound_port = start_http_server(abs_file, port)

        url = f"http://localhost:{bound_port}/"
        if not already_running:
            webbrowser.open(url)

        span.set_attribute("server.started", started)
        span.set_attribute("server.port", bound_port)
        logger.info("start_server file=%s port=%d started=%s", abs_file, bound_port, started)
        return {
            "ok": True,
            "url": url,
            "file": abs_file,
            "port": bound_port,
            "started": started,
        }


@mcp.tool()
def stop_server() -> dict[str, Any]:
    """Stop the WYSIWYG HTTP server.

    Returns:
        Dict with key: ok.
    """
    with trace_span("mcp.stop_server"):
        stop_http_server()
    return {"ok": True}


@mcp.tool()
def get_status() -> dict[str, Any]:
    """Return the current server status.

    Returns:
        Dict with keys: file, port, pid, update_in_progress, mtime, running.
    """
    state = get_state()
    with trace_span("mcp.get_status", {"server.running": is_server_running()}):
        return {
            "file": state.current_file,
            "port": state.port,
            "pid": state.server_pid,
            "update_in_progress": state.update_in_progress,
            "mtime": state.get_mtime(),
            "running": is_server_running(),
        }


@mcp.tool()
def open_file(file: str) -> dict[str, Any]:
    """Change the HTML file being served.

    The browser will pick up the change on its next poll cycle
    (within poll_interval ms) and reload the content automatically.

    Args:
        file: Path to the new HTML file.

    Returns:
        Dict with keys: ok, file.
    """
    abs_file = str(Path(file).resolve())
    state = get_state()
    with trace_span("mcp.open_file", {"file.path": abs_file}):
        state.set_file(abs_file)
    logger.info("open_file %s", abs_file)
    return {"ok": True, "file": abs_file}


@mcp.tool()
def update_start() -> dict[str, Any]:
    """Signal that a content modification is starting.

    Sets the update_in_progress flag so the browser shows the
    'modification en cours' overlay and does not apply concurrent
    mtime-triggered reloads.

    Returns:
        Dict with key: ok.
    """
    state = get_state()
    with trace_span("mcp.update_start", {"file.path": state.current_file or ""}):
        state.set_update_flag(True)
    return {"ok": True}


@mcp.tool()
def update_end() -> dict[str, Any]:
    """Signal that a content modification is complete.

    Clears the update_in_progress flag. The browser will detect the
    changed mtime on the next poll and reload the content automatically.

    Returns:
        Dict with key: ok.
    """
    state = get_state()
    with trace_span("mcp.update_end", {"file.path": state.current_file or ""}):
        state.set_update_flag(False)
    return {"ok": True}


def run_mcp_server() -> None:
    """Entry point: run the MCP server over stdio transport.

    Logging goes to stderr and to the log file only: stdout carries the MCP
    protocol frames.
    """
    logger.info("Starting MCP server (stdio transport)")
    mcp.run(transport="stdio")
