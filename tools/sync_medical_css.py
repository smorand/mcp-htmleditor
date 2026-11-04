#!/usr/bin/env python3
"""Propagate the medical charter CSS from its bootstrap to the reference decks.

``templates/bootstrap/slides-medical-empty.html`` is the single source of the
``medical`` charter CSS. The reference catalogue and the complete example are
standalone files (they must open on their own, without the bootstrap), so each
embeds a copy of that same ``<style>`` block. This script rewrites those copies,
and ``tests/test_medical_template.py`` fails the build when they diverge.

Usage:
    python tools/sync_medical_css.py           # rewrite the copies
    python tools/sync_medical_css.py --check   # report freshness, write nothing
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from freshness import report_line, source_missing_error

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "templates" / "bootstrap" / "slides-medical-empty.html"
TARGETS = [
    REPO / "templates" / "reference" / "slides" / "medical.html",
    REPO / "templates" / "reference" / "slides" / "example-medical-complete.html",
]

# Anchored on a line of its own: a header comment mentioning the style tag
# would otherwise start the match and the "CSS" would swallow <html> and <head>.
_STYLE_RE = re.compile(r"^<style>\n.*?^</style>", re.DOTALL | re.MULTILINE)


def style_block_span(path: Path) -> tuple[str, int]:
    """Return the first ``<style>…</style>`` block of an HTML file and its start offset."""
    text = path.read_text(encoding="utf-8")
    match = _STYLE_RE.search(text)
    if match is None:
        raise SystemExit(f"no <style> block found in {path}")
    return match.group(0), match.start()


def style_block(path: Path) -> str:
    """Return the first ``<style>…</style>`` block of an HTML file."""
    return style_block_span(path)[0]


def check(reference: str) -> int:
    """Print one freshness line per target; return 0 only when all are fresh."""
    all_fresh = True
    for target in TARGETS:
        rel = target.relative_to(REPO).as_posix()
        if not target.is_file():
            line, is_fresh = report_line(rel, reference, None, "sync-medical-css")
        else:
            current, start = style_block_span(target)
            text = target.read_text(encoding="utf-8")
            block_line = text.count("\n", 0, start) + 1
            line, is_fresh = report_line(rel, reference, current, "sync-medical-css", offset=block_line - 1)
        print(line)
        all_fresh &= is_fresh
    return 0 if all_fresh else 1


def main(argv: list[str]) -> int:
    """Sync (or check) the CSS copies; return a process exit code."""
    check_only = "--check" in argv
    if check_only and not SOURCE.is_file():
        print(source_missing_error(SOURCE.relative_to(REPO).as_posix()), file=sys.stderr)
        return 1
    reference = style_block(SOURCE)
    if check_only:
        return check(reference)
    for target in TARGETS:
        if not target.is_file():
            print(f"skip (absent): {target.relative_to(REPO)}")
            continue
        text = target.read_text(encoding="utf-8")
        current = style_block(target)
        if current == reference:
            print(f"ok: {target.relative_to(REPO)}")
            continue
        target.write_text(text.replace(current, reference, 1), encoding="utf-8")
        print(f"updated: {target.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
