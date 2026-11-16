"""Folder and presentation names (SPEC-0025, DEC-029): composed form, the unique key, the display order; the size
text of a presentation (DEC-031).

``lower()`` and never ``casefold()``: ``ß`` and ``SS`` stay two names, as "without regard to case" reads in the spec.
"""

from __future__ import annotations

import unicodedata
from typing import Final

COMPOSED: Final = "NFC"
DECOMPOSED: Final = "NFD"
NONSPACING_MARK: Final = "Mn"
KILOBYTE: Final = 1_024
MEGABYTE: Final = 1_048_576


def compose(text: str) -> str:
    """The composed form (NFC): ``Café`` typed with a combining accent becomes the one character ``é``."""
    return unicodedata.normalize(COMPOSED, text)


def name_key(name: str) -> str:
    """The unique key of a name: the composed form of the lower cased composed text."""
    return compose(compose(name).lower())


def order_key(name: str) -> tuple[str, str]:
    """Accents removed (NFD, nonspacing marks dropped), lower case, compared by code point, then the exact name.

    Digits sort before Latin letters, Latin letters before other alphabets (FR-NEW-015).
    """
    decomposed = unicodedata.normalize(DECOMPOSED, name)
    bare = "".join(character for character in decomposed if unicodedata.category(character) != NONSPACING_MARK)
    return compose(bare.lower()), name


def format_size(count: int) -> str:
    """``1 byte``, ``N bytes`` below 1 024, then KB, then MB from 1 048 576, with one decimal rounded half up from the
    exact value in integer arithmetic (``round`` rounds half to even): 1 075 bytes is ``1.0 KB``, 1 076 ``1.1 KB``,
    1 048 575 ``1024.0 KB``."""
    if count == 1:
        return "1 byte"
    if count < KILOBYTE:
        return f"{count} bytes"
    unit, label = (MEGABYTE, "MB") if count >= MEGABYTE else (KILOBYTE, "KB")
    tenths = (count * 20 + unit) // (2 * unit)  # floor(count * 10 / unit + 1 / 2)
    return f"{tenths // 10}.{tenths % 10} {label}"
