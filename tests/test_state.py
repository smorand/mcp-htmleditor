"""Tests for the EditorState singleton and its persistence."""

from __future__ import annotations

import json
from pathlib import Path

from mcp_htmleditor.state import EditorState, get_state


def test_singleton_identity(fresh_state: EditorState) -> None:
    """get_state() always returns the same instance."""
    assert get_state() is fresh_state
    assert EditorState() is fresh_state


def test_singleton_preserves_state_across_init(fresh_state: EditorState) -> None:
    """Re-instantiating does not reset already-populated fields."""
    fresh_state.port = 9999
    # A second construction must not wipe the field (init guard).
    again = EditorState()
    assert again.port == 9999


def test_defaults(fresh_state: EditorState) -> None:
    """A fresh state exposes the documented defaults."""
    assert fresh_state.current_file is None
    assert fresh_state.port == 7842
    assert fresh_state.server_pid is None
    assert fresh_state.update_in_progress is False
    assert isinstance(fresh_state.poll_interval, int)


def test_set_file_resolves_and_persists(fresh_state: EditorState, html_file: Path) -> None:
    """set_file stores an absolute path and writes the state file next to it."""
    fresh_state.set_file(str(html_file))
    assert fresh_state.current_file == str(html_file.resolve())

    state_path = html_file.parent / ".mcp_state.json"
    assert state_path.exists()
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["current_file"] == str(html_file.resolve())


def test_set_update_flag_persists(fresh_state: EditorState, html_file: Path) -> None:
    """set_update_flag toggles the flag and writes it to disk."""
    fresh_state.set_file(str(html_file))
    fresh_state.set_update_flag(True)
    assert fresh_state.update_in_progress is True

    state_path = html_file.parent / ".mcp_state.json"
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["update_in_progress"] is True

    fresh_state.set_update_flag(False)
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["update_in_progress"] is False


def test_get_mtime_without_file(fresh_state: EditorState) -> None:
    """No current file → mtime is 0.0."""
    assert fresh_state.get_mtime() == 0.0


def test_get_mtime_missing_file(fresh_state: EditorState, tmp_path: Path) -> None:
    """A current file that does not exist → mtime is 0.0."""
    fresh_state.current_file = str(tmp_path / "nope.html")
    assert fresh_state.get_mtime() == 0.0


def test_get_mtime_existing_file(fresh_state: EditorState, html_file: Path) -> None:
    """An existing current file returns its real mtime."""
    fresh_state.set_file(str(html_file))
    assert fresh_state.get_mtime() == html_file.stat().st_mtime


def test_save_then_load_roundtrip(fresh_state: EditorState, html_file: Path) -> None:
    """load() restores what save() persisted."""
    fresh_state.set_file(str(html_file))
    fresh_state.port = 5555
    fresh_state.server_pid = 4242
    fresh_state.poll_interval = 250
    fresh_state.save()

    # Mutate in-memory, then load from disk to overwrite.
    fresh_state.port = 1
    fresh_state.server_pid = None
    fresh_state.poll_interval = 1
    fresh_state.load()

    assert fresh_state.port == 5555
    assert fresh_state.server_pid == 4242
    assert fresh_state.poll_interval == 250


def test_load_missing_file_is_noop(fresh_state: EditorState, tmp_path: Path) -> None:
    """load() with no state file on disk leaves state untouched."""
    fresh_state.current_file = str(tmp_path / "doc.html")
    fresh_state.port = 4321
    fresh_state.load()
    assert fresh_state.port == 4321


def test_load_corrupt_file_is_ignored(fresh_state: EditorState, html_file: Path) -> None:
    """A corrupt state file is swallowed and does not raise."""
    fresh_state.set_file(str(html_file))
    state_path = html_file.parent / ".mcp_state.json"
    state_path.write_text("{ not valid json", encoding="utf-8")
    # Must not raise.
    fresh_state.load()
    # current_file should still point at the html file (unchanged).
    assert fresh_state.current_file == str(html_file.resolve())
