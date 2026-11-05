"""Text that UTF-8 cannot hold (SPEC-0013 DEC-001).

JSON and operating system strings can carry a lone surrogate (U+D800 to U+DFFF) that no UTF-8 encoder accepts.
This module holds the one predicate, the replacement and the three messages every surface reuses. It imports
nothing from the package, so ``deck`` and ``fileio`` can both use it without an import cycle.
"""

from __future__ import annotations

UNENCODABLE_TEXT = "Text cannot be encoded as UTF-8"
UNENCODABLE_FILE_NAME = "File name cannot be encoded"
UNENCODABLE_BIND_ADDRESS = "Bind address cannot be encoded"
REPLACEMENT_CHARACTER = "\ufffd"

_SURROGATES = dict.fromkeys(range(0xD800, 0xE000), REPLACEMENT_CHARACTER)


def is_utf8_encodable(text: str) -> bool:
    """True when ``text.encode("utf-8")`` (strict) succeeds; False for any U+D800 to U+DFFF, escaped bytes included."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def replace_unencodable(text: str) -> str:
    """Each code point U+D800 to U+DFFF replaced by U+FFFD; encodable text is returned unchanged."""
    return text.translate(_SURROGATES)
