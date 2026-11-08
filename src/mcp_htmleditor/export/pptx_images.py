"""Annotated image, image and picture primitives of the PPTX slide builder.

``ImagesMixin`` renders annotated images and plain images, and holds the picture
primitives (source decoding, aspect probing, insertion) other mixins reuse.
"""

from __future__ import annotations

import base64
import binascii
import io
from pathlib import Path
from typing import Any

from bs4 import Tag
from pptx.util import Inches

from .pptx_components import color_of, first_pct, inches
from .pptx_model import _ANNOT_CLASS_COLORS, FILL_KEYS, _BuilderBase, _Para
from .pptx_style import Box, TextStyle, classes, parse_color, style_props
from .pptx_vectors import is_vector_src


class ImagesMixin(_BuilderBase):
    """Annotated image, image and picture primitives of the slide builder."""

    def _render_annotated_image(self, box: Box, element: Tag) -> None:
        """Render an annotated image and place its callouts over the picture."""
        img = element.find("img")
        if not isinstance(img, Tag):
            self.ctx.report.warn("Bloc annotated-image sans <img>: annotations seules exportees.")
            image_box = box
        else:
            width = min(box.width, self._max_width(element, box.width))
            centered = "auto" in style_props(element).get("margin", "")
            frame = box.center_horizontally(width) if centered else box.resize(width=width)
            picture = self._add_picture(frame, str(img.get("src") or ""), mode="fit")
            image_box = (
                Box(
                    inches(picture.left),
                    inches(picture.top),
                    inches(picture.width),
                    inches(picture.height),
                )
                if picture
                else frame
            )
        for annotation in element.find_all(attrs={"data-type": "annotation"}):
            if isinstance(annotation, Tag):
                self._render_annotation(image_box, annotation)

    def _render_annotation(self, image_box: Box, annotation: Tag) -> None:
        """Render one callout positioned in percentages of the image box."""
        text = annotation.get_text(" ", strip=True)
        if not text:
            return
        props = style_props(annotation)
        x = first_pct(annotation.get("data-x"), props.get("left"))
        y = first_pct(annotation.get("data-y"), props.get("top"))
        fill, fg = self._annotation_colors(annotation)
        size = 9.5
        width = min(len(text) * size * 0.56 / 72.0 + 0.16, image_box.width * 0.9)
        height = 0.24
        box = Box(
            image_box.left + image_box.width * x / 100.0,
            image_box.top + image_box.height * y / 100.0,
            width,
            height,
        )
        self._rect(box, fill=fill)
        style = TextStyle(size=size, bold=True, color=fg, align="center", space_after=0)
        _, frame = self._textbox(box, anchor="middle")
        self._write(frame, [_Para(style, [(text, style)])])

    def _annotation_colors(self, annotation: Tag) -> tuple[str, str]:
        """Resolve the (fill, text) colors of an annotation."""
        props = self.res.props(annotation)
        fill = color_of(props, FILL_KEYS, self.res)
        color = parse_color(props.get("color"), self.res.css_vars)
        if not fill:
            for name in classes(annotation):
                if name in _ANNOT_CLASS_COLORS:
                    fill, fallback = _ANNOT_CLASS_COLORS[name]
                    return fill, color or fallback
        return fill or "FFF176", color or "262626"

    def _render_image(self, box: Box, element: Tag) -> None:
        """Render a standalone image, fitted inside its block."""
        self._add_picture(box, str(element.get("src") or ""), mode="fit")

    # -- shapes and pictures ----------------------------------------------

    def _image_source(self, src: str) -> io.BytesIO | str | None:
        """Resolve an image source to something python-pptx can read.

        Data URIs are decoded in memory; relative paths resolve against the
        directory of the HTML file; remote URLs are refused. A vector source gives
        ``None`` without a warning: the slide pre pass already named it.
        """
        if not src or is_vector_src(src):
            return None
        if src.startswith("data:"):
            header, _, payload = src.partition(",")
            if "base64" not in header or not payload:
                self.ctx.report.warn("Image data URI non base64 ignoree.")
                return None
            try:
                return io.BytesIO(base64.b64decode(payload, validate=False))
            except (binascii.Error, ValueError):
                self.ctx.report.warn("Image data URI illisible ignoree.")
                return None
        if src.startswith(("http://", "https://", "//")):
            self.ctx.report.warn(f"Image distante non telechargee: {src[:60]}")
            return None
        path = Path(src)
        if not path.is_absolute():
            path = self.ctx.base_dir / path
        if not path.exists():
            self.ctx.report.warn(f"Image introuvable, ignoree: {path}")
            return None
        return str(path)

    def _image_aspect(self, src: str) -> float | None:
        """Return the width / height ratio of an image, ``None`` if unknown."""
        source = self._image_source(src)
        if source is None:
            return None
        try:
            picture = self.slide.shapes.add_picture(source, 0, 0)
        except Exception as exc:
            self.ctx.report.warn(f"Image non decodable ignoree: {exc}")
            return None
        aspect = picture.width / picture.height if picture.height else None
        picture._element.getparent().remove(picture._element)
        return aspect

    def _add_picture(self, box: Box, src: str, mode: str = "fit") -> Any:
        """Insert a picture in ``box``.

        Modes: ``fit`` keeps the aspect ratio inside the box and centers it,
        ``cover`` fills the box and crops the overflow (CSS ``object-fit:
        cover``), ``fit-height`` keeps the height and derives the width,
        ``stretch`` forces the box dimensions.
        """
        source = self._image_source(src)
        if source is None:
            return None
        if isinstance(source, io.BytesIO):
            source.seek(0)
        try:
            picture = self.slide.shapes.add_picture(source, Inches(box.left), Inches(box.top))
        except Exception as exc:
            self.ctx.report.warn(f"Image non inseree ({exc}): {src[:40]}")
            return None
        natural = picture.width / picture.height if picture.height else 1.0

        if mode == "stretch":
            picture.width, picture.height = Inches(box.width), Inches(box.height)
            return picture
        if mode == "fit-height":
            picture.height = Inches(box.height)
            picture.width = Inches(box.height * natural)
            return picture
        if mode == "cover":
            picture.width, picture.height = Inches(box.width), Inches(box.height)
            target = box.width / box.height
            if natural > target:
                crop = (1.0 - target / natural) / 2.0
                picture.crop_left = crop
                picture.crop_right = crop
            elif natural < target:
                crop = (1.0 - natural / target) / 2.0
                picture.crop_top = crop
                picture.crop_bottom = crop
            return picture
        scale = min(box.width / natural, box.height) if natural else box.height
        width, height = scale * natural, scale
        picture.width, picture.height = Inches(width), Inches(height)
        picture.left = Inches(box.left + (box.width - width) / 2.0)
        picture.top = Inches(box.top + (box.height - height) / 2.0)
        return picture
