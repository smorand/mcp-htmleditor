"""State management for mcp-htmleditor (SPEC-0009 FR-NEW-006, FR-NEW-008).

Singleton in-process state whose records live in the state directory
(:func:`config.state_dir`), never next to the user's file::

    <state_dir>/last.json                  {"file"}                            file most recently served or opened
    <state_dir>/files/<key>/server.json    {"file","port","pid","poll_interval"}
    <state_dir>/files/<key>/update.json    {"file","started_at"}               removed by end_update

``key`` is ``sha256(resolved absolute path).hexdigest()[:32]``. Each record is a whole file written
atomically, so processes sharing a file never clobber each other's fields. The update flag expires
``UPDATE_TTL_SECONDS`` after the last ``start_update``; it is computed on read from ``clock``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeGuard

from . import config

logger = logging.getLogger(__name__)

UPDATE_TTL_SECONDS = 120.0
_KEY_LENGTH = 32
_DIR_MODE = 0o700
_LAST = "last.json"
_SERVER = "server.json"
_UPDATE = "update.json"


class EditorState:
    """Singleton editor state.

    ``current_file`` is the file this process serves. A process with no file of its own acts on the
    file named by ``last.json``; with neither, the update flag is held in memory.
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
        self.poll_interval: int = config.default_poll_interval()
        self.clock: Callable[[], float] = time.time
        self.save_lock = threading.Lock()
        # Start times this process could not write, keyed by target file (None when unbound).
        self._memory_updates: dict[str | None, float] = {}
        # End times of updates whose record this process could not remove.
        self._memory_ends: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Update flag
    # ------------------------------------------------------------------

    @property
    def update_expires_in(self) -> int | None:
        """Whole seconds left on the update flag (1 to 120), or None when no update is in progress."""
        started_at = self._started_at(self._target_file())
        if started_at is None:
            return None
        elapsed = max(0.0, self.clock() - started_at)
        if elapsed >= UPDATE_TTL_SECONDS:
            return None
        return math.ceil(UPDATE_TTL_SECONDS - elapsed)

    @property
    def update_in_progress(self) -> bool:
        """True while less than 120 seconds have elapsed since the last ``start_update``."""
        return self.update_expires_in is not None

    def start_update(self) -> int:
        """Raise (or renew) the update flag of the target file; return its lifetime in seconds."""
        target = self._target_file()
        started_at = self.clock()
        self._memory_updates.pop(target, None)
        if target is not None:
            self._memory_ends.pop(target, None)
        if target is None or not self._write_record(_file_dir(target) / _UPDATE, _update_record(target, started_at)):
            self._memory_updates[target] = started_at
        return int(UPDATE_TTL_SECONDS)

    def end_update(self) -> None:
        """Clear the update flag of the target file at once."""
        target = self._target_file()
        self._memory_updates.pop(target, None)
        if target is None:
            return
        try:
            (_file_dir(target) / _UPDATE).unlink(missing_ok=True)
        except OSError as exc:
            self._memory_ends[target] = self.clock()
            logger.warning("Cannot remove the update record of %s: %s", target, exc)

    def set_update_flag(self, value: bool) -> None:
        """Compatibility wrapper (SPEC-0007 ``patch``): True starts an update, False ends it."""
        if value:
            self.start_update()
        else:
            self.end_update()

    def _started_at(self, target: str | None) -> float | None:
        """The latest known start: the record or this process's unwritten start, whichever is later.

        A record not newer than an end this process failed to remove reads as ended.
        """
        recorded = self._recorded_start(target)
        memory = self._memory_updates.get(target)
        if recorded is None or memory is None:
            return memory if recorded is None else recorded
        return max(recorded, memory)

    def _recorded_start(self, target: str | None) -> float | None:
        if target is None:
            return None
        started_at = _read_record(_file_dir(target) / _UPDATE).get("started_at")
        if not _is_number(started_at):
            return None
        ended_at = self._memory_ends.get(target)
        return None if ended_at is not None and started_at <= ended_at else float(started_at)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _target_file(self) -> str | None:
        """The file this process serves, else the one named by ``last.json``."""
        if self.current_file:
            return self.current_file
        last = _read_record(config.state_dir() / _LAST).get("file")
        return last if isinstance(last, str) and last else None

    def save(self) -> None:
        """Persist the server record of the current file; failures are logged, never raised (DEC-022)."""
        if not self.current_file:
            return
        record = {
            "file": self.current_file,
            "port": self.port,
            "pid": self.server_pid,
            "poll_interval": self.poll_interval,
        }
        self._write_record(_file_dir(self.current_file) / _SERVER, record)

    def load(self) -> None:
        """Load port, pid and poll interval from the current file's server record, if readable."""
        if not self.current_file:
            return
        data = _read_record(_file_dir(self.current_file) / _SERVER)
        port, pid, poll = data.get("port"), data.get("pid"), data.get("poll_interval")
        self.port = port if _is_int(port) else self.port
        self.server_pid = pid if _is_int(pid) else self.server_pid
        self.poll_interval = int(poll) if _is_number(poll) else self.poll_interval

    def _write_record(self, path: Path, record: dict[str, Any]) -> bool:
        try:
            _atomic_write_json(path, record)
        except OSError as exc:
            logger.warning("Cannot write the state record %s: %s", path, exc)
            return False
        return True

    # ------------------------------------------------------------------
    # Mutation and read helpers
    # ------------------------------------------------------------------

    def set_file(self, path: str) -> None:
        """Set the current HTML file, persist its server record and name it in ``last.json``."""
        self.current_file = str(Path(path).resolve())
        self.save()
        self._write_record(config.state_dir() / _LAST, {"file": self.current_file})

    def get_mtime(self) -> float:
        """Return the mtime of the target HTML file, or 0.0 if not set."""
        target = self._target_file()
        if not target:
            return 0.0
        try:
            return Path(target).stat().st_mtime
        except OSError:
            return 0.0

    def snapshot(self) -> dict[str, Any]:
        """Return file, port, pid, update flag, its expiry and mtime, as seen by this process."""
        target = self._target_file()
        port, pid = self.port, self.server_pid
        if target is not None and not self.current_file:
            server = _read_record(_file_dir(target) / _SERVER)
            port, pid = server.get("port", port), server.get("pid", pid)
        expires_in = self.update_expires_in
        return {
            "file": target,
            "port": port,
            "pid": pid,
            "update_in_progress": expires_in is not None,
            "update_expires_in": expires_in,
            "mtime": self.get_mtime(),
        }


def _file_dir(file: str) -> Path:
    """Directory holding the records of ``file``, keyed by its resolved absolute path."""
    key = hashlib.sha256(str(Path(file).resolve()).encode("utf-8")).hexdigest()[:_KEY_LENGTH]
    return config.state_dir() / "files" / key


def _is_int(value: Any) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _update_record(file: str, started_at: float) -> dict[str, Any]:
    return {"file": file, "started_at": float(started_at)}


def _read_record(path: Path) -> dict[str, Any]:
    """Return the JSON object stored at ``path``; missing or corrupt records read as empty."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _ensure_private_dir(path: Path) -> None:
    """Create the state directories down to ``path``, each one below the state root with mode 0700."""
    root = config.state_dir()
    for folder in (root, *reversed([p for p in path.parents if root in p.parents]), path):
        if not folder.is_dir():
            folder.mkdir(mode=_DIR_MODE, parents=folder == root, exist_ok=True)


def _atomic_write_json(path: Path, record: dict[str, Any]) -> None:
    """Replace ``path`` by ``record`` through a temporary file in the same directory."""
    _ensure_private_dir(path.parent)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


# Module-level singleton accessor
def get_state() -> EditorState:
    """Return the global EditorState singleton."""
    return EditorState()
