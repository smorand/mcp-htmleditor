"""Atomic file writing (SPEC-0007 DEC-010, SPEC-0009 US-0048).

``atomic_write`` writes ``patch``, the browser save and the arch layout: the new bytes go to a temporary file
in the same directory, then an atomic replace swaps it in, so a reader sees the old file or the new one,
never a mix. The mode of the replaced file is kept.
"""

from __future__ import annotations

import logging
import os
import stat
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .deck import DeckError
from .tracing import trace_span

if TYPE_CHECKING:
    from .history import HistoryStore, Version

logger = logging.getLogger(__name__)

DEFAULT_FILE_MODE = 0o666
TEMPLATE_MARKERS = ("/templates/bootstrap/", "/templates/reference/")


class WriteError(DeckError):
    """A write failed; ``reason`` is the operating system message (``strerror``, else the exception text)."""

    def __init__(self, path: str | Path, reason: str) -> None:
        super().__init__(f"Cannot write {path}: {reason}")
        self.reason = reason


def is_template_path(path: str) -> bool:
    """True when ``path`` (a backslash read as a slash) lies under a bootstrap or reference templates folder."""
    normalized = path.replace("\\", "/")
    return any(marker in normalized for marker in TEMPLATE_MARKERS)


def replace_file(source: str, destination: str) -> None:
    """Move ``source`` over ``destination``: the single failure seam of ``atomic_write`` (patched by tests)."""
    Path(source).replace(destination)


def atomic_write(
    path: str | Path, data: bytes | str, *, reason: str | None = None, history: HistoryStore | None = None
) -> bool:
    """Replace the file at ``path`` (symlinks followed) by ``data``; return False when the bytes are equal.

    With a ``reason`` the previous content is first kept in the history (``history``, else the default store),
    and kept only if the write succeeds; without one nothing is kept. Raises ``WriteError`` (a ``DeckError``)
    on failure, with the file and the history untouched and no temporary file left.
    """
    payload = data.encode("utf-8") if isinstance(data, str) else data
    target = Path(path).resolve()
    with trace_span("file.write", {"file.path": str(target), "file.size": len(payload)}):
        try:
            return _replace(target, payload, reason, history)
        except OSError as exc:
            raise WriteError(path, exc.strerror or str(exc)) from exc


def _replace(target: Path, data: bytes, reason: str | None, history: HistoryStore | None) -> bool:
    existing = target.read_bytes() if target.is_file() else None
    if existing == data:
        return False
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else DEFAULT_FILE_MODE & ~_umask()
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    store, staged = history, None
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary).chmod(mode)
        if reason is not None and existing is not None:
            store = store or _default_store()
            staged = _stage_snapshot(store, target, existing, reason)
        replace_file(temporary, str(target))
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        if store is not None and staged is not None:
            store.discard(target, staged)
        raise
    if store is not None and staged is not None:
        _prune_quietly(store, target)
    return True


def _default_store() -> HistoryStore:
    from .history import default_store  # noqa: PLC0415 - history imports this module (restore_version)

    return default_store()


def _stage_snapshot(store: HistoryStore, target: Path, content: bytes, reason: str) -> Version:
    with trace_span(
        "history.snapshot", {"file.path": str(target), "file.size": len(content), "history.reason": reason}
    ):
        return store.stage(target, content, reason)


def _prune_quietly(store: HistoryStore, target: Path) -> None:
    """The write succeeded: a failure to prune must not turn it into an error."""
    try:
        store.prune(target)
    except OSError as exc:
        logger.warning("Cannot prune the history of %s: %s", target, exc)


def _umask() -> int:
    current = os.umask(0)
    os.umask(current)
    return current
