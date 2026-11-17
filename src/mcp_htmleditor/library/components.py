# ruff: noqa: E501 - the SVG paths of the logo, the ridge and the Google mark are single lines of data
"""Pieces of markup shared by the web library pages (SPEC-0025): the document, the logo, the ridge, the Google mark.

No text of the product lives here (every text is a constant of ``pages.py``, DEC-055). Everything is inline SVG or a
class of ``static/library.css``: the page policy allows no style attribute and no external file but the site's own.
"""

from __future__ import annotations

from typing import Final

STYLESHEET_PATH: Final = "/lib/library.css"
SCRIPT_PATH: Final = "/lib/library.js"
THEME_SCRIPT_PATH: Final = "/lib/theme.js"
LOGO: Final = (
    '<svg viewBox="0 0 48 48" aria-hidden="true" focusable="false"><rect width="48" height="48" rx="12" fill="var(--primary)"/>'
    '<path d="M5 37L18 14l8 12 5-7 12 18z" fill="#fff" opacity=".95"/>'
    '<path d="M18 14l-4.5 8 3 2 2-2 2.5 2 2.5-2z" fill="var(--primary-soft)"/><circle cx="36" cy="12" r="3" fill="var(--accent)"/>'
    '<path d="M18 14V5M15.5 8h5M16.5 10.5h3" stroke="#fff" stroke-width="1.8" stroke-linecap="round" fill="none"/>'
    '<circle cx="18" cy="4.5" r="1.4" fill="var(--accent)"/></svg>'
)
RIDGE: Final = (
    '<svg class="ridge" viewBox="0 0 1200 200" preserveAspectRatio="none" aria-hidden="true" focusable="false">'
    '<path class="r1" d="M0 200V110l90-40 70 30 110-70 80 60 90-50 100 80 120-90 80 70 110-60 90 50 120-70 140 90V200z"/>'
    '<path class="r2" d="M0 200V140l120-60 60 40 130-80 90 70 110-40 130 70 100-60 120 50 100-50 140 60 100-40V200z"/>'
    '<path class="r3" d="M0 200V170l150-50 80 30 120-70 100 60 140-30 130 40 120-60 90 50 130-30 140 50V200z"/></svg>'
)
GOOGLE_MARK: Final = (
    '<svg class="ico plain" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
    '<path fill="#4285F4" d="M22.5 12.2c0-.8-.1-1.5-.2-2.2H12v4.3h5.9a5 5 0 01-2.2 3.3v2.7h3.5c2.1-1.9 3.3-4.7 3.3-8.1z"/>'
    '<path fill="#34A853" d="M12 23c3 0 5.5-1 7.3-2.7l-3.5-2.7c-1 .7-2.2 1-3.8 1-2.9 0-5.4-2-6.3-4.6H2.100v2.800A11 11 0 0012 23z"/>'
    '<path fill="#FBBC05" d="M5.700 14.100a6.600 6.600 0 010-4.200V7.100H2.100a11 11 0 000 9.800z"/>'
    '<path fill="#EA4335" d="M12 5.400c1.600 0 3.100.6 4.200 1.700l3.100-3.100A11 11 0 002.100 7.100l3.600 2.800C6.600 7.400 9.100 5.400 12 5.400z"/></svg>'
)


def document(title: str, body: str) -> bytes:
    """A whole page: the theme script first (it sets the theme before the first paint), the design system's styles,
    and the library script, deferred. ``title`` and ``body`` are already escaped."""
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f"<title>{title}</title>"
        f'<script src="{THEME_SCRIPT_PATH}"></script>'
        f'<link rel="stylesheet" href="{STYLESHEET_PATH}"><script src="{SCRIPT_PATH}" defer></script></head>'
        f"<body>{body}</body></html>"
    ).encode()
