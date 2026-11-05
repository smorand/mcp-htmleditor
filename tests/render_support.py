"""Fixtures shared by every render test (SPEC-0008).

Decks come from the SPEC-0007 helpers of ``tests/deck_support.py`` plus string injectors; nothing is
committed and nothing is read from ``~/.config``. PNG data is generated with ``zlib`` and ``struct``.
"""

from __future__ import annotations

import platform
import re
import struct
import zlib
from pathlib import Path
from typing import Final

import pytest
from PIL import Image

from tests.deck_support import EI_TITLES as _EI_TITLES
from tests.deck_support import TINY_PNG, build_deck, deck_med

EI_TITLES: Final[tuple[str, ...]] = _EI_TITLES

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_IHDR_SIZE_OFFSET = 16
_FIGURE_HEIGHT = "h-md"
_ARTICLE_END = "</article>"
_BODY_OPEN = re.compile(r'<div class="slide-body"[^>]*>')


def _chromium_cache_dir() -> Path:
    home = Path.home()
    if platform.system() == "Darwin":
        return home / "Library" / "Caches" / "ms-playwright"
    return home / ".cache" / "ms-playwright"


HAS_CHROMIUM = any(_chromium_cache_dir().glob("chromium-*"))
needs_chromium = pytest.mark.skipif(
    not HAS_CHROMIUM,
    reason="Playwright Chromium is not installed; run `make install-browser`",
)


def ei_deck_html() -> str:
    """DECK-EI for render tests: 8 slides, no big image."""
    return build_deck("ei", EI_TITLES)


def med_deck_html(dark_slide: str = "slide-2") -> str:
    """DECK-MED with class ``slide dark`` on ``dark_slide``, its figures given a height class.

    The medical stylesheet needs ``h-sm|h-md|h-lg|h-xl`` on a figure (a bare ``height:auto`` image fills the
    budget and overflows); ``deck_med()`` of SPEC-0007 omits it, so it is added here, the measure untouched.
    """
    html = deck_med().replace('class="med-figure w-50"', f'class="med-figure w-50 {_FIGURE_HEIGHT}"')
    return set_slide_class(html, dark_slide, "dark")


def _article_bounds(html: str, slide_id: str) -> tuple[int, int, int]:
    """Return the offsets of the article ``slide_id``: its tag start, its tag end and its ``</article>``."""
    opening = re.search(rf'<article\b[^>]*\bid="{re.escape(slide_id)}"[^>]*>', html)
    if opening is None:
        raise ValueError(f"no article with id {slide_id!r}")
    return opening.start(), opening.end(), html.index(_ARTICLE_END, opening.end())


def inject_in_body(html: str, slide_id: str, snippet: str) -> str:
    """Put ``snippet`` as the first child of the ``.slide-body`` of ``slide_id``."""
    _, open_end, end = _article_bounds(html, slide_id)
    body = _BODY_OPEN.search(html, open_end, end)
    if body is None:
        raise ValueError(f"{slide_id!r} has no .slide-body")
    return html[: body.end()] + snippet + html[body.end() :]


def append_to_slide(html: str, slide_id: str, snippet: str) -> str:
    """Put ``snippet`` after the inner frame of ``slide_id``, right before its ``</article>``."""
    _, _, end = _article_bounds(html, slide_id)
    return html[:end] + snippet + html[end:]


def set_slide_class(html: str, slide_id: str, cls: str) -> str:
    """Add ``cls`` to the class list of the article ``slide_id`` and to no other."""
    start, open_end, _ = _article_bounds(html, slide_id)
    tag = re.sub(r'class="([^"]*)"', lambda m: f'class="{m.group(1)} {cls}"', html[start:open_end], count=1)
    return html[:start] + tag + html[open_end:]


def add_script(html: str, js: str) -> str:
    """Add a classic script running ``js`` just before ``</body>``."""
    return html.replace("</body>", f"<script>{js}</script>\n</body>", 1)


def big_deck(count: int = 40, *, with_images: bool = False) -> str:
    """A deck of ``count`` slides; ``with_images`` gives each a data address picture, every other one also a file."""
    html = build_deck("ei", tuple(f"Slide {i}" for i in range(count)))
    if not with_images:
        return html
    for i in range(count):
        picture = f'<img src="data:image/png;base64,{TINY_PNG}" alt="p{i}">'
        if i % 2:
            picture += '<img src="pics/ok.png" alt="f">'
        html = append_to_slide(html, f"slide-{i}", picture)
    return html


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def tiny_png_bytes() -> bytes:
    """A valid 1x1 white PNG."""
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        _PNG_SIGNATURE
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
        + _chunk(b"IEND", b"")
    )


def png_size(path: Path) -> tuple[int, int]:
    """Width and height read from the IHDR chunk, without Pillow."""
    data = path.read_bytes()[: _IHDR_SIZE_OFFSET + 8]
    width, height = struct.unpack(">II", data[_IHDR_SIZE_OFFSET:])
    return width, height


def png_pixel(path: Path, x: int, y: int) -> tuple[int, int, int]:
    """RGB of the pixel ``(x, y)``; Pillow is present through python-pptx."""
    with Image.open(path) as image:
        red, green, blue = image.convert("RGB").getpixel((x, y))  # type: ignore[misc]
    return red, green, blue
