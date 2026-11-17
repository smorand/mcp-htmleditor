# ruff: noqa: E501 - SVG path data, one icon per line
"""Icons of the web library pages (SPEC-0025): the 24 by 24 outlines of the design system (app-design assets/js/icons-data.js).

Inline SVG, because the page policy allows no external resource but the site's own files and no style attribute.
"""

from __future__ import annotations

from typing import Final

PATHS: Final[dict[str, str]] = {
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>',
    "moon": '<path d="M20 14.5A8.5 8.5 0 019.5 4 8.5 8.5 0 1020 14.5z"/>',
    "upload": '<path d="M12 16V5M7 9l5-5 5 5M5 20h14"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6"/><path d="M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0113 0M16 4.7a3.5 3.5 0 010 6.6M18 14a6.5 6.5 0 013.5 6"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
    "folder": '<path d="M3 6a1 1 0 011-1h5l2 2.5h9a1 1 0 011 1V19a1 1 0 01-1 1H4a1 1 0 01-1-1z"/>',
    "file-text": '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.7"/><path d="M21 16l-5-5-9 9"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5M3 17.5l9 5 9-5" transform="translate(0 -1.5)"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
    "alert-circle": '<circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16.5v.5"/>',
    "logout": '<path d="M10 4H5a1 1 0 00-1 1v14a1 1 0 001 1h5M15 8l4 4-4 4M19 12H9"/>',
    "more-v": '<circle cx="12" cy="5" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="12" cy="19" r="1.2"/>',
    "chevron-left": '<path d="M15 6l-6 6 6 6"/>',
    "chevron-right": '<path d="M9 6l6 6-6 6"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0116 0"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>',
    "layout": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M10 10v10"/>',
    "edit": '<path d="M4 20h4L19 9a2.8 2.8 0 00-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    "refresh": '<path d="M20 11a8 8 0 00-14-4L4 9M4 4v5h5M4 13a8 8 0 0014 4l2-2M20 20v-5h-5"/>',
}


def icon(name: str, size: str = "") -> str:
    """The inline SVG of an icon, hidden from assistive technology (the control around it carries the name)."""
    classes = f"ico {size}".strip()
    return f'<svg class="{classes}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{PATHS[name]}</svg>'
