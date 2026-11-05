"""US-0065: font, script and image problems (SPEC-0008 E2E-015, E2E-016, E2E-017, E2E-019 and the extra tests)."""

from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from mcp_htmleditor.render import RenderProblem
from mcp_htmleditor.render.problems import RawSlide, build_problems, shorten_source
from tests import render_support as rs
from tests.deck_support import TINY_PNG, write_deck
from tests.deck_support import run_cli as _run_cli

BLOCK = '<div style="height:700px">x</div>'
MISSING = '<img src="pics/missing.png">'
FONT_LINE = 'font slide-1: "NoSuchFont" is not available, fallback used'
IMAGE_LINE = "image slide-6: pics/missing.png did not load"
THROW_BOOM = 'throw new Error("boom");'
LATE_OBSERVER = (
    "new MutationObserver(() => {"
    " if (document.getElementById('slide-3').classList.contains('active')) throw new Error('late');"
    "}).observe(document.getElementById('slide-3'), {attributes: true, attributeFilter: ['class']});"
)


def run_cli(*args: str) -> tuple[str, str, int]:
    """Run the CLI in its own thread (the Playwright sync API refuses a running event loop)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_cli, *args).result()


@pytest.fixture(autouse=True)
def out_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    return tmp_path / "tmp" / "htmleditor-render"


def _deck(tmp_path, html: str | None = None) -> str:
    return write_deck(tmp_path / "DECK-EI.html", html if html is not None else rs.ei_deck_html())


def _fonts(*families: str) -> str:
    return "".join(f'<p style="font-family:{family}">Texte</p>' for family in families)


def _font_deck(*families: str) -> str:
    return rs.inject_in_body(rs.ei_deck_html(), "slide-1", _fonts(*families))


def _report_only(tmp_path, html: str) -> tuple[list[str], int]:
    stdout, _, status = run_cli("render", _deck(tmp_path, html), "--report-only")
    return stdout.splitlines(), status


# unit tests


def test_shorten_source_cuts_a_long_data_address():
    src = "data:image/png;base64," + "A" * 38
    assert len(src) == 60
    assert shorten_source(src) == src[:40] + "..."


def test_shorten_source_keeps_a_short_data_address_and_a_path():
    short = "data:image/png;base64," + "A" * 8
    assert len(short) == 30
    assert shorten_source(short) == short
    assert shorten_source("pics/missing.png") == "pics/missing.png"


def test_shorten_source_keeps_a_long_path():
    path = "pics/" + "a" * 60 + ".png"
    assert shorten_source(path) == path


def test_fonts_become_problems_in_document_order():
    problems = build_problems([RawSlide("slide-1", 1, 100, (), ("Aaa", "Bbb"))])
    assert [(p.kind, p.message) for p in problems] == [
        ("font", '"Aaa" is not available, fallback used'),
        ("font", '"Bbb" is not available, fallback used'),
    ]


def test_ordering_of_the_five_kinds_on_two_slides_and_a_dash_problem():
    slides = [
        RawSlide("slide-2", 2, 600, ("p",), ("F2",)),
        RawSlide("slide-1", 1, 600, ("p",), ("F1",)),
    ]
    errors = [
        RenderProblem("script", "slide-2", "Error: b"),
        RenderProblem("script", "-", "Error: a"),
        RenderProblem("script", "slide-1", "Error: c"),
    ]
    images = [
        RenderProblem("image", "slide-2", "b.png did not load"),
        RenderProblem("image", "slide-1", "a.png did not load"),
    ]
    problems = build_problems(slides, images=images, errors=errors)
    assert [(p.slide, p.kind) for p in problems] == [
        ("-", "script"),
        ("slide-1", "script"),
        ("slide-1", "image"),
        ("slide-1", "font"),
        ("slide-1", "overflow"),
        ("slide-1", "clipped"),
        ("slide-2", "script"),
        ("slide-2", "image"),
        ("slide-2", "font"),
        ("slide-2", "overflow"),
        ("slide-2", "clipped"),
    ]


# browser tests: the four acceptance tests


@rs.needs_chromium
def test_e2e_015_missing_font(tmp_path):
    html = _font_deck("NoSuchFont, sans-serif", "NoSuchFont, sans-serif")
    stdout, _, status = run_cli("render", _deck(tmp_path, html), "--report-only")
    assert stdout.splitlines() == [FONT_LINE, "report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_e2e_016_script_error_at_load(tmp_path):
    html = rs.append_to_slide(rs.ei_deck_html(), "slide-2", f"<script>{THROW_BOOM}</script>")
    stdout, _, status = run_cli("render", _deck(tmp_path, html), "--slide", "slide-2", "--report")
    lines = stdout.splitlines()
    assert "script -: Error: boom" in lines
    assert lines[-1] == "report: 1 problem"
    assert status == 1


@rs.needs_chromium
def test_e2e_017_image_that_does_not_load(tmp_path):
    html = rs.inject_in_body(rs.ei_deck_html(), "slide-6", MISSING)
    lines, status = _report_only(tmp_path, html)
    assert lines == [IMAGE_LINE, "report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_e2e_019_several_problems_counted(tmp_path):
    html = rs.inject_in_body(_font_deck("NoSuchFont, sans-serif"), "slide-4", BLOCK)
    html = rs.inject_in_body(html, "slide-6", MISSING)
    lines, status = _report_only(tmp_path, html)
    assert lines[0] == FONT_LINE
    assert lines[1].startswith("overflow slide-4: content is ")
    assert lines[2:] == [IMAGE_LINE, "report: 3 problems"]
    assert status == 1


# browser tests: fonts


@rs.needs_chromium
def test_installed_name_after_a_missing_one_is_not_reported(tmp_path):
    lines, status = _report_only(tmp_path, _font_deck('"Other Fnt", Arial'))
    assert (lines, status) == (["report: OK"], 0)


@rs.needs_chromium
def test_first_missing_name_is_the_one_printed(tmp_path):
    lines, status = _report_only(tmp_path, _font_deck("'Other Fnt', NoSuchFont"))
    assert lines == ['font slide-1: "Other Fnt" is not available, fallback used', "report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_generic_family_alone_is_not_reported(tmp_path):
    lines, status = _report_only(tmp_path, _font_deck("sans-serif", "serif", "monospace", "system-ui"))
    assert (lines, status) == (["report: OK"], 0)


@rs.needs_chromium
def test_same_family_twice_gives_one_line(tmp_path):
    lines, _ = _report_only(tmp_path, _font_deck("NoSuchFont", "'NoSuchFont', serif"))
    assert lines == [FONT_LINE, "report: 1 problem"]


GONE_FACE = '<style>@font-face{font-family:"Gone";src:url(gone.woff2)}</style>'
BAD_FACE = '<style>@font-face{font-family:"BadWeb";src:url(data:font/ttf;base64,AAAA)}</style>'


def _face_deck(face: str, family: str) -> str:
    return rs.inject_in_body(rs.ei_deck_html(), "slide-1", face + _fonts(family))


@rs.needs_chromium
def test_failing_font_face_before_an_installed_name_is_not_reported(tmp_path):
    lines, status = _report_only(tmp_path, _face_deck(GONE_FACE, "Gone, Arial"))
    assert (lines, status) == (["report: OK"], 0)


@rs.needs_chromium
def test_failing_font_face_before_a_generic_is_reported(tmp_path):
    lines, status = _report_only(tmp_path, _face_deck(GONE_FACE, "Gone, sans-serif"))
    assert lines == ['font slide-1: "Gone" is not available, fallback used', "report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_failing_font_face_alone_is_reported(tmp_path):
    lines, status = _report_only(tmp_path, _face_deck(GONE_FACE, "Gone"))
    assert lines == ['font slide-1: "Gone" is not available, fallback used', "report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_font_face_with_invalid_data_is_reported_not_fatal(tmp_path):
    lines, status = _report_only(tmp_path, _face_deck(BAD_FACE, "BadWeb"))
    assert lines == ['font slide-1: "BadWeb" is not available, fallback used', "report: 1 problem"]
    assert status == 1


# browser tests: script errors


@rs.needs_chromium
def test_late_error_is_attributed_to_the_slide_shown(tmp_path):
    html = rs.add_script(rs.ei_deck_html(), LATE_OBSERVER)
    lines, status = _report_only(tmp_path, html)
    assert lines == ["script slide-3: Error: late", "report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_load_error_is_on_dash_and_repeated_error_is_listed_once(tmp_path):
    html = rs.add_script(rs.add_script(rs.ei_deck_html(), THROW_BOOM), THROW_BOOM)
    lines, status = _report_only(tmp_path, html)
    assert lines == ["script -: Error: boom", "report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_dash_comes_first_then_the_slide_error(tmp_path):
    html = rs.add_script(rs.add_script(rs.ei_deck_html(), LATE_OBSERVER), THROW_BOOM)
    lines, _ = _report_only(tmp_path, html)
    assert lines == ["script -: Error: boom", "script slide-3: Error: late", "report: 2 problems"]


# browser tests: images


@rs.needs_chromium
def test_valid_data_png_and_viewbox_only_svg_are_not_images_problems(tmp_path):
    svg = "data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'%3E%3C/svg%3E"
    small = 'style="width:10px;height:10px"'
    snippet = f'<img {small} src="data:image/png;base64,{TINY_PNG}"><img {small} src="{svg}">'
    lines, status = _report_only(tmp_path, rs.inject_in_body(rs.ei_deck_html(), "slide-6", snippet))
    assert (lines, status) == (["report: OK"], 0)


@rs.needs_chromium
def test_broken_long_data_address_is_shortened(tmp_path):
    src = "data:image/png;base64," + "QUJD" * 20
    lines, _ = _report_only(tmp_path, rs.inject_in_body(rs.ei_deck_html(), "slide-6", f'<img src="{src}">'))
    assert lines == [f"image slide-6: {src[:40]}... did not load", "report: 1 problem"]


@rs.needs_chromium
def test_report_ignores_other_slides_images_but_lists_a_load_error(tmp_path):
    html = rs.inject_in_body(rs.ei_deck_html(), "slide-6", MISSING)
    html = rs.add_script(html, THROW_BOOM)
    stdout, _, status = run_cli("render", _deck(tmp_path, html), "--slide", "slide-2", "--report")
    lines = stdout.splitlines()
    assert IMAGE_LINE not in lines
    assert lines[1:] == ["script -: Error: boom", "report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_report_lists_the_images_of_the_rendered_slide(tmp_path):
    html = rs.inject_in_body(rs.ei_deck_html(), "slide-6", MISSING)
    stdout, _, status = run_cli("render", _deck(tmp_path, html), "--slide", "slide-6", "--report")
    assert stdout.splitlines()[1:] == [IMAGE_LINE, "report: 1 problem"]
    assert status == 1
