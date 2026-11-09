"""The state record is read by the live reader only: no `load` method, and a corrupt record never raises (SPEC-0019)."""

from __future__ import annotations

from pathlib import Path

from mcp_htmleditor import config
from mcp_htmleditor.state import EditorState

from .test_state import _file_dir


def test_corrupt_server_record_never_raises(fresh_state: EditorState, html_file: Path) -> None:
    """DT-001: a corrupt server.json reads as absent through snapshot() (SPEC-0001 E2E-007)."""
    fresh_state.set_file(str(html_file))
    fresh_state.port = 6001
    fresh_state.save()
    (_file_dir(html_file) / "server.json").write_text("{ not valid json", encoding="utf-8")

    EditorState._instance = None
    snapshot = EditorState().snapshot()

    assert snapshot["file"] == str(html_file.resolve())
    assert snapshot["port"] == config.default_port()
    assert snapshot["pid"] is None


def test_editor_state_has_no_load_method() -> None:
    """DT-002: the restore SPEC-0016 forbids has no entry point."""
    assert not hasattr(EditorState, "load")
