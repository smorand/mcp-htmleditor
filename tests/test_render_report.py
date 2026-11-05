"""US-0063: layout report for one slide (SPEC-0008 E2E-003, E2E-013, E2E-014, E2E-024 and the measures)."""

from __future__ import annotations

import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from mcp_htmleditor.render import RenderProblem
from mcp_htmleditor.render.problems import RawSlide, build_problems, final_line, format_line
from tests import render_support as rs
from tests.deck_support import run_cli as _run_cli
from tests.deck_support import write_deck

PROBE = '<div class="probe" style="position:absolute; left:940px; top:10px; width:100px; height:20px">x</div>'


def run_cli(*args: str) -> tuple[str, str, int]:
    """Run the CLI in its own thread (the Playwright sync API refuses a running event loop)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_cli, *args).result()


@pytest.fixture(autouse=True)
def out_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path / "htmleditor-render"


def _deck(tmp_path, html: str | None = None) -> str:
    return write_deck(tmp_path / "DECK-EI.html", html if html is not None else rs.ei_deck_html())


def _article_style(html: str, slide_id: str, style: str) -> str:
    return re.sub(rf'(<article\b[^>]*\bid="{slide_id}")', rf'\1 style="{style}"', html, count=1)


def _lines(stdout: str) -> list[str]:
    return stdout.splitlines()


# pure tests


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, "report: OK"), (1, "report: 1 problem"), (2, "report: 2 problems"), (12, "report: 12 problems")],
)
def test_final_line(count, expected):
    assert final_line(count) == expected


def test_format_line():
    problem = RenderProblem("clipped", "slide-5", "div.probe is outside the slide frame")
    assert format_line(problem) == "clipped slide-5: div.probe is outside the slide frame"


def test_no_overflow_at_540():
    assert build_problems([RawSlide("slide-1", 1, 540, (), ())]) == []


def test_overflow_at_541():
    problems = build_problems([RawSlide("slide-1", 1, 541, (), ())])
    assert problems == [RenderProblem("overflow", "slide-1", "content is 541px tall, the slide is 540px")]


def test_clipped_lines_come_after_the_overflow_line():
    problems = build_problems([RawSlide("slide-1", 1, 600, ("p", "div.a"), ())])
    assert [(p.kind, p.message) for p in problems] == [
        ("overflow", "content is 600px tall, the slide is 540px"),
        ("clipped", "p is outside the slide frame"),
        ("clipped", "div.a is outside the slide frame"),
    ]


def test_slide_order_then_kind_order_then_dash_first():
    slides = [RawSlide("slide-2", 2, 600, ("p",), ()), RawSlide("slide-1", 1, 600, (), ())]
    extra = [RenderProblem("script", "-", "Error: boom"), RenderProblem("image", "slide-2", "a.png did not load")]
    problems = build_problems(slides, images=extra[1:], errors=extra[:1])
    assert [(p.slide, p.kind) for p in problems] == [
        ("-", "script"),
        ("slide-1", "overflow"),
        ("slide-2", "image"),
        ("slide-2", "overflow"),
        ("slide-2", "clipped"),
    ]


# browser tests


@rs.needs_chromium
def test_clean_report(tmp_path, out_dir):
    file = _deck(tmp_path)
    stdout, stderr, status = run_cli("render", file, "--slide", "slide-2", "--report")
    assert (stdout, stderr, status) == (
        f"Rendered slide-2 to {out_dir / 'DECK-EI-slide-2.png'} (480x270)\nreport: OK\n",
        "",
        0,
    )


@rs.needs_chromium
def test_clipped_element(tmp_path):
    html = _article_style(rs.ei_deck_html(), "slide-5", "position:relative")
    file = _deck(tmp_path, rs.inject_in_body(html, "slide-5", PROBE))
    stdout, _, status = run_cli("render", file, "--slide", "slide-5", "--report")
    lines = _lines(stdout)
    assert lines[0].startswith("Rendered slide-5 to ")
    assert lines[1:] == ["clipped slide-5: div.probe is outside the slide frame", "report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_page_number_outside_the_frame(tmp_path):
    html = rs.ei_deck_html()
    start = html.index('id="slide-3"')
    end = html.index("</article>", start)
    part = html[start:end].replace(
        '<span class="slide-foot-page">', '<span class="slide-foot-page" style="position:relative; left:920px">', 1
    )
    file = _deck(tmp_path, html[:start] + part + html[end:])
    stdout, _, status = run_cli("render", file, "--slide", "slide-3", "--report")
    assert _lines(stdout)[1:] == [
        "clipped slide-3: span.slide-foot-page is outside the slide frame",
        "report: 1 problem",
    ]
    assert status == 1


@rs.needs_chromium
def test_file_untouched(tmp_path):
    file = _deck(tmp_path)
    os.utime(file, (1_000_000_000, 1_000_000_000))
    before = (Path(file).read_bytes(), Path(file).stat().st_mtime_ns)
    assert run_cli("render", file, "--report")[2] == 0
    assert (Path(file).read_bytes(), Path(file).stat().st_mtime_ns) == before


@pytest.mark.parametrize(
    ("snippet", "line"),
    [
        ('<p style="position:absolute; left:950px">x</p>', "p is outside the slide frame"),
        ('<div class="a b" style="position:absolute; left:950px">x</div>', "div.a.b is outside the slide frame"),
        (
            '<div class="outer" style="position:absolute; left:950px">x<span class="inner">y</span></div>',
            "div.outer is outside the slide frame",
        ),
    ],
)
@rs.needs_chromium
def test_selector_format(tmp_path, snippet, line):
    html = _article_style(rs.ei_deck_html(), "slide-2", "position:relative")
    file = _deck(tmp_path, rs.inject_in_body(html, "slide-2", snippet))
    stdout, _, status = run_cli("render", file, "--slide", "slide-2", "--report")
    assert _lines(stdout)[1:] == [f"clipped slide-2: {line}", "report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_tall_body_block_is_overflow_without_clipped(tmp_path):
    html = rs.inject_in_body(rs.ei_deck_html(), "slide-4", '<div style="height:700px">x</div>')
    file = _deck(tmp_path, html)
    stdout, _, status = run_cli("render", file, "--slide", "slide-4", "--report")
    lines = _lines(stdout)
    assert re.fullmatch(r"overflow slide-4: content is (\d+)px tall, the slide is 540px", lines[1])
    assert int(re.findall(r"\d+", lines[1])[1]) >= 700
    assert lines[2:] == ["report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_other_slides_are_not_listed(tmp_path):
    html = rs.inject_in_body(rs.ei_deck_html(), "slide-4", '<div style="height:700px">x</div>')
    file = _deck(tmp_path, html)
    stdout, _, status = run_cli("render", file, "--slide", "slide-2", "--report")
    assert _lines(stdout)[1:] == ["report: OK"]
    assert status == 0


@rs.needs_chromium
def test_rendered_line_comes_first_and_without_report_nothing_more(tmp_path):
    file = _deck(tmp_path)
    stdout, _, status = run_cli("render", file)
    assert len(_lines(stdout)) == 1
    assert status == 0
