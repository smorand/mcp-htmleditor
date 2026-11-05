"""Where render pictures live and how they are written and cleaned up (SPEC-0008 DEC-016)."""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Sequence
from pathlib import Path

from ..fileio import atomic_write
from ..tracing import trace_span

logger = logging.getLogger(__name__)

RENDER_DIR_NAME = "htmleditor-render"
UNSAFE_ID_CHARS = ("/", "\\", "\x00")


def render_dir() -> Path:
    """The folder holding every picture, under the system temporary directory."""
    return Path(tempfile.gettempdir()) / RENDER_DIR_NAME


def picture_path(file: str, slide_id: str) -> Path:
    """``<render dir>/<file stem>-<slide id>.png``; separators and NUL in the id become ``_``."""
    safe = slide_id
    for char in UNSAFE_ID_CHARS:
        safe = safe.replace(char, "_")
    return render_dir() / f"{Path(file).stem}-{safe}.png"


def write_picture(path: Path, data: bytes) -> None:
    """Create the folder, then write the picture atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, data)


def remove_stale(file: str, slide_ids: Sequence[str], keep: Path) -> int:
    """Unlink the pictures of the presentation's own slide ids other than ``keep``; return how many went."""
    removed = 0
    with trace_span("render.cleanup") as span:
        for slide_id in slide_ids:
            path = picture_path(file, slide_id)
            if path != keep and path.is_file() and _unlink_quietly(path):
                removed += 1
        span.set_attribute("file.count", removed)
    return removed


def _unlink_quietly(path: Path) -> bool:
    try:
        path.unlink()
    except OSError:
        logger.warning("render: could not remove %s", path)
        return False
    return True
