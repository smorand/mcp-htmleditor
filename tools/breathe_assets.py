#!/usr/bin/env python3
"""Breathe decoration catalogue generator: circled line icons, slide backgrounds, logo disc, samples (SPEC-0023).

Usage (make is the entry point):
    make breathe-assets                         # redraw everything into templates/assets/breathe
    make breathe-assets ARGS=--list             # print the catalogue, write nothing
    make breathe-assets ARGS="--out DIR"        # write into DIR
    make breathe-assets ARGS="--src DIR"        # read the three source pictures from DIR
    make breathe-assets ARGS="--only bg-white-s0.png,icon-scope-now.png"   # a subset, by output name

Everything is drawn at 4x the 2x target and reduced with LANCZOS, so every PNG is crisp at 2x on the 960 x 540
canvas. The backgrounds carry the whole decoration (split panels, ice facets, airway line, station markers,
divider tracker line, watermark): a Breathe deck shows them as the CSS background of the <article> (class
med-bg-<preset>-s<N>) and the PPTX export paints the same PNG behind the slide. Geometry shared with the CSS of
templates/reference/slides/breathe.html: rail at y=34, stations at x=190/397/603/810, divider tracker at y=420,
outline tracker at y=300, panes listed in PRESETS.

Add an icon: write a glyph_<name>(pen, colour, width) function drawing in a 100 x 100 box (disc radius 46 around
50,50; keep the glyph inside 22..78), add it to GLYPHS, run the generator, use class med-ico-<name>-<variant>.
Ported from ~/projects/lamya/presentations/_template/breathe/tools/breathe_assets.py (2026-11-13).
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[1]
CATALOGUE = REPO / "templates" / "assets" / "breathe"
SS = 4  # supersampling over the 2x target
X2 = 2  # target pixels per CSS pixel

WATERMARK_SOURCE = "filigrane-stethoscope-poumons.png"
LOGO_SOURCE = "logo-2026-botanical-transparent.png"
PARTNER_SOURCE = "wiip-strong-logo.png"
SOURCES = (WATERMARK_SOURCE, LOGO_SOURCE, PARTNER_SOURCE)

Colour = tuple[int, ...]
Point = tuple[float, float]

# Cabinet palette (email signature 2024).
ICE = (231, 247, 255)
AQUA = (162, 234, 247)
NAVY = (25, 71, 87)
NAVY_DEEP = (14, 43, 53)
TEAL = (12, 123, 112)
TINT = (131, 187, 181)
WHITE = (255, 255, 255)

RAIL_Y = 34
STATIONS = [190, 397, 603, 810]
DIVIDER_BAND = 318
DIVIDER_Y = 420
OUTLINE_Y = 300


# -- drawing -------------------------------------------------------------------------------------------------


class Pen:
    """Draws in logical units onto a supersampled RGBA canvas."""

    def __init__(self, width: float, height: float, unit: float, background: Colour = (0, 0, 0, 0)) -> None:
        self.unit = unit
        self.image = Image.new("RGBA", (round(width * unit), round(height * unit)), background)
        self.draw = ImageDraw.Draw(self.image)

    def p(self, x: float, y: float) -> Point:
        return (x * self.unit, y * self.unit)

    def line(self, points: Sequence[Point], color: Colour, width: float, caps: bool = True) -> None:
        pts = [self.p(x, y) for x, y in points]
        w = max(1, round(width * self.unit))
        self.draw.line(pts, fill=color, width=w, joint="curve")
        if caps:
            for x, y in (pts[0], pts[-1]):
                r = w / 2
                self.draw.ellipse((x - r, y - r, x + r, y + r), fill=color)

    def circle(
        self,
        cx: float,
        cy: float,
        r: float,
        fill: Colour | None = None,
        outline: Colour | None = None,
        width: float = 0,
    ) -> None:
        x, y = self.p(cx, cy)
        rr = r * self.unit
        self.draw.ellipse(
            (x - rr, y - rr, x + rr, y + rr), fill=fill, outline=outline, width=max(0, round(width * self.unit))
        )

    def polygon(self, points: Sequence[Point], fill: Colour) -> None:
        self.draw.polygon([self.p(x, y) for x, y in points], fill=fill)

    def rect(
        self,
        box: tuple[float, float, float, float],
        fill: Colour | None = None,
        outline: Colour | None = None,
        width: float = 0,
        radius: float = 0,
    ) -> None:
        x0, y0 = self.p(box[0], box[1])
        x1, y1 = self.p(box[2], box[3])
        self.draw.rounded_rectangle(
            (x0, y0, x1, y1),
            radius=radius * self.unit,
            fill=fill,
            outline=outline,
            width=max(0, round(width * self.unit)),
        )


def bezier(p0: Point, p1: Point, p2: Point, p3: Point, steps: int = 40) -> list[Point]:
    out = []
    for i in range(steps + 1):
        t = i / steps
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t**2, t**3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def closed_spline(points: Sequence[Point], steps: int = 16) -> list[Point]:
    out: list[Point] = []
    n = len(points)
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            x, y = (
                0.5
                * (
                    2 * p1[k]
                    + (-p0[k] + p2[k]) * t
                    + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3
                )
                for k in range(2)
            )
            out.append((x, y))
    out.append(out[0])
    return out


def arc_points(
    cx: float, cy: float, rx: float, ry: float, start_deg: float, end_deg: float, steps: int = 40
) -> list[Point]:
    angles = [start_deg + (end_deg - start_deg) * i / steps for i in range(steps + 1)]
    return [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a))) for a in angles]


# -- glyphs: 100 x 100 box, disc radius 46 around (50, 50) ---------------------------------------------------


def glyph_lungs(pen: Pen, c: Colour, w: float) -> None:
    pen.line([(50, 22), (50, 44)], c, w)
    pen.line([(50, 44), (43, 51)], c, w)
    pen.line([(50, 44), (57, 51)], c, w)
    left = [(44, 34), (36, 30), (29, 40), (26, 56), (27, 72), (35, 76), (44, 70), (45, 52)]
    pen.line(closed_spline(left), c, w)
    pen.line(closed_spline([(100 - x, y) for x, y in left]), c, w)


def glyph_scope(pen: Pen, c: Colour, w: float) -> None:
    pen.rect((29, 20, 41, 46), outline=c, width=w, radius=4)
    pen.line([(41, 29), (48, 25)], c, w)
    pen.line([(35, 46), (35, 52)], c, w)
    tube = bezier((35, 52), (35, 80), (64, 82), (66, 60), 50)
    tube += bezier((66, 60), (67, 51), (69, 46), (72, 42), 20)[1:]
    pen.line(tube, c, w)
    pen.circle(73, 41, 3.4, fill=c)


def glyph_microscope(pen: Pen, c: Colour, w: float) -> None:
    pen.line([(42, 21), (55, 49)], c, w * 2.1)
    pen.line([(38, 23), (46, 19)], c, w)
    pen.line([(55, 49), (56, 56)], c, w)
    pen.line([(36, 61), (62, 61)], c, w)
    pen.line(bezier((53, 34), (73, 40), (76, 66), (58, 77), 40), c, w)
    pen.line([(28, 78), (72, 78)], c, w)


def glyph_coins(pen: Pen, c: Colour, w: float) -> None:
    pen.line(arc_points(39, 38, 14, 5.5, 0, 360, 60), c, w)
    pen.line([(25, 38), (25, 66)], c, w)
    pen.line([(53, 38), (53, 50)], c, w)
    for y in (47, 56, 66):
        pen.line(arc_points(39, y, 14, 5.5, 0, 180, 30), c, w)
    pen.circle(68, 60, 12, outline=c, width=w)
    pen.circle(68, 60, 6, outline=c, width=w * 0.8)


def glyph_people(pen: Pen, c: Colour, w: float) -> None:
    pen.circle(64, 36, 7, outline=c, width=w)
    pen.line(arc_points(64, 66, 14, 15, 250, 345), c, w)
    pen.circle(43, 40, 9, outline=c, width=w)
    pen.line(arc_points(43, 76, 18, 20, 180, 360), c, w)


def glyph_clock(pen: Pen, c: Colour, w: float) -> None:
    pen.circle(50, 50, 24, outline=c, width=w)
    pen.line([(50, 50), (50, 35)], c, w)
    pen.line([(50, 50), (61, 57)], c, w)
    for a in (0, 90, 180, 270):
        pen.circle(50 + 19 * math.cos(math.radians(a)), 50 + 19 * math.sin(math.radians(a)), 1.6, fill=c)


def glyph_map(pen: Pen, c: Colour, w: float) -> None:
    pen.line([(25, 33), (40, 27), (60, 33), (75, 27), (75, 67), (60, 73), (40, 67), (25, 73), (25, 33)], c, w)
    pen.line([(40, 27), (40, 67)], c, w * 0.8)
    pen.line([(60, 33), (60, 73)], c, w * 0.8)
    for x, y in [(31, 60), (36, 54), (44, 52), (51, 47), (57, 45)]:
        pen.circle(x, y, 1.5, fill=c)
    pen.circle(64, 42, 5, outline=c, width=w * 0.9)


def glyph_cap(pen: Pen, c: Colour, w: float) -> None:
    pen.line([(50, 27), (79, 40), (50, 53), (21, 40), (50, 27)], c, w)
    pen.line([(34, 47), (34, 61), *bezier((34, 61), (40, 69), (60, 69), (66, 61), 30), (66, 47)], c, w)
    pen.line([(76, 41), (76, 60)], c, w * 0.8)
    pen.circle(76, 62, 2.6, fill=c)


def glyph_check(pen: Pen, c: Colour, w: float) -> None:
    pen.line([(31, 51), (44, 64), (70, 36)], c, w)


def glyph_hospital(pen: Pen, c: Colour, w: float) -> None:
    pen.line([(31, 36), (69, 36), (69, 74), (31, 74), (31, 36)], c, w)
    pen.line([(25, 74), (75, 74)], c, w)
    pen.line([(50, 42), (50, 56)], c, w * 1.1)
    pen.line([(43, 49), (57, 49)], c, w * 1.1)
    pen.line([(45, 74), (45, 64), (55, 64), (55, 74)], c, w)
    pen.line([(40, 29), (60, 29)], c, w)


def glyph_mail(pen: Pen, c: Colour, w: float) -> None:
    pen.line([(27, 34), (73, 34), (73, 66), (27, 66), (27, 34)], c, w)
    pen.line([(28, 36), (50, 52), (72, 36)], c, w)


def glyph_pin(pen: Pen, c: Colour, w: float) -> None:
    pen.line([*arc_points(50, 42, 15, 15, 150, 390, 80), (50, 74), arc_points(50, 42, 15, 15, 150, 151, 1)[0]], c, w)
    pen.circle(50, 42, 5.5, outline=c, width=w)


def glyph_search(pen: Pen, c: Colour, w: float) -> None:
    pen.circle(45, 45, 15, outline=c, width=w)
    pen.line([(56, 56), (69, 69)], c, w * 1.45)


def glyph_chart(pen: Pen, c: Colour, w: float) -> None:
    pen.line([(26, 74), (74, 74)], c, w)
    for x, top in ((34, 58), (46, 44), (58, 50), (70, 30)):
        pen.line([(x, 72), (x, top)], c, w * 1.9, caps=False)


def glyph_doc(pen: Pen, c: Colour, w: float) -> None:
    pen.line([(32, 24), (58, 24), (68, 34), (68, 76), (32, 76), (32, 24)], c, w)
    pen.line([(58, 24), (58, 34), (68, 34)], c, w)
    for y in (46, 55, 64):
        pen.line([(40, y), (60, y)], c, w * 0.85)


def glyph_shield(pen: Pen, c: Colour, w: float) -> None:
    outline = [
        (50, 23),
        (72, 31),
        (71, 52),
        *bezier((71, 52), (69, 66), (58, 73), (50, 77), 24),
        *bezier((50, 77), (42, 73), (31, 66), (29, 52), 24)[1:],
        (28, 31),
        (50, 23),
    ]
    pen.line(outline, c, w)
    pen.line([(41, 50), (48, 57), (60, 43)], c, w)


Glyph = Callable[[Pen, Colour, float], None]
GLYPHS: dict[str, Glyph] = {
    "lungs": glyph_lungs,
    "scope": glyph_scope,
    "microscope": glyph_microscope,
    "coins": glyph_coins,
    "people": glyph_people,
    "clock": glyph_clock,
    "map": glyph_map,
    "cap": glyph_cap,
    "check": glyph_check,
    "hospital": glyph_hospital,
    "mail": glyph_mail,
    "pin": glyph_pin,
    "search": glyph_search,
    "chart": glyph_chart,
    "doc": glyph_doc,
    "shield": glyph_shield,
}

# variant: (disc fill, ring, glyph, halo, css size of the disc, css size of the box)
VARIANTS: dict[str, tuple[Colour | None, Colour, Colour, bool, int, int]] = {
    "ring": (WHITE, TEAL, TEAL, False, 52, 52),  # light surfaces
    "solid": (TEAL, TEAL, WHITE, False, 52, 52),
    "dark": (None, AQUA, AQUA, False, 52, 52),  # deep navy surfaces
    "done": (WHITE, TEAL, TEAL, False, 64, 88),  # tracker, stage passed
    "now": (TEAL, TEAL, WHITE, True, 76, 88),  # tracker, current stage
    "todo": (ICE, TINT, TINT, False, 64, 88),  # tracker, stage to come
}


def make_icon(out: Path, name: str, variant: str) -> Path:
    fill, ring, ink, halo, disc, box = VARIANTS[variant]
    unit = SS * X2 * box / 100
    pen = Pen(100, 100, unit)
    scale = disc / box
    per_px = 100 / box
    if halo:
        pen.circle(50, 50, 49, outline=(*TEAL, 110), width=1.4 * per_px)
    if fill:
        pen.circle(50, 50, 46 * scale, fill=(*fill, 255))
    pen.circle(50, 50, 46 * scale - 0.8 * per_px, outline=(*ring, 255), width=1.6 * per_px)
    sub = Pen(100, 100, unit)
    GLYPHS[name](sub, (*ink, 255), 2.1 * 100 / disc)
    gw = round(sub.image.width * scale * 1.04)
    glyph = sub.image.resize((gw, gw), Image.Resampling.LANCZOS)
    off = (pen.image.width - gw) // 2
    pen.image.alpha_composite(glyph, (off, off))
    path = out / f"icon-{name}-{variant}.png"
    pen.image.resize((box * X2, box * X2), Image.Resampling.LANCZOS).save(path, optimize=True)
    return path


# -- airway rail ---------------------------------------------------------------------------------------------

PAINT: dict[str, tuple[Colour, Colour, Colour]] = {  # surface: (done colour, todo colour, fill under hollow markers)
    "white": ((*TEAL, 255), (*TINT, 210), (*WHITE, 255)),
    "ice": ((*TEAL, 255), (*TINT, 210), (*ICE, 255)),
    "navy": ((*AQUA, 255), (*AQUA, 95), (*NAVY, 255)),
    "deep": ((*AQUA, 255), (*AQUA, 85), (*NAVY_DEEP, 255)),
}
SURFACE_RGB = {"white": WHITE, "ice": ICE, "navy": NAVY, "deep": NAVY_DEEP}
Pane = tuple[tuple[float, float, float, float], str]


def surface_at(panes: Sequence[Pane], x: float, y: float) -> str:
    for (x0, y0, x1, y1), kind in reversed(panes):  # later panes are drawn on top
        if x0 <= x < x1 and y0 <= y < y1:
            return kind
    return panes[0][1]


def twig(pen: Pen, x: float, y: float, up: bool, color: Colour, scale: float = 1.0) -> None:
    """One bronchial branch: a tapered stem that splits once, alveolar dots at the tips."""
    sign = -1 if up else 1
    a = math.radians(38)
    l1, l2 = 15 * scale, 8 * scale
    x1, y1 = x + l1 * math.cos(a), y + sign * l1 * math.sin(a)
    pen.line([(x, y), (x1, y1)], color, 1.8 * scale)
    for da in (-0.5, 0.42):
        b = a + da
        x2, y2 = x1 + l2 * math.cos(b), y1 + sign * l2 * math.sin(b)
        pen.line([(x1, y1), (x2, y2)], color, 1.15 * scale)
        pen.circle(x2, y2, 1.7 * scale, fill=color)


def terminal_fan(pen: Pen, x: float, y: float, color: Colour) -> None:
    """End of the airway: three generations of branching, alveolar dots at the tips."""

    def branch(x0: float, y0: float, angle: float, length: float, width: float, depth: int) -> None:
        x1, y1 = x0 + length * math.cos(angle), y0 + length * math.sin(angle)
        pen.line([(x0, y0), (x1, y1)], color, width)
        if depth == 0:
            pen.circle(x1, y1, 2.2, fill=color)
            return
        for da in (-0.42, 0.42):
            branch(x1, y1, angle + da, length * 0.72, width * 0.72, depth - 1)

    for da in (-0.36, 0.36):
        branch(x, y, da, 20, 2.4, 2)


def twigs_between(
    x_from: float, x_to: float, avoid: Sequence[tuple[float, float]], spacing: float = 46, up: bool = True
) -> list[tuple[float, bool]]:
    out, x = [], x_from
    while x < x_to:
        if not any(a <= x <= b for a, b in avoid):
            out.append((x, up))
            up = not up
        x += spacing
    return out


def draw_rail(
    pen: Pen,
    panes: Sequence[Pane],
    y: float,
    current: int,
    *,
    x_from: float = 0,
    x_to: float = 960,
    scale: float = 1.0,
    markers: bool = True,
    label: tuple[float, float] | None = None,
    start: bool = False,
    fan: bool = False,
) -> None:
    """Airway at height y. current: 0 nothing passed, 1..4 the current stage, 5 all passed."""
    progress = {0: x_from + (56 if start else 0)}.get(current, STATIONS[min(current, 4) - 1] if current else 0)
    if current >= 5:
        progress = x_to
    x = x_from
    while x < x_to:
        nx = min(x + 2, x_to)
        done, todo, _ = PAINT[surface_at(panes, x, y)]
        pen.line([(x, y), (nx + 0.5, y)], done if x < progress else todo, 2.6 * scale, caps=False)
        x = nx
    avoid = [(s - 22 * scale, s + 18 * scale) for s in STATIONS] if markers else []
    if markers is False and scale > 1:
        avoid = [(s - 58, s + 50) for s in STATIONS]
    if label:
        avoid.append(label)
    if start:
        avoid.append((x_from - 10, x_from + 30))
    for tx, up in twigs_between(x_from + 20, x_to - (40 if fan else 0), avoid, spacing=46 * min(scale, 1.15)):
        done, todo, _ = PAINT[surface_at(panes, tx, y)]
        twig(pen, tx, y, up, done if tx < progress else todo, scale)
    if markers:
        for i, sx in enumerate(STATIONS, start=1):
            if sx > x_to:
                continue
            done, todo, under = PAINT[surface_at(panes, sx, y)]
            if i == current:
                pen.circle(sx, y, 13, outline=(*done[:3], 90), width=2)
                pen.circle(sx, y, 8, fill=under, outline=done, width=3)
                pen.circle(sx, y, 3.6, fill=done)
            elif i < current:
                pen.circle(sx, y, 5.5, fill=done)
            else:
                pen.circle(sx, y, 5.5, fill=under, outline=todo, width=2)
    if start:
        done, _, _ = PAINT[surface_at(panes, x_from, y)]
        pen.circle(x_from + 56, y, 12, outline=(*done[:3], 90), width=2)
        pen.circle(x_from + 56, y, 6.5, fill=done)
    if fan:
        done, _, _ = PAINT[surface_at(panes, x_to, y)]
        terminal_fan(pen, x_to, y, done)


def facets(pen: Pen, box: tuple[float, float, float, float], flip: bool) -> None:
    """Soft diagonal light facets of the 2024 signature background, clipped to box."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    layer = Pen(960, 540, pen.unit)
    shapes: list[tuple[list[Point], Colour]] = [
        ([(0.0, 0.0), (0.7, 0.0), (0.0, 0.55)], (*WHITE, 70)),
        ([(0.25, 1.0), (1.0, 0.45), (1.0, 1.0)], (*WHITE, 60)),
        ([(0.62, 0.0), (1.0, 0.0), (1.0, 0.3)], (*AQUA, 38)),
        ([(0.0, 0.8), (0.22, 1.0), (0.0, 1.0)], (*AQUA, 34)),
        ([(0.3, 0.0), (0.52, 0.0), (0.0, 0.38)], (*WHITE, 45)),
    ]
    for pts, col in shapes:
        layer.polygon([(x0 + (1 - u if flip else u) * w, y0 + v * h) for u, v in pts], col)
    mask = Image.new("L", layer.image.size, 0)
    ImageDraw.Draw(mask).rectangle([round(v * pen.unit) for v in box], fill=255)
    clipped = Image.new("RGBA", layer.image.size, (0, 0, 0, 0))
    clipped.paste(layer.image, (0, 0), mask)
    pen.image.alpha_composite(clipped)


