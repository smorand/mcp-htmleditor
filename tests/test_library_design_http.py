"""The design system on the library pages (SPEC-0025, app-design): covers, theme file, no inline style.

The second channel of the cover refusals is the bytes received: a refused person gets no picture byte.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from mcp_htmleditor.library.covers import first_cover
from tests import library_support
from tests.deck_support import build_deck
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    CAROL,
    DAN,
    PNEUMO,
    PNG_1X1,
    FakeGoogle,
    Presentation,
    RunningLibrary,
    signed_in,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)
BOB = "bob.nobody@gmail.com"


def picture(size: int = 3_000, kind: str = "png") -> tuple[bytes, str]:
    """A data address of ``size`` base64 characters (padded after a real PNG header) and the bytes it holds."""
    raw = (PNG_1X1 + b"\x00" * (size * 3 // 4))[: size * 3 // 4]
    return raw, f"data:image/{kind};base64,{base64.b64encode(raw).decode()}"


COVER_IMAGE = re.compile(r'<img[^>]*src="data:[^"]*"[^>]*>')  # every embedded picture of the template deck


def deck_with(*sources: str) -> bytes:
    """A real deck without its own pictures whose first slide holds ``<img>`` elements for ``sources``."""
    images = "".join(f'<img src="{source}" alt="">' for source in sources)
    text = COVER_IMAGE.sub("", build_deck("ei", ("Cover", "Two", "Three")))
    opening = re.search(r'<article[^>]*data-type="slide"[^>]*>', text)
    assert opening is not None
    return (text[: opening.end()] + images + text[opening.end() :]).encode()


@pytest.fixture
def gallery(library_server: START, fake_google: FakeGoogle) -> tuple[RunningLibrary, dict[str, str], FakeGoogle]:
    running = library_server(fake_google)
    ids = running.builder.standard()
    return running, ids, fake_google


def make(running: RunningLibrary, ids: dict[str, str], name: str, data: bytes) -> Presentation:
    deck = running.builder.presentation(ids[CARDIOLOGY], name, size=1, modified=MODIFIED, slides=1)
    deck.path.write_bytes(data)
    return deck


def test_first_cover_is_the_largest_raster_picture_of_the_first_slide_only() -> None:
    small, small_uri = picture(2_100)
    large, large_uri = picture(6_000)
    _other, other_uri = picture(9_000)
    first_slide = COVER_IMAGE.sub("", build_deck("ei", ("A", "B")))
    first_slide = first_slide.replace("</article>", f'<img src="{small_uri}"><img src="{large_uri}"></article>', 1)
    second = first_slide.index("</article>") + len("</article>")
    first_slide = (
        first_slide[:second] + f'<article data-type="slide"><img src="{other_uri}"></article>' + first_slide[second:]
    )

    cover = first_cover(first_slide)

    assert cover is not None
    assert (cover.media_type, cover.data) == ("image/png", large)
    assert small != large


@pytest.mark.parametrize(
    "text",
    ["", "<html><body>no slide</body></html>", build_deck("ei", ("A",))],
    ids=["empty", "no-slide", "no-picture-after-removal"],
)
def test_first_cover_is_none_without_a_usable_picture(text: str) -> None:
    stripped = re.sub(r'<img[^>]*src="data:[^"]*"[^>]*>', "", text)
    assert first_cover(stripped) is None


def test_first_cover_ignores_icons_svg_and_broken_base64() -> None:
    _tiny, tiny_uri = picture(300)
    svg = "data:image/svg+xml;base64," + base64.b64encode(b"<svg onload='alert(1)'>" + b"x" * 4_000).decode()
    broken = "data:image/png;base64," + "A" * 2_500 + "!!!"
    deck = build_deck("ei", ("A", "B")).replace(
        "</article>", f'<img src="{tiny_uri}"><img src="{svg}"><img src="{broken}"></article>', 1
    )
    stripped = COVER_IMAGE.sub("", deck)

    assert first_cover(stripped) is None


def test_the_cover_route_serves_the_picture_to_every_role_and_refuses_the_rest(
    gallery: tuple[RunningLibrary, dict[str, str], FakeGoogle],
) -> None:
    running, ids, google = gallery
    raw, uri = picture(4_000, "jpeg")
    deck = make(running, ids, "With Cover", deck_with(uri))
    for email in (DAN, CAROL, ADMIN):
        reply = signed_in(running, google, email).open(f"/cover/{deck.id}")
        assert reply.status == 200, email
        assert reply.headers["content-type"] == "image/jpeg"
        assert reply.headers["x-content-type-options"] == "nosniff"
        assert reply.body == raw

    other = signed_in(running, google, BOB).open(f"/cover/{deck.id}")
    visitor = running.browser().open(f"/cover/{deck.id}")
    unknown = signed_in(running, google, ADMIN).open("/cover/" + "0" * 32)

    assert other.status == 403 and raw[:20] not in other.body
    assert visitor.status == 200 and b"Sign in with Google" in visitor.body and raw[:20] not in visitor.body
    assert unknown.status == 403


def test_a_deck_without_a_picture_has_no_cover_and_a_replacement_changes_it(
    gallery: tuple[RunningLibrary, dict[str, str], FakeGoogle],
) -> None:
    running, ids, google = gallery
    deck = make(running, ids, "Plain", deck_with())
    dan = signed_in(running, google, DAN)
    assert dan.open(f"/cover/{deck.id}").status == 404

    first, first_uri = picture(3_000)
    assert dan.upload(ids[CARDIOLOGY], "Plain.html", deck_with(first_uri), replace=True).status == 201
    assert dan.open(f"/cover/{deck.id}").body == first
    second, second_uri = picture(5_000)
    assert dan.upload(ids[CARDIOLOGY], "Plain.html", deck_with(second_uri), replace=True).status == 201
    assert dan.open(f"/cover/{deck.id}").body == second  # the cache follows the file, not the first answer


def test_the_cover_cache_is_bounded(gallery: tuple[RunningLibrary, dict[str, str], FakeGoogle]) -> None:
    running, ids, _google = gallery
    library = running.server.library
    decks = [make(running, ids, f"Deck {number}", deck_with()) for number in range(70)]

    for deck in decks:
        assert library.cover(deck.id) is None

    assert len(library._covers) <= 64


def test_the_pages_carry_no_style_attribute_and_name_only_files_of_the_site(
    gallery: tuple[RunningLibrary, dict[str, str], FakeGoogle],
) -> None:
    """The page policy allows no inline style and no external file: a ``style=`` or an absolute address would be
    refused by the browser and break the design."""
    running, ids, google = gallery
    make(running, ids, "Deck", deck_with())
    admin = signed_in(running, google, ADMIN)
    dan = signed_in(running, google, DAN)
    pages = [
        running.browser().open("/").text,
        admin.open("/").text,
        admin.open("/admin").text,
        dan.open(f"/f/{ids[CARDIOLOGY]}").text,
        signed_in(running, google, BOB).open("/").text,
    ]

    for page in pages:
        assert " style=" not in page
        assert "<style" not in page
        assert not re.search(r'(?:src|href)="(?:https?:)?//', page)
        assert not re.search(r"<script(?![^>]*\bsrc=)", page)  # no inline script
    assert admin.open("/").text.count("data-theme-toggle") == 1


def test_the_theme_script_and_the_stylesheet_are_public_and_know_only_two_themes(
    gallery: tuple[RunningLibrary, dict[str, str], FakeGoogle],
) -> None:
    running, _ids, _google = gallery
    client = running.client()

    theme = client.get("/lib/theme.js")
    stylesheet = client.get("/lib/library.css")

    assert theme.status == 200 and theme.headers["content-type"].startswith("application/javascript")
    assert b"library-theme" in theme.body and b"prefers-color-scheme" in theme.body
    assert stylesheet.status == 200
    text = stylesheet.text
    assert '[data-theme="dark"]' in text and ':root,[data-theme="light"]' in text
    assert 'data-theme="green"' not in text and "carbon" not in text
    assert "@import" not in text and "url(" not in text


def test_the_home_page_counts_the_presentations_of_each_folder(
    gallery: tuple[RunningLibrary, dict[str, str], FakeGoogle],
) -> None:
    running, ids, google = gallery
    make(running, ids, "One", deck_with())
    make(running, ids, "Two", deck_with())
    rows = signed_in(running, google, ADMIN).open("/").text

    assert "2 presentations" in rows
    assert "0 presentations" in rows  # Pneumo and WCBIP are empty
    running.builder.presentation(ids[PNEUMO], "Only", size=1, modified=MODIFIED, slides=1)
    assert "1 presentation<" in signed_in(running, google, ADMIN).open("/").text
