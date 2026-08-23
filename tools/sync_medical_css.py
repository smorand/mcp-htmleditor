#!/usr/bin/env python3
"""Propagate the medical charter CSS from its bootstrap to the reference decks.

``templates/bootstrap/slides-medical-empty.html`` is the single source of the
``medical`` charter CSS. The reference catalogue and the complete example are
standalone files (they must open on their own, without the bootstrap), so each
embeds a copy of that same ``<style>`` block. This script rewrites those copies,
and ``tests/test_medical_template.py`` fails the build when they diverge.

Usage:
    python tools/sync_medical_css.py           # rewrite the copies
    python tools/sync_medical_css.py --check   # report divergence, write nothing
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "templates" / "bootstrap" / "slides-medical-empty.html"
TARGETS = [
    REPO / "templates" / "reference" / "slides" / "medical.html",
    REPO / "templates" / "reference" / "slides" / "example-medical-complete.html",
]

# Anchored on a line of its own: a header comment mentioning the style tag
# would otherwise start the match and the "CSS" would swallow <html> and <head>.
_STYLE_RE = re.compile(r"^<style>\n.*?^</style>", re.DOTALL | re.MULTILINE)


def style_block(path: Path) -> str:
    """Return the first ``<style>…</style>`` block of an HTML file."""
    match = _STYLE_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"no <style> block found in {path}")
    return match.group(0)


def main(argv: list[str]) -> int:
    """Sync (or check) the CSS copies; return a process exit code."""
    check = "--check" in argv
    reference = style_block(SOURCE)
    diverged: list[Path] = []
    for target in TARGETS:
        if not target.is_file():
            print(f"skip (absent): {target.relative_to(REPO)}")
            continue
        text = target.read_text(encoding="utf-8")
        current = style_block(target)
        if current == reference:
            print(f"ok: {target.relative_to(REPO)}")
            continue
        diverged.append(target)
        if check:
            print(f"DIVERGED: {target.relative_to(REPO)}")
            continue
        target.write_text(text.replace(current, reference, 1), encoding="utf-8")
        print(f"updated: {target.relative_to(REPO)}")
    if check and diverged:
        print("\nRun `make sync-medical-css` to propagate the bootstrap CSS.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
