"""Fixtures of the Breathe tests (SPEC-0023): decks built from the shipped Breathe files, never from scratch."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO / "templates" / "bootstrap" / "slides-breathe-empty.html"
REFERENCE = REPO / "templates" / "reference" / "slides" / "breathe.html"
CATALOGUE = REPO / "templates" / "assets" / "breathe"
WCBIP = Path.home() / "projects" / "lamya" / "presentations" / "WABIP_2026-12_Melbourne" / "deck" / "wcbip2026-v1.html"
COVER_PLACEHOLDER = "Title of the presentation"
MARKER_LINE = "    --breathe-ice:#E7F7FF;\n"
DECLARED_BREATHE = 'data-doc-template="breathe"'
DECLARED_MEDICAL = 'data-doc-template="medical"'
REFERENCE_NAMES = (
    "Cover",
    "Disclosure",
    "Pathway",
    "Part 2: Diagnose",
    "Key figures",
    "Key figures, deep",
    "Statement",
    "Content with picture",
    "Content with card",
    "Table",
    "Clinical image",
    "Compare",
    "Statement, deep",
    "Clinical case",
    "Annotated image",
    "Timeline",
    "Paper highlight",
    "Video poster",
    "Survey",
    "Priorities",
    "References",
    "Thanks, collage",
    "Thanks, message",
)
_ARTICLE = re.compile(r"[ \t]*<article\s[^>]*data-type=\"slide\".*?</article>\n", re.S)


def breathe_slide(  # noqa: PLR0913 - one keyword per slide trait
    title: str,
    body: str = "",
    *,
    kind: str = "content",
    background: str = "white-s2",
    notes: str = "",
    page: int | None = None,
) -> str:
    """One Breathe slide on a background preset; ids are set by ``breathe_deck``."""
    foot = f'<span class="slide-foot-page">{page}</span>' if page is not None else ""
    return (
        f'    <article class="slide med-bg-{background}" id="slide-N" data-type="slide" data-id="slide-N"\n'
        f'             data-slide-type="{kind}" data-title="{title}" style="background-color:var(--med-ice)">\n'
        f'      <div class="med-bleed">\n        <div class="med-pane w-60 med-px-600">\n'
        f'          <h1 class="med-title" data-editable="text">{title}</h1>\n          {body}\n        </div>\n'
        f'        <div class="med-pane w-40 med-px-360">{foot}</div>\n      </div>\n'
        f'      <aside data-role="speaker-notes">{notes}</aside>\n    </article>\n'
    )


def reference_slide(name: str) -> str:
    """The article of the reference deck named ``name`` (ids left as in the reference)."""
    for match in _ARTICLE.finditer(REFERENCE.read_text(encoding="utf-8")):
        if f'data-title="{name}"' in match.group():
            return match.group()
    raise AssertionError(f"no reference slide {name!r}")


def breathe_deck(*slides: str, cover: str = "Cover title", source: Path = BOOTSTRAP) -> str:
    """The starting point with its cover retitled ``cover`` and ``slides`` appended, ids, TOTAL and names set."""
    text = source.read_text(encoding="utf-8").replace(COVER_PLACEHOLDER, cover)
    covers = list(_ARTICLE.finditer(text))
    end = covers[-1].end()
    text = text[:end] + "".join(slides) + text[end:]
    articles = list(_ARTICLE.finditer(text))
    names: list[str] = []
    pieces: list[str] = []
    last = 0
    for index, match in enumerate(articles):
        article = re.sub(r'id="slide-[^"]*"', f'id="slide-{index}"', match.group(), count=1)
        article = re.sub(r'data-id="slide-[^"]*"', f'data-id="slide-{index}"', article, count=1)
        names.append(re.search(r'data-title="([^"]*)"', article).group(1))  # type: ignore[union-attr]
        pieces += [text[last : match.start()], article]
        last = match.end()
    text = "".join(pieces) + text[last:]
    listed = "".join(f"    {name!r},\n".replace("'", '"') for name in names)
    text = re.sub(r"const TOTAL = \d+;", f"const TOTAL = {len(names)};", text)
    return re.sub(r"const slideNames = \[.*?\];", lambda _: f"const slideNames = [\n{listed}  ];", text, flags=re.S)


def as_medical(html: str, *, keep_marker: bool = False) -> str:
    """The same deck declaring ``medical``, the Breathe marker removed unless ``keep_marker``."""
    html = html.replace(DECLARED_BREATHE, DECLARED_MEDICAL, 1)
    return html if keep_marker else html.replace(MARKER_LINE, "", 1)


def legacy_deck() -> str:
    """LEGACY: 3 slides declaring medical, medical token, Breathe classes, a decoration block, a cds-tile, no marker."""
    deck = breathe_deck(
        breathe_slide(
            "Burden",
            '<i class="med-ico med-ico-scope-ring med-s52"></i><div class="cds-tile"></div>',
            background="split-s1",
            page=2,
        ),
        breathe_slide("Delays", "<p>Late diagnosis.</p>", background="deep-s1", page=3),
    )
    return as_medical(deck)


def wcbip_or_skip() -> str:
    """The private WCBIP deck (constraint 3.3: never committed), or skip when it is not on this machine."""
    if not WCBIP.is_file():
        pytest.skip(f"private deck absent: {WCBIP}")
    return WCBIP.read_text(encoding="utf-8")
