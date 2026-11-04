"""Lint a presentation: structure rules L001 to L006 (SPEC-0007 FR-NEW-012, FR-NEW-013, DEC-008).

Rules are plain functions held in two tables keyed by code: file scope rules read the whole deck and
return ``(slide index or None, message)`` pairs, slide scope rules return messages for one slide.
``lint_deck`` runs both, then orders the problems (whole file first, slide index, code; stable inside a
code). A file that is not a presentation has no problem here. Expected counters are recomputed here, never
read from ``deck/renumber.py`` (only its counter pattern is shared). No printing.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from bs4.element import Comment, NavigableString, Tag

from . import Deck, load_deck, slide_id
from .renumber import COUNTER

ERROR = "error"
CARBON = "carbon"
TOTAL = re.compile(r"const\s+TOTAL\s*=\s*(\d+)\s*;")
NAMES = re.compile(r"const\s+slideNames\s*=\s*\[")
TEMPLATE_TEXTS = ("Contenu de la slide", "Titre de la présentation")
TEMPLATE_EYEBROW = "Section · Slide 01 / 01"
HIDDEN_TEXT_TAGS = frozenset({"script", "style"})
QUOTES = "\"'`"
OPEN_BRACKETS = "[({"
CLOSE_BRACKETS = "])}"


@dataclass(frozen=True, slots=True)
class Problem:
    """One finding: ``slide_index`` and ``slide`` are ``None`` for the whole file."""

    code: str
    severity: str
    slide_index: int | None
    slide: str | None
    message: str


FilePair = tuple[int | None, str]


def lint_deck(deck: Deck) -> list[Problem]:
    """Return every problem of ``deck``, ordered whole file first, then slide by slide, then by code."""
    if deck.doc_type != "presentation":
        return []
    problems: list[Problem] = []
    for code, file_rule in FILE_RULES.items():
        problems.extend(_problem(deck, code, index, message) for index, message in file_rule(deck))
    for index, slide in enumerate(deck.slides):
        for code, slide_rule in SLIDE_RULES.items():
            problems.extend(_problem(deck, code, index, message) for message in slide_rule(deck, slide, index))
    return sorted(problems, key=lambda p: (-1 if p.slide_index is None else p.slide_index, p.code))


def lint_file(file: str) -> dict[str, Any]:
    """Return the JSON form of the report of ``file``; raise ``DeckError`` when it cannot be read."""
    return report_dict(lint_deck(load_deck(file)))


def report_dict(problems: Sequence[Problem]) -> dict[str, Any]:
    """Return the JSON form of a list of problems."""
    return {
        "problems": [
            {"code": p.code, "severity": p.severity, "slide": p.slide, "message": p.message} for p in problems
        ],
        "errors": _count(problems, ERROR),
        "warnings": _count(problems, "warning"),
    }


def format_report(problems: Sequence[Problem]) -> list[str]:
    """Return one line per problem, then the verdict line."""
    lines = [f"{p.severity} {p.code} {'-' if p.slide is None else p.slide} {p.message}" for p in problems]
    errors, warnings = _count(problems, ERROR), _count(problems, "warning")
    verdict = "FAIL" if errors else "OK"
    lines.append(f"lint: {verdict} ({_plural(errors, 'error')}, {_plural(warnings, 'warning')})")
    return lines


def _count(problems: Sequence[Problem], severity: str) -> int:
    return sum(1 for p in problems if p.severity == severity)


def _plural(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _problem(deck: Deck, code: str, index: int | None, message: str) -> Problem:
    label = None if index is None else _label(deck.slides[index], index)
    return Problem(code, ERROR, index, label, message)


def _label(slide: Tag, index: int) -> str:
    return slide_id(slide) or f"slide-{index}"


def _script_texts(deck: Deck) -> list[str]:
    return [tag.get_text() for tag in deck.soup.find_all("script")]


def _first_match(deck: Deck, pattern: re.Pattern[str]) -> tuple[str, re.Match[str]] | None:
    for text in _script_texts(deck):
        found = pattern.search(text)
        if found:
            return text, found
    return None


def _total_mismatch(deck: Deck) -> list[FilePair]:
    """L002."""
    found = _first_match(deck, TOTAL)
    if found is None or int(found[1].group(1)) == len(deck.slides):
        return []
    return [(None, f"TOTAL is {found[1].group(1)} but the file has {len(deck.slides)} slides")]


def _names_mismatch(deck: Deck) -> list[FilePair]:
    """L003."""
    found = _first_match(deck, NAMES)
    count = None if found is None else count_literals(found[0], found[1].end())
    if count is None or count == len(deck.slides):
        return []
    return [(None, f"slideNames has {count} entries but the file has {len(deck.slides)} slides")]


class _Literals:
    """Cursor over the source of a JavaScript list, just after its ``[``."""

    __slots__ = ("count", "depth", "index", "source")

    def __init__(self, source: str, start: int) -> None:
        self.source = source
        self.index = start
        self.depth = 1
        self.count = 0


def count_literals(source: str, start: int) -> int | None:
    """Count the top level entries (string literals, a nested group counting as one) of a list.

    The list content begins at ``source[start]``. Strings (``"``, ``'`` and backtick) are skipped whole,
    escapes included, as are ``//`` and ``/* */`` comments; brackets inside a nested group are not
    counted. ``None`` when the list never closes.
    """
    scan = _Literals(source, start)
    while scan.index < len(source) and scan.depth > 0:
        _HANDLERS.get(source[scan.index], _skip_char)(scan)
    return scan.count if scan.depth == 0 else None


def _skip_char(scan: _Literals) -> None:
    scan.index += 1


def _read_string(scan: _Literals) -> None:
    quote = scan.source[scan.index]
    position = scan.index + 1
    while position < len(scan.source) and scan.source[position] != quote:
        position += 2 if scan.source[position] == "\\" else 1
    if scan.depth == 1 and position < len(scan.source):
        scan.count += 1
    scan.index = position + 1


def _read_slash(scan: _Literals) -> None:
    marker = scan.source[scan.index : scan.index + 2]
    closing = {"//": "\n", "/*": "*/"}.get(marker)
    if closing is None:
        scan.index += 1
        return
    found = scan.source.find(closing, scan.index + 2)
    scan.index = len(scan.source) if found < 0 else found + (len(closing) if marker == "/*" else 0)


def _open_bracket(scan: _Literals) -> None:
    if scan.depth == 1:  # a nested group is one entry of the list
        scan.count += 1
    scan.depth += 1
    scan.index += 1


def _close_bracket(scan: _Literals) -> None:
    scan.depth -= 1
    scan.index += 1


_HANDLERS: dict[str, Callable[[_Literals], None]] = {
    **dict.fromkeys(QUOTES, _read_string),
    **dict.fromkeys(OPEN_BRACKETS, _open_bracket),
    **dict.fromkeys(CLOSE_BRACKETS, _close_bracket),
    "/": _read_slash,
}


def _missing_attributes(deck: Deck, slide: Tag, index: int) -> list[str]:  # noqa: ARG001 - table signature
    """L001."""
    checks = (
        ("data-type", slide.get("data-type") == "slide"),
        ("data-id", bool(slide.get("data-id"))),
        ("data-title", bool(slide.get("data-title"))),
    )
    return [f"missing attribute {name}" for name, is_present in checks if not is_present]


def _id_problems(deck: Deck) -> list[FilePair]:
    """L004: a duplicate beats an id out of order."""
    seen: set[str] = set()
    pairs: list[FilePair] = []
    for index, slide in enumerate(deck.slides):
        found = slide_id(slide)
        if found is None:
            continue
        if found in seen:
            pairs.append((index, f'duplicate id "{found}"'))
        elif found != f"slide-{index}":
            pairs.append((index, f'expected id "slide-{index}" but found "{found}"'))
        seen.add(found)
    return pairs


def _counter_problems(deck: Deck, slide: Tag, index: int) -> list[str]:
    """L005: the eyebrow, then the footer (Carbon) or the page element (other charters)."""
    total = len(deck.slides)
    messages = _pattern_problem(slide, ".slide-eyebrow", "eyebrow", f"Slide {index + 1:02d} / {total:02d}")
    if deck.charter == CARBON:
        return messages + _pattern_problem(slide, ".slide-footer-right", "footer", f"Slide {index + 1} / {total}")
    return messages + _page_problem(slide, str(index + 1))


def _pattern_problem(slide: Tag, selector: str, name: str, expected: str) -> list[str]:
    element = slide.select_one(selector)
    found = COUNTER.search(element.get_text()) if element else None
    if found is None or found.group() == expected:
        return []
    return [f'{name} counter says "{found.group()}", expected "{expected}"']


def _page_problem(slide: Tag, expected: str) -> list[str]:
    element = slide.select_one(".slide-foot-page")
    text = element.get_text().strip() if element else ""
    return [f'page counter says "{text}", expected "{expected}"'] if text and text != expected else []


def _template_text(deck: Deck, slide: Tag, index: int) -> list[str]:
    """L006."""
    text = _visible_text(slide)
    left = [phrase for phrase in TEMPLATE_TEXTS if phrase in text]
    if TEMPLATE_EYEBROW in text and not (len(deck.slides) == 1 and index == 0):
        left.append(TEMPLATE_EYEBROW)
    return [f'template text left: "{phrase}"' for phrase in left]


def _visible_text(slide: Tag) -> str:
    parts = (t for t in slide.find_all(string=True) if _is_slide_text(t))
    return re.sub(r"\s+", " ", "".join(parts))


def _is_slide_text(text: NavigableString) -> bool:
    return not isinstance(text, Comment) and not any(p.name in HIDDEN_TEXT_TAGS for p in text.parents)


FILE_RULES: dict[str, Callable[[Deck], list[FilePair]]] = {
    "L002": _total_mismatch,
    "L003": _names_mismatch,
    "L004": _id_problems,
}
SLIDE_RULES: dict[str, Callable[[Deck, Tag, int], list[str]]] = {
    "L001": _missing_attributes,
    "L005": _counter_problems,
    "L006": _template_text,
}
