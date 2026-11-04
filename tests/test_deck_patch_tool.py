"""The patch tool: result shape, CLI error text, editor flag, modification time (SPEC-0007 FR-NEW-003/016)."""

from __future__ import annotations

import json
import os
import socket
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor import config as config_module
from mcp_htmleditor import state as state_module
from mcp_htmleditor.http_server import start_http_server, stop_http_server

from .deck_support import FIXED_TIME, call_tool, deck_ei, run_cli, write_deck

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "skill" / "core.md"
SET_TITLE = {"op": "set_text", "id": "slide-2", "selector": ".slide-h1", "text": "Contexte et enjeux"}
SAME_TITLE = {"op": "set_text", "id": "slide-2", "selector": ".slide-h1", "text": "Contexte"}


def _call_patch(**arguments: Any) -> tuple[bool, Any]:
    """``call_tool`` for arguments that are not strings (a list of operations, a boolean)."""
    return call_tool("patch", **arguments)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int) -> None:
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    pytest.fail("HTTP server did not start in time")


@pytest.fixture
def ei_file(tmp_path: Path, fresh_state: state_module.EditorState) -> str:
    return write_deck(tmp_path / "ei.html", deck_ei())


@pytest.fixture
def served(ei_file: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """DECK-EI served by an in process editor server; yields the file path."""
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", str(REPO / "templates"))
    config_module.reset_settings_cache()
    port = _free_port()
    start_http_server(ei_file, port=port)
    _wait_for_port(port)
    try:
        yield ei_file
    finally:
        stop_http_server()


def _spy_flag(monkeypatch: pytest.MonkeyPatch, state: state_module.EditorState) -> list[bool]:
    calls: list[bool] = []
    original = state.set_update_flag

    def record(value: bool) -> None:
        calls.append(value)
        original(value)

    monkeypatch.setattr(state, "set_update_flag", record)
    return calls


def test_editor_state_around_a_patch(served: str) -> None:
    """SPEC-0007/E2E-034."""
    ok, status = call_tool("get_status")
    assert ok
    assert status["file"] == str(Path(served).resolve())
    assert status["mtime"] == FIXED_TIME

    ok, result = _call_patch(file=served, ops=[SET_TITLE])
    assert ok, result
    ok, after = call_tool("get_status")
    assert ok
    assert after["update_in_progress"] is False
    assert after["mtime"] > FIXED_TIME

    os.utime(served, (FIXED_TIME, FIXED_TIME))
    ok, result = _call_patch(file=served, ops=[{**SET_TITLE}])
    assert ok, result
    assert result["changed"] is False
    ok, unchanged = call_tool("get_status")
    assert ok
    assert unchanged["mtime"] == FIXED_TIME
    assert unchanged["update_in_progress"] is False


def test_result_shape_for_a_change(ei_file: str) -> None:
    ok, result = _call_patch(file=ei_file, ops=[SET_TITLE])

    assert ok
    assert result == {"ok": True, "changed": True, "slides": 8, "problems": []}
    assert list(result) == ["ok", "changed", "slides", "problems"]
    assert "Contexte et enjeux" in Path(ei_file).read_text(encoding="utf-8")


def test_dry_run_adds_the_flag_last_and_writes_nothing(ei_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
    before = Path(ei_file).read_bytes()
    calls = _spy_flag(monkeypatch, state_module.get_state())

    ok, result = _call_patch(file=ei_file, ops=[SET_TITLE], dry_run=True)

    assert ok
    assert result == {"ok": True, "changed": True, "slides": 8, "problems": [], "dry_run": True}
    assert list(result)[-1] == "dry_run"
    assert Path(ei_file).read_bytes() == before
    assert Path(ei_file).stat().st_mtime == FIXED_TIME
    assert calls == []


def test_no_change_patch_touches_neither_flag_nor_mtime(ei_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _spy_flag(monkeypatch, state_module.get_state())

    ok, result = _call_patch(file=ei_file, ops=[SAME_TITLE])

    assert ok
    assert result["changed"] is False
    assert calls == []
    assert Path(ei_file).stat().st_mtime == FIXED_TIME


def test_error_text_is_the_cli_line_without_its_prefix(ei_file: str, tmp_path: Path) -> None:
    ops = [SET_TITLE, {"op": "frobnicate"}]
    ops_file = tmp_path / "ops.json"
    ops_file.write_text(json.dumps(ops), encoding="utf-8")
    _, stderr, status = run_cli("patch", ei_file, "--ops", str(ops_file))

    ok, message = _call_patch(file=ei_file, ops=ops)

    assert status == 1
    assert not ok
    assert message == 'patch failed at operation 2: unknown operation "frobnicate" (nothing written)'
    assert stderr.strip() == f"error: {message}"
    assert not message.startswith("error: ")


def test_unknown_operation_as_first_operation_message(ei_file: str) -> None:
    ok, message = _call_patch(file=ei_file, ops=[{"op": "frobnicate"}])

    assert not ok
    assert message == 'patch failed at operation 1: unknown operation "frobnicate" (nothing written)'


def test_malformed_operation_reaches_the_spec_message(ei_file: str) -> None:
    ok, message = _call_patch(file=ei_file, ops=[3])

    assert not ok
    assert message == "patch failed at operation 1: operation must be an object (nothing written)"
    assert Path(ei_file).stat().st_mtime == FIXED_TIME


def test_flag_calls_for_a_write_and_for_a_validation_failure(ei_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _spy_flag(monkeypatch, state_module.get_state())

    ok, _ = _call_patch(file=ei_file, ops=[{"op": "set_text", "id": "slide-99", "selector": "h1", "text": "x"}])
    assert not ok
    assert calls == []

    ok, _ = _call_patch(file=ei_file, ops=[SET_TITLE])
    assert ok
    assert calls == [True, False]
    assert state_module.get_state().update_in_progress is False


def test_flag_is_false_after_a_failing_write(tmp_path: Path, fresh_state: state_module.EditorState) -> None:
    directory = tmp_path / "locked"
    directory.mkdir()
    path = write_deck(directory / "ei.html", deck_ei())
    directory.chmod(0o500)
    try:
        ok, message = _call_patch(file=path, ops=[SET_TITLE])
    finally:
        directory.chmod(0o700)

    assert not ok
    assert message.startswith(f"Cannot write {path}: ")
    assert fresh_state.update_in_progress is False
    assert Path(path).stat().st_mtime == FIXED_TIME


def test_flag_calls_for_a_failing_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = state_module.get_state()
    directory = tmp_path / "locked"
    directory.mkdir()
    path = write_deck(directory / "ei.html", deck_ei())
    calls = _spy_flag(monkeypatch, state)
    directory.chmod(0o500)
    try:
        ok, _ = _call_patch(file=path, ops=[SET_TITLE])
    finally:
        directory.chmod(0o700)

    assert not ok
    assert calls == [True, False]


def test_a_template_is_refused(tmp_path: Path, fresh_state: state_module.EditorState) -> None:
    folder = tmp_path / "templates" / "bootstrap"
    folder.mkdir(parents=True)
    path = write_deck(folder / "x.html", deck_ei())

    ok, message = _call_patch(file=path, ops=[SET_TITLE])

    assert not ok
    assert message == f"Refusing to modify a template: {path}"
    assert Path(path).stat().st_mtime == FIXED_TIME


def test_patch_is_registered_and_listed_in_the_skill_core() -> None:
    from mcp_htmleditor.mcp_server import registered_tool_names

    lines = CORE.read_text(encoding="utf-8").split("## Tools", 1)[1].split("## ", 1)[0].splitlines()
    stdout, _, status = run_cli("skill-audit")

    assert "patch" in registered_tool_names()
    assert any(line.startswith("- patch:") for line in lines)
    assert status == 0, stdout
