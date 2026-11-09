"""`serve --poll N` sets the served interval without touching the environment (SPEC-0019)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from mcp_htmleditor import config
from mcp_htmleditor.cli import _serve_file
from mcp_htmleditor.state import EditorState, get_state

SRC = Path(__file__).resolve().parents[1] / "src" / "mcp_htmleditor"
VARIABLE = "HTMLEDITOR_POLL_INTERVAL"
FORBIDDEN = ("os.environ", "os.putenv", "os.getenv")


def _stop_after_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the server and the wait loop so `_serve_file` returns at once."""

    def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("mcp_htmleditor.http_server.start_http_server", lambda *_args, **_kwargs: (True, 7999))
    monkeypatch.setattr("mcp_htmleditor.http_server.stop_http_server", lambda: None)
    monkeypatch.setattr(time, "sleep", interrupt)


def test_no_environment_access_outside_config() -> None:
    """DT-003: configuration is read through Settings, never through the process environment."""
    offenders = [
        f"{path.relative_to(SRC)}: {token}"
        for path in sorted(SRC.rglob("*.py"))
        if path.name != "config.py"
        for token in FORBIDDEN
        if token in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_poll_flag_sets_interval_without_environment(
    fresh_state: EditorState, html_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DT-010: --poll 250 is served as 250 and leaves the variable absent."""
    monkeypatch.delenv(VARIABLE, raising=False)
    _stop_after_start(monkeypatch)

    _serve_file(str(html_file), None, 250, "127.0.0.1", open_browser=False)

    assert get_state().poll_interval == 250
    assert VARIABLE not in os.environ
    assert config.get_settings().poll_interval == 1000


def test_without_poll_flag_interval_comes_from_settings(
    reset_state: None, html_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DT-011: no --poll, the interval is the Settings value and the variable is untouched."""
    monkeypatch.setenv(VARIABLE, "400")
    EditorState._instance = None
    _stop_after_start(monkeypatch)

    _serve_file(str(html_file), None, None, "127.0.0.1", open_browser=False)

    assert get_state().poll_interval == 400
    assert os.environ[VARIABLE] == "400"
