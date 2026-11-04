"""Apply a list of operations to a deck file in one atomic write (SPEC-0007 FR-NEW-003 to FR-NEW-009).

The file text is cut into a working copy: an ordered list of raw gaps and slide atoms (DEC-003). The five
operations edit that list; the output is the join of the atoms, so bytes outside an edit are identical by
construction. Every slide keeps the id it had in the original file for as long as it stays in the list
(including after a move or a replace); an inserted slide has none. After the last operation a structural
patch is renumbered once (``renumber.py``).
Cost: one scan and one parse of the file, one scan and one parse of the slide per ``set_text`` or ``replace_slide``,
one parse of the html per ``insert_slide`` or ``replace_slide``, and for a structural patch one more scan
and parse of the assembled text.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import soupsieve
from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag

from ..fileio import atomic_write
from . import Deck, DeckError, load_deck, slide_id
from .renumber import apply_edits, renumber_edits
from .scan import Node, large_images, scan

TEMPLATE_FOLDERS = (("templates", "bootstrap"), ("templates", "reference"))
REQUIRED_FIELDS = {
    "set_text": ("id", "selector", "text"),
    "replace_slide": ("id", "html"),
    "insert_slide": ("after", "html"),
    "delete_slide": ("id",),
    "move_slide": ("id", "after"),
}
START = "start"  # the value of ``after`` that designates the place before the first slide
SLIDE_HTML_REASON = 'slide html must have data-type="slide" and a data-id'
IMAGE_TOKEN = re.compile(r"data:ref:img-(\d+)")
LINE_BREAK = re.compile(r"\r?\n")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
MAX_IMAGE_DIGITS = 9  # a longer number is beyond any slide, and ``int`` refuses very long ones


class OperationError(Exception):
    """Why one operation cannot be applied; ``apply_patch`` adds its number."""


@dataclass(frozen=True, slots=True)
class Operation:
    """One validated operation: its name and its required string fields."""

    op: str
    fields: dict[str, str]


@dataclass(frozen=True, slots=True)
class Atom:
    """A piece of the file: a raw gap, or a slide (``is_slide``) with its leading whitespace ``pre``.

    ``orig_id`` is the slide's id in the original file; it is ``None`` for a gap and for an inserted slide.
    """

    pre: str
    body: str
    orig_id: str | None
    touched: bool
    is_slide: bool = False


class Working:
    """The working copy of a file: atoms in order."""

    def __init__(self, deck: Deck) -> None:
        self._atoms: list[Atom] = []
        self.is_structural = False
        nodes: dict[tuple[int | None, int | None], Node] = {(node.line, node.col): node for node in scan(deck.text)}
        cursor = 0
        for index, tag in enumerate(deck.slides):
            node = nodes[(tag.sourceline, tag.sourcepos)]
            start = _pre_start(deck.text, node.start, cursor)
            self._add_gap(deck.text[cursor:start])
            pre, body = deck.text[start : node.start], deck.text[node.start : node.end_end]
            self._atoms.append(Atom(pre, body, slide_id(tag) or f"slide-{index}", touched=False, is_slide=True))
            cursor = node.end_end
        self._add_gap(deck.text[cursor:])

    @property
    def slide_count(self) -> int:
        """Return the number of slide atoms."""
        return sum(atom.is_slide for atom in self._atoms)

    def text(self) -> str:
        """Return the file text: the atoms joined."""
        return "".join(atom.pre + atom.body for atom in self._atoms)

    def delete_slide(self, slide: str) -> None:
        """Remove the atom of ``slide``: its leading line break and the slide; the last slide is protected."""
        position = self._require_slide(slide)
        if self.slide_count == 1:
            raise OperationError("cannot delete the last slide")
        del self._atoms[position]
        self.is_structural = True

    def set_text(self, slide: str, selector: str, text: str) -> None:
        """Replace the inner content of the first element matching ``selector`` in ``slide`` by ``text``."""
        position = self._require_slide(slide)
        atom = self._atoms[position]
        edited = _splice_text(atom.body, slide, selector, text)
        if edited != atom.body:
            self._atoms[position] = replace(atom, body=edited, touched=True)

    def replace_slide(self, slide: str, html: str) -> None:
        """Replace the slide range by ``html``, each ``data:ref:img-N`` restored from the current slide text."""
        position = self._require_slide(slide)
        _check_slide_html(html)
        atom = self._atoms[position]
        self._atoms[position] = replace(atom, body=_restore_images(html, atom.body), touched=True)
        self.is_structural = True

    def insert_slide(self, after: str, html: str) -> None:
        """Insert ``html`` after the slide ``after``, or before the first slide when ``after`` is ``start``."""
        anchor = None if after == START else self._require_slide(after)
        _check_slide_html(html)
        token = IMAGE_TOKEN.search(html)
        if token:
            raise OperationError(f'unknown image reference "{token.group()}"')
        self._place(Atom("", html, None, touched=True, is_slide=True), anchor, is_pre_kept=False)
        self.is_structural = True

    def move_slide(self, slide: str, after: str) -> None:
        """Move ``slide`` with its leading whitespace after the slide ``after``, or first when ``start``."""
        position = self._require_slide(slide)
        anchor = None if after == START else self._require_slide(after)
        if anchor == position or (anchor is None and position == self._first_slide()):
            return
        moved = self._atoms.pop(position)
        self._place(moved, None if anchor is None else self._require_slide(after), is_pre_kept=True)
        self.is_structural = True

    def _place(self, slide: Atom, anchor: int | None, *, is_pre_kept: bool) -> None:
        """Put ``slide`` after the atom at ``anchor``, or before the first slide when ``anchor`` is ``None``."""
        if anchor is None:
            at = self._first_slide()
            first = self._atoms[at]
            self._atoms[at] = replace(first, pre=_line_pre(first.pre))
            self._atoms.insert(at, replace(slide, pre=first.pre))
            return
        pre = slide.pre if is_pre_kept else _line_pre(self._atoms[anchor].pre)
        self._atoms.insert(anchor + 1, replace(slide, pre=pre))

    def _first_slide(self) -> int:
        return next(position for position, atom in enumerate(self._atoms) if atom.is_slide)

    def _require_slide(self, slide: str) -> int:
        """Return the position of the atom whose original id is ``slide``."""
        for position, atom in enumerate(self._atoms):
            if atom.orig_id == slide:
                return position
        raise OperationError(f'unknown slide id "{slide}"')

    def _add_gap(self, text: str) -> None:
        if text:
            self._atoms.append(Atom("", text, None, touched=False))


def check_target(file: str) -> None:
    """Refuse a template path, then a missing file, in that order (DEC-014)."""
    resolved = tuple(part.casefold() for part in Path(file).resolve().parts)
    for folder in TEMPLATE_FOLDERS:
        if any(resolved[i : i + len(folder)] == folder for i in range(len(resolved))):
            raise DeckError(f"Refusing to modify a template: {file}")
    if not Path(file).is_file():
        raise DeckError(f"File not found: {file}")


def apply_patch(
    file: str,
    ops: object,
    *,
    dry_run: bool = False,
    set_update_flag: Callable[[bool], None] | None = None,
) -> dict[str, Any]:
    """Apply ``ops`` to ``file``: all of them or none; return the result of the patch."""
    check_target(file)
    deck = load_deck(file)
    if not isinstance(ops, list):
        raise DeckError("Invalid operations JSON: expected a list")
    working = Working(deck)
    for number, item in enumerate(ops, start=1):
        operation = _parse_operation(number, item)
        try:
            _apply_operation(working, deck, operation)
        except OperationError as exc:
            raise _failure(number, str(exc)) from exc
    text = working.text()
    if working.is_structural:
        text = apply_edits(text, renumber_edits(text))
    data = text.encode("utf-8")
    is_changed = text != deck.text
    if is_changed and not dry_run:
        _write(file, data, set_update_flag)
    result: dict[str, Any] = {"ok": True, "changed": is_changed, "slides": working.slide_count, "problems": []}
    if dry_run:
        result["dry_run"] = True
    return result


def _parse_operation(number: int, item: object) -> Operation:
    if not isinstance(item, dict):
        raise _failure(number, "operation must be an object")
    name = item.get("op")
    if not isinstance(name, str):
        raise _failure(number, 'missing field "op"' if "op" not in item else 'field "op" must be a string')
    if name not in REQUIRED_FIELDS:
        raise _failure(number, f'unknown operation "{name}"')
    for field in REQUIRED_FIELDS[name]:
        if field not in item:
            raise _failure(number, f'missing field "{field}"')
        if not isinstance(item[field], str):
            raise _failure(number, f'field "{field}" must be a string')
    return Operation(name, {field: item[field] for field in REQUIRED_FIELDS[name]})


def _failure(number: int, reason: str) -> DeckError:
    return DeckError(f"patch failed at operation {number}: {reason} (nothing written)")


def _apply_operation(working: Working, deck: Deck, operation: Operation) -> None:
    if not deck.slides:
        raise OperationError(f'operation "{operation.op}" needs a presentation')
    fields = operation.fields
    match operation.op:
        case "set_text":
            working.set_text(fields["id"], fields["selector"], fields["text"])
        case "replace_slide":
            working.replace_slide(fields["id"], fields["html"])
        case "insert_slide":
            working.insert_slide(fields["after"], fields["html"])
        case "delete_slide":
            working.delete_slide(fields["id"])
        case "move_slide":
            working.move_slide(fields["id"], fields["after"])


def _write(file: str, data: bytes, set_update_flag: Callable[[bool], None] | None) -> None:
    if set_update_flag is None:
        atomic_write(file, data)
        return
    set_update_flag(True)
    try:
        atomic_write(file, data)
    finally:
        set_update_flag(False)


def _pre_start(text: str, start: int, floor: int) -> int:
    """Return where the ``pre`` of the slide at ``start`` begins: spaces and tabs, then one line break."""
    begin = start
    while begin > floor and text[begin - 1] in " \t":
        begin -= 1
    if begin > floor and text[begin - 1] == "\n":
        begin -= 1
        if begin > floor and text[begin - 1] == "\r":
            begin -= 1
    return begin


def _splice_text(slide_text: str, slide: str, selector: str, replacement: str) -> str:
    root = cast(Tag, BeautifulSoup(slide_text, "html.parser").find(True))
    try:
        element = root if soupsieve.match(selector, root) else root.select_one(selector)
    except soupsieve.SelectorSyntaxError:
        raise OperationError(f'invalid selector "{selector}"') from None
    if element is None:
        raise OperationError(f'selector "{selector}" matches no element in slide "{slide}"')
    node = next(n for n in scan(slide_text) if (n.line, n.col) == (element.sourceline, element.sourcepos))
    if node.start_end == node.end_end:
        raise OperationError(f'element matched by selector "{selector}" has no content')
    escaped = replacement.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return slide_text[: node.start_end] + escaped + slide_text[node.end_start :]


def _line_pre(pre: str) -> str:
    """Return a line break (``\\r\\n`` when ``pre`` uses it) and the leading whitespace of ``pre`` after its own."""
    return ("\r\n" if "\r\n" in pre else "\n") + LINE_BREAK.sub("", pre, count=1)


def _check_slide_html(html: str) -> None:
    """Require one closed top level slide element with a ``data-id``; only blanks and comments may surround it."""
    nodes = [
        node
        for node in BeautifulSoup(html, "html.parser").contents
        if not isinstance(node, Comment) and not (isinstance(node, NavigableString) and not node.strip())
    ]
    root = nodes[0] if len(nodes) == 1 else None
    if not isinstance(root, Tag) or root.get("data-type") != "slide" or not root.get("data-id"):
        raise OperationError(SLIDE_HTML_REASON)
    node = scan(html)[0]
    if node.end_start == node.end_end or COMMENT.sub("", html[node.end_end :]).strip():
        raise OperationError(SLIDE_HTML_REASON)


def _restore_images(html: str, slide_text: str) -> str:
    """Replace each ``data:ref:img-N`` of ``html`` by the ``src`` of the Nth large image of ``slide_text``."""
    sources = [slide_text[start:end] for start, end in large_images(slide_text)]

    def source(token: re.Match[str]) -> str:
        trimmed = token.group(1).lstrip("0")
        number = int(trimmed) if 0 < len(trimmed) <= MAX_IMAGE_DIGITS else 0
        if not 1 <= number <= len(sources):
            raise OperationError(f'unknown image reference "{token.group()}"')
        return sources[number - 1]

    return IMAGE_TOKEN.sub(source, html)
