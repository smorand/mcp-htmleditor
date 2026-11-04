"""Apply a list of operations to a deck file in one atomic write (SPEC-0007 FR-NEW-003, FR-NEW-004).

The file text is cut into a working copy: an ordered list of raw gaps and slide atoms (DEC-003). Only
``set_text`` is executed; the four structural operations are parsed and validated, then refused until
they land. The output is the join of the atoms, so bytes outside an edit are identical by construction.
Cost: one scan and one parse of the file, plus one scan and one parse of the slide per ``set_text``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import soupsieve
from bs4 import BeautifulSoup
from bs4.element import Tag

from ..fileio import atomic_write
from . import Deck, DeckError, load_deck, slide_id
from .scan import Node, scan

TEMPLATE_FOLDERS = (("templates", "bootstrap"), ("templates", "reference"))
REQUIRED_FIELDS = {
    "set_text": ("id", "selector", "text"),
    "replace_slide": ("id", "html"),
    "insert_slide": ("after", "html"),
    "delete_slide": ("id",),
    "move_slide": ("id", "after"),
}
SLIDE_REFERENCES = ("id", "after")  # fields holding the id of an existing slide


class OperationError(Exception):
    """Why one operation cannot be applied; ``apply_patch`` adds its number."""


@dataclass(frozen=True, slots=True)
class Operation:
    """One validated operation: its name and its required string fields."""

    op: str
    fields: dict[str, str]


@dataclass(frozen=True, slots=True)
class Atom:
    """A piece of the file: raw gap (``orig_id`` is ``None``) or a slide with its leading ``pre``."""

    text: str
    orig_id: str | None
    touched: bool


class Working:
    """The working copy of a file: atoms in order, and the map from original slide id to atom."""

    def __init__(self, deck: Deck) -> None:
        self._atoms: list[Atom] = []
        self._position: dict[str, int] = {}
        nodes: dict[tuple[int | None, int | None], Node] = {(node.line, node.col): node for node in scan(deck.text)}
        cursor = 0
        for index, tag in enumerate(deck.slides):
            node = nodes[(tag.sourceline, tag.sourcepos)]
            start = _pre_start(deck.text, node.start, cursor)
            self._add(deck.text[cursor:start], None)
            self._add(deck.text[start : node.end_end], slide_id(tag) or f"slide-{index}")
            cursor = node.end_end
        self._add(deck.text[cursor:], None)

    @property
    def slide_count(self) -> int:
        """Return the number of slide atoms."""
        return len(self._position)

    def text(self) -> str:
        """Return the file text: the atoms joined."""
        return "".join(atom.text for atom in self._atoms)

    def require_slide(self, slide: str) -> int:
        """Return the position of the atom of original id ``slide``."""
        if slide not in self._position:
            raise OperationError(f'unknown slide id "{slide}"')
        return self._position[slide]

    def set_text(self, slide: str, selector: str, text: str) -> None:
        """Replace the inner content of the first element matching ``selector`` in ``slide`` by ``text``."""
        position = self.require_slide(slide)
        atom = self._atoms[position]
        edited = _splice_text(atom.text, slide, selector, text)
        if edited != atom.text:
            self._atoms[position] = replace(atom, text=edited, touched=True)

    def _add(self, text: str, orig_id: str | None) -> None:
        if orig_id is not None:
            self._position[orig_id] = len(self._atoms)
        if text or orig_id is not None:
            self._atoms.append(Atom(text, orig_id, touched=False))


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
    data = working.text().encode("utf-8")
    is_changed = working.text() != deck.text
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
    if operation.op == "set_text":
        working.set_text(fields["id"], fields["selector"], fields["text"])
        return
    for field in SLIDE_REFERENCES:
        if field in fields:
            working.require_slide(fields[field])
    raise OperationError(f'operation "{operation.op}" is not supported yet')


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
