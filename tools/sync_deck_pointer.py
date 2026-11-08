#!/usr/bin/env python3
"""Propagate the presentation pointer block from the Carbon bootstrap to every presentation template.

``templates/bootstrap/slides-empty.html`` is the single source of the pointer code: the block between
``<!-- deck-pointer:begin -->`` and ``<!-- deck-pointer:end -->`` (markers included). Every other
``templates/**/*.html`` whose opening ``<html>`` tag holds ``data-doc-type="presentation"`` and that already
holds the begin marker gets its block replaced by the source's. A template without the marker is left alone.
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
BEGIN = "<!-- deck-pointer:begin -->"
END = "<!-- deck-pointer:end -->"
MAKE_TARGET = "sync-deck-pointer"

HTML_TAG = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
PRESENTATION_ATTRIBUTE = re.compile(r"""data-doc-type\s*=\s*["']presentation["']""", re.IGNORECASE)


def is_presentation(html: str) -> bool:
    """True when the document's own ``<html>`` tag (not one quoted in a comment) says presentation."""
    match = HTML_TAG.search(HTML_COMMENT.sub("", html))
    return match is not None and PRESENTATION_ATTRIBUTE.search(match.group(0)) is not None


def block_span(text: str, label: str) -> tuple[int, int] | None:
    """Offsets of the block, markers included; None without a begin marker; SystemExit without an end marker."""
    start = text.find(BEGIN)
    if start == -1:
        return None
    end = text.find(END, start)
    if end == -1:
        raise SystemExit(f"error: {label} has {BEGIN} but no {END}")
    return start, end + len(END)


def source_block(source: Path, label: str) -> str:
    """The block of the source file; SystemExit when the source or its block is absent."""
    if not source.is_file():
        raise SystemExit(f"error: source not found: {label}")
    text = source.read_text(encoding="utf-8")
    span = block_span(text, label)
    if span is None:
        raise SystemExit(f"error: {label} has no {BEGIN} block to copy")
    return text[span[0] : span[1]]


def target_files(root: Path, source: Path) -> list[Path]:
    """Presentation templates, other than the source, that hold the begin marker, sorted."""
    found = []
    for path in sorted(root.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        if path != source and BEGIN in text and is_presentation(text):
            found.append(path)
    return found


def sync(root: Path, check: bool) -> int:
    """Rewrite (or only check) the block of every target under ``root``; return a process exit code."""
    source = root / SOURCE_REL
    reference = source_block(source, source.relative_to(root.parent).as_posix())
    all_fresh = True
    for target in target_files(root, source):
        label = target.relative_to(root.parent).as_posix()
        text = target.read_text(encoding="utf-8")
        span = block_span(text, label)
        if span is None:  # unreachable: target_files kept only files holding the begin marker
            continue
        current = text[span[0] : span[1]]
        line, is_fresh = report_line(label, reference, current, MAKE_TARGET, offset=text.count("\n", 0, span[0]))
        if check:
            print(line)
        elif is_fresh:
            print(f"ok: {label}")
        else:
            target.write_text(text[: span[0]] + reference + text[span[1] :], encoding="utf-8")
            print(f"updated: {label}")
        all_fresh &= is_fresh
    return 0 if all_fresh or not check else 1


def main(argv: list[str]) -> int:
    """Sync (or check) the templates of the repository."""
    return sync(TEMPLATES, "--check" in argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
