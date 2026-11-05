"""Rules of the request loop: queue, list, complete and delete the requests of a file (SPEC-0010 US-0052).

The rules and their messages live here only; the HTTP routes and the command line translate a ``RequestError``
(``kind`` to a status or an ``error: `` line), so every surface says the same thing (SPEC-0010 DEC-005).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import get_settings
from .request_store import ErrorKind, Record, Request, RequestError, RequestStore, Suggestion
from .textcheck import UNENCODABLE_FILE_NAME, UNENCODABLE_TEXT, is_utf8_encodable

__all__ = [
    "BODY_MAX_BYTES",
    "ErrorKind",
    "RequestError",
    "RequestService",
    "Snapshot",
    "build_request_service",
    "is_blank",
    "request_to_dict",
    "require_file",
    "snapshot_to_dict",
    "suggestion_to_dict",
    "utc_now",
]

INSTRUCTION_MAX = 4000
PENDING_MAX = 50
TITLE_MAX = 60
REVIEW_MAX = 6
BODY_MAX_BYTES = 1_048_576
QUEUED_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
COMPLETE_STATUSES = ("done", "skipped")
SUGGESTION_FIELDS = ("id", "slide", "title", "why", "change")

# The Unicode White_Space set: \t \n \v \f \r, space, U+0085, U+00A0, U+1680, U+2000 to U+200A, U+2028, U+2029,
# U+202F, U+205F, U+3000. ``str.strip`` would also drop U+001C to U+001F, which are not White_Space.
_BLANK = re.compile(r"[\t-\r \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*")
_LINE_BREAK = re.compile(r"\r\n|\n|\r")


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """What ``GET /requests`` shows: the record revision, the pending count, the requests and the suggestions."""

    revision: int
    pending: int
    requests: list[Request]
    suggestions: list[Suggestion]


class RequestService:
    """Queues, lists, completes and deletes requests; every change goes through ``RequestStore.update``."""

    def __init__(self, store: RequestStore, clock: Callable[[], datetime] = utc_now) -> None:
        self._store = store
        self._clock = clock

    def queue(self, file: Path, instruction: str, slide: str | None) -> Request:
        """Store a pending request: blank, then length, then (under the lock) the pending limit."""
        if is_blank(instruction):
            raise RequestError("invalid", "Write a request first")
        _check_length(instruction)
        try:
            return self._store.update(file, "queue", lambda record: self._append(record, instruction, slide))
        except OSError as exc:
            raise RequestError("storage", f"Could not queue the request: {exc}") from exc

    def apply_suggestion(self, file: Path, suggestion_id: str) -> Request:
        """Queue the request of a suggestion and mark it applied in one record write (FR-NEW-007)."""
        try:
            return self._store.update(file, "apply_suggestion", lambda record: self._apply(record, suggestion_id))
        except OSError as exc:
            raise RequestError("storage", f"Could not queue the request: {exc}") from exc

    def list_requests(self, file: Path) -> list[Request]:
        """Every request of ``file`` whatever its status, oldest first."""
        return list(self._store.read(file).requests)

    def complete(self, file: Path, request_id: str, status: str, reason: str | None) -> Request:
        """Mark a request ``done`` or ``skipped``; the checks and the write share one store update."""
        if reason is not None and not is_utf8_encodable(reason):
            raise RequestError("invalid", UNENCODABLE_TEXT)
        try:
            return self._store.update(file, "complete", lambda record: self._finish(record, request_id, status, reason))
        except OSError as exc:
            raise RequestError("storage", f"Could not update the request: {exc}") from exc

    def delete(self, file: Path, request_id: str) -> None:
        """Remove a request; an unknown id changes nothing (so the revision does not move)."""

        def remove(record: Record) -> None:
            record.requests = [request for request in record.requests if request.id != request_id]

        try:
            self._store.update(file, "delete", remove)
        except OSError as exc:
            raise RequestError("storage", f"Could not delete the request: {exc}") from exc

    def write_review(self, file: Path, raw: object) -> int:
        """Replace the review of ``file`` by ``raw`` and return the count; the rules run before any write."""
        suggestions = _check_review(raw)

        def replace_review(record: Record) -> None:
            record.review = suggestions

        try:
            self._store.update(file, "write_review", replace_review)
        except OSError as exc:
            raise RequestError("storage", f"Could not write the review: {exc}") from exc
        return len(suggestions)

    def read_review(self, file: Path) -> list[Suggestion]:
        """The stored suggestions of ``file``; ``[]`` when the review was never written or is empty."""
        return list(self._store.read(file).review or [])

    def snapshot(self, file: Path) -> Snapshot:
        """The record as one consistent read (an atomic rename makes a lock free read consistent)."""
        record = self._store.read(file)
        pending = sum(1 for request in record.requests if request.status == "pending")
        return Snapshot(record.revision, pending, list(record.requests), list(record.review or []))

    def revision(self, file: Path) -> int:
        """The record revision for ``/status``: 0 when absent or unreadable."""
        return self._store.revision(file)

    def _finish(self, record: Record, request_id: str, status: str, reason: str | None) -> Request:
        """Checks in order: id, status, reason, already completed; ``done`` drops the reason, ``skipped`` keeps it."""
        index = next((position for position, item in enumerate(record.requests) if item.id == request_id), None)
        if index is None:
            valid = ", ".join(item.id for item in record.requests) or "none"
            raise RequestError("not_found", f'Unknown request id "{request_id}". Valid ids: {valid}')
        if status not in COMPLETE_STATUSES:
            raise RequestError("invalid", "Status must be done or skipped")
        if status == "skipped" and (reason is None or is_blank(reason)):
            raise RequestError("invalid", "A reason is required to skip a request")
        current = record.requests[index]
        if current.status != "pending":
            raise RequestError("conflict", f"Request {current.id} is already {current.status}")
        updated = replace(current, status=status, reason=reason if status == "skipped" else None)
        record.requests[index] = updated
        return updated

    def _apply(self, record: Record, suggestion_id: str) -> Request:
        """Checks in order: unknown id, already applied, length, pending limit; nothing changes on a refusal."""
        index = next((i for i, item in enumerate(record.review or []) if item.id == suggestion_id), None)
        if index is None or record.review is None:
            raise RequestError("not_found", f"Suggestion {suggestion_id} no longer exists")
        current = record.review[index]
        if current.applied:
            raise RequestError("conflict", f"Suggestion {suggestion_id} was already applied")
        instruction = f"{current.title}. {current.change}"
        _check_length(instruction)
        request = self._append(record, instruction, current.slide)
        record.review[index] = replace(current, applied=True)
        return request

    def _append(self, record: Record, instruction: str, slide: str | None) -> Request:
        if sum(1 for request in record.requests if request.status == "pending") >= PENDING_MAX:
            raise RequestError("conflict", f"Too many pending requests (max {PENDING_MAX})")
        request = Request(
            id=f"R-{record.next_id:04d}",
            slide=slide,
            title=_LINE_BREAK.sub(" ", instruction)[:TITLE_MAX],
            queued=self._clock().strftime(QUEUED_FORMAT),
            instruction=instruction,
            status="pending",
            reason=None,
        )
        record.next_id += 1
        record.requests.append(request)
        return request


def _check_length(instruction: str) -> None:
    if len(instruction) > INSTRUCTION_MAX:
        raise RequestError("invalid", f"Request too long (max {INSTRUCTION_MAX} characters)")


def _check_review(raw: object) -> list[Suggestion]:
    """Count first, then each position in turn: the first faulty suggestion decides the message."""
    if not isinstance(raw, list):
        raise RequestError("invalid", "Review must be a list of suggestions")
    if len(raw) > REVIEW_MAX:
        raise RequestError("invalid", f"At most {REVIEW_MAX} suggestions")
    seen: set[str] = set()
    suggestions: list[Suggestion] = []
    for position, item in enumerate(raw, start=1):
        suggestion = _check_suggestion(position, item, seen)
        seen.add(suggestion.id)
        suggestions.append(suggestion)
    for suggestion in suggestions:
        for name in SUGGESTION_FIELDS:
            if (value := getattr(suggestion, name)) is not None:
                _require_encodable(value)
    return suggestions


def _require_encodable(text: str) -> None:
    if not is_utf8_encodable(text):
        raise RequestError("invalid", UNENCODABLE_TEXT)


def _check_suggestion(position: int, item: object, seen: set[str]) -> Suggestion:
    """Missing or invalid field (in field order), then the title length, then a repeated id."""
    fields = item if isinstance(item, dict) else {}
    for name in SUGGESTION_FIELDS:
        if name not in fields or not _has_text(fields[name], is_nullable=name == "slide"):
            raise RequestError("invalid", f'Suggestion {position}: missing field "{name}"')
    if len(fields["title"]) > TITLE_MAX:
        raise RequestError("invalid", f"Suggestion {position}: title is longer than {TITLE_MAX} characters")
    if fields["id"] in seen:
        _require_encodable(fields["id"])  # the message below quotes the id
        raise RequestError("invalid", f'Suggestion {position}: duplicate id "{fields["id"]}"')
    return Suggestion(
        id=fields["id"],
        slide=fields["slide"],
        title=fields["title"],
        why=fields["why"],
        change=fields["change"],
        applied=False,
    )


def _has_text(value: object, *, is_nullable: bool) -> bool:
    if value is None:
        return is_nullable
    return isinstance(value, str) and not is_blank(value)


def is_blank(text: str) -> bool:
    """True when ``text`` holds only Unicode White_Space characters (or nothing)."""
    return _BLANK.fullmatch(text) is not None


def require_file(file: str) -> Path:
    """Resolve ``file``, which must exist; the error names it as typed, and refuses a name UTF-8 cannot hold."""
    if not is_utf8_encodable(file):
        raise RequestError("invalid", UNENCODABLE_FILE_NAME)
    path = Path(file).resolve()
    if not path.is_file():
        raise RequestError("not_found", f"File not found: {file}")
    return path


def build_request_service() -> RequestService:
    return RequestService(RequestStore(get_settings().state_dir))


def request_to_dict(request: Request) -> dict[str, Any]:
    return asdict(request)


def suggestion_to_dict(suggestion: Suggestion) -> dict[str, Any]:
    return asdict(suggestion)


def snapshot_to_dict(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "revision": snapshot.revision,
        "pending": snapshot.pending,
        "requests": [request_to_dict(request) for request in snapshot.requests],
        "suggestions": [suggestion_to_dict(suggestion) for suggestion in snapshot.suggestions],
    }
