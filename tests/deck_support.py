"""Fixture builders and CLI runner shared by the deck service tests (SPEC-0007).

Decks are generated from the real ``templates/bootstrap`` files, never committed. Counters,
``TOTAL`` and ``slideNames`` are written by plain string formatting, independent of product code.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest import mock

from click.testing import CliRunner
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mcp_htmleditor import cli as cli_module
from mcp_htmleditor.cli import main

BOOTSTRAP = Path(__file__).resolve().parents[1] / "templates" / "bootstrap"
BOOTSTRAP_FILES = {
    "ei": "slides-ei-empty.html",
    "carbon": "slides-empty.html",
    "medical": "slides-medical-empty.html",
    "doc-perso": "document-perso-empty.html",
}
COVER_TITLE = "Titre de la présentation"
FIXED_TIME = 1_000_000_000
TINY_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

EI_TITLES = ("Couverture", "Sommaire", "Contexte", "Besoins", "Architecture", "Planning", "Risques", "Merci")
CARBON_TITLES = ("Intro", "Offre", "Chiffres", "Plan", "Fin")
MED_TITLES = ("Couverture", "Contexte", "Technique", "Résultats", "Limites", "Conclusion")

_EI_SLIDE = """    <article class="slide" id="slide-{i}" data-type="slide" data-id="slide-{i}"
             data-slide-type="content" data-title="{title}">
      <div class="slide-inner">
        <div class="slide-eyebrow" data-editable="text">Cat · Slide {n:02d} / {total:02d}</div>
        <h1 class="slide-h1" data-editable="text">{title}</h1>
        <div class="slide-title-rule"></div>
        <div class="slide-body" data-editable="text"><p>Texte de {title}.</p>{image}</div>
      </div>
      <div class="slide-foot">
        <span class="slide-foot-page">{n}</span>
        <span class="slide-foot-title" data-editable="text">Réunion · Mois</span>
      </div>
    </article>
"""
_EI_SECTION = """    <article class="slide" id="slide-{i}" data-type="slide" data-id="slide-{i}"
             data-slide-type="section" data-title="{title}">
      <div class="slide-section-body">
        <div class="slide-section-title" data-editable="text">{title}</div>{image}
      </div>
    </article>
"""
_CARBON_SLIDE = """    <article class="slide" id="slide-{i}" data-type="slide" data-id="slide-{i}" data-title="{title}">
      <div class="slide-header">
        <div class="slide-eyebrow" data-editable="text">Section · Slide {n:02d} / {total:02d}</div>
        <h1 class="slide-h1" data-editable="text"><strong>{title}</strong></h1>
      </div>
      <div class="slide-body" data-editable="text"><p>Texte de {title}.</p>{image}</div>
      <div class="slide-footer">
        <span class="slide-footer-left" data-editable="text">Produit</span>
        <span class="slide-footer-right">Slide {n} / {total}</span>
      </div>
    </article>
"""
_MED_SLIDE = """    <article class="slide" id="slide-{i}" data-type="slide" data-id="slide-{i}"
             data-slide-type="content" data-title="{title}">
      <div class="med-band"></div>
      <div class="med-head">
        <div class="slide-eyebrow" data-editable="text">Cat · Slide {n:02d} / {total:02d}</div>
        <h1 class="slide-h1" data-editable="text">{title}</h1>
        <div class="med-rule"><i></i><b></b></div>
      </div>
      <div class="slide-body">
        <div class="med-strip">
          <figure class="med-figure w-50"><img src="data:image/png;base64,{png}" alt="a">
            <figcaption class="med-caption">Légende.</figcaption></figure>
          <div class="med-comment w-50"><ul class="med-list"><li>Point de {title}.</li></ul></div>
        </div>
      </div>
      <div class="med-foot">
        <div class="med-sources"><p class="med-source"><span class="src-title">Titre</span> : Auteur A. 2024.</p></div>
        <span class="slide-foot-page">{n}</span>
      </div>
    </article>
