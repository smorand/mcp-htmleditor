"""Deck service layer: load a file, detect its charter and kind (SPEC-0007).

This package never prints; ``cli.py`` and ``mcp_server.py`` call it and turn ``DeckError``
into their own error surface. ``export.to_pptx`` (python-pptx) is imported lazily.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import Tag

from ..export.charters import REGISTRY

DOC_TYPES = ("presentation", "document", "website")
MEDICAL_MARK = "--med-teal"
EI_MARK = "--ei-blue"
EI_COVER_CLASS = "slide-cover-logos"
DEFAULT_DOCUMENT_CHARTER = "doc"
# data-doc-template value -> charter key, for every non presentation charter
DOCUMENT_CHARTERS = {(c.docx_key or c.key): c.key for c in REGISTRY if c.kind != "presentation"}


class DeckError(Exception):
    """A user facing failure: the message is shown as is."""


@dataclass(frozen=True, slots=True)
class Deck:
    """A parsed file: raw text, soup, outermost slides, charter key and document type."""

    path: str
    text: str
    soup: BeautifulSoup
    slides: tuple[Tag, ...]
    charter: str
    doc_type: str


def load_deck(file: str) -> Deck:
    """Read and parse ``file``; raise ``DeckError`` when it is missing or not UTF-8."""
    try:
        text = Path(file).read_bytes().decode("utf-8")
    except FileNotFoundError:
        raise DeckError(f"File not found: {file}") from None
    except UnicodeDecodeError:
        raise DeckError(f"File is not valid UTF-8: {file}") from None
    return deck_from_text(file, text)


def deck_from_text(file: str, text: str) -> Deck:
    """Parse ``text`` as the content of ``file``, without reading the disk."""
    from ..export.to_pptx import find_slides  # noqa: PLC0415 - python-pptx costs 0.29 s, never at import

    soup = BeautifulSoup(text, "html.parser")
    slides = tuple(find_slides(soup))
    doc_type = detect_doc_type(soup, bool(slides))
    return Deck(file, text, soup, slides, detect_charter(soup, doc_type), doc_type)


def slide_id(tag: Tag) -> str | None:
    """Return ``data-id``, else ``id``, else ``None``."""
    return str(tag.get("data-id") or tag.get("id") or "") or None


def detect_doc_type(soup: BeautifulSoup, has_slides: bool) -> str:
    """Return the ``<html data-doc-type>`` value when known, else decide from the slides."""
    html = soup.find("html")
    declared = html.get("data-doc-type") if isinstance(html, Tag) else None
    if declared in DOC_TYPES:
        return str(declared)
    return "presentation" if has_slides else "document"


def detect_charter(soup: BeautifulSoup, doc_type: str) -> str:
    """Return the charter key of a parsed file (DEC-006)."""
    if doc_type == "presentation":
        return _presentation_charter(soup)
    article = document_article(soup)
    template = str(article.get("data-doc-template", "")) if article else ""
    return DOCUMENT_CHARTERS.get(template, DEFAULT_DOCUMENT_CHARTER)


def document_article(soup: BeautifulSoup) -> Tag | None:
    """Return the first ``data-type="document"`` article, if any."""
    found = soup.find("article", attrs={"data-type": "document"})
    return found if isinstance(found, Tag) else None


def _presentation_charter(soup: BeautifulSoup) -> str:
    html = soup.find("html")
    style = "".join(tag.get_text() for tag in soup.find_all("style"))
    if MEDICAL_MARK in style or (isinstance(html, Tag) and html.get("data-doc-template") == "medical"):
        return "medical"
    if EI_MARK in style or soup.find(class_=EI_COVER_CLASS) is not None:
        return "ei"
    return "carbon"
