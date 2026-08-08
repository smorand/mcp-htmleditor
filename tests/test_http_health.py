"""Tests for the /health payload of the editor HTTP server."""

from __future__ import annotations

from pathlib import Path

from mcp_htmleditor import state as state_module
from mcp_htmleditor.http_server import health_payload
from mcp_htmleditor.version import __version__


def test_health_reports_status_and_version(fresh_state: state_module.EditorState) -> None:
    """Without a file loaded, /health still answers ok with the version."""
    payload = health_payload()

    assert payload["status"] == "ok"
    assert payload["version"] == __version__
    assert payload["file"] is None
    assert payload["port"] == 7842


def test_health_reports_the_served_file(fresh_state: state_module.EditorState, html_file: Path) -> None:
    """Once a file is loaded, /health names it and its port."""
    fresh_state.set_file(str(html_file))
    fresh_state.port = 9001

    payload = health_payload()

    assert payload["file"] == str(html_file.resolve())
    assert payload["port"] == 9001
    assert payload["status"] == "ok"


def test_version_is_a_non_empty_string() -> None:
    """The version placeholder is replaced at build time, never empty."""
    assert isinstance(__version__, str)
    assert __version__
