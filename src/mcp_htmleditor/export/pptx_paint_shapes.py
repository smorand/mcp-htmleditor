"""Shape writers of the painted PPTX export (SPEC-0024 FR-3, FR-4): rectangles, gradients, shadows, pictures.

A mixin of ``Painter`` (``pptx_paint.py``): it reads the ``rect``, ``pic`` and ``slide`` items of the measure and adds
native shapes to ``self.slide``. Charter agnostic: the items carry computed geometry and style only.
"""

from __future__ import annotations

import base64
import binascii
import io
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from PIL import Image
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.util import Emu

from .pptx_paint_style import (
    EMU_PER_POINT,
    OOXML_PERCENT,
    Gradient,
    Shadow,
    alpha_of,
    fit_picture,
    parse_gradient,
    parse_shadow,
    rgb,
    shape_for_radii,
    to_emu,
)
from .pptx_vectors import is_vector_src

REMOTE: Final = re.compile(r"^https?://")
ANGLE_UNIT: Final = 60000
PRESETS: Final = {
    "rect": MSO_SHAPE.RECTANGLE,
    "ellipse": MSO_SHAPE.OVAL,
    "round": MSO_SHAPE.ROUNDED_RECTANGLE,
    "round_top": MSO_SHAPE.ROUND_2_SAME_RECTANGLE,
}
DASHES: Final = {"dashed": MSO_LINE.DASH, "dotted": MSO_LINE.ROUND_DOT}


def child(parent: Any, tag: str, attributes: dict[str, str] | None = None) -> Any:
    """Append and return a new ``tag`` element (``a:...``) under ``parent``."""
    element = parent.makeelement(qn(tag), attributes or {})
    parent.append(element)
    return element


def add_alpha(colour_element: Any, alpha: float) -> None:
    """Append an ``a:alpha`` child to a colour element when the colour is not opaque."""
    if alpha < 1:
        colour_element.append(colour_element.makeelement(qn("a:alpha"), {"val": str(round(alpha * OOXML_PERCENT))}))


def srgb_element(parent: Any, colour: Sequence[float], opacity: float = 1.0) -> Any:
    """Add an ``a:srgbClr`` (with alpha) under ``parent`` and return it."""
    element = child(parent, "a:srgbClr", {"val": str(rgb(colour))})
    add_alpha(element, alpha_of(colour, opacity))
    return element


