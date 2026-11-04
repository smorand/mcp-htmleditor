"""Renumber a presentation text: ids, ``active``, counters, ``TOTAL``, ``slideNames`` (SPEC-0007 DEC-005).

``renumber_edits`` scans the assembled text once, enumerates the slides with ``find_slides`` and returns
non overlapping edits; an edit whose replacement equals the current bytes is never returned, so a
consistent file yields ``[]``. The rules reproduce ``renumberSlides`` of ``static/editor-slides.js``.
Cost: one scan and one parse of the text, then one pass over the slides (linear). No printing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from bs4 import BeautifulSoup
from bs4.element import Tag

from . import detect_charter
from .scan import Node, scan

CARBON = "carbon"
COUNTER = re.compile(r"Slide\s*\d+\s*/\s*\d+")
ATTRIBUTE = re.compile(r"""([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?""")
TAG_NAME = re.compile(r"<[^\s/>]+")
TOTAL = re.compile(r"(const\s+TOTAL\s*=\s*)\d+(?=\s*;)")
# the list ends at the first ``]`` outside a string, so a title holding ``];`` cannot cut it short
NAMES = re.compile(r"const\s+slideNames\s*=\s*\[(?:[^\]\"']|\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')*\]\s*;")
MISSING_TITLE = "Slide"  # what editor-slides.js writes for a slide with no data-title


@dataclass(frozen=True, slots=True)
class Edit:
    """Replace ``text[start:end]`` by ``text``."""

    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class Context:
    """What the counter rules read: the text, its nodes by position, the slide total and the counter kind."""

    text: str
    nodes: dict[tuple[int | None, int | None], Node]
    total: int
    is_carbon: bool


def renumber_edits(text: str) -> list[Edit]:
    """Return the edits, in document order, that make ids, counters and the navigation script consistent."""
    from ..export.to_pptx import find_slides  # noqa: PLC0415 - python-pptx costs 0.29 s, never at import

    soup = BeautifulSoup(text, "html.parser")
    slides = find_slides(soup)
    if not slides:
        return []
    nodes: dict[tuple[int | None, int | None], Node] = {(node.line, node.col): node for node in scan(text)}
    context = Context(text, nodes, len(slides), detect_charter(soup, "presentation") == CARBON)
    candidates: list[Edit] = []
    for index, slide in enumerate(slides):
        node = nodes[(slide.sourceline, slide.sourcepos)]
        candidates.append(Edit(node.start, node.start_end, _start_tag(text[node.start : node.start_end], index)))
        candidates.extend(_counter_edits(context, slide, index))
    titles = [str(slide.get("data-title") or MISSING_TITLE) for slide in slides]
    candidates.extend(_script_edits(text, context.nodes.values(), titles))
    return sorted((e for e in candidates if e.text != text[e.start : e.end]), key=lambda e: e.start)


def apply_edits(text: str, edits: list[Edit]) -> str:
    """Return ``text`` with the non overlapping ``edits`` applied, from the end backwards."""
    for edit in reversed(edits):
        text = text[: edit.start] + edit.text + text[edit.end :]
    return text


def _start_tag(tag_text: str, index: int) -> str:
    """Return the start tag with ``id``, ``data-id`` set to ``slide-<index>`` and ``active`` only on slide 0."""
    wanted = f"slide-{index}"
    name_end = _name_end(tag_text)
    found: dict[str, re.Match[str]] = {}
    for match in ATTRIBUTE.finditer(tag_text, name_end):
        found.setdefault(match.group(1).lower(), match)
    changes: list[tuple[int, int, str]] = []
    appended = ""
    for name, value in (("id", wanted), ("data-id", wanted)):
        if name in found:
            changes.append(_set_value(found[name], value))
        else:
            appended += f' {name}="{value}"'
    classes = found.get("class")
    current = (classes.group(2) or classes.group(3) or classes.group(4) or "").split() if classes else []
    if index == 0:
        target = current if "active" in current else [*current, "active"]
    else:
        target = [c for c in current if c != "active"]
    if classes and target != current:
        changes.append(_set_value(classes, " ".join(target)))
    elif not classes and target:
        appended += f' class="{" ".join(target)}"'
    for start, end, value in sorted(changes, reverse=True):
        tag_text = tag_text[:start] + value + tag_text[end:]
    if not appended:
        return tag_text
    last = max((m.end() for m in found.values()), default=name_end) + sum(len(v) - (e - s) for s, e, v in changes)
    return tag_text[:last] + appended + tag_text[last:]


def _name_end(tag_text: str) -> int:
    name = TAG_NAME.match(tag_text)
    return name.end() if name else 1


def _set_value(match: re.Match[str], value: str) -> tuple[int, int, str]:
    """Return the change that gives the attribute ``match`` the value ``value``, quoted ones in place."""
    group = next((g for g in (2, 3) if match.group(g) is not None), None)
    if group is None:  # bare name or unquoted value: write the whole attribute again
        return match.start(), match.end(), f'{match.group(1)}="{value}"'
    return match.start(group), match.end(group), value


def _counter_edits(context: Context, slide: Tag, index: int) -> list[Edit]:
    """Return the eyebrow, footer and page counter edits of one slide; absent elements are not created."""
    edits: list[Edit] = []
    position = index + 1
    eyebrow = _inner(context, slide.select_one(".slide-eyebrow"))
    if eyebrow:
        edits.extend(_pattern_edit(context.text, eyebrow, f"Slide {position:02d} / {context.total:02d}"))
    if context.is_carbon:
        footer = _inner(context, slide.select_one(".slide-footer-right"))
        if footer:
            edits.extend(_pattern_edit(context.text, footer, f"Slide {position} / {context.total}"))
    else:
        page = _inner(context, slide.select_one(".slide-foot-page"))
        if page:
            edits.append(Edit(page[0], page[1], str(position)))
    return edits


def _inner(context: Context, element: Tag | None) -> tuple[int, int] | None:
    """Return the span of the raw content of ``element``, or ``None`` when it has none to rewrite."""
    if element is None:
        return None
    node = context.nodes[(element.sourceline, element.sourcepos)]
    return None if node.start_end == node.end_end else (node.start_end, node.end_start)


def _pattern_edit(text: str, span: tuple[int, int], replacement: str) -> list[Edit]:
    found = COUNTER.search(text, *span)
    return [Edit(found.start(), found.end(), replacement)] if found else []


def _script_edits(text: str, nodes: Iterable[Node], titles: list[str]) -> list[Edit]:
    """Return the edits of the first ``TOTAL`` constant and the first ``slideNames`` list of the scripts."""
    edits: list[Edit] = []
    is_total_done = is_names_done = False
    for node in nodes:
        if node.tag != "script":
            continue
        total = None if is_total_done else TOTAL.search(text, node.start_end, node.end_start)
        if total:
            is_total_done = True
            edits.append(Edit(total.end(1), total.end(), str(len(titles))))
        names = None if is_names_done else NAMES.search(text, node.start_end, node.end_start)
        if names:
            is_names_done = True
            edits.append(Edit(names.start(), names.end(), _names_statement(text, names, titles)))
    return edits


def _names_statement(text: str, found: re.Match[str], titles: list[str]) -> str:
    """Return the ``slideNames`` statement: one entry per line, first entry's indent, trailing commas."""
    line_start = text.rfind("\n", 0, found.start()) + 1
    outer = re.match(r"[ \t]*", text[line_start:]).group()  # type: ignore[union-attr] # always matches
    block = found.group()
    first = re.match(r"[^\[]*\[\s*\n([ \t]*)\S", block)
    inner = first.group(1) if first else outer + "  "
    eol = "\r\n" if "\r\n" in (block if "\n" in block else text) else "\n"
    entries = "".join(f"{inner}{_quote(title)},{eol}" for title in titles)
    return f"const slideNames = [{eol}{entries}{outer}];"


def _quote(title: str) -> str:
    escaped = title.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n")
    return '"' + escaped.replace("</", "<\\/") + '"'
