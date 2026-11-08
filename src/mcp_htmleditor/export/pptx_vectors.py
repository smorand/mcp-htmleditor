"""Vector figures of a slide, named in the PPTX export warnings (SPEC-0016, DEC-003).

The PPTX exporter converts no vector: an inline ``<svg>`` is skipped by every walker and a vector ``<img>`` cannot be
decoded. This pure pre pass reports each such figure once, with its slide number and the DOCX advice sentence.
"""

from __future__ import annotations

from bs4 import Tag

from .to_docx import SVG_ADVICE

VECTOR_ADVICE = SVG_ADVICE
#: Elements whose descendants are interface or inert markup, never slide content.
SILENT_ANCESTORS = frozenset({"button", "script", "template", "noscript", "select"})
SRC_PREVIEW_CHARS = 60
_IGNORED = "l'export PPTX ne convertit pas les vecteurs."


def is_vector_src(src: str) -> bool:
    """Return whether an ``<img>`` source is a vector image (``.svg`` file or ``data:image/svg`` URI)."""
    lowered = src.lower()
    return lowered.split("?")[0].endswith(".svg") or lowered.startswith("data:image/svg")


def vector_figure_warnings(slide: Tag, number: int) -> list[str]:
    """Return one warning per vector figure of ``slide``, in document order.

    Args:
        slide: The exported slide element.
        number: Its 1 based position in the export.
    """
    warnings: list[str] = []
    for element in slide.find_all(["svg", "img"]):
        if not isinstance(element, Tag) or _is_silent(element, slide):
            continue
        if element.name == "svg":
            warnings.append(f"Slide {number}: balise <svg> en ligne ignoree, {_IGNORED} {VECTOR_ADVICE}")
            continue
        src = str(element.get("src") or "")
        if is_vector_src(src):
            warnings.append(
                f"Slide {number}: image SVG ignoree ({src[:SRC_PREVIEW_CHARS]}), {_IGNORED} {VECTOR_ADVICE}"
            )
    return warnings


def _is_silent(element: Tag, slide: Tag) -> bool:
    """Whether a figure sits in a silent ancestor, or an ``<svg>`` in another ``<svg>``, inside the slide."""
    for ancestor in element.parents:
        if ancestor is slide:
            return False
        if ancestor.name in SILENT_ANCESTORS or (element.name == "svg" and ancestor.name == "svg"):
            return True
    return False
