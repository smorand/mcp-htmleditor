"""Atomic file writing (SPEC-0007 DEC-010, SPEC-0009 US-0048).

``atomic_write`` writes ``patch``, the browser save and the arch layout: the new bytes go to a temporary file
in the same directory, then an atomic replace swaps it in, so a reader sees the old file or the new one,
never a mix. The mode of the replaced file is kept.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from .deck import DeckError
from .tracing import trace_span

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


def atomic_write(path: str | Path, data: bytes | str) -> bool:
    """Replace the file at ``path`` (symlinks followed) by ``data``; return False when the bytes are equal.

    Raises ``WriteError`` (a ``DeckError``) on failure, with the file untouched and no temporary file left.
    """
    payload = data.encode("utf-8") if isinstance(data, str) else data
    target = Path(path).resolve()
    with trace_span("file.write", {"file.path": str(target), "file.size": len(payload)}):
        try:
            return _replace(target, payload)
        except OSError as exc:
            raise WriteError(path, exc.strerror or str(exc)) from exc


def _replace(target: Path, data: bytes) -> bool:
    if target.is_file() and target.read_bytes() == data:
        return False
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else DEFAULT_FILE_MODE & ~_umask()
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary).chmod(mode)
        replace_file(temporary, str(target))
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return True


def _umask() -> int:
    current = os.umask(0)
    os.umask(current)
    return current