def watermark(pen: Pen, src: Path, box: tuple[float, float, float, float], opacity: int = 46) -> None:
    """Cabinet emblem (stethoscope + lungs) as a pale aqua watermark, fitted to the height of box.

    The source is opaque and pale on white: the alpha is the distance to white. Never on a slide that also shows
    the botanical logo (two emblems never share a surface).
    """
    image = Image.open(src / WATERMARK_SOURCE).convert("RGB")
    r, g, b = image.split()
    dist = ImageChops.lighter(ImageChops.lighter(ImageChops.invert(r), ImageChops.invert(g)), ImageChops.invert(b))
    alpha = dist.point(lambda v: min(255, v * 8))
    bbox = alpha.point(lambda v: 255 if v > 24 else 0).getbbox()
    alpha = alpha.crop(bbox)
    mark = Image.new("RGBA", alpha.size, (*AQUA, 0))
    mark.putalpha(alpha.point(lambda v: v * opacity // 255))
    x0, y0, _x1, y1 = box
    target_h = (y1 - y0) * pen.unit
    mark = mark.resize((round(mark.width * target_h / mark.height), round(target_h)), Image.Resampling.LANCZOS)
    pen.image.alpha_composite(mark, (round(x0 * pen.unit), round(y0 * pen.unit)))


# -- background presets --------------------------------------------------------------------------------------
# name: panes (box, surface), facet boxes, rail kind
PRESETS: dict[str, tuple[list[Pane], list[tuple[tuple[float, float, float, float], bool]], str]] = {
    "cover": ([((0, 0, 960, 540), "ice"), ((0, 0, 600, 540), "navy")], [((600, 0, 960, 540), True)], "cover"),
    "white": ([((0, 0, 960, 540), "white")], [], "rail"),
    "ice": ([((0, 0, 960, 540), "ice")], [((0, 0, 960, 540), False)], "rail"),
    "deep": ([((0, 0, 960, 540), "navy")], [], "rail"),
    "dark": ([((0, 0, 960, 540), "deep")], [], "rail"),
    "side": ([((0, 0, 960, 540), "ice"), ((0, 0, 300, 540), "navy")], [((300, 0, 960, 540), False)], "rail"),
    "split": ([((0, 0, 960, 540), "navy"), ((0, 0, 480, 540), "ice")], [((0, 0, 480, 540), False)], "rail"),
    "image": ([((0, 0, 960, 540), "white"), ((540, 0, 960, 430), "navy")], [], "rail"),
    "compare": (
        [((0, 0, 960, 540), "white"), ((0, 150, 480, 540), "ice"), ((480, 150, 960, 540), "navy")],
        [((0, 150, 480, 540), False)],
        "rail",
    ),
    "divider": (
        [((0, 0, 960, 540), "ice"), ((0, 0, 960, DIVIDER_BAND), "navy")],
        [((0, DIVIDER_BAND, 960, 540), True)],
        "divider",
    ),
    "track": ([((0, 0, 960, 540), "ice")], [((0, 0, 960, 540), True)], "track"),
    "thanks": ([((0, 0, 960, 540), "navy")], [], "thanks"),
}
STATIONS_OF = {"cover": [0], "thanks": [5], "divider": [1, 2, 3, 4], "track": [0, 5]}
LABEL_ZONES = {1: (206, 380), 2: (413, 560), 3: (619, 800), 4: (640, 796)}  # where the HTML station label sits


def make_background(out: Path, src: Path, name: str, current: int) -> Path:
    panes, facet_boxes, rail = PRESETS[name]
    pen = Pen(960, 540, SS * X2)
    for (x0, y0, x1, y1), kind in panes:
        pen.rect((x0, y0, x1, y1), fill=(*SURFACE_RGB[kind], 255))
    for box, flip in facet_boxes:
        facets(pen, box, flip)
    if rail == "cover":
        draw_rail(pen, panes, RAIL_Y, 0, start=True, label=(72, 262))
        pen.line([(0, RAIL_Y), (56, RAIL_Y)], (*AQUA, 255), 2.6, caps=False)
    elif rail == "rail":
        draw_rail(pen, panes, RAIL_Y, current, start=current == 0, label=LABEL_ZONES.get(current))
    elif rail == "divider":
        watermark(pen, src, (655, 14, 905, 304))
        draw_rail(pen, panes, DIVIDER_Y, current, scale=1.7, markers=False)
    elif rail == "track":
        draw_rail(pen, panes, OUTLINE_Y, current, scale=1.7, markers=False, start=current == 0)
    elif rail == "thanks":
        draw_rail(pen, panes, RAIL_Y, 5, x_to=318, markers=False, fan=True)
    path = out / f"bg-{name}-s{current}.png"
    img = pen.image.resize((960 * X2, 540 * X2), Image.Resampling.LANCZOS).convert("RGB")
    img.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(path, optimize=True)
    return path


def catalogue() -> list[tuple[str, int]]:
    return [(name, s) for name in PRESETS for s in STATIONS_OF.get(name, [0, 1, 2, 3, 4, 5])]


# -- pictures ------------------------------------------------------------------------------------------------


def logo_disc(out: Path, src: Path) -> Path:
    """Botanical logo on a white disc with a soft shadow and an aqua outer ring (light or navy surfaces)."""
    css = 320
    size = css * X2
    pen = Pen(css, css, X2 * SS)
    pen.circle(160, 160, 158, outline=(*AQUA, 255), width=2)
    pen.circle(160, 160, 146, fill=(*WHITE, 255))
    shadow = Image.new("RGBA", pen.image.size, (0, 0, 0, 0))
    c, r = 160 * X2 * SS, 146 * X2 * SS
    ImageDraw.Draw(shadow).ellipse((c - r, c - r + 10 * SS, c + r, c + r + 10 * SS), fill=(*NAVY, 70))
    base = Image.new("RGBA", pen.image.size, (0, 0, 0, 0))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14 * SS)))
    base.alpha_composite(pen.image)
    base = base.resize((size, size), Image.Resampling.LANCZOS)
    logo = Image.open(src / LOGO_SOURCE).convert("RGBA")
    lw = round(size * 0.70)
    lh = round(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
    base.alpha_composite(logo, ((size - lw) // 2, (size - lh) // 2 + 4))
    path = out / "logo-disc.png"
    base.save(path, optimize=True)
    return path


def white_to_alpha(out: Path, src: Path, name: str, out_name: str) -> Path:
    """A logo printed on white made transparent (for light surfaces only)."""
    image = Image.open(src / name).convert("RGB")
    r, g, b = image.split()
    alpha = ImageChops.invert(ImageChops.darker(ImageChops.darker(r, g), b)).point(lambda v: min(255, v * 2))
    pixels, a_px = image.get_flattened_data(), alpha.get_flattened_data()
    data: list[tuple[int, int, int, int]] = []
    for colour, a in zip(pixels, a_px, strict=True):
        if a == 0:
            data.append((255, 255, 255, 0))
            continue
        k = a / 255
        rr, gg, bb = (max(0, min(255, round((v - 255 * (1 - k)) / k))) for v in colour)
        data.append((rr, gg, bb, a))
    result = Image.new("RGBA", image.size)
    result.putdata(data)
    path = out / out_name
    result.save(path, optimize=True)
    return path


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    name = "Trebuchet MS Bold.ttf" if bold else "Trebuchet MS.ttf"
    try:
        return ImageFont.truetype(f"/System/Library/Fonts/Supplemental/{name}", size)
    except OSError:
        return ImageFont.load_default(size)


def sample(
    out: Path,
    name: str,
    size: tuple[int, int],
    background: Colour,
    lines: list[str],
    ink: Colour,
    markers: Iterable[tuple[int, int]] = (),
    play: bool = False,
) -> Path:
    """Sample picture of a layout, to be replaced by the real one (drawn: no patient data)."""
    w, h = size
    marks = list(markers)
    pen = Pen(w, h, SS, (*background, 255))
    for mx, my in marks:
        pen.circle(mx, my, 38, fill=(*AQUA, 255))
        pen.circle(mx, my, 38, outline=(*WHITE, 255), width=3)
    if play:
        pen.circle(w / 2, h / 2 - 30, 70, fill=(*WHITE, 255))
        pen.polygon([(w / 2 - 22, h / 2 - 68), (w / 2 - 22, h / 2 + 8), (w / 2 + 38, h / 2 - 30)], (*TEAL, 255))
    img = pen.image.resize(size, Image.Resampling.LANCZOS).convert("RGB")
    draw = ImageDraw.Draw(img)
    for i, (mx, my) in enumerate(marks, start=1):
        draw.text((mx, my), str(i), fill=NAVY, font=font(44, True), anchor="mm")
    y = h * (0.78 if play else 0.5) - 26 * (len(lines) - 1)
    for line in lines:
        draw.text((w / 2, y), line, fill=ink, font=font(34), anchor="mm")
        y += 52
    path = out / name
    img.save(path, quality=88)
    return path


GREY = (150, 170, 178)
SAMPLES: dict[str, Callable[[Path], Path]] = {
    "sample-clinical-b.jpg": lambda out: sample(
        out,
        "sample-clinical-b.jpg",
        (1200, 750),
        (16, 20, 24),
        ["Anonymised clinical image", "(replace, keep laterality and scale)"],
        GREY,
    ),
    "sample-annotated-b.jpg": lambda out: sample(
        out,
        "sample-annotated-b.jpg",
        (1200, 750),
        (16, 20, 24),
        ["Anonymised procedure still", "(numbers baked into the picture)"],
        GREY,
        markers=[(380, 200), (880, 210), (560, 570)],
    ),
    "sample-photo-b.jpg": lambda out: sample(
        out,
        "sample-photo-b.jpg",
        (1200, 900),
        ICE,
        ["Photo of the team or the event", "(people who agreed to appear)"],
        NAVY,
    ),
    "sample-video-b.jpg": lambda out: sample(
        out,
        "sample-video-b.jpg",
        (1200, 750),
        NAVY_DEEP,
        ["Poster frame of the video (first frame, anonymised)"],
        GREY,
        play=True,
    ),
}


def jobs(out: Path, src: Path) -> dict[str, Callable[[], Path]]:
    """Every output file name and the function that writes it, in catalogue order."""
    work: dict[str, Callable[[], Path]] = {}
    for glyph in GLYPHS:
        for variant in VARIANTS:
            work[f"icon-{glyph}-{variant}.png"] = lambda g=glyph, v=variant: make_icon(out, g, v)
    for name, stage in catalogue():
        work[f"bg-{name}-s{stage}.png"] = lambda n=name, s=stage: make_background(out, src, n, s)
    work["logo-disc.png"] = lambda: logo_disc(out, src)
    work["wiip-strong-logo-alpha.png"] = lambda: white_to_alpha(out, src, PARTNER_SOURCE, "wiip-strong-logo-alpha.png")
    for name, make in SAMPLES.items():
        work[name] = lambda m=make: m(out)
    return work


def listing() -> list[str]:
    lines = [f"bg-{name}-s{stage}.png  class med-bg-{name}-s{stage}" for name, stage in catalogue()]
    variants = "|".join(VARIANTS)
    lines += [f"icon-{glyph}-<{variants}>.png  class med-ico-{glyph}-<variant>" for glyph in GLYPHS]
    return lines


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Breathe decoration catalogue generator")
    parser.add_argument("--list", action="store_true", help="print the catalogue, write nothing")
    parser.add_argument("--out", type=Path, default=CATALOGUE, help="output folder (default: the catalogue)")
    parser.add_argument("--src", type=Path, default=None, help="folder of the three source pictures")
    parser.add_argument("--only", default="", help="comma separated output names to write")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(listing()))
        return 0
    src: Path = args.src or CATALOGUE
    for name in SOURCES:
        if not (src / name).is_file():
            print(f"error: source picture {name} not found in {src}", file=sys.stderr)
            return 1
    out: Path = args.out
    work = jobs(out, src)
    wanted = [name for name in args.only.split(",") if name] or list(work)
    unknown = [name for name in wanted if name not in work]
    if unknown:
        print(f"error: unknown catalogue file {', '.join(unknown)}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    made = [work[name]() for name in wanted]
    total = sum(path.stat().st_size for path in made)
    print(f"{len(made)} files written to {out} ({total // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
