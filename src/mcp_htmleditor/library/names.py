"""Folder and presentation names (SPEC-0025, DEC-029): composed form, the unique key and the display order.

``lower()`` and never ``casefold()``: ``ß`` and ``SS`` stay two names, as "without regard to case" reads in the spec.
"""

from __future__ import annotations

import unicodedata
from typing import Final

COMPOSED: Final = "NFC"
DECOMPOSED: Final = "NFD"
NONSPACING_MARK: Final = "Mn"


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
