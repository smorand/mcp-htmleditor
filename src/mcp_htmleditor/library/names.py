"""Folder and presentation names (SPEC-0025, DEC-029): composed form, the unique key, the display order, the folder
name rule, the member address rule; the size text of a presentation (DEC-031).

``lower()`` and never ``casefold()``: ``ß`` and ``SS`` stay two names, as "without regard to case" reads in the spec.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

COMPOSED: Final = "NFC"
DECOMPOSED: Final = "NFD"
NONSPACING_MARK: Final = "Mn"
KILOBYTE: Final = 1_024
MEGABYTE: Final = 1_048_576
FOLDER_NAME_MAX: Final = 60
FILE_EXTENSION: Final = ".html"
FILE_NAME_MAX: Final = 100  # composed characters before the extension (FR-NEW-032)
FILE_NAME_SIGNS: Final = frozenset(" ._-()'")  # the straight apostrophe U+0027 only
ASCII_DIGITS: Final = frozenset("0123456789")
LATIN: Final = "LATIN"
FOLDER_NAME_SIGNS: Final = frozenset(" -")  # the space U+0020 and the plain hyphen U+002D, nothing that looks alike
FOLDER_NAME_CATEGORIES: Final = ("L", "M")  # what a combining mark may follow
LETTER: Final = "L"
MARK: Final = "M"
VARIATION_SELECTORS: Final = frozenset(map(chr, range(0xFE00, 0xFE10)))  # Mn, but they only select an emoji look
DECIMAL_DIGIT: Final = "Nd"
EMAIL_PATTERN: Final = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+")  # DEC-029, ASCII only


class NameRefused(ValueError):  # noqa: N818 - name fixed by the design (section 5.8)
    """A name outside its rule; it carries no text of the name (names are not logged)."""


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


def check_folder_name(raw: str) -> str:
    """The trimmed composed name: 1 to 60 characters once composed, each a letter of any alphabet (``L*``), a mark
    (``M*``), a decimal digit (``Nd``), the space or the hyphen (FR-NEW-040, FR-NEW-041); ``NameRefused`` otherwise."""
    name = compose(raw.strip())
    if not 1 <= len(name) <= FOLDER_NAME_MAX:
        raise NameRefused
    previous = ""  # a mark needs a letter or a mark before it: no lone accent, no emoji presentation selector
    for character in name:
        category = unicodedata.category(character)
        if category.startswith(MARK):
            if not previous.startswith(FOLDER_NAME_CATEGORIES) or character in VARIATION_SELECTORS:
                raise NameRefused
        elif not (character in FOLDER_NAME_SIGNS or category.startswith(LETTER) or category == DECIMAL_DIGIT):
            raise NameRefused
        previous = category
    return name


def check_file_name(raw: str) -> str:
    """The composed stem of an uploaded file name, without ``.html``; ``NameRefused`` when the name is not allowed
    (FR-NEW-032, DEC-029). ``raw`` is the percent decoded name, whose extension was checked already.

    Refused: an empty or all space stem, an edge space, a leading dot, more than 100 composed characters, and any
    character that is not a Latin script letter (by ``unicodedata.name``, so ``ł ø œ ß`` and every accented Latin
    letter pass, a Cyrillic or a fullwidth one does not), an ASCII digit, a space, one of ``. _ - ( ) '`` (the straight
    apostrophe only), or a combining mark right after such a letter. Time O(n) in the name length.
    """
    name = compose(raw)
    stem = name[: -len(FILE_EXTENSION)] if name.lower().endswith(FILE_EXTENSION) else name
    if not stem.strip() or stem != stem.strip(" ") or stem.startswith(".") or len(stem) > FILE_NAME_MAX:
        raise NameRefused
    previous_is_letter = False
    for character in stem:
        if unicodedata.category(character) == NONSPACING_MARK:
            if not previous_is_letter:
                raise NameRefused
            continue
        is_letter = unicodedata.category(character).startswith(LETTER) and unicodedata.name(character, "").startswith(
            LATIN
        )
        if not (is_letter or character in FILE_NAME_SIGNS or character in ASCII_DIGITS):
            raise NameRefused
        previous_is_letter = is_letter
    return stem


def check_email(raw: str) -> str:
    """The trimmed lower case address when the trimmed text is one ``local@domain`` address (FR-NEW-046): letters,
    digits and ``. _ % + -`` before the ``@``, ASCII letters, digits and hyphens in dot separated labels after it, at
    least one dot; ``NameRefused`` otherwise (two addresses, a space, an apostrophe, a missing dot)."""
    address = raw.strip()
    if EMAIL_PATTERN.fullmatch(address) is None:
        raise NameRefused
    return address.lower()


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
