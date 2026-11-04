"""Byte offset scanner: locate elements in raw HTML without re-serializing it (SPEC-0007 DEC-001, DEC-002).

``scan`` records, for every element, the offsets of its start and end tags so a slide can be cut out of
the file text as is. BeautifulSoup tags are bridged to nodes by ``(sourceline, sourcepos)``, which equals
the ``getpos()`` of the scanner. Pure functions, no printing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from html.parser import HTMLParser

VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
)
LARGE_SOURCE_CHARS = 1000
IMAGE_REFERENCE = "data:ref:img-{}"
# one attribute: name, then an optionally quoted value; quoted values are consumed whole, so a
# look alike ``src=`` inside another value is never matched
_ATTRIBUTE = re.compile(r"""([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?""")
_TAG_NAME = re.compile(r"<[^\s/>]+")


@dataclass(frozen=True, slots=True)
class Node:
    """An element: ``start`` is its ``<``, ``start_end`` is after the start tag ``>``.

    ``end_start`` is the ``</`` and ``end_end`` is after the end tag ``>``; an element with no end tag
    (void, ``<x/>``) has ``end_start == end_end == start_end``. ``line`` is 1-based, ``col`` 0-based.
    """

    tag: str
    start: int
    start_end: int
    end_start: int
    end_end: int
    line: int
    col: int


class Scanner(HTMLParser):
    """Collect ``Node`` objects in document order; an end tag closes the nearest open element of its name."""

    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=False)
        self._text = text
        self._line_starts = [0, *(i + 1 for i, ch in enumerate(text) if ch == "\n")]
        self.nodes: list[Node] = []
        self._open: list[int] = []  # indexes into ``nodes``

    def scan(self) -> list[Node]:
        """Feed the whole text and close what is still open at its end."""
        self.feed(self._text)
        self.close()
        end = len(self._text)
        for index in self._open:
            self.nodes[index] = replace(self.nodes[index], end_start=end, end_end=end)
        self._open.clear()
        return self.nodes

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: ARG002 - override
        index = self._add(tag)
        if tag not in VOID_TAGS:
            self._open.append(index)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: ARG002 - override
        self._add(tag)

    def handle_endtag(self, tag: str) -> None:
        end_start = self._offset()
        end_end = self._text.find(">", end_start) + 1 or len(self._text)
        for depth in range(len(self._open) - 1, -1, -1):
            if self.nodes[self._open[depth]].tag == tag:
                break
        else:
            return
        for position, index in enumerate(self._open[depth:]):
            closing_end = end_end if position == 0 else end_start
            self.nodes[index] = replace(self.nodes[index], end_start=end_start, end_end=closing_end)
        del self._open[depth:]

    def _add(self, tag: str) -> int:
        start = self._offset()
        start_end = start + len(self.get_starttag_text() or "")
        line, col = self.getpos()
        self.nodes.append(Node(tag, start, start_end, start_end, start_end, line, col))
        return len(self.nodes) - 1

    def _offset(self) -> int:
        line, col = self.getpos()
        return self._line_starts[line - 1] + col


def scan(text: str) -> list[Node]:
    """Return every element of ``text`` in document order."""
    return Scanner(text).scan()


def slide_range(nodes: list[Node], node: Node) -> tuple[int, int]:  # noqa: ARG001 - signature set by the contract
    """Return ``[start, end)`` of the element ``node`` of ``nodes`` (its start tag through its end tag)."""
    return node.start, node.end_end


def large_images(slide_text: str) -> list[tuple[int, int]]:
    """Return ``(start, end)`` of the ``src`` value of each ``img`` holding a data address over 1 000 chars."""
    spans: list[tuple[int, int]] = []
    for node in scan(slide_text):
        if node.tag != "img":
            continue
        span = _source_span(slide_text, node)
        if span and span[1] - span[0] > LARGE_SOURCE_CHARS and slide_text.startswith("data:", span[0]):
            spans.append(span)
    return spans


def hide_images(slide_text: str) -> str:
    """Replace the Nth large image source of ``slide_text`` by ``data:ref:img-N`` (N from 1)."""
    pieces: list[str] = []
    cursor = 0
    for number, (start, end) in enumerate(large_images(slide_text), start=1):
        pieces.extend((slide_text[cursor:start], IMAGE_REFERENCE.format(number)))
        cursor = end
    pieces.append(slide_text[cursor:])
    return "".join(pieces)


def _source_span(text: str, node: Node) -> tuple[int, int] | None:
    """Return the offsets of the ``src`` value inside the start tag of ``node``."""
    tag_text = text[node.start : node.start_end]
    name = _TAG_NAME.match(tag_text)
    begin = name.end() if name else 0
    for match in _ATTRIBUTE.finditer(tag_text, begin):
        if match.group(1).lower() != "src":
            continue
        group = next((g for g in (2, 3, 4) if match.group(g) is not None), None)
        return None if group is None else (node.start + match.start(group), node.start + match.end(group))
    return None
