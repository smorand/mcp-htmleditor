"""Read only views of a deck: the outline (SPEC-0007 FR-NEW-001)."""

from __future__ import annotations

import re
from typing import Any

from bs4.element import Comment, NavigableString, Tag

from . import Deck, document_article, load_deck, slide_id

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


def _slide_facts(deck: Deck) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "id": slide_id(slide) or f"slide-{index}",
            "title": str(slide.get("data-title", "")),
            "slide_type": str(slide.get("data-slide-type", "")),
            "words": count_words(slide),
            "images": len(slide.find_all("img")),
            "problems": 0,
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
