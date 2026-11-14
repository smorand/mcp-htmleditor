"""Charter rules L007 to L011 (SPEC-0007 FR-NEW-014, DEC-006, DEC-008; SPEC-0023 FR-NEW-011 to FR-NEW-013).

Foreign classes, flex rows and source lines (medical and Breathe), remote images and palette warnings for one
slide (or one scope for the images). The class tables and the palettes of the four presentation charters live
here and nowhere else. Rules are plain functions held in a table keyed by code; no printing.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from bs4.element import Tag

ERROR = "error"
WARNING = "warning"
MEDICAL = "medical"
BREATHE = "breathe"
FOREIGN_CLASSES: dict[str, tuple[tuple[str, ...], frozenset[str]]] = {
    MEDICAL: (
        ("cds-", "tag-", "stat-", "ei-"),
        frozenset({"slide-inner", "slide-header", "slide-footer", "slide-foot", "slide-foot-logo", "slide-foot-title"}),
    ),
    # Breathe shares the med- prefix with medical (SPEC-0023 DEC-004): the medical structure is named instead.
    BREATHE: (
        ("cds-", "tag-", "stat-", "ei-"),
        frozenset(
            {
                "slide-inner",
                "slide-header",
                "slide-footer",
                "slide-foot",
                "slide-foot-logo",
                "slide-foot-title",
                "med-band",
                "med-rule",
                "med-head",
                "med-foot",
                "slide-body",
                "slide-h1",
                "slide-eyebrow",
            }
        ),
    ),
    "ei": (("med-", "stat-", "cw-", "mention-"), frozenset({"slide-header", "slide-footer"})),
    "carbon": (
        ("med-",),
        frozenset(
            {"slide-inner", "slide-foot", "slide-foot-logo", "slide-foot-title", "slide-foot-page", "slide-title-rule"}
        ),
    ),
}
FLEX_ROWS = (
    "med-strip",
    "med-split",
    "med-cols",
    "med-compare",
    "med-steps",
    "med-stats",
    "med-timeline",
    "med-section-figs",
)
# Rows checked by L008 per charter: Breathe adds its full bleed panes, deep figures and priority rows.
CHARTER_FLEX_ROWS: dict[str, tuple[str, ...]] = {
    MEDICAL: FLEX_ROWS,
    BREATHE: ("med-bleed", "med-figs-deep", "med-prio-row", *FLEX_ROWS),
}
WIDTH_CLASSES = frozenset({"w-25", "w-30", "w-33", "w-40", "w-50", "w-60", "w-70"})
NO_SOURCE_TYPES = frozenset({"title", "thanks"})
SOURCE_CHARTERS = frozenset({MEDICAL, BREATHE})  # L009: every picture of these charters cites its source
PALETTES: dict[str, frozenset[str]] = {
    "ei": frozenset(["#003A8D", "#284AAA", "#285C99", "#FBAE40", "#EC6962", "#50565B", "#262626", "#F4F6F9"]),
    "carbon": frozenset(
        ["#0F62FE", "#0043CE", "#EDF5FF", "#161616", "#F4F4F4", "#E0E0E0", "#525252", "#198038", "#DA1E28"]
    ),
    MEDICAL: frozenset(
        [
            "#159984",
            "#0F6F60",
            "#EE5A02",
            "#E9EDEE",
            "#F5F7F8",
            "#D7DEE2",
            "#252525",
            "#3A3A3A",
            "#5D5D5D",
            "#3D85C6",
            "#C81E3A",
            "#0F2E4C",
            "#0B0E11",
            "#14181D",
            "#2A323B",
            "#E8EDF2",
            "#9AA7B4",
            "#4FC3D9",
            "#F2A33C",
        ]
    ),
    BREATHE: frozenset(
        [
            "#0C7B70",
            "#1D8379",
            "#194757",
            "#0E2B35",
            "#E7F7FF",
            "#F3FDFF",
            "#A2EAF7",
            "#83BBB5",
            "#58A19A",
            "#CD8684",
            "#2F4C56",
            "#587480",
            "#9FC4CF",
            "#CFE3EA",
        ]
    ),
}
HEX_COLOUR = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")
# url(...) and comments hold no colour of the element: a fragment id or a data URI is not one
NOT_COLOUR = re.compile(r"url\(\s*(?:'[^']*'|\"[^\"]*\"|[^)]*)\)|/\*.*?\*/", re.IGNORECASE | re.DOTALL)
FULL_HEX = 6
REMOTE_SCHEMES = ("http://", "https://")

SlideRule = Callable[[Tag, str], list[str]]


def foreign_class_problems(slide: Tag, charter: str) -> list[tuple[str, str]]:
    """L007: one ``(code, message)`` per distinct foreign class of ``slide``, in first occurrence order."""
    prefixes, names = FOREIGN_CLASSES.get(charter, ((), frozenset()))
    found = dict.fromkeys(c for c in _classes(slide) if c.startswith(prefixes) or c in names)
    return [("L007", f'class "{name}" belongs to another charter than {charter}') for name in found]


def charter_problems(slide: Tag, charter: str) -> list[tuple[str, str, str]]:
    """Return ``(code, severity, message)`` of L007 to L009 and L011 for ``slide`` (L010 is per image)."""
    if charter not in PALETTES:
        return []
    found = [(code, ERROR, message) for code, message in foreign_class_problems(slide, charter)]
    for code, (severity, rule) in SLIDE_RULES.items():
        found.extend((code, severity, message) for message in rule(slide, charter))
    return found


def remote_image_problems(scope: Tag) -> list[str]:
    """L010: one message per remote ``img`` inside ``scope``, in document order."""
    return [message for image in scope.find_all("img") if (message := remote_image_message(image))]


def remote_image_message(image: Tag) -> str | None:
    """Return the L010 message of ``image``, or ``None`` when its ``src`` is not an ``http(s)://`` url."""
    source = str(image.get("src") or "").strip()
    return f"remote image {source} is not exported" if source.lower().startswith(REMOTE_SCHEMES) else None


