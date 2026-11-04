"""Read only views of a deck: the outline and one slide (SPEC-0007 FR-NEW-001, FR-NEW-002)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from bs4.element import Comment, NavigableString, Tag

from . import Deck, DeckError, document_article, load_deck, slide_id
from .lint import lint_deck
from .scan import hide_images, scan, slide_range

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5")
HIDDEN_TEXT_TAGS = frozenset({"script", "style", "svg"})


def outline(file: str) -> dict[str, Any]:
    """Return the structure of ``file``: charter, type, slide facts, headings; never image data."""
    deck = load_deck(file)
    is_presentation = deck.doc_type == "presentation"
    return {
        "file": file,
        "charter": deck.charter,
        "doc_type": deck.doc_type,
        "total": len(deck.slides) if is_presentation else 0,
        "slides": _slide_facts(deck) if is_presentation else [],
        "headings": [] if is_presentation else _headings(deck),
    }


def get_slide(file: str, slide_id_: str) -> str:
    """Return the raw HTML of one slide, large image sources replaced by ``data:ref:img-N`` (DEC-019)."""
    deck = load_deck(file)
    if not deck.slides:
        raise DeckError(f"get_slide needs a presentation: {file}")
    ids = [slide_id(slide) or f"slide-{index}" for index, slide in enumerate(deck.slides)]
    if slide_id_ not in ids:
        raise DeckError(f'Unknown slide id "{slide_id_}". Valid ids: {", ".join(ids)}')
    tag = deck.slides[ids.index(slide_id_)]
    nodes = scan(deck.text)
    node = next(n for n in nodes if (n.line, n.col) == (tag.sourceline, tag.sourcepos))
    start, end = slide_range(nodes, node)
    return hide_images(deck.text[start:end])


def _slide_facts(deck: Deck) -> list[dict[str, Any]]:
    counts = Counter(problem.slide_index for problem in lint_deck(deck))
    return [
        {
            "index": index,
            "id": slide_id(slide) or f"slide-{index}",
            "title": str(slide.get("data-title", "")),
            "slide_type": str(slide.get("data-slide-type", "")),
            "words": count_words(slide),
            "images": len(slide.find_all("img")),
            "problems": counts[index],
        }
        for index, slide in enumerate(deck.slides)
    ]


def count_words(element: Tag) -> int:
    """Count whitespace separated tokens of the visible text nodes of ``element`` (DEC-018)."""
    return sum(len(text.split()) for text in element.find_all(string=True) if _is_visible(text))


def _is_visible(text: NavigableString) -> bool:
    return not isinstance(text, Comment) and not any(p.name in HIDDEN_TEXT_TAGS for p in text.parents)


def _headings(deck: Deck) -> list[dict[str, Any]]:
    article = document_article(deck.soup)
    if article is None:
        return []
    return [
        {"level": int(tag.name[1]), "text": re.sub(r"\s+", " ", tag.get_text()).strip()}
        for tag in article.find_all(HEADING_TAGS)
        if "doc-title" not in (tag.get("class") or [])
    ]
