"""Files next to the open deck, answered by the editor server (SPEC-0023 FR-NEW-009, FR-NEW-010, DEC-008).

A deck shown in the editor's frame (``/content-frame``) asks ``/assets/photo.png`` for its relative
``assets/photo.png``. :func:`deck_file` maps such a request path to a file of the deck's folder, or refuses it.
Pure path logic, no I/O beyond ``resolve`` and ``is_file``; the request gate runs before it.

Refused (``None``): no deck open; an empty path or one ending with ``/``; a NUL after percent decoding; a first
segment the editor owns; a hidden segment (starts with a dot, ``.`` and ``..`` aside), in the request or in the
resolved location; a ``..`` climbing above the folder (lexically, before the file system is touched); a resolved
location outside the folder (links followed); a type outside :data:`DECK_FILE_TYPES`; a missing file.
"""

from __future__ import annotations

import posixpath
from pathlib import Path, PurePosixPath
from typing import Final
from urllib.parse import unquote

DECK_FILE_TYPES: Final = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".ogg": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".css": "text/css",
}
RESERVED_SEGMENTS: Final = frozenset(
    {"static", "content", "content-frame", "status", "export", "requests", "review", "health", "arch-layout"}
)
SVG: Final = ".svg"
# An SVG opened at the editor's address must not run scripts in the editor's origin (E2E-SEC-010).
SVG_POLICY: Final = "sandbox; script-src 'none'"


def _hidden(segments: tuple[str, ...] | list[str]) -> bool:
    return any(segment.startswith(".") and segment not in {".", ".."} for segment in segments)


def deck_file(current_file: str | None, raw_path: str) -> Path | None:
    """The file of the open deck's folder named by ``raw_path`` (the request path, query dropped), else ``None``."""
    relative = _request_relative(raw_path) if current_file else None
    if current_file is None or relative is None:
        return None
    base = Path(current_file).resolve().parent
    target = (base / relative).resolve()
    inside = target.is_relative_to(base) and not _hidden(target.relative_to(base).parts)
    return target if inside and target.suffix.lower() in DECK_FILE_TYPES and target.is_file() else None


def _request_relative(raw_path: str) -> str | None:
    """The request path decoded once and normalised on its text, relative to the deck's folder, else ``None``."""
    if not raw_path or raw_path.endswith("/"):
        return None
    decoded = unquote(raw_path)
    segments = [segment for segment in decoded.split("/") if segment]
    if "\x00" in decoded or not segments or segments[0] in RESERVED_SEGMENTS or _hidden(segments):
        return None
    relative = posixpath.normpath("/".join(segments))
    climbs = relative in {".", ".."} or relative.startswith("../")
    return None if climbs or PurePosixPath(relative).suffix.lower() not in DECK_FILE_TYPES else relative


def media_type(path: Path) -> str:
    """The media type answered for an accepted deck file."""
    return DECK_FILE_TYPES[path.suffix.lower()]
