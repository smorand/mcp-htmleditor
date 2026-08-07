"""Skill content assembly for `mcp-htmleditor skill`.

Concatenates the skill index (SKILL.md) with all sub-documents
(workflows + per-type rules) into a single Markdown block, so an agent
gets the complete skill in one command.
"""

from __future__ import annotations

from pathlib import Path


def _skill_dir() -> Path:
    """Return the bundled skill directory (repo skill/ or package skill/)."""
    candidates = [
        Path(__file__).resolve().parents[2] / "skill",
        Path(__file__).resolve().parent / "skill",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


# Order in which sub-documents are concatenated after SKILL.md.
_SUBDOCS = [
    "workflow-create.md",
    "workflow-export.md",
    "workflow-templates.md",
    "types/slides.md",
    "types/document.md",
    "types/gantt.md",
    "types/arch-diagram.md",
    "types/annotated-image.md",
    "types/tables.md",
]


def build_skill_content() -> str:
    """Assemble the full skill as a single Markdown string.

    Returns:
        SKILL.md followed by each existing sub-document, separated by rules.
    """
    skill = _skill_dir()
    parts: list[str] = []

    index = skill / "SKILL.md"
    if index.is_file():
        parts.append(index.read_text(encoding="utf-8").rstrip())

    for rel in _SUBDOCS:
        path = skill / rel
        if path.is_file():
            parts.append(
                f"\n\n---\n\n<!-- ===== {rel} ===== -->\n\n"
                + path.read_text(encoding="utf-8").rstrip()
            )

    return "\n".join(parts) + "\n"