class ShapesMixin:
    """Rectangles, backgrounds and pictures of a painted slide."""

    slide: Any
    report: Any
    base_dir: Path

    def background(self, item: dict[str, Any]) -> None:
        """The slide colour (or gradient) and background picture, full bleed."""
        gradient = parse_gradient(item.get("gradient"))
        if gradient is not None:
            holder = self.slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, 0, 0, Emu(960 * EMU_PER_POINT), Emu(540 * EMU_PER_POINT)
            )
            self._finish_shape(holder, gradient=gradient, colour=None, opacity=1.0, border=None)
        elif item.get("color"):
            fill = self.slide.background.fill
            fill.solid()
            fill.fore_color.rgb = rgb(item["color"])
        if item.get("image"):
            self.picture({"box": [0, 0, 960, 540], "src": item["image"], "fit": "fill"})

    def rect(self, item: dict[str, Any]) -> None:
        """A rectangle, rounded rectangle or ellipse: fill, gradient, uniform border, opacity, outer shadow."""
        x, y, width, height = item["box"]
        border = item.get("border")
        radii = list(item.get("radius") or (0, 0, 0, 0))
        if border:  # the line is centred on the edge: draw it half a line inside
            inset = border["w"] / 2
            x, y, width, height = x + inset, y + inset, max(width - border["w"], 1), max(height - border["w"], 1)
            radii = [max(r - inset, 0) for r in radii]
        kind, adjustments = shape_for_radii(radii, width, height)
        shape = self.slide.shapes.add_shape(PRESETS[kind], *to_emu([x, y, width, height]))
        for index, value in enumerate(adjustments):
            shape.adjustments[index] = value
        self._finish_shape(
            shape,
            gradient=parse_gradient(item.get("gradient")),
            colour=item.get("color"),
            opacity=item.get("op", 1.0),
            border=border,
            shadow=parse_shadow(item.get("shadow")),
        )

    def _finish_shape(
        self,
        shape: Any,
        *,
        gradient: Gradient | None,
        colour: Sequence[float] | None,
        opacity: float,
        border: dict[str, Any] | None,
        shadow: Shadow | None = None,
    ) -> None:
        if gradient is not None:
            self._gradient_fill(shape, gradient, opacity)
        elif colour is not None:
            shape.fill.solid()
            shape.fill.fore_color.rgb = rgb(colour)
            solid = shape._element.spPr.find(qn("a:solidFill"))
            add_alpha(solid.find(qn("a:srgbClr")), alpha_of(colour, opacity))
        else:
            shape.fill.background()
        if border:
            shape.line.width = Emu(round(border["w"] * EMU_PER_POINT))
            shape.line.color.rgb = rgb(border["color"])
            if border.get("style") in DASHES:
                shape.line.dash_style = DASHES[border["style"]]
            line_colour = shape._element.spPr.find(qn("a:ln")).find(qn("a:solidFill")).find(qn("a:srgbClr"))
            add_alpha(line_colour, alpha_of(border["color"], opacity))
        else:
            shape.line.fill.background()
        style = shape._element.find(qn("p:style"))  # theme references bring a shadow and an outline
        if style is not None:
            shape._element.remove(style)
        if shadow is not None:
            self._shadow(shape, shadow, opacity)

    @staticmethod
    def _gradient_fill(shape: Any, gradient: Gradient, opacity: float) -> None:
        shape.fill.gradient()
        fill = shape._element.spPr.find(qn("a:gradFill"))
        for old in list(fill):
            fill.remove(old)
        stops = child(fill, "a:gsLst")
        for position, colour in gradient.stops:
            stop = child(stops, "a:gs", {"pos": str(round(position * OOXML_PERCENT))})
            srgb_element(stop, colour, opacity)
        child(fill, "a:lin", {"ang": str(round(gradient.angle * ANGLE_UNIT)), "scaled": "0"})

    @staticmethod
    def _shadow(shape: Any, shadow: Shadow, opacity: float) -> None:
        effects = child(shape._element.spPr, "a:effectLst")
        outer = child(
            effects,
            "a:outerShdw",
            {
                "blurRad": str(round(shadow.blur * EMU_PER_POINT)),
                "dist": str(round(shadow.distance * EMU_PER_POINT)),
                "dir": str(round(shadow.direction * ANGLE_UNIT)),
                "algn": "ctr",
                "rotWithShape": "0",
            },
        )
        srgb_element(outer, shadow.colour, opacity)

    # -- pictures -------------------------------------------------------------------------------------------

    def _bytes(self, src: str) -> bytes | None:
        """Bytes of a measured picture: a data URI or a local file; remote, missing and vector ones skipped."""
        if not src or is_vector_src(src):
            return None
        if src.startswith("data:"):
            header, _, payload = src.partition(",")
            if "base64" not in header:
                return None
            try:
                return base64.b64decode(payload, validate=False)
            except (binascii.Error, ValueError):
                self.report.warn("Image data URI illisible ignoree.")
                return None
        if REMOTE.match(src):
            self.report.warn(f"Image distante non telechargee: {src[:60]}")
            return None
        parsed = urlparse(src)
        path = Path(url2pathname(unquote(parsed.path))) if parsed.scheme == "file" else self.base_dir / src
        if not path.is_file():
            self.report.warn(f"Image introuvable, ignoree: {path}")
            return None
        return path.read_bytes()

    def picture(self, item: dict[str, Any]) -> None:
        """A picture at its rendered box with the ``object-fit`` crop (cover) or box (contain)."""
        data = self._bytes(item["src"])
        if data is None:
            return
        natural = item.get("natural")
        if not natural or not natural[0]:
            natural = _natural_size(data)
        box, (left, top, right, bottom) = fit_picture(
            item.get("fit", "fill"), item["box"], natural, item.get("position")
        )
        try:
            pic = self.slide.shapes.add_picture(io.BytesIO(data), *to_emu(box))
        except Exception as exc:
            self.report.warn(f"Image non inseree ({exc}): {item['src'][:40]}")
            return
        pic.crop_left, pic.crop_top, pic.crop_right, pic.crop_bottom = left, top, right, bottom
        if item.get("alt"):  # the words of a rasterised figure stay readable and searchable
            pic._element.nvPicPr.cNvPr.set("descr", item["alt"])
        opacity = item.get("op", 1.0)
        if opacity < 1:
            blip = pic._element.find(".//" + qn("a:blip"))
            blip.append(blip.makeelement(qn("a:alphaModFix"), {"amt": str(round(opacity * OOXML_PERCENT))}))


def _natural_size(data: bytes) -> tuple[int, int] | None:
    try:
        with Image.open(io.BytesIO(data)) as image:
            return image.size
    except Exception:
        return None


__all__ = ["ShapesMixin", "add_alpha", "srgb_element"]
