#!/usr/bin/env python3
"""Propagate the deck blocks (pointer, presenter) from the Carbon bootstrap to every presentation template.

``templates/bootstrap/slides-empty.html`` is the single source of the deck code: the blocks between
``<!-- deck-pointer:begin -->`` / ``<!-- deck-pointer:end -->`` and ``<!-- deck-presenter:begin -->`` /
``<!-- deck-presenter:end -->`` (markers included). Every other ``templates/**/*.html`` whose opening ``<html>``
tag holds ``data-doc-type="presentation"`` and that already holds the pointer begin marker gets each block replaced
by the source's; a block the source holds and the template lacks is inserted right after the previous block.
A template without the pointer marker is left alone. The pointer block is mandatory in the source; the others
are synced only when the source holds them.
``tests/test_presentation_templates_fullscreen.py`` names the templates that still lack the pointer.

Usage:
    python tools/sync_deck_pointer.py           # rewrite the blocks
    python tools/sync_deck_pointer.py --check   # report freshness, write nothing, exit 1 when stale
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from freshness import report_line

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = REPO / "templates"
SOURCE_REL = "bootstrap/slides-empty.html"
BLOCKS = ("deck-pointer", "deck-presenter")
BEGIN = f"<!-- {BLOCKS[0]}:begin -->"
END = f"<!-- {BLOCKS[0]}:end -->"
MAKE_TARGET = "sync-deck-pointer"

HTML_TAG = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
PRESENTATION_ATTRIBUTE = re.compile(r"""data-doc-type\s*=\s*["']presentation["']""", re.IGNORECASE)


def is_presentation(html: str) -> bool:
    """True when the document's own ``<html>`` tag (not one quoted in a comment) says presentation."""
    match = HTML_TAG.search(HTML_COMMENT.sub("", html))
    return match is not None and PRESENTATION_ATTRIBUTE.search(match.group(0)) is not None


def markers(name: str) -> tuple[str, str]:
    return f"<!-- {name}:begin -->", f"<!-- {name}:end -->"


def block_span(text: str, label: str, name: str = BLOCKS[0]) -> tuple[int, int] | None:
    """Offsets of the block, markers included; None without a begin marker; SystemExit without an end marker."""
    begin, end_marker = markers(name)
    start = text.find(begin)
    if start == -1:
        return None
    end = text.find(end_marker, start)
    if end == -1:
        raise SystemExit(f"error: {label} has {begin} but no {end_marker}")
    return start, end + len(end_marker)


def source_blocks(source: Path, label: str) -> dict[str, str]:
    """The blocks of the source file by name; SystemExit when the source or its pointer block is absent."""
    if not source.is_file():
        raise SystemExit(f"error: source not found: {label}")
    text = source.read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for name in BLOCKS:
        span = block_span(text, label, name)
        if span is not None:
            found[name] = text[span[0] : span[1]]
    if BLOCKS[0] not in found:
        raise SystemExit(f"error: {label} has no {BEGIN} block to copy")
    return found


def target_files(root: Path, source: Path) -> list[Path]:
    """Presentation templates, other than the source, that hold the begin marker, sorted."""
    found = []
    for path in sorted(root.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        if path != source and BEGIN in text and is_presentation(text):
            found.append(path)
    return found


def sync(root: Path, check: bool) -> int:
    """Rewrite (or only check) the blocks of every target under ``root``; return a process exit code."""
    source = root / SOURCE_REL
    references = source_blocks(source, source.relative_to(root.parent).as_posix())
    all_fresh = True
    for target in target_files(root, source):
        base_label = target.relative_to(root.parent).as_posix()
        text = target.read_text(encoding="utf-8")
        for name, reference in references.items():
            label = base_label if name == BLOCKS[0] else f"{base_label} [{name}]"
            span = block_span(text, label, name)
            if span is None:
                previous = block_span(text, label, BLOCKS[BLOCKS.index(name) - 1])
                if previous is None:  # unreachable: the pointer block is held, and blocks are inserted in order
                    continue
                if check:
                    print(f"{label}: stale (block missing); run: make {MAKE_TARGET}")
                else:
                    text = text[: previous[1]] + "\n" + reference + text[previous[1] :]
                    target.write_text(text, encoding="utf-8")
                    print(f"updated: {label}")
                all_fresh = False
                continue
            current = text[span[0] : span[1]]
            line, is_fresh = report_line(label, reference, current, MAKE_TARGET, offset=text.count("\n", 0, span[0]))
            if check:
                print(line)
            elif is_fresh:
                print(f"ok: {label}")
            else:
                text = text[: span[0]] + reference + text[span[1] :]
                target.write_text(text, encoding="utf-8")
                print(f"updated: {label}")
            all_fresh &= is_fresh
    return 0 if all_fresh or not check else 1


def main(argv: list[str]) -> int:
    """Sync (or check) the templates of the repository."""
    return sync(TEMPLATES, "--check" in argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
