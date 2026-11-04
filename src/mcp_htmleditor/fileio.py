"""Atomic file writing (SPEC-0007 DEC-010).

``atomic_write`` is the only writer of ``patch``: the new bytes go to a temporary file in the same
directory, then ``os.replace`` swaps it in, so a reader sees the old file or the new one, never a mix.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from .deck import DeckError
from .tracing import trace_span

DEFAULT_FILE_MODE = 0o666


def atomic_write(path: str | Path, data: bytes) -> None:
    """Replace the file at ``path`` (symlinks followed) by ``data``; raise ``DeckError`` on failure."""
    target = Path(path).resolve()
    with trace_span("file.write", {"file.path": str(target), "file.size": len(data)}):
        try:
            _replace(target, data)
        except OSError as exc:
            raise DeckError(f"Cannot write {path}: {exc.strerror or exc}") from exc


def _replace(target: Path, data: bytes) -> None:
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else DEFAULT_FILE_MODE & ~_umask()
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary).chmod(mode)
        Path(temporary).replace(target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _umask() -> int:
    current = os.umask(0)
    os.umask(current)
    return current
