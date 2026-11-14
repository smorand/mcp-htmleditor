"""Pure CSS to PPTX mappings of the painted export (SPEC-0024 FR-2, FR-3, FR-4): no I/O, no browser, no charter.

Radius to a preset shape, linear gradient and box shadow parsing, ``object-fit`` crop, list marker mapping, colour and
face helpers. Every function takes values as the browser reports them (computed styles) and returns plain data.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from pptx.dml.color import RGBColor

Colour = Sequence[float]
Box = Sequence[float]

FACES: Final = {
    "serif": "Georgia",
    "sans-serif": "Trebuchet MS",
    "cursive": "Brush Script MT",
    "monospace": "Courier New",
}
SYSTEM_FACES: Final = frozenset({"-apple-system", "blinkmacsystemfont"})
OPAQUE: Final = 1
CSS_TOP_TO_OOXML: Final = 90  # CSS 0deg points up, OOXML 0 points right, both clockwise
HALF: Final = 0.5
FULL_ANGLE: Final = 360
DEFAULT_ANGLE: Final = 180
EMU_PER_POINT: Final = 12700
OOXML_PERCENT: Final = 100000
SIDE_ANGLES: Final = {"top": 0, "right": 90, "bottom": 180, "left": 270}
CORNER_ANGLES: Final = {
    frozenset({"top", "right"}): 45,
    frozenset({"bottom", "right"}): 135,
    frozenset({"bottom", "left"}): 225,
    frozenset({"top", "left"}): 315,
}
NUMBER: Final = re.compile(r"-?\d+(?:\.\d+)?")
COLOUR_TOKEN: Final = re.compile(r"rgba?\([^)]*\)")


@dataclass(frozen=True, slots=True)
class Gradient:
    """A linear gradient: OOXML angle (degrees, clockwise from the right) and stops (position 0..1, rgba)."""

    angle: float
    stops: tuple[tuple[float, tuple[float, float, float, float]], ...]


@dataclass(frozen=True, slots=True)
class Shadow:
    """A simple outer shadow in points: offset, blur, and the rgba colour."""

    dx: float
    dy: float
    blur: float
    colour: tuple[float, float, float, float]

    @property
    def distance(self) -> float:
        return math.hypot(self.dx, self.dy)

    @property
    def direction(self) -> float:
        """OOXML direction: degrees clockwise from the right (0 when there is no offset)."""
        return math.degrees(math.atan2(self.dy, self.dx)) % FULL_ANGLE if self.distance else 0.0


@dataclass(frozen=True, slots=True)
class Bullet:
    """A paragraph marker: a literal character, or an automatic number scheme."""

    char: str | None
    numbering: str | None


def to_emu(box: Box) -> tuple[int, int, int, int]:
    """A box in points as EMU (x, y, width, height), the size at least 1 so a hairline survives."""
    x, y, w, h = box
    return (
        round(x * EMU_PER_POINT),
        round(y * EMU_PER_POINT),
        max(round(w * EMU_PER_POINT), 1),
        max(round(h * EMU_PER_POINT), 1),
    )


def rgb(colour: Colour) -> RGBColor:
    """The ``RGBColor`` of the first three channels, clamped to 0..255."""
    return RGBColor(*(max(0, min(255, round(v))) for v in colour[:3]))


def alpha_of(colour: Colour | None, opacity: float = 1.0) -> float:
    """The effective alpha of an rgba colour times the element opacity, 0..1."""
    base = colour[3] if colour is not None and len(colour) > 3 else 1.0
    return max(0.0, min(1.0, base * opacity))


def first_face(family: str) -> str:
    """The first usable face of a CSS ``font-family`` list: system aliases skipped, generic families mapped."""
    for part in family.split(","):
        face = part.strip().strip("'\"")
        if face and face.casefold() not in SYSTEM_FACES:
            return FACES.get(face, face)
    return "Arial"


def parse_colour(text: str) -> tuple[float, float, float, float] | None:
    """An ``rgb()`` or ``rgba()`` token as four numbers (alpha 1 when absent); None when it is not one."""
    match = COLOUR_TOKEN.search(text)
    if match is None:
        return None
    numbers = [float(n) for n in NUMBER.findall(match.group(0))]
    if len(numbers) < 3:
        return None
    alpha = numbers[3] if len(numbers) > 3 else 1.0
    return (numbers[0], numbers[1], numbers[2], alpha)


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current = ""
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        parts.append(current.strip())
    return parts


def _gradient_angle(first: str) -> float | None:
    """The CSS angle of the first argument, None when it is not a direction (it is then a colour stop)."""
    text = first.strip()
    if text.endswith("deg"):
        return float(text[:-3])
    if text.startswith("to "):
        sides = text[3:].split()
        angles = [SIDE_ANGLES[s] for s in sides if s in SIDE_ANGLES]
        if len(angles) == 1:
            return float(angles[0])
        corner = CORNER_ANGLES.get(frozenset(sides))
        if corner is not None:
            return float(corner)
    return None


def parse_gradient(css: str | None) -> Gradient | None:
    """The first ``linear-gradient(...)`` of a computed ``background-image``; None when absent or unsupported."""
    if not css or "linear-gradient(" not in css:
        return None
    start = css.index("linear-gradient(") + len("linear-gradient(")
    depth = 1
    end = start
    while end < len(css) and depth:
        depth += {"(": 1, ")": -1}.get(css[end], 0)
        end += 1
    arguments = _split_top_level(css[start : end - 1])
    angle = _gradient_angle(arguments[0]) if arguments else None
    stops_text = arguments[1:] if angle is not None else arguments
    colours = [parse_colour(arg) for arg in stops_text]
    if len(stops_text) < 2 or any(c is None for c in colours):
        return None
    positions = [_stop_position(arg) for arg in stops_text]
    filled = _fill_positions(positions)
    css_angle = DEFAULT_ANGLE if angle is None else angle
    stops = tuple((pos, colour) for pos, colour in zip(filled, colours, strict=True) if colour is not None)
    return Gradient((css_angle - CSS_TOP_TO_OOXML) % FULL_ANGLE, stops)


def _stop_position(argument: str) -> float | None:
    rest = COLOUR_TOKEN.sub("", argument)
    match = re.search(r"(-?\d+(?:\.\d+)?)%", rest)
    return float(match.group(1)) / 100 if match else None


def _fill_positions(positions: list[float | None]) -> list[float]:
    """Stops without a position are spread evenly between their neighbours (first 0, last 1)."""
    result = list(positions)
    result[0] = 0.0 if result[0] is None else result[0]
    result[-1] = 1.0 if result[-1] is None else result[-1]
    index = 0
    while index < len(result):
        if result[index] is not None:
            index += 1
            continue
        low = index - 1
        high = index
        while result[high] is None:
            high += 1
        for offset in range(index, high):
            result[offset] = (result[low] or 0.0) + ((result[high] or 1.0) - (result[low] or 0.0)) * (
                (offset - low) / (high - low)
            )
        index = high
    return [float(v) for v in result if v is not None]


def parse_shadow(css: str | None) -> Shadow | None:
    """The first outer ``box-shadow`` as a :class:`Shadow`; None for none, inset, spread or an unreadable value."""
    if not css or css == "none" or "inset" in css:
        return None
    first = _split_top_level(css)[0]
    colour = parse_colour(first)
    if colour is None or colour[3] == 0:
        return None
    lengths = [float(n) for n in NUMBER.findall(COLOUR_TOKEN.sub("", first))]
    if len(lengths) < 2:
        return None
    spread = lengths[3] if len(lengths) > 3 else 0.0
    if spread:
        return None
    return Shadow(lengths[0], lengths[1], lengths[2] if len(lengths) > 2 else 0.0, colour)


def shape_for_radii(radii: Sequence[float], width: float, height: float) -> tuple[str, tuple[float, ...]]:
    """Preset for four corner radii (tl, tr, br, bl) in points: ``rect``, ``ellipse``, ``round`` or ``round_top``.

    The adjustments are the PowerPoint ones: the radius as a share of the shorter side (at most 0.5).
    """
    short = max(min(width, height), 1.0)
    top_left, top_right, bottom_right, bottom_left = (max(r, 0.0) for r in radii)
    if max(top_left, top_right, bottom_right, bottom_left) <= HALF:
        return "rect", ()
    if min(top_left, top_right, bottom_right, bottom_left) >= short / 2 - HALF and abs(width - height) <= max(
        1.0, short * 0.02
    ):
        return "ellipse", ()
    if top_left == bottom_left and top_right == bottom_right and top_left == top_right:
        return "round", (min(top_left / short, HALF),)
    if top_left == top_right and bottom_left == bottom_right:
        return "round_top", (min(top_left / short, HALF), min(bottom_left / short, HALF))
    return "round", (min(max(radii) / short, HALF),)


def parse_position(position: str | None) -> tuple[float, float]:
    """``object-position`` or ``background-position`` as fractions of the free space (default 50 % 50 %)."""
    if not position:
        return (HALF, HALF)
    values: list[float] = []
    for token in position.split()[:2]:
        if token.endswith("%"):
            values.append(float(token[:-1]) / 100)
        else:
            values.append({"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 1.0}.get(token, HALF))
    while len(values) < 2:
        values.append(HALF)
    return (values[0], values[1])


def fit_picture(
    fit: str, box: Box, natural: Sequence[int] | None, position: str | None = None
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """The drawn box and the crop (left, top, right, bottom shares) of a picture put in ``box``.

    ``cover`` crops the picture to fill the box; ``contain`` and ``scale-down`` shrink the box to the picture ratio;
    anything else (``fill``, unknown natural size) stretches it like the browser does.
    """
    x, y, width, height = box
    stretch = ((x, y, width, height), (0.0, 0.0, 0.0, 0.0))
    if not natural or not natural[0] or not natural[1] or width <= 0 or height <= 0:
        return stretch
    fx, fy = parse_position(position)
    box_ratio = width / height
    image_ratio = natural[0] / natural[1]
    if fit == "cover":
        if image_ratio > box_ratio:
            slack = 1 - box_ratio / image_ratio
            return (x, y, width, height), (slack * fx, 0.0, slack * (1 - fx), 0.0)
        slack = 1 - image_ratio / box_ratio
        return (x, y, width, height), (0.0, slack * fy, 0.0, slack * (1 - fy))
    if fit in {"contain", "scale-down"}:
        if image_ratio > box_ratio:
            drawn = width / image_ratio
            return (x, y + (height - drawn) * fy, width, drawn), (0.0, 0.0, 0.0, 0.0)
        drawn = height * image_ratio
        return (x + (width - drawn) * fx, y, drawn, height), (0.0, 0.0, 0.0, 0.0)
    return stretch


ROMAN: Final = {"upper-roman": "romanUcPeriod", "lower-roman": "romanLcPeriod"}
NUMBERING: Final = {
    "decimal": "arabicPeriod",
    "decimal-leading-zero": "arabicPeriod",
    "lower-alpha": "alphaLcPeriod",
    "lower-latin": "alphaLcPeriod",
    "upper-alpha": "alphaUcPeriod",
    "upper-latin": "alphaUcPeriod",
    **ROMAN,
}
CHARS: Final = {"disc": "\u2022", "circle": "\u25e6", "square": "\u25aa"}


def bullet_for(list_style_type: str) -> Bullet:
    """The paragraph marker of a computed ``list-style-type`` (a quoted string marker keeps its text)."""
    kind = list_style_type.strip()
    if kind in NUMBERING:
        return Bullet(None, NUMBERING[kind])
    if kind[:1] in {'"', "'"} and len(kind) > 2:
        return Bullet(kind[1:-1].strip() or "\u2022", None)
    return Bullet(CHARS.get(kind, "\u2022"), None)


def hanging_indent(size: float) -> float:
    """The marker column of a list item in points: the space the browser leaves outside the text."""
    return max(round(size * 1.35, 1), 10.0)


def table_span(cell: dict[str, int]) -> tuple[int, int, int, int]:
    """First and last row and column (inclusive) of a measured table cell."""
    return (cell["r"], cell["c"], cell["r"] + cell["rs"] - 1, cell["c"] + cell["cs"] - 1)


def line_dash(style: str | None) -> str | None:
    """The OOXML preset dash of a CSS border style; None for a solid line."""
    return {"dashed": "dash", "dotted": "sysDot"}.get(style or "")
