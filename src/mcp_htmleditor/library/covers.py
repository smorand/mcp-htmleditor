"""The cover of a presentation for the folder gallery (SPEC-0025): the largest picture embedded in its first slide.

No rendering and no browser: the file is read as text, the first slide is cut out and its ``data:`` pictures are
looked at. Only raster types are served (an SVG could carry markup); a deck with no such picture has no cover and the
page shows the ridge of the design system instead.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from typing import Final

SLIDE_START: Final = re.compile(r"""<(?:article|section|div)\b[^>]*\bdata-type=["']slide["'][^>]*>""")
PICTURE: Final = re.compile(
    r"""<img\b[^>]*?\bsrc=["']data:(image/(?:png|jpeg|webp|gif));base64,([A-Za-z0-9+/=\s]+)["']"""
)
MIN_BASE64_CHARS: Final = 2_000  # below this a picture is an icon or a logo, not a cover
MAX_COVER_BYTES: Final = 4_194_304


@dataclass(frozen=True, slots=True)
class Cover:
    """A cover picture: its media type and its bytes."""

    media_type: str
    data: bytes


def first_cover(text: str) -> Cover | None:
    """The largest raster ``data:`` picture of the first slide of ``text``, None when there is none. One regular
    expression scan of the first slide only: time O(size of the first slide)."""
    first = SLIDE_START.search(text)
    if first is None:
        return None
    following = SLIDE_START.search(text, first.end())
    slide = text[first.end() : following.start() if following else len(text)]
    best: tuple[int, str, str] | None = None
    for found in PICTURE.finditer(slide):
        size = len(found[2])
        if size >= MIN_BASE64_CHARS and (best is None or size > best[0]):
            best = (size, found[1], found[2])
    if best is None:
        return None
    try:
        data = base64.b64decode(re.sub(r"\s+", "", best[2]), validate=True)
    except (binascii.Error, ValueError):
        return None
    return Cover(best[1], data) if len(data) <= MAX_COVER_BYTES else None
