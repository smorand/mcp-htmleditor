"""User-editable QA checklist for architecture diagrams.

Mirrors ``templates.py``'s search path exactly, so the same mental model
applies to both: the checklist is resolved from, in priority order,

    1. HTMLEDITOR_ARCH_CHECKS_DIR (env override)
    2. ~/.config/mcp-htmleditor/arch-checks/arch-diagram-checklist.md
       (seeded once by `make install`, never overwritten on reinstall: this
       file is meant to be hand-edited, see `skill/checks/`)
    3. <repo>/skill/checks/arch-diagram-checklist.md (bundled fallback)

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
    """Return the skill/checks/ directory bundled in the repo/package."""
    candidates = [
        Path(__file__).resolve().parents[2] / "skill" / "checks",
        Path(__file__).resolve().parent / "skill" / "checks",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


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


def read_checklist() -> str:
    """Return the resolved checklist's current content.

    Re-reads the file every call (no caching): editing it takes effect on the
    very next `mcp-htmleditor skill` or QA subagent run, no reinstall needed.
    """
    path = checklist_path()
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")
