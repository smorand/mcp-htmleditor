"""Template registry for mcp-htmleditor.

Templates are resolved from a search path, in priority order:

    1. HTMLEDITOR_TEMPLATES_DIR (env override)
    2. ~/.config/mcp-htmleditor/templates   (installed by `make install`)
    3. <repo>/templates                     (development / bundled fallback)

Each template key maps to a bootstrap file (templates/bootstrap/*.html).
Reference examples live under templates/reference/ for cloning.
"""

from __future__ import annotations

from pathlib import Path

from . import config


def _repo_templates_dir() -> Path:
    """Return the templates/ directory bundled in the repo/package."""
    # src/mcp_htmleditor/templates.py -> repo root is parents[2]
    candidates = [
        Path(__file__).resolve().parents[2] / "templates",
        Path(__file__).resolve().parent / "templates",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


def template_search_path() -> list[Path]:
    """Return the ordered list of directories to search for templates."""
    return [config.templates_dir(), _repo_templates_dir()]


# key -> (relative path under a templates dir, human description)
TEMPLATES: dict[str, tuple[str, str]] = {
    "ei": (
        "bootstrap/slides-ei-empty.html",
        "Euro-Information presentation (Crédit Mutuel / CIC), 1 title slide",
    ),
    "carbon": (
        "bootstrap/slides-empty.html",
        "IBM Carbon presentation, 1 empty slide",
    ),
    "doc": (
        "bootstrap/document-empty.html",
        "Word-like document (single column)",
    ),
}


def template_path(key: str) -> Path:
    """Return the absolute path to the bootstrap file for a template key.

    Searches the template search path in priority order and returns the
    first match.

    Args:
        key: Template key (e.g. 'ei', 'carbon', 'doc').

    Returns:
        Absolute path to the bootstrap HTML file.

    Raises:
        KeyError: If the key is unknown.
        FileNotFoundError: If no matching file exists in the search path.
    """
    if key not in TEMPLATES:
        raise KeyError(key)
    rel, _ = TEMPLATES[key]
    for base in template_search_path():
        candidate = base / rel
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(b / rel) for b in template_search_path())
    raise FileNotFoundError(f"template '{key}' not found in: {searched}")


def list_templates() -> list[tuple[str, str]]:
    """Return a list of (key, description) for all available templates."""
    return [(key, desc) for key, (_, desc) in TEMPLATES.items()]
