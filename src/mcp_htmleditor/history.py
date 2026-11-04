"""File history in the state directory (SPEC-0009 US-0050, DEC-001 to DEC-003).

A version is the previous content of a file, kept verbatim as ``<id>.<reason>.html`` under
``<state_dir>/files/<key>/history/``; there is no index. The id is the UTC time ``YYYYMMDDTHHMMSS`` plus ``Z``,
with ``-2``, ``-3``, ... when taken. Versions are staged through a hidden temporary file, so a reader never
sees a partial one; hidden files are ignored by the listing.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import config
from .deck import DeckError
from .state import _file_dir, get_state
from .tracing import trace_span

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 20
_MAX_ATTEMPTS = 1000
_NAME = re.compile(r"^(\d{8}T\d{6}Z)(?:-(\d+))?\.([a-z-]+)\.html$")


@dataclass(frozen=True, slots=True)
class Version:
    """One kept version: its id, the UTF-8 byte count of its content and why it was kept."""

    id: str
    bytes: int
    reason: str


class HistoryError(DeckError):
    """A history command failed; ``str(exc)`` is the message printed after ``error: ``."""


def _id_in_use(folder: Path, version_id: str) -> bool:
    """True when a file of ``folder`` already carries ``version_id`` (any reason)."""
    prefix = f"{version_id}."
    return any(entry.name.startswith(prefix) and _NAME.match(entry.name) for entry in folder.iterdir())


def _publish(folder: Path, temporary: Path, version_id: str, reason: str, content: bytes) -> bool:
    """Move the staged file to ``<id>.<reason>.html`` without replacing anything; False when the id is taken."""
    claim = folder / f".{version_id}.claim"
    try:
        os.close(os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return False
    try:
        if _id_in_use(folder, version_id):
            return False
        final = folder / f"{version_id}.{reason}.html"
        try:
            os.link(temporary, final)
        except FileExistsError:
            return False
        except OSError:  # hard links unsupported: exclusive create instead (the claim keeps the id ours)
            with final.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        return True
    finally:
        claim.unlink(missing_ok=True)


class HistoryStore:
    """The versions of every file, under ``root`` (the state directory)."""

    def __init__(self, root: Path, clock: Callable[[], float] = time.time) -> None:
        self._root = root
        self._clock = clock

    def stage(self, path: Path, content: bytes, reason: str) -> Version:
        """Keep ``content`` as a new version of ``path`` (written to a hidden file, then published exclusively).

        The id is claimed with an exclusive hidden ``.<id>.claim`` file and refused when any file already carries
        it (whatever its reason); the final name is published with ``os.link`` so an existing file is never
        replaced. Two writers racing for the same second therefore end on distinct ids.
        """
        folder = self.list_dir(path)
        folder.mkdir(parents=True, exist_ok=True)
        base = time.strftime("%Y%m%dT%H%M%S", time.gmtime(self._clock())) + "Z"
        descriptor, temporary = tempfile.mkstemp(dir=folder, prefix=".", suffix=".tmp")
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            for suffix in range(1, _MAX_ATTEMPTS + 1):
                version_id = base if suffix == 1 else f"{base}-{suffix}"
                if _publish(folder, Path(temporary), version_id, reason, content):
                    return Version(version_id, len(content), reason)
            raise HistoryError(f"Could not find a free history id for {base}")
        finally:
            Path(temporary).unlink(missing_ok=True)

    def discard(self, path: Path, version: Version) -> None:
        """Remove a staged version (no error when it is already gone)."""
        (self.list_dir(path) / f"{version.id}.{version.reason}.html").unlink(missing_ok=True)

    def prune(self, path: Path) -> None:
        """Delete the oldest versions beyond ``HISTORY_LIMIT``."""
        for version in self.list_versions(path)[HISTORY_LIMIT:]:
            self.discard(path, version)

    def list_versions(self, path: Path) -> list[Version]:
        """The versions of ``path``, newest first (by timestamp, then numeric suffix)."""
        folder = self.list_dir(path)
        if not folder.is_dir():
            return []
        found: list[tuple[str, int, Version]] = []
        for entry in folder.iterdir():
            match = _NAME.match(entry.name)
            if match:
                stamp, suffix, reason = match.group(1), int(match.group(2) or 1), match.group(3)
                version_id = stamp if suffix == 1 else f"{stamp}-{suffix}"
                found.append((stamp, suffix, Version(version_id, entry.stat().st_size, reason)))
        return [version for _, _, version in sorted(found, key=lambda item: item[:2], reverse=True)]

    def list_dir(self, path: Path) -> Path:
        """The folder holding the versions of ``path``."""
        return self._root / "files" / _file_dir(str(path)).name / "history"

    def read(self, path: Path, version_id: str) -> bytes:
        """The content of version ``version_id``; ``HistoryError`` (naming the valid ids) when unknown."""
        versions = self.list_versions(path)
        for version in versions:
            if version.id == version_id:
                return (self.list_dir(path) / f"{version.id}.{version.reason}.html").read_bytes()
        valid = ", ".join(version.id for version in versions) or "none"
        raise HistoryError(f'Unknown history id "{version_id}". Valid ids: {valid}')


def default_store() -> HistoryStore:
    """The store in the state directory, with the ids driven by the editor clock."""
    return HistoryStore(config.state_dir(), lambda: get_state().clock())


def list_versions(file: str, store: HistoryStore | None = None) -> tuple[Path, list[Version]]:
    """Resolve ``file`` (it must exist) and return it with its versions, newest first."""
    target = Path(file).resolve()
    if not target.is_file():
        raise HistoryError(f"File not found: {file}")
    return target, (store or default_store()).list_versions(target)


def restore_version(file: str, version_id: str, store: HistoryStore | None = None) -> Path:
    """Put version ``version_id`` back (the current content is kept first); return the resolved path."""
    from .fileio import WriteError, atomic_write, is_template_path  # noqa: PLC0415 - fileio imports this module

    target = Path(file).resolve()
    if is_template_path(str(target)):
        raise HistoryError(f"Refusing to modify a template: {file}")
    if not target.is_file():
        raise HistoryError(f"File not found: {file}")
    history = store or default_store()
    content = history.read(target, version_id)
    with trace_span("history.restore", {"file.path": str(target), "history.id": version_id}):
        try:
            atomic_write(target, content, reason="restore", history=history)
        except WriteError as exc:
            raise HistoryError(exc.reason) from exc
    return target
