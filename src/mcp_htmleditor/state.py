"""State management for mcp-htmleditor.

Singleton in-process state backed by a .mcp_state.json file
placed next to the current HTML file (or in CWD if no file set).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config

_STATE_FILENAME = ".mcp_state.json"


class EditorState:
    """Singleton editor state.

    Keeps in-process state in sync with a JSON file on disk so that
    external processes (e.g. browser polling /status) can read it.
    """

    _instance: EditorState | None = None
    _initialized: bool = False

    def __new__(cls) -> EditorState:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self.current_file: str | None = None
        self.port: int = config.default_port()
        self.server_pid: int | None = None
        self.update_in_progress: bool = False
        self.poll_interval: int = config.default_poll_interval()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _state_path(self) -> Path:
        """Return the path of the .mcp_state.json file."""
        if self.current_file:
            return Path(self.current_file).parent / _STATE_FILENAME
        return Path.cwd() / _STATE_FILENAME

    def _to_dict(self) -> dict[str, Any]:
        return {
            "current_file": self.current_file,
            "port": self.port,
            "server_pid": self.server_pid,
            "update_in_progress": self.update_in_progress,
            "poll_interval": self.poll_interval,
        }

    def save(self) -> None:
        """Persist current state to .mcp_state.json."""
        path = self._state_path()
        path.write_text(json.dumps(self._to_dict(), indent=2), encoding="utf-8")

    def load(self) -> None:
        """Load state from .mcp_state.json if it exists."""
        path = self._state_path()
        if not path.exists():
            return
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            self.current_file = data.get("current_file", self.current_file)
            self.port = data.get("port", self.port)
            self.server_pid = data.get("server_pid", self.server_pid)
            self.update_in_progress = data.get(
                "update_in_progress", self.update_in_progress
            )
            self.poll_interval = data.get("poll_interval", self.poll_interval)
        except (json.JSONDecodeError, OSError):
            pass

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def set_file(self, path: str) -> None:
        """Set the current HTML file and persist state."""
        self.current_file = str(Path(path).resolve())
        self.save()

    def set_update_flag(self, value: bool) -> None:
        """Set the update_in_progress flag and persist state."""
        self.update_in_progress = value
        self.save()

    def get_mtime(self) -> float:
        """Return the mtime of the current HTML file, or 0.0 if not set."""
        if not self.current_file:
            return 0.0
        try:
            return Path(self.current_file).stat().st_mtime
        except OSError:
            return 0.0


# Module-level singleton accessor
def get_state() -> EditorState:
    """Return the global EditorState singleton."""
    return EditorState()