"""
_TEMPLATES = {"ei": _EI_SLIDE, "carbon": _CARBON_SLIDE, "medical": _MED_SLIDE}


def build_deck(
    charter: str,
    titles: tuple[str, ...],
    *,
    image_chars: int | None = None,
    image_slide: int | None = None,
    mutate: Callable[[str], str] | None = None,
) -> str:
    """Return a deck of ``len(titles)`` slides built on the real ``charter`` bootstrap.

    The bootstrap is cut at its first ``<article`` and after its last ``</article>``; the retitled
    cover is kept and the other slides come from small literal templates copying the real classes.
    """
    text = (BOOTSTRAP / BOOTSTRAP_FILES[charter]).read_text(encoding="utf-8")
    start = text.index("<article")
    start = text.rfind("\n", 0, start) + 1
    end = text.rindex("</article>") + len("</article>\n")
    head, cover, tail = text[:start], text[start:end], text[end:]
    total = len(titles)
    slides = [_retitle_cover(charter, cover, titles[0], total)]
    for i, title in enumerate(titles[1:], start=1):
        slides.append(_slide(charter, i, title, total, image_chars if image_slide == i else None))
    names = "".join(f'    "{title}",\n' for title in titles)
    tail = re.sub(r"const TOTAL = \d+;", f"const TOTAL = {total};", tail)
    tail = re.sub(r"const slideNames = \[.*?\];", f"const slideNames = [\n{names}  ];", tail, flags=re.S)
    result = head + "".join(slides) + tail
    return mutate(result) if mutate else result


def _retitle_cover(charter: str, cover: str, title: str, total: int) -> str:
    cover = cover.replace(COVER_TITLE, title)
    if charter == "carbon":
        cover = cover.replace("<strong>Titre</strong> de la présentation", f"<strong>{title}</strong>")
        cover = cover.replace("Slide 01 / 01", f"Slide 01 / {total:02d}").replace("Slide 1 / 1", f"Slide 1 / {total}")
    if charter == "medical":
        cover = cover.replace("Titre de la <span>présentation</span>", title)
    return cover


def _slide(charter: str, i: int, title: str, total: int, image_chars: int | None) -> str:
    image = f'<img src="data:image/png;base64,{"A" * image_chars}" alt="big">' if image_chars else ""
    template = _EI_SECTION if charter == "ei" and i == total - 1 else _TEMPLATES[charter]
    return template.format(i=i, n=i + 1, total=total, title=title, image=image, png=TINY_PNG)


def deck_ei() -> str:
    """DECK-EI: 8 slides, a 1 500 character image on slide 3, a section slide last."""
    return build_deck("ei", EI_TITLES, image_chars=1500, image_slide=3)


def deck_carbon() -> str:
    """DECK-CARBON: 5 slides."""
    return build_deck("carbon", CARBON_TITLES)


def deck_med() -> str:
    """DECK-MED: a cover then 5 content slides."""
    return build_deck("medical", MED_TITLES)


def doc_perso() -> str:
    """DOC-PERSO: the Perso document bootstrap with a known heading outline."""
    text = (BOOTSTRAP / BOOTSTRAP_FILES["doc-perso"]).read_text(encoding="utf-8")
    start = text.index("<article")
    start = text.index(">", start) + 1
    body = (
        '\n    <h1 class="doc-title">Rapport</h1>\n'
        '    <h1 class="doc-h1">Contexte</h1>\n'
        '    <h2 class="doc-h2">Périmètre</h2>\n'
        '    <h1 class="doc-h1">Risques</h1>\n  '
    )
    return text[:start] + body + text[text.rindex("</article>") :]


def write_deck(path: Path, content: str) -> str:
    """Write ``content`` at ``path`` with a fixed modification time and return the path string."""
    path.write_text(content, encoding="utf-8")
    os.utime(path, (FIXED_TIME, FIXED_TIME))
    return str(path)


def assert_only_region_changed(before: bytes, after: bytes, inner_marker: bytes) -> None:
    """Assert the bytes that differ lie inside the inner content of the element ``inner_marker``.

    ``inner_marker`` is the element as written in ``before`` (start tag, content, end tag), located by
    plain substring search, independent of the scanner. The common prefix and suffix of the two byte
    strings must leave the whole difference between the end of the start tag and the start of the end tag.
    """
    assert before != after
    assert before.count(inner_marker) == 1, "the marker must locate exactly one element"
    element = before.index(inner_marker)
    inner_start = element + inner_marker.index(b">") + 1
    inner_end = element + inner_marker.rindex(b"</")
    prefix = len(os.path.commonprefix([before, after]))
    suffix = min(len(os.path.commonprefix([before[::-1], after[::-1]])), min(len(before), len(after)) - prefix)
    assert inner_start <= prefix, f"a byte before the element content changed (offset {prefix})"
    assert len(before) - suffix <= inner_end, (
        f"a byte after the element content changed (offset {len(before) - suffix})"
    )


def run_cli(*args: str, input: str | None = None) -> tuple[str, str, int]:  # noqa: A002 - mirrors CliRunner
    """Run the CLI and return ``(stdout, stderr, exit_code)`` with separate streams."""
    # the group callback would install the process wide tracer, which tests/test_tracing.py owns
    with mock.patch.object(cli_module, "configure_tracing", lambda settings=None: None):
        result = CliRunner().invoke(main, list(args), input=input)
    return result.stdout, result.stderr, result.exit_code


def call_tool(name: str, **arguments: str) -> tuple[bool, Any]:
    """Call a tool through an in process ``fastmcp.Client``: ``(True, data)`` or ``(False, ToolError text)``.

    The session runs in its own thread: the e2e suite keeps an event loop alive in the caller's.
    """
    from mcp_htmleditor.mcp_server import mcp

    async def session() -> tuple[bool, Any]:
        async with Client(mcp) as client:
            try:
                result = await client.call_tool(name, arguments)
            except ToolError as exc:
                return False, str(exc)
            return True, result.data

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, session()).result()
