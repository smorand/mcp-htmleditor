"""Geometry, CSS parsing and theme helpers for the HTML to PPTX exporter.

The exporter models a slide as the 960x540 CSS pixel canvas used by every
mcp-htmleditor slide template, mapped onto a 16:9 PowerPoint slide of
13.333 x 7.5 inches. One CSS pixel is therefore exactly 1/72 inch, so a CSS
``font-size`` in pixels converts to the same number of points.

This module holds everything that does not touch python-pptx shapes:

* :class:`Box`, an inches rectangle with percentage and inset arithmetic;
* CSS helpers (inline style parsing, lengths, colors, custom properties);
* :class:`Theme`, the per-template color and font charter;
* :class:`TextStyle` plus the class driven typographic scale of both templates.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace

from bs4 import BeautifulSoup, Tag
from pptx.util import Emu, Inches

# ---------------------------------------------------------------------------
# Canvas geometry
# ---------------------------------------------------------------------------

SLIDE_W_IN = 13.333
"""Slide width in inches (16:9, matching the templates aspect-ratio)."""

SLIDE_H_IN = 7.5
"""Slide height in inches."""

CANVAS_W_PX = 960.0
"""Reference slide width in CSS pixels (``max-width`` of the templates)."""

CANVAS_H_PX = 540.0
"""Reference slide height in CSS pixels."""

PX_IN = SLIDE_W_IN / CANVAS_W_PX
"""Inches per CSS pixel of the reference canvas (1/72 in, i.e. one point)."""


@dataclass(frozen=True)
class Box:
    """An axis aligned rectangle expressed in inches on the slide canvas."""

    left: float
    top: float
    width: float
    height: float

    @classmethod
    def slide(cls) -> Box:
        """Return the full slide box."""
        return cls(0.0, 0.0, SLIDE_W_IN, SLIDE_H_IN)

    @property
    def right(self) -> float:
        """Right edge, in inches."""
        return self.left + self.width

    @property
    def bottom(self) -> float:
        """Bottom edge, in inches."""
        return self.top + self.height

    def inset(
        self,
        left: float = 0.0,
        top: float = 0.0,
        right: float | None = None,
        bottom: float | None = None,
    ) -> Box:
        """Shrink the box by the given inch margins.

        ``right`` defaults to ``left`` and ``bottom`` defaults to ``top`` so a
        symmetric inset can be written ``box.inset(0.2, 0.1)``.
        """
        right = left if right is None else right
        bottom = top if bottom is None else bottom
        return Box(
            self.left + left,
            self.top + top,
            max(self.width - left - right, 0.01),
            max(self.height - top - bottom, 0.01),
        )

    def inset_px(
        self,
        left: float = 0.0,
        top: float = 0.0,
        right: float | None = None,
        bottom: float | None = None,
    ) -> Box:
        """Same as :meth:`inset` but with CSS pixel margins."""
        right = left if right is None else right
        bottom = top if bottom is None else bottom
        return self.inset(left * PX_IN, top * PX_IN, right * PX_IN, bottom * PX_IN)

    def pct(self, x: float, y: float, w: float, h: float) -> Box:
        """Return the sub-box given by percentages (0-100) of this box."""
        return Box(
            self.left + self.width * x / 100.0,
            self.top + self.height * y / 100.0,
            max(self.width * w / 100.0, 0.01),
            max(self.height * h / 100.0, 0.01),
        )

    def slice_top(self, height: float) -> Box:
        """Return a band of ``height`` inches taken from the top of the box."""
        return Box(self.left, self.top, self.width, min(height, self.height))

    def offset(self, dx: float = 0.0, dy: float = 0.0) -> Box:
        """Return the box translated by ``dx`` / ``dy`` inches."""
        return Box(self.left + dx, self.top + dy, self.width, self.height)

    def resize(self, width: float | None = None, height: float | None = None) -> Box:
        """Return the box with a new width and/or height, same origin."""
        return Box(
            self.left,
            self.top,
            self.width if width is None else max(width, 0.01),
            self.height if height is None else max(height, 0.01),
        )

    def center_horizontally(self, width: float) -> Box:
        """Return a ``width`` wide box horizontally centered in this box."""
        return Box(self.left + (self.width - width) / 2.0, self.top, width, self.height)

    def emu(self) -> tuple[Emu, Emu, Emu, Emu]:
        """Return ``(left, top, width, height)`` as python-pptx EMU values."""
        return (
            Inches(self.left),
            Inches(self.top),
            Inches(self.width),
            Inches(self.height),
        )


# ---------------------------------------------------------------------------
# CSS parsing
# ---------------------------------------------------------------------------

_NUM = r"(-?[\d.]+)"
_PCT_RE = re.compile(rf"{_NUM}\s*%")
_PX_RE = re.compile(rf"{_NUM}\s*px")
_HEX_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
_RGB_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
_VAR_RE = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,([^)]*))?\)")
_CSS_VAR_DECL_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;}]+)")
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

_NAMED_COLORS = {
    "white": "FFFFFF",
    "black": "000000",
    "red": "FF0000",
    "grey": "808080",
    "gray": "808080",
}


def parse_pct(value: str) -> float:
    """Parse a percentage such as ``'12.5%'`` into a float 0-100 (0 if absent)."""
    m = _PCT_RE.search(value or "")
    return float(m.group(1)) if m else 0.0


def parse_px(value: str) -> float:
    """Parse a pixel length such as ``'96px'`` into a float (0 if absent)."""
    m = _PX_RE.search(value or "")
    return float(m.group(1)) if m else 0.0


def parse_length(value: str | None, reference_in: float) -> float | None:
    """Convert a CSS length to inches.

    Percentages resolve against ``reference_in``; pixels use the canvas scale.
    Returns ``None`` when the value is missing or not a supported unit.
    """
    if not value:
        return None
    text = value.strip()
    if _PCT_RE.search(text):
        return parse_pct(text) / 100.0 * reference_in
    if _PX_RE.search(text):
        return parse_px(text) * PX_IN
    return None


def parse_declarations(body: str) -> dict[str, str]:
    """Parse a CSS declaration list (``a: 1; b: 2``) into a dict."""
    props: dict[str, str] = {}
    for part in body.split(";"):
        if ":" in part:
            key, val = part.split(":", 1)
            props[key.strip().lower()] = val.strip()
    return props


def style_props(element: Tag | None) -> dict[str, str]:
    """Return the inline ``style`` declarations of an element as a dict."""
    if element is None:
        return {}
    return parse_declarations(str(element.get("style") or ""))


def stylesheet_text(soup: BeautifulSoup) -> str:
    """Return the concatenated document stylesheets, comments stripped."""
    css = "\n".join(style.get_text() for style in soup.find_all("style"))
    return _COMMENT_RE.sub(" ", css)


def collect_css_vars(soup: BeautifulSoup) -> dict[str, str]:
    """Collect every CSS custom property declared in the document ``<style>``."""
    variables: dict[str, str] = {}
    for name, value in _CSS_VAR_DECL_RE.findall(stylesheet_text(soup)):
        variables.setdefault(name, value.strip())
    return variables


def parse_color(value: str | None, css_vars: dict[str, str] | None = None) -> str | None:
    """Resolve a CSS color to an uppercase ``RRGGBB`` string.

    Supports hex (3 or 6 digits), ``rgb()`` / ``rgba()`` (alpha dropped), a few
    named colors and ``var(--token)`` indirection through ``css_vars``.
    """
    if not value:
        return None
    text = value.strip()
    css_vars = css_vars or {}

    for _ in range(4):  # resolve nested var() a few levels deep
        m = _VAR_RE.search(text)
        if not m:
            break
        token, fallback = m.group(1), (m.group(2) or "").strip()
        text = css_vars.get(token, fallback)
        if not text:
            return None

    m_hex = _HEX_RE.search(text)
    if m_hex:
        digits = m_hex.group(1)
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        return digits.upper()

    m_rgb = _RGB_RE.search(text)
    if m_rgb:
        return "".join(f"{min(int(c), 255):02X}" for c in m_rgb.groups())

    return _NAMED_COLORS.get(text.lower().split()[0] if text.split() else "")


def color_from_props(
    props: dict[str, str],
    keys: tuple[str, ...],
    css_vars: dict[str, str],
) -> str | None:
    """Return the first resolvable color among ``keys`` of a style dict."""
    for key in keys:
        color = parse_color(props.get(key), css_vars)
        if color:
            return color
    return None


def classes(element: Tag | None) -> list[str]:
    """Return the CSS classes of an element as a list of strings."""
    if element is None:
        return []
    raw = element.get("class") or []
    if isinstance(raw, str):
        return raw.split()
    return [str(c) for c in raw]


def has_class(element: Tag | None, *names: str) -> bool:
    """Tell whether the element carries any of the given CSS classes."""
    present = set(classes(element))
    return any(name in present for name in names)


# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Theme:
    """Color and font charter of a slide template."""

    key: str
    font: str
    mono_font: str
    primary: str
    primary_alt: str
    accent: str
    text: str
    secondary: str
    surface: str
    border: str
    table_header_bg: str
    table_header_fg: str
    inverse_text: str = "FFFFFF"

    def color(self, name: str) -> str:
        """Resolve a theme color name, or pass an explicit ``RRGGBB`` through."""
        if re.fullmatch(r"[0-9A-Fa-f]{6}", name):
            return name.upper()
        return str(getattr(self, name, self.text))


THEME_EI = Theme(
    key="ei",
    font="Segoe UI",
    mono_font="Consolas",
    primary="003A8D",
    primary_alt="284AAA",
    accent="FBAE40",
    text="262626",
    secondary="50565B",
    surface="F4F6F9",
    border="D9DEE6",
    table_header_bg="003A8D",
    table_header_fg="FFFFFF",
)

THEME_CARBON = Theme(
    key="carbon",
    font="IBM Plex Sans",
    mono_font="IBM Plex Mono",
    primary="0F62FE",
    primary_alt="0043CE",
    accent="0F62FE",
    text="161616",
    secondary="525252",
    surface="F4F4F4",
    border="E0E0E0",
    table_header_bg="161616",
    table_header_fg="FFFFFF",
)

THEME_GENERIC = Theme(
    key="generic",
    font="Arial",
    mono_font="Courier New",
    primary="1F4E79",
    primary_alt="2E74B5",
    accent="C55A11",
    text="262626",
    secondary="595959",
    surface="F2F2F2",
    border="D0D0D0",
    table_header_bg="1F4E79",
    table_header_fg="FFFFFF",
)


def detect_theme(soup: BeautifulSoup) -> Theme:
    """Pick the charter of a document from its CSS tokens and markup."""
    css = stylesheet_text(soup)
    if "--ei-blue" in css or soup.find(class_="slide-inner") is not None:
        return THEME_EI
    if "--ibm-blue" in css or "--cds-" in css or soup.find(class_="slide-header") is not None:
        return THEME_CARBON
    return THEME_GENERIC


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TextStyle:
    """Resolved character and paragraph style of a run of text."""

    size: float = 12.0
    bold: bool = False
    italic: bool = False
    color: str = "text"
    align: str = "left"
    upper: bool = False
    mono: bool = False
    space_after: float = 2.0
    line_spacing: float = 1.2

    def scaled(self, factor: float) -> TextStyle:
        """Return the same style with the font size multiplied by ``factor``."""
        return replace(self, size=max(self.size * factor, 6.0))


_EI_STYLES: dict[str, TextStyle] = {
    "slide-eyebrow": TextStyle(size=12, bold=True, color="primary_alt", upper=True, space_after=4),
    "slide-h1": TextStyle(size=28, bold=True, color="primary", space_after=4, line_spacing=1.1),
    "slide-subtitle": TextStyle(size=14, color="secondary", space_after=4),
    "slide-cover-title": TextStyle(size=30, bold=True, color="primary", align="center", line_spacing=1.15),
    "slide-cover-subtitle": TextStyle(size=15, color="secondary", align="center"),
    "slide-section-num": TextStyle(size=16, bold=True, color="accent", upper=True, space_after=8),
    "slide-section-title": TextStyle(size=40, bold=True, color="inverse_text", line_spacing=1.1, space_after=10),
    "slide-section-sub": TextStyle(size=16, color="C6D0E4"),
    "slide-foot-page": TextStyle(size=12, bold=True, color="primary"),
    "slide-foot-title": TextStyle(size=11, color="285C99", upper=True, align="center"),
    "tile-eyebrow": TextStyle(size=10.5, bold=True, color="primary_alt", upper=True, space_after=2),
    "tile-title": TextStyle(size=14, bold=True, color="primary", space_after=2),
    "notif-title": TextStyle(size=13, bold=True, color="primary", space_after=2),
    "notif-body": TextStyle(size=12, color="secondary"),
    "gantt-label": TextStyle(size=11, color="text", space_after=0),
    "gantt-dates": TextStyle(size=10, color="secondary", align="right", space_after=0),
    "num": TextStyle(size=20, bold=True, color="accent"),
    "agenda-sub": TextStyle(size=11.5, color="secondary"),
    "stat-value": TextStyle(size=30, bold=True, color="primary", space_after=2),
    "stat-label": TextStyle(size=12, color="secondary"),
}

_CARBON_STYLES: dict[str, TextStyle] = {
    "slide-eyebrow": TextStyle(size=12, bold=True, color="primary", upper=True, space_after=4),
    "slide-h1": TextStyle(size=34, color="text", space_after=4, line_spacing=1.15),
    "slide-subtitle": TextStyle(size=15, color="secondary", space_after=4),
    "slide-footer-left": TextStyle(size=11, color="secondary"),
    "slide-footer-right": TextStyle(size=11, color="8D8D8D", align="right"),
    "tile-eyebrow": TextStyle(size=11, bold=True, color="primary", upper=True, space_after=2),
    "tile-title": TextStyle(size=14, bold=True, color="text", space_after=2),
    "stat-value": TextStyle(size=30, color="primary", space_after=2),
    "stat-label": TextStyle(size=12, color="secondary"),
    "notif-title": TextStyle(size=13, bold=True, color="primary_alt", space_after=2),
    "notif-body": TextStyle(size=12, color="secondary"),
    "gantt-label": TextStyle(size=11.5, color="text", space_after=0),
    "gantt-dates": TextStyle(size=10.5, color="secondary", align="right", space_after=0),
    "q": TextStyle(size=11, bold=True, color="secondary", upper=True, align="center", space_after=0),
    "arch-node-label": TextStyle(size=10, color="secondary", space_after=0),
    "num": TextStyle(size=18, bold=True, color="primary"),
    "agenda-sub": TextStyle(size=11.5, color="secondary"),
}

_TAG_STYLES: dict[str, TextStyle] = {
    "h1": TextStyle(size=26, bold=True, color="primary", space_after=4),
    "h2": TextStyle(size=21, bold=True, color="primary", space_after=4),
    "h3": TextStyle(size=15, bold=True, color="text", space_after=3),
    "h4": TextStyle(size=13, bold=True, color="text", space_after=3),
    "h5": TextStyle(size=12, bold=True, color="text", space_after=2),
    "h6": TextStyle(size=11, bold=True, color="text", space_after=2),
    "p": TextStyle(size=12, color="text"),
    "li": TextStyle(size=12, color="text", space_after=1),
    "small": TextStyle(size=9.5, color="secondary", space_after=0),
    "th": TextStyle(size=10.5, bold=True, color="table_header_fg", upper=True, space_after=0),
    "td": TextStyle(size=11, color="text", space_after=0),
    "code": TextStyle(size=10.5, color="primary_alt", mono=True, space_after=0),
    "figcaption": TextStyle(size=10, italic=True, color="secondary"),
}

_CLASS_STYLES: dict[str, dict[str, TextStyle]] = {
    "ei": _EI_STYLES,
    "carbon": _CARBON_STYLES,
    "generic": {},
}

_ALIGN_VALUES = {"left", "center", "right", "justify"}


_SELECTOR_REJECT = re.compile(r"[\[\]:>+~*@]")
_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _selector_classes(selector: str) -> list[str]:
    """Return the class targeted by the last compound of a CSS selector.

    Ancestor constraints are dropped on purpose: ``.card .name`` is indexed as
    ``name``. The exporter only needs colors and typography, and slide
    documents are small and internally consistent, so this approximation is
    much cheaper than a real cascade. Ignored selectors: pseudo classes,
    attribute filters, combinators, at-rules, and multi-class compounds such as
    ``.notification.error`` whose declarations must not leak onto either class.
    """
    text = selector.strip()
    if not text or _SELECTOR_REJECT.search(text):
        return []
    last = text.split()[-1]
    parts = [part for part in last.split(".")[1:] if part]
    return parts if len(parts) == 1 else []


@dataclass
class StyleResolver:
    """Resolve colors and text styles of an element for a given document.

    Declarations are merged in cascade order: CSS rules keyed by class, then
    the inline ``style`` attribute.
    """

    theme: Theme
    css_vars: dict[str, str]
    class_props: dict[str, dict[str, str]]

    @classmethod
    def from_soup(cls, soup: BeautifulSoup) -> StyleResolver:
        """Build a resolver from the ``<style>`` blocks of a document."""
        class_props: dict[str, dict[str, str]] = {}
        for selectors, body in _RULE_RE.findall(stylesheet_text(soup)):
            props = parse_declarations(body)
            if not props:
                continue
            for selector in selectors.split(","):
                for name in _selector_classes(selector):
                    class_props.setdefault(name, {}).update(props)
        return cls(detect_theme(soup), collect_css_vars(soup), class_props)

    def props(self, element: Tag) -> dict[str, str]:
        """Return the declarations that apply to an element."""
        merged: dict[str, str] = {}
        for name in classes(element):
            merged.update(self.class_props.get(name, {}))
        merged.update(style_props(element))
        return merged

    def color(self, element: Tag, keys: tuple[str, ...]) -> str | None:
        """Return the first resolvable color among ``keys`` for an element."""
        return color_from_props(self.props(element), keys, self.css_vars)

    def style(self, element: Tag, inherited: TextStyle | None = None) -> TextStyle:
        """Resolve the text style of an element.

        Priority: curated class scale of the template, then tag defaults, then
        the inherited style; CSS and inline declarations are overlaid last.
        """
        table = _CLASS_STYLES.get(self.theme.key, {})
        style: TextStyle | None = None
        for name in classes(element):
            if name in table:
                style = table[name]
                break
        if style is None and element.name in _TAG_STYLES:
            style = _TAG_STYLES[element.name]
        if style is None:
            style = inherited if inherited is not None else TextStyle()
        return self.apply(style, self.props(element))

    def apply(self, style: TextStyle, props: dict[str, str]) -> TextStyle:
        """Overlay CSS declarations (size, weight, color, alignment) on a style."""
        if not props:
            return style
        updates: dict[str, object] = {}
        size = props.get("font-size")
        if size and _PX_RE.search(size):
            updates["size"] = parse_px(size)
        weight = props.get("font-weight", "")
        if weight in {"bold", "600", "700", "800", "900"}:
            updates["bold"] = True
        elif weight in {"300", "400", "normal"}:
            updates["bold"] = False
        align = props.get("text-align", "").strip()
        if align in _ALIGN_VALUES:
            updates["align"] = align
        if props.get("text-transform", "").strip() == "uppercase":
            updates["upper"] = True
        color = parse_color(props.get("color"), self.css_vars)
        if color:
            updates["color"] = color
        if props.get("font-style", "").strip() == "italic":
            updates["italic"] = True
        return replace(style, **updates)  # type: ignore[arg-type]  # keys match fields


def estimate_lines(text: str, style: TextStyle, width_in: float) -> int:
    """Estimate how many lines ``text`` needs at ``style`` inside ``width_in``."""
    if not text.strip():
        return 1
    width_pt = max(width_in * 72.0, 12.0)
    chars_per_line = max(width_pt / (style.size * 0.5), 6.0)
    lines = 0
    for hard_line in text.split("\n"):
        lines += max(1, math.ceil(len(hard_line) / chars_per_line))
    return lines


def block_height(text: str, style: TextStyle, width_in: float) -> float:
    """Estimate the height in inches taken by ``text`` rendered at ``style``."""
    lines = estimate_lines(text, style, width_in)
    return (lines * style.size * style.line_spacing + style.space_after) / 72.0
