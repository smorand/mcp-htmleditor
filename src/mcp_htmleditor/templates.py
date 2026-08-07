"""Template registry for mcp-htmleditor.

Maps short template keys (used by `mcp-htmleditor new <key>`) to the
bootstrap HTML files bundled in the package skill directory.
"""

from __future__ import annotations

from pathlib import Path


def _skill_dir() -> Path:
    """Return the path to the bundled skill directory.

    The skill lives at the repo root (skill/), one level above the package
    source. When installed as a wheel it is shipped alongside the package.
    """
    # src/mcp_htmleditor/templates.py -> repo root is parents[2]
    candidates = [
        Path(__file__).resolve().parents[2] / "skill",
        Path(__file__).resolve().parent / "skill",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    # Fallback: repo-root skill even if missing (error surfaced later)
    return candidates[0]


# key -> (relative path under skill/, human description)
TEMPLATES: dict[str, tuple[str, str]] = {
    "ei": (
        "templates/bootstrap/slides-ei-empty.html",
        "Euro-Information presentation (Crédit Mutuel / CIC), 1 title slide",
    ),
    "carbon": (
        "templates/bootstrap/slides-empty.html",
        "IBM Carbon presentation, 1 empty slide",
    ),
    "doc": (
        "templates/bootstrap/document-empty.html",
        "Word-like document (single column)",
    ),
}


def template_path(key: str) -> Path:
    """Return the absolute path to the bootstrap file for a template key.

    Args:
        key: Template key (e.g. 'ei', 'carbon', 'doc').

    Returns:
        Absolute path to the bootstrap HTML file.

    Raises:
        KeyError: If the key is unknown.
        FileNotFoundError: If the bootstrap file is missing on disk.
    """
    if key not in TEMPLATES:
        raise KeyError(key)
    rel, _ = TEMPLATES[key]
    path = _skill_dir() / rel
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return path


def list_templates() -> list[tuple[str, str]]:
    """Return a list of (key, description) for all available templates."""
    return [(key, desc) for key, (_, desc) in TEMPLATES.items()]
