"""Older decks for the add-pointer tests (SPEC-0034): a template deck with the three parts of the pointer taken out.

``older_deck`` copies a presentation template into a folder of the test and removes the parts not in ``keep``:
``code`` (the block between the pointer markers), ``control`` (the ``btn-pointer`` line) and ``key`` (the line testing
the ``L`` key). The copy sits outside any template folder, so the command accepts it.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO_ROOT / "templates" / "bootstrap"
REFERENCE = REPO_ROOT / "templates" / "reference" / "slides"
CARBON = BOOTSTRAP / "slides-empty.html"
CHARTERS = {
    "carbon": CARBON,
    "ei": BOOTSTRAP / "slides-ei-empty.html",
    "medical": BOOTSTRAP / "slides-medical-empty.html",
    "breathe": BOOTSTRAP / "slides-breathe-empty.html",
    "standard": REFERENCE / "presentation-standard.html",
}
PARTS = ("code", "control", "key")

CODE_BLOCK = re.compile(r"<!-- deck-pointer:begin -->.*?<!-- deck-pointer:end -->\n", re.DOTALL)
CONTROL_LINE = re.compile(r'^[ \t]*<button[^\n]*id="btn-pointer"[^\n]*\n', re.MULTILINE)
KEY_LINE = re.compile(r"^[^\n]*\.key === 'l'[^\n]*\n", re.MULTILINE)
PRESENT_BUTTON = re.compile(r'[ \t]*<button\b[^>]*\bid="btn-present"[^>]*>.*?</button>\n', re.DOTALL)
INSERTED_CONTROL = re.compile(r'\r?\n[ \t]*<button[^\n]*id="btn-pointer"[^\n]*?</button>')
INSERTED_CODE = re.compile(r"<!-- deck-pointer:begin -->.*?<!-- deck-pointer:end -->\r?\n", re.DOTALL)
INSERTED_KEY = re.compile(r'<script id="deck-pointer-key">.*?</script>\r?\n', re.DOTALL)


def older_text(template: Path, keep: tuple[str, ...] = ()) -> str:
    """The template text with the parts not in ``keep`` removed."""
    text = template.read_text(encoding="utf-8")
    for part, pattern in (("code", CODE_BLOCK), ("control", CONTROL_LINE), ("key", KEY_LINE)):
        if part not in keep:
            text, count = pattern.subn("", text)
            assert count == 1, f"{template.name}: {part} not found exactly once"
    return text


def older_deck(template: Path, folder: Path, name: str = "deck.html", keep: tuple[str, ...] = ()) -> Path:
    """Write an older deck of ``template`` as ``folder/name``; ``keep`` lists the parts left in."""
    path = folder / name
    path.write_text(older_text(template, keep), encoding="utf-8", newline="")
    return path


def parts_in(text: str) -> dict[str, int]:
    """How many times each part is in ``text`` (comments ignored)."""
    seen = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return {
        "code": seen.count('<script id="deck-pointer-script"'),
        "control": seen.count('id="btn-pointer"'),
        "key": seen.count("key === 'l'"),
    }


def without_inserted(text: str) -> str:
    """``text`` with what ``add-pointer`` inserts taken out again: the control after ``btn-present`` and the code."""
    return INSERTED_KEY.sub("", INSERTED_CODE.sub("", INSERTED_CONTROL.sub("", text)))
