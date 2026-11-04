"""Tests for ``mcp-htmleditor get-slide`` and the byte offset scanner (SPEC-0007 FR-NEW-002, US-0036)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from mcp_htmleditor.deck.read import get_slide as get_slide_text
from mcp_htmleditor.deck.scan import Node, hide_images, large_images, scan, slide_range

from .deck_support import (
    EI_TITLES,
    build_deck,
    deck_carbon,
    deck_ei,
    doc_perso,
    run_cli,
    write_deck,
)

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
DATA_PREFIX = "data:image/png;base64,"
SLIDE_3_OPEN = '<article class="slide" id="slide-3"'


def img_with_source_length(length: int) -> str:
    """Return an ``img`` whose ``src`` value is exactly ``length`` characters."""
    return f'<img src="{DATA_PREFIX}{"A" * (length - len(DATA_PREFIX))}" alt="x">'


def slides_page(*slides: str) -> str:
    """Wrap slide inner markup in articles ``slide-0``..; the result is a minimal presentation."""
    articles = "".join(f'<article id="slide-{i}" data-type="slide">{body}</article>' for i, body in enumerate(slides))
    return f"<html><body>{articles}</body></html>"


def get_slide(tmp_path: Path, content: str, slide: str) -> tuple[str, str, int]:
    """Write ``content`` and run ``get-slide`` on it."""
    return run_cli("get-slide", write_deck(tmp_path / "f.html", content), slide)


def test_deck_get_slide_unknown_id(tmp_path: Path) -> None:
    """E2E-012: an unknown id lists every valid id."""
    path = write_deck(tmp_path / "carbon.html", deck_carbon())
    stdout, stderr, code = run_cli("get-slide", path, "slide-9")
    expected = 'error: Unknown slide id "slide-9". Valid ids: slide-0, slide-1, slide-2, slide-3, slide-4\n'
    assert (stdout, stderr, code) == ("", expected, 1)


def test_deck_get_slide_two_megabyte_image_stays_small(tmp_path: Path) -> None:
    """E2E-031: a 2 MB image does not reach the outline or the slide HTML."""
    content = build_deck("ei", EI_TITLES, image_chars=2_000_000, image_slide=3)
    path = write_deck(tmp_path / "big.html", content)
    outline_out, _, outline_code = run_cli("outline", path)
    slide_out, _, slide_code = run_cli("get-slide", path, "slide-3")
    assert (outline_code, slide_code) == (0, 0)
    assert len(outline_out.encode()) < 20_000
    assert len(slide_out.encode()) < 5_000


def test_deck_get_slide_replaces_the_image_only(tmp_path: Path) -> None:
    """The output is the file slice of the slide with only the ``src`` value changed."""
    content = deck_ei()
    start = content.index(SLIDE_3_OPEN)
    end = content.index("</article>", start) + len("</article>")
    expected = content[start:end].replace(DATA_PREFIX + "A" * 1500, "data:ref:img-1")
    stdout, stderr, code = get_slide(tmp_path, content, "slide-3")
    assert (stderr, code) == ("", 0)
    assert stdout == expected + "\n"
    assert stdout.startswith("<article")
    assert 'id="slide-3"' in stdout
    assert "data:ref:img-1" in stdout
    assert "base64" not in stdout
    assert "Contexte" not in stdout


def test_deck_get_slide_numbers_images_in_document_order(tmp_path: Path) -> None:
    """Two large images become img-1 then img-2; a small one is kept."""
    small = f'<img src="{DATA_PREFIX}AAAA" alt="s">'
    page = slides_page("x", f"{img_with_source_length(1500)}{small}{img_with_source_length(1200)}")
    stdout, _, code = get_slide(tmp_path, page, "slide-1")
    assert code == 0
    assert stdout.index("data:ref:img-1") < stdout.index("data:ref:img-2")
    assert f"{DATA_PREFIX}AAAA" in stdout
    assert "A" * 100 not in stdout


def test_deck_get_slide_threshold_is_1000_characters() -> None:
    """Exactly 1 000 characters stays, 1 001 is replaced."""
    at_limit = f"<p>{img_with_source_length(1000)}</p>"
    over_limit = f"<p>{img_with_source_length(1001)}</p>"
    assert hide_images(at_limit) == at_limit
    assert large_images(at_limit) == []
    assert hide_images(over_limit) == '<p><img src="data:ref:img-1" alt="x"></p>'
    ((start, end),) = large_images(over_limit)
    assert over_limit[start:end].startswith(DATA_PREFIX)
    assert end - start == 1001


def test_deck_get_slide_ignores_other_attributes_and_quotes() -> None:
    """Only the ``src`` value of an ``img`` counts; single quotes and look alike attributes work."""
    big = DATA_PREFIX + "A" * 1100
    text = f"<img alt=\"src='{big}'\" data-src='{big}' src='{big}'><a href=\"{big}\">l</a>"
    assert (
        hide_images(text) == f"<img alt=\"src='{big}'\" data-src='{big}' src='data:ref:img-1'><a href=\"{big}\">l</a>"
    )


def test_deck_scan_offsets_and_closing_rules() -> None:
    """Offsets of a nested document, a void element, a self closing tag and an unclosed ``p``."""
    text = "<div>\n <article><br><x/><p>a</article></div>"
    nodes = {n.tag: n for n in scan(text)}
    assert set(nodes) == {"div", "article", "br", "x", "p"}
    article = nodes["article"]
    assert text[article.start : article.start_end] == "<article>"
    assert text[article.end_start : article.end_end] == "</article>"
    assert (article.line, article.col) == (2, 1)
    for tag in ("br", "x"):
        node = nodes[tag]
        assert node.end_start == node.end_end == node.start_end
    unclosed = nodes["p"]
    assert unclosed.end_start == unclosed.end_end == article.end_start
    assert [n.tag for n in scan(text)] == ["div", "article", "br", "x", "p"]


def test_deck_scan_ignores_an_end_tag_without_open_element() -> None:
    """A stray end tag does not pop anything."""
    nodes = scan("<div>a</span>b</div>")
    assert len(nodes) == 1
    assert nodes[0].end_end == len("<div>a</span>b</div>")


def test_deck_scan_unclosed_element_ends_at_end_of_text() -> None:
    """An element never closed runs to the end of the text."""
    text = "<div><p>a"
    nodes = scan(text)
    assert [(n.tag, n.end_start, n.end_end) for n in nodes] == [("div", 9, 9), ("p", 9, 9)]


def test_deck_scan_slide_range_is_the_element() -> None:
    """The slide range spans from ``<`` to after the end tag."""
    text = "<body><article>a</article>tail</body>"
    nodes = scan(text)
    article = next(n for n in nodes if n.tag == "article")
    start, end = slide_range(nodes, article)
    assert text[start:end] == "<article>a</article>"


@pytest.mark.parametrize("path", sorted(TEMPLATES.rglob("*.html")), ids=lambda p: p.name)
def test_deck_scan_agrees_with_beautifulsoup_on_every_template(path: Path) -> None:
    """Every BeautifulSoup tag has a scanner node at ``(sourceline, sourcepos)`` with the same name."""
    text = path.read_text(encoding="utf-8")
    by_position: dict[tuple[int, int], Node] = {(n.line, n.col): n for n in scan(text)}
    tags = BeautifulSoup(text, "html.parser").find_all(True)
    assert tags
    for tag in tags:
        node = by_position.get((tag.sourceline, tag.sourcepos))
        assert node is not None, (tag.name, tag.sourceline, tag.sourcepos)
        assert node.tag == tag.name
        assert text[node.start : node.start + 1] == "<"
    assert len(by_position) == len(tags)


def test_deck_get_slide_unclosed_paragraph_does_not_move_the_end(tmp_path: Path) -> None:
    """An unclosed ``p`` inside a slide leaves the slide end on its own end tag."""
    page = slides_page("<p>one<div>two</div>", "next")
    stdout, _, code = get_slide(tmp_path, page, "slide-0")
    assert code == 0
    assert stdout == '<article id="slide-0" data-type="slide"><p>one<div>two</div></article>\n'


def test_deck_get_slide_script_text_is_not_markup(tmp_path: Path) -> None:
    """A script string holding ``</article>`` does not end the slide."""
    body = '<script>var s = "</article>";</script><p>after</p>'
    stdout, _, code = get_slide(tmp_path, slides_page(body), "slide-0")
    assert code == 0
    assert stdout == f'<article id="slide-0" data-type="slide">{body}</article>\n'


def test_deck_get_slide_keeps_crlf(tmp_path: Path) -> None:
    """Line endings of a CRLF file are returned untouched."""
    content = deck_carbon().replace("\n", "\r\n")
    path = tmp_path / "crlf.html"
    path.write_bytes(content.encode())
    stdout = get_slide_text(str(path), "slide-2")  # the CLI runner translates line endings itself
    assert "\r\n" in stdout
    start = content.index('id="slide-2"')
    start = content.rindex("<article", 0, start)
    end = content.index("</article>", start) + len("</article>")
    assert stdout == content[start:end]


def test_deck_get_slide_comment_between_slides_belongs_to_none(tmp_path: Path) -> None:
    """A comment between two slides is outside both ranges."""
    page = slides_page("a", "b").replace("</article><article", "</article><!-- between --><article")
    for slide in ("slide-0", "slide-1"):
        stdout, _, code = get_slide(tmp_path, page, slide)
        assert code == 0
        assert "between" not in stdout
    nodes = scan(page)
    ranges = [slide_range(nodes, n) for n in nodes if n.tag == "article"]
    comment = page.index("<!--")
    assert not any(start <= comment < end for start, end in ranges)


def test_deck_get_slide_document_is_refused(tmp_path: Path) -> None:
    """A file without slides cannot give a slide."""
    path = write_deck(tmp_path / "doc.html", doc_perso())
    stdout, stderr, code = run_cli("get-slide", path, "slide-0")
    assert (stdout, stderr, code) == ("", f"error: get_slide needs a presentation: {path}\n", 1)


def test_deck_get_slide_missing_file() -> None:
    """A missing file is reported as given."""
    stdout, stderr, code = run_cli("get-slide", "ghost.html", "slide-0")
    assert (stdout, stderr, code) == ("", "error: File not found: ghost.html\n", 1)


def test_deck_get_slide_uses_positional_id_when_slide_has_none(tmp_path: Path) -> None:
    """A slide without ``data-id`` or ``id`` is addressed as in the outline: ``slide-<index>``."""
    page = '<html><body><article data-type="slide">a</article><article data-type="slide">b</article></body></html>'
    outline_out, _, _ = run_cli("outline", write_deck(tmp_path / "f.html", page))
    ids = [s["id"] for s in json.loads(outline_out)["slides"]]
    assert ids == ["slide-0", "slide-1"]
    stdout, _, code = get_slide(tmp_path, page, "slide-1")
    assert (stdout, code) == ('<article data-type="slide">b</article>\n', 0)
