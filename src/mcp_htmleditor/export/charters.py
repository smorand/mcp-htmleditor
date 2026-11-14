"""Single registry of the nine charters (templates, detectors, DOCX keys).

Stdlib only: this module imports nothing from the project, so ``templates``,
``pptx_style`` and ``reference_docx`` can all read it without an import cycle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CharterSpec:
    """One charter: its template, its detection markers and its DOCX key."""

    key: str
    kind: str  # presentation, document, mail or website
    template: str  # path under a templates directory
    description: str
    css_tokens: tuple[str, ...]  # substrings searched in the style text
    css_classes: tuple[str, ...]  # class names searched in the markup
    layout_set: str | None  # slide layout set: carbon, ei, medical or breathe
    docx_key: str | None  # key of a reference_docx charter


BREATHE = "breathe"
MEDICAL = "medical"
BREATHE_MARK = "--breathe-ice"
"""Style token naming the Breathe charter (SPEC-0023 FR-NEW-003); Breathe keeps the ``--med-*`` tokens otherwise."""
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def is_breathe(declared: str | None, css: str) -> bool:
    """Tell whether a presentation is Breathe (SPEC-0023 DEC-001): the page declaration wins, then the marker.

    ``declared`` is the ``data-doc-template`` value of the page (compared case sensitively), ``css`` the text of its
    ``<style>`` blocks; the marker counts outside CSS comments only. A page declaring ``medical`` stays medical
    whatever its styles hold. O(len(css)).
    """
    if declared == BREATHE:
        return True
    return declared != MEDICAL and BREATHE_MARK in css and BREATHE_MARK in _CSS_COMMENT.sub("", css)


REGISTRY: tuple[CharterSpec, ...] = (
    CharterSpec(
        key="ei",
        kind="presentation",
        template="bootstrap/slides-ei-empty.html",
        description="Euro-Information presentation (Crédit Mutuel / CIC), 1 title slide",
        css_tokens=("--ei-blue",),
        css_classes=("slide-inner",),
        layout_set="ei",
        docx_key=None,
    ),
    CharterSpec(
        key="carbon",
        kind="presentation",
        template="bootstrap/slides-empty.html",
        description="IBM Carbon presentation, 1 empty slide",
        css_tokens=("--ibm-blue", "--cds-"),
        css_classes=("slide-header",),
        layout_set="carbon",
        docx_key=None,
    ),
    CharterSpec(
        key="medical",
        kind="presentation",
        template="bootstrap/slides-medical-empty.html",
        description="Presentation medicale (congres/staff): teal+orange, images commentees, citations",
        css_tokens=("--med-teal",),
        css_classes=("med-rule",),
        layout_set="medical",
        docx_key=None,
    ),
    CharterSpec(
        key="breathe",
        kind="presentation",
        template="bootstrap/slides-breathe-empty.html",
        description=(
            "Breathe congress presentation: airway story line, ice and navy panels, Georgia titles, 1 cover slide"
        ),
        css_tokens=(BREATHE_MARK,),
        css_classes=(),
        layout_set="breathe",
        docx_key=None,
    ),
    CharterSpec(
        key="doc",
        kind="document",
        template="bootstrap/document-empty.html",
        description="Word-like document (single column)",
        css_tokens=(),
        css_classes=(),
        layout_set=None,
        docx_key=None,
    ),
    CharterSpec(
        key="doc-perso",
        kind="document",
        template="bootstrap/document-perso-empty.html",
        description="Document charte Perso (Arial, headings colores)",
        css_tokens=(),
        css_classes=(),
        layout_set=None,
        docx_key="perso",
    ),
    CharterSpec(
        key="doc-ei",
        kind="document",
        template="bootstrap/document-ei-empty.html",
        description="Document Euro-Information (bleu EI, Segoe UI)",
        css_tokens=(),
        css_classes=(),
        layout_set=None,
        docx_key="ei",
    ),
    CharterSpec(
        key="mail",
        kind="mail",
        template="bootstrap/mail-empty.html",
        description="Mail HTML Carbon leger (tables imbriquees, CSS inline, 640px)",
        css_tokens=(),
        css_classes=(),
        layout_set=None,
        docx_key=None,
    ),
    CharterSpec(
        key="website",
        kind="website",
        template="bootstrap/website-empty.html",
        description="Site web Carbon (nav, hero, tabs, cartes, footer), pas d'export PPTX/DOCX",
        css_tokens=(),
        css_classes=(),
        layout_set=None,
        docx_key=None,
    ),
)
