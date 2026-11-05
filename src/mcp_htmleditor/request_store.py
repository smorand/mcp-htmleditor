"""Request record of a file: one JSON document per user file under the state directory (SPEC-0010 US-0052).

The record holds the id counter, the requests and the review of one file, so an id, a request and an applied
mark can never disagree after a crash. It lives in ``<state_dir>/files/<key>/requests/record.json``, where
``<key>`` is the SPEC-0009 key of the file (``sha256(realpath)[:32]``), so nothing is ever created next to the
user's file and a symlink shares the record of its target.

A change takes an exclusive ``fcntl.flock`` on the sibling ``record.lock`` (``flock`` belongs to the open file
description, so it excludes other processes and other threads), reads the record, applies the change and swaps
the new bytes in with an atomic rename. Readers take no lock: they see the old record or the new one.
``fcntl`` limits the module to macOS, Linux and Docker (SPEC-0010 DEC-015).
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .fileio import WriteError, atomic_write
from .tracing import trace_span

logger = logging.getLogger(__name__)

RECORD_VERSION = 1
RECORD_NAME = "record.json"
LOCK_NAME = "record.lock"
KEY_LENGTH = 32
DIR_MODE = 0o700
LOCK_MODE = 0o600
STATUSES = ("pending", "done", "skipped")

ErrorKind = Literal["invalid", "conflict", "not_found", "storage"]


class RequestError(Exception):
    """A refused or failed request operation; ``kind`` picks the status of each surface, ``message`` is the text."""

    def __init__(self, kind: ErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind: ErrorKind = kind
        self.message = message


@dataclass(frozen=True, slots=True)
class Request:
    id: str
    slide: str | None
    title: str
    queued: str
    instruction: str
    status: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class Suggestion:
    id: str
    slide: str | None
    title: str
    why: str
    change: str
    applied: bool


@dataclass(slots=True)
class Record:
    next_id: int = 1
    revision: int = 0
    requests: list[Request] = field(default_factory=list)
    review: list[Suggestion] | None = None


class RequestStore:
    """Reads and changes the request record of a file; ``state_dir`` is ``get_settings().state_dir``."""

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir

    def record_dir(self, file: Path) -> Path:
        """``<state_dir>/files/<key>/requests``, the key being the SPEC-0009 one (symlinks resolved)."""
        key = hashlib.sha256(os.path.realpath(file).encode("utf-8")).hexdigest()[:KEY_LENGTH]
        return self._state_dir / "files" / key / "requests"

    def read(self, file: Path) -> Record:
        """The record of ``file``, lock free; an absent record is an empty one and nothing is created."""
        path = self.record_dir(file) / RECORD_NAME
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return Record()
        except (OSError, ValueError) as exc:
            raise _unreadable(file, exc) from exc
        try:
            return _parse_record(text)
        except (ValueError, TypeError) as exc:
            raise _unreadable(file, exc) from exc

    def update[T](self, file: Path, operation: str, change: Callable[[Record], T]) -> T:
        """Run ``change`` on the record under the exclusive lock and write it back when it changed.

        The revision grows by one only when the serialized record differs; an exception from ``change`` (or an
        unreadable record) writes nothing. ``operation`` names the span; the text of a request never does.
        """
        directory = self.record_dir(file)
        with trace_span(
            "requests.update", {"file.path": str(directory / RECORD_NAME), "requests.operation": operation}
        ):
            self._make_private_dir(directory)
            with _exclusive_lock(directory / LOCK_NAME):
                record = self.read(file)
                before = _serialize(file, record)
                result = change(record)
                if _serialize(file, record) != before:
                    record.revision += 1
                    _write(directory / RECORD_NAME, _serialize(file, record))
                return result

    def revision(self, file: Path) -> int:
        """The revision of the record, 0 when absent or unreadable (the status poll must never fail)."""
        try:
            return self.read(file).revision
        except RequestError as exc:
            logger.warning("Cannot read the requests revision: %s", exc.message)
            return 0

    def _make_private_dir(self, directory: Path) -> None:
        """Create the state directories down to ``directory``, each one with mode 0700."""
        self._state_dir.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
        folder = self._state_dir
        for part in directory.relative_to(self._state_dir).parts:
            folder = folder / part
            folder.mkdir(mode=DIR_MODE, exist_ok=True)


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, LOCK_MODE)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _write(path: Path, data: bytes) -> None:
    try:
        atomic_write(path, data)
    except WriteError as exc:
        raise OSError(exc.reason) from exc


def _unreadable(file: Path, exc: Exception) -> RequestError:
    reason = getattr(exc, "strerror", None) or str(exc)
    return RequestError("storage", f"Requests record of {file} is unreadable: {reason}")


def _serialize(file: Path, record: Record) -> bytes:
    payload = {
        "version": RECORD_VERSION,
        "file": os.path.realpath(file),
        "revision": record.revision,
        "next_id": record.next_id,
        "requests": [asdict(request) for request in record.requests],
        "review": None if record.review is None else [asdict(suggestion) for suggestion in record.review],
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _parse_record(text: str) -> Record:
    """Read a record; any shape error is a ``ValueError`` naming the field, never its content."""
    data = json.loads(text)
    if not isinstance(data, dict) or data.get("version") != RECORD_VERSION:
        raise ValueError("unsupported record version")
    requests = _items(data, "requests")
    review = data.get("review")
    if review is not None and not isinstance(review, list):
        raise ValueError("review is not a list")
    return Record(
        next_id=_whole(data, "next_id", minimum=1),
        revision=_whole(data, "revision", minimum=0),
        requests=[_parse_request(item) for item in requests],
        review=None if review is None else [_parse_suggestion(item) for item in review],
    )


def _parse_request(item: object) -> Request:
    fields = _fields(item, "request")
    status = _text(fields, "status")
    if status not in STATUSES:
        raise ValueError("request status is unknown")
    return Request(
        id=_text(fields, "id"),
        slide=_text(fields, "slide", nullable=True),
        title=_text(fields, "title"),
        queued=_text(fields, "queued"),
        instruction=_text(fields, "instruction"),
        status=status,
        reason=_text(fields, "reason", nullable=True),
    )


def _parse_suggestion(item: object) -> Suggestion:
    fields = _fields(item, "suggestion")
    applied = fields.get("applied")
    if not isinstance(applied, bool):
        raise ValueError("suggestion applied is not a boolean")
    return Suggestion(
        id=_text(fields, "id"),
        slide=_text(fields, "slide", nullable=True),
        title=_text(fields, "title"),
        why=_text(fields, "why"),
        change=_text(fields, "change"),
        applied=applied,
    )


def _items(data: dict[str, Any], name: str) -> list[object]:
    value = data.get(name)
    if not isinstance(value, list):
        raise ValueError(f"{name} is not a list")
    return value


def _fields(item: object, kind: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"a {kind} is not an object")
    return item


def _whole(data: dict[str, Any], name: str, *, minimum: int) -> int:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} is not a valid counter")
    return value


def _text(fields: dict[str, Any], name: str, *, nullable: bool = False) -> Any:
    value = fields.get(name)
    if isinstance(value, str) or (nullable and value is None):
        return value
    raise ValueError(f"{name} is not a string")