def _elements(slide: Tag) -> list[Tag]:
    return [slide, *slide.find_all(True)]


def _classes(slide: Tag) -> list[str]:
    return [name for element in _elements(slide) for name in element.get("class") or []]


def _width_problems(slide: Tag, charter: str) -> list[str]:
    """L008."""
    rows = CHARTER_FLEX_ROWS.get(charter)
    if rows is None:
        return []
    return [
        f"child of .{row} has no w-* width class"
        for element, row in _flex_rows(slide, rows)
        for child in element.find_all(True, recursive=False)
        if not WIDTH_CLASSES.intersection(child.get("class") or [])
    ]


def _flex_rows(slide: Tag, names: tuple[str, ...]) -> list[tuple[Tag, str]]:
    rows = []
    for element in _elements(slide):
        row = next((c for c in element.get("class") or [] if c in names), None)
        if row:
            rows.append((element, row))
    return rows


def _source_problems(slide: Tag, charter: str) -> list[str]:
    """L009."""
    if charter not in SOURCE_CHARTERS or slide.get("data-slide-type") in NO_SOURCE_TYPES or slide.find("img") is None:
        return []
    has_source = any(source.get_text().strip() for source in slide.select(".med-source"))
    return [] if has_source else ["slide has an image and no source line"]


def _palette_problems(slide: Tag, charter: str) -> list[str]:
    """L011: one per distinct colour (letter case and 3 digit form ignored), shown as first written."""
    found: dict[str, str] = {}
    for element in _elements(slide):
        style = NOT_COLOUR.sub("", str(element.get("style") or ""))
        for written in HEX_COLOUR.findall(style):
            found.setdefault(_expand(written), written)
    allowed = PALETTES[charter]
    return [
        f"colour {written} is not in the {charter} palette"
        for key, written in found.items()
        if not _is_accepted(key, allowed)
    ]


def _expand(colour: str) -> str:
    digits = colour[1:].upper()
    return "#" + (digits if len(digits) == FULL_HEX else "".join(d * 2 for d in digits))


def _is_accepted(colour: str, palette: frozenset[str]) -> bool:
    red, green, blue = colour[1:3], colour[3:5], colour[5:7]
    return colour in palette or red == green == blue


SLIDE_RULES: dict[str, tuple[str, SlideRule]] = {
    "L008": (ERROR, _width_problems),
    "L009": (ERROR, _source_problems),
    "L011": (WARNING, _palette_problems),
}
