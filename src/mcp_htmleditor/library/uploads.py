"""Upload checks of the web library mode (SPEC-0025, DEC-033, DEC-034): the validity of a file as a presentation.

Everything runs on the bytes in memory: no temporary file, no path, so no message can carry a location.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final
from urllib.parse import unquote

from bs4 import Tag

from ..deck import deck_from_text
from ..deck.lint import lint_deck

NOT_VALID: Final = "This file is not a valid presentation: "
NOT_UTF_8: Final = "the file is not valid UTF-8 text"
NOT_DECLARED: Final = "the file is not declared as a presentation"
NO_SLIDE: Final = "the file has no slide"
NAME_HEADER: Final = "x-file-name"
LENGTH_HEADER: Final = "content-length"
ENCODING_HEADER: Final = "transfer-encoding"
REPLACE_HEADER: Final = "x-replace"
EXTENSION: Final = ".html"
MAX_BYTES: Final = 26_214_400  # 25 MB exactly (FR-NEW-030)
CHUNK_LINE_MAX: Final = 32  # the longest chunk size line read (DEC-033)
TRAILER_MAX: Final = 8_192
UPLOAD_FAILED: Final = "The upload failed. Nothing was changed."
ERROR: Final = "error"
PRESENTATION: Final = "presentation"


class UploadRefused(ValueError):  # noqa: N818 - a domain outcome whose text is the message shown to the person
    """A refused upload; ``str(exc)`` is the exact message."""


def check_validity(data: bytes) -> None:
    """Raise ``UploadRefused`` with the first problem of ``data`` as a presentation (DEC-034), else return.

    Order: UTF-8 text, declared as a presentation (an empty file included), at least one slide, then the first error
    of the editor's own checks (whole file first, then slide by slide, then by code), its message only. Warnings
    never block and are never first. Time O(n) in the size of the file (one parse, one lint).
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadRefused(f"{NOT_VALID}{NOT_UTF_8}.") from exc
    deck = deck_from_text("upload.html", text)
    root = deck.soup.find("html")
    if not isinstance(root, Tag) or root.get("data-doc-type") != PRESENTATION:
        raise UploadRefused(f"{NOT_VALID}{NOT_DECLARED}.")
    if not deck.slides:
        raise UploadRefused(f"{NOT_VALID}{NO_SLIDE}.")
    first = next((problem for problem in lint_deck(deck) if problem.severity == ERROR), None)
    if first is not None:
        raise UploadRefused(f"{NOT_VALID}{first.message}.")


def file_name(raw: str) -> str | None:
    """The file name of ``X-File-Name`` (percent encoded UTF-8), None when it is not that."""
    if not raw.isascii():
        return None
    try:
        return unquote(raw, encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        return None


def declared_length(raw: str | None) -> int:
    """The ``Content-Length`` as a count (no header is an empty body); a signed or non decimal value is refused, and
    so is one with more digits than any accepted size could need (the body is not read)."""
    if raw is None:
        return 0
    if not raw.isascii() or not raw.isdigit() or len(raw) > len(str(MAX_BYTES)) + 8:
        raise UploadRefused(UPLOAD_FAILED)
    return int(raw)


class UploadBusy(RuntimeError):  # noqa: N818 - a domain outcome: four uploads are already being received
    """No upload slot is free (DEC-033): the fifth concurrent upload is refused, never queued."""


def read_chunked(read_line: Callable[[int], bytes], read: Callable[[int], bytes], limit: int) -> bytes:
    """Decode a ``Transfer-Encoding: chunked`` body, stopping once ``limit`` bytes are held (the caller passes
    ``MAX_BYTES + 1`` so an oversize body is seen without being read to its end).

    A chunk size line above ``CHUNK_LINE_MAX`` bytes, a size that is not hexadecimal, a missing line end after a
    chunk, or trailers above ``TRAILER_MAX`` bytes make the body unreadable (``UploadRefused``). Memory is bounded by
    ``limit``; time is O(bytes read).
    """
    data = bytearray()
    while len(data) < limit:
        size_line = read_line(CHUNK_LINE_MAX + 1)
        if not size_line.endswith(b"\n") or len(size_line) > CHUNK_LINE_MAX:
            raise UploadRefused(UPLOAD_FAILED)
        try:
            size = int(size_line.split(b";", 1)[0].strip(), 16)
        except ValueError as exc:
            raise UploadRefused(UPLOAD_FAILED) from exc
        if size < 0:
            raise UploadRefused(UPLOAD_FAILED)
        if size == 0:
            _skip_trailers(read_line)
            break
        data += read(min(size, limit - len(data)))
        if len(data) < limit and read_line(CHUNK_LINE_MAX + 1).strip():
            raise UploadRefused(UPLOAD_FAILED)
    return bytes(data)


def _skip_trailers(read_line: Callable[[int], bytes]) -> None:
    """Read the trailer lines up to the empty one, refusing more than ``TRAILER_MAX`` bytes of them."""
    total = 0
    while (line := read_line(CHUNK_LINE_MAX + 1)).strip():
        total += len(line)
        if total > TRAILER_MAX:
            raise UploadRefused(UPLOAD_FAILED)
