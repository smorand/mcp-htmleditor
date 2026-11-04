"""User-editable QA checklist for architecture diagrams.

Mirrors ``templates.py``'s search path exactly, so the same mental model
applies to both: the checklist is resolved from, in priority order,

    1. HTMLEDITOR_ARCH_CHECKS_DIR (env override)
    2. ~/.config/mcp-htmleditor/arch-checks/arch-diagram-checklist.md
       (seeded once by `make install`, never overwritten on reinstall: this
       file is meant to be hand-edited, see `skill/checks/`)
    3. <skill dir>/checks/arch-diagram-checklist.md (shipped fallback)

Editing the installed copy directly is the supported way to add or change a
control ("ajoute ce contrôle", "change cette règle"): no code change, no
reinstall, and ``mcp-htmleditor skill`` picks it up on its next call since it
re-reads the file every time rather than embedding a frozen copy.
"""

from __future__ import annotations

from pathlib import Path

from . import config

CHECKLIST_FILENAME = "arch-diagram-checklist.md"


def _repo_checks_dir() -> Path:
    """Return the shipped checks directory, ``<skill dir>/checks``."""
    return config.skill_dir() / "checks"


def checklist_search_path() -> list[Path]:
    """Return the ordered list of directories to search for the checklist."""
    return [config.arch_checks_dir(), _repo_checks_dir()]


def checklist_path() -> Path:
    """Return the resolved checklist file, following the search path.

    Falls back to the bundled repo copy when the user directory has no file
    yet (e.g. before the first `make install`, or in a dev checkout).
    """
    for base in checklist_search_path():
        candidate = base / CHECKLIST_FILENAME
        if candidate.is_file():
            return candidate
    return _repo_checks_dir() / CHECKLIST_FILENAME


def _read_usable(path: Path) -> str:
    """Return the file's text, or "" when it is not a file, unreadable or blank."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return text if text.strip() else ""


def read_checklist() -> str:
    """Return the first usable checklist along the search path, "" when none.

    Re-reads the files every call (no caching): editing the user file takes
    effect on the very next `mcp-htmleditor skill` or QA subagent run. A
    candidate that is not a file, is unreadable or is blank is skipped.
    """
    for base in checklist_search_path():
        text = _read_usable(base / CHECKLIST_FILENAME)
        if text:
            return text
    return ""


def read_shipped_checklist() -> str:
    """Return the shipped checklist only (never the user file), "" on any failure."""
    return _read_usable(_repo_checks_dir() / CHECKLIST_FILENAME)
