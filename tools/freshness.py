"""Shared report format of the template generators' ``--check`` mode (SPEC-0011).

Pure functions, stdlib only: one line format and one first-difference rule for
``gen_ei_bootstrap.py`` and ``sync_medical_css.py``.
"""

from __future__ import annotations

from itertools import zip_longest


def first_difference_line(expected: str, actual: str, offset: int = 0) -> int:
    """Return the 1-based line of the first differing line, plus ``offset``.

    When one text is the start of the other, the answer is the number of lines of
    the shorter plus one. Lines keep their newline, so a text that differs only by
    its trailing newline counts as differing. Raises ``ValueError`` for equal texts.
    Time and space O(n) (both texts are split once).
    """
    pairs = zip_longest(expected.splitlines(keepends=True), actual.splitlines(keepends=True))
    for number, (want, have) in enumerate(pairs, start=1):
        if want != have:
            return number + offset
    raise ValueError("texts are equal: there is no first difference")


def report_line(
    relpath: str,
    expected: str,
    actual: str | None,
    make_target: str,
    offset: int = 0,
) -> tuple[str, bool]:
    """Return ``(line, is_fresh)``; ``actual`` None means the file is missing."""
    if actual is None:
        return f"{relpath}: missing; run: make {make_target}", False
    if actual == expected:
        return f"{relpath}: fresh", True
    line = first_difference_line(expected, actual, offset)
    return f"{relpath}: stale (first difference at line {line}); run: make {make_target}", False


def source_missing_error(relpath: str) -> str:
    """Return the error line printed on the error output when a source is absent."""
    return f"error: source not found: {relpath}"
