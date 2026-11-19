"""The folder rule of a deck (SPEC-0026): a local picture is read only from the deck's own folder.

A picture address is "inside" when its real path, symlinks followed, lies in the folder of the deck file or below it.
The PPTX exports, the DOCX export and ``render`` share this one rule, so each read site only asks :func:`is_inside`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

OUTSIDE_PREFIX: Final = "Image hors du dossier du deck, ignoree: "
"""Start of the warning of a refused picture (SPEC-0026 BR-005); the address follows."""
SOURCE_CHARS: Final = 60
"""Characters of the address kept in the warning."""


def is_inside(root: Path, path: Path) -> bool:
    """True when ``path`` (symlinks followed, need not exist) lies in ``root`` or below. O(depth)."""
    return path.resolve().is_relative_to(root.resolve())


def url_to_path(url: str) -> Path | None:
    """The local path of a ``file://`` URL, ``None`` for any other scheme."""
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    return Path(url2pathname(unquote(parsed.path)))


def outside_warning(src: str) -> str:
    """The warning of a refused picture, the address cut at :data:`SOURCE_CHARS` characters."""
    return OUTSIDE_PREFIX + src[:SOURCE_CHARS]


def guard_browser(target: Any, root: Path) -> None:
    """Abort every ``file://`` request of a Playwright page or context outside ``root`` (any resource type)."""

    def handle(route: Any) -> None:
        path = url_to_path(route.request.url)
        if path is not None and is_inside(root, path):
            route.continue_()
        else:
            route.abort()

    target.route("file://**", handle)


__all__ = ["OUTSIDE_PREFIX", "SOURCE_CHARS", "guard_browser", "is_inside", "outside_warning", "url_to_path"]
