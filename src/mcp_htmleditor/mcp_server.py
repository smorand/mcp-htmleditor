"""MCP server for html-editor.

Exposes 6 tools for LLM agents to control the WYSIWYG editor.
"""

from __future__ import annotations

import webbrowser
from typing import Any

from fastmcp import FastMCP

from .http_server import (
    is_server_running,
    start_http_server,
    stop_http_server,
)
from .state import get_state

mcp: FastMCP = FastMCP("html-editor")


@mcp.tool()
def start_server(file: str, port: int = 7842) -> dict[str, Any]:
    """Start the WYSIWYG HTTP server for the given HTML file.

    Idempotent: if the server is already running on the same port with the
    same file, returns OK without restarting anything. Opens the browser
    automatically.

    Args:
        file: Absolute or relative path to the HTML file to edit.
        port: TCP port for the HTTP server (default 7842).

    Returns:
        Dict with keys: ok, url, file, port, started (bool).
    """
    from pathlib import Path

    abs_file = str(Path(file).resolve())
    state = get_state()

    already_running = is_server_running() and state.current_file == abs_file

    started = start_http_server(abs_file, port) if not already_running else False

    url = f"http://localhost:{port}/"
    if not already_running:
        webbrowser.open(url)

    return {
        "ok": True,
        "url": url,
        "file": abs_file,
        "port": port,
        "started": started,
    }


@mcp.tool()
def stop_server() -> dict[str, Any]:
    """Stop the WYSIWYG HTTP server.

    Returns:
        Dict with key: ok.
    """
    stop_http_server()
    return {"ok": True}


@mcp.tool()
def get_status() -> dict[str, Any]:
    """Return the current server status.

    Returns:
        Dict with keys: file, port, pid, update_in_progress, mtime, running.
    """
    state = get_state()
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
    from pathlib import Path

    abs_file = str(Path(file).resolve())
    state = get_state()
    state.set_file(abs_file)
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
    state.set_update_flag(False)
    return {"ok": True}


def run_mcp_server() -> None:
    """Entry point: run the MCP server over stdio transport."""
    mcp.run(transport="stdio")
