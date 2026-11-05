"""US-0064: report only across the deck (SPEC-0008 E2E-004, E2E-010, E2E-012, E2E-018 and the extra tests)."""

from __future__ import annotations

import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tests import render_support as rs
from tests.deck_support import doc_perso, write_deck
from tests.deck_support import run_cli as _run_cli

CONFLICT = "Error: --report-only cannot be used with --slide, --scale or --report"
BLOCK = '<div style="height:700px">x</div>'
OVERFLOW = re.compile(r"overflow (slide-\d+): content is (\d+)px tall, the slide is 540px")


def run_cli(*args: str) -> tuple[str, str, int]:
    """Run the CLI in its own thread (the Playwright sync API refuses a running event loop)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_cli, *args).result()


@pytest.fixture(autouse=True)
def out_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    return tmp_path / "tmp" / "htmleditor-render"


def _deck(tmp_path, html: str | None = None, name: str = "DECK-EI") -> str:
    return write_deck(tmp_path / f"{name}.html", html if html is not None else rs.ei_deck_html())


# unit tests


def test_check_options_accepts_report_only_alone():
    from mcp_htmleditor.render.options import check_options

    check_options(slide=None, scale=None, report=False, report_only=True)


@pytest.mark.parametrize(
    ("slide", "scale", "report"),
    [(None, None, False), ("slide-1", None, False), (None, "0.7", False), (None, None, True), ("a", 0.5, True)],
)
def test_check_options_accepts_the_others_without_report_only(slide, scale, report):
    from mcp_htmleditor.render.options import check_options

    check_options(slide=slide, scale=scale, report=report, report_only=False)


@pytest.mark.parametrize(
    ("slide", "scale", "report"),
    [("slide-1", None, False), (None, "0.7", False), (None, 0.5, False), (None, "0.5", False), (None, None, True)],
)
def test_check_options_refuses_a_conflict(slide, scale, report):
    from mcp_htmleditor.render import RenderUsageError
    from mcp_htmleditor.render.options import check_options

    with pytest.raises(RenderUsageError, match=r"^--report-only cannot be used with --slide, --scale or --report$"):
        check_options(slide=slide, scale=scale, report=report, report_only=True)


# usage errors and presentation check, no browser needed


@pytest.mark.parametrize(
    "extra",
    [("--slide", "slide-1"), ("--scale", "0.7"), ("--scale", "0.5"), ("--report",)],
)
def test_conflict_table(tmp_path, extra):
    stdout, stderr, status = run_cli("render", _deck(tmp_path), "--report-only", *extra)
    assert (stdout, stderr.strip(), status) == ("", CONFLICT, 2)


def test_e2e_018_slide_conflict(tmp_path):
    stdout, stderr, status = run_cli("render", _deck(tmp_path), "--report-only", "--slide", "slide-1")
    assert (stdout, stderr, status) == ("", CONFLICT + "\n", 2)


def test_conflict_comes_before_the_other_checks(tmp_path):
    stdout, stderr, status = run_cli("render", str(tmp_path / "missing.html"), "--report-only", "--scale", "abc")
    assert (stdout, stderr.strip(), status) == ("", CONFLICT, 2)


def test_other_errors_keep_their_prefix(tmp_path):
    stdout, stderr, status = run_cli("render", str(tmp_path / "missing.html"), "--report-only")
    assert stdout == ""
    assert stderr.startswith("error: ")
    assert status == 1


def test_e2e_010_not_a_presentation(tmp_path, monkeypatch):
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "empty"))
    file = write_deck(tmp_path / "DOC-PERSO.html", doc_perso())
    for args in (("render", file), ("render", file, "--report-only")):
        stdout, stderr, status = run_cli(*args)
        assert (stdout, stderr.strip(), status) == ("", f"error: render needs a presentation: {file}", 1)


# browser tests


@rs.needs_chromium
def test_e2e_004_clean_report_only(tmp_path, out_dir):
    stdout, stderr, status = run_cli("render", _deck(tmp_path), "--report-only")
    assert (stdout, stderr, status) == ("report: OK\n", "", 0)
    assert not out_dir.exists()


@rs.needs_chromium
def test_deck_ei_and_deck_med_are_clean(tmp_path):
    for name, html in (("DECK-EI", rs.ei_deck_html()), ("DECK-MED", rs.med_deck_html())):
        stdout, _, status = run_cli("render", _deck(tmp_path, html, name), "--report-only")
        assert (name, stdout, status) == (name, "report: OK\n", 0)


@rs.needs_chromium
def test_e2e_012_block_in_the_body(tmp_path):
    original = rs.ei_deck_html()
    file = _deck(tmp_path, rs.inject_in_body(original, "slide-4", BLOCK))
    before = Path(file).read_bytes()
    stdout, _, status = run_cli("render", file, "--report-only")
    lines = stdout.splitlines()
    match = OVERFLOW.fullmatch(lines[0])
    assert match and match.group(1) == "slide-4" and int(match.group(2)) >= 700
    assert lines[1:] == ["report: 1 problem"]
    assert status == 1
    assert Path(file).read_bytes() == before


@rs.needs_chromium
def test_e2e_012_block_after_the_inner_frame(tmp_path):
    file = _deck(tmp_path, rs.append_to_slide(rs.ei_deck_html(), "slide-4", BLOCK))
    stdout, _, status = run_cli("render", file, "--report-only")
    lines = stdout.splitlines()
    match = OVERFLOW.fullmatch(lines[0])
    assert match and match.group(1) == "slide-4" and int(match.group(2)) >= 700
    assert lines[1:] == ["report: 1 problem"]
    assert status == 1


@rs.needs_chromium
def test_e2e_012_small_body_gives_no_overflow(tmp_path):
    file = _deck(tmp_path, rs.inject_in_body(rs.ei_deck_html(), "slide-4", '<div style="height:300px"></div>'))
    stdout, _, status = run_cli("render", file, "--report-only")
    assert "overflow" not in stdout
    assert (stdout, status) == ("report: OK\n", 0)


@rs.needs_chromium
def test_two_overflows_in_slide_order(tmp_path):
    html = rs.inject_in_body(rs.inject_in_body(rs.ei_deck_html(), "slide-4", BLOCK), "slide-1", BLOCK)
    stdout, _, status = run_cli("render", _deck(tmp_path, html), "--report-only")
    lines = stdout.splitlines()
    assert [OVERFLOW.fullmatch(line).group(1) for line in lines[:2]] == ["slide-1", "slide-4"]  # type: ignore[union-attr]
    assert lines[2:] == ["report: 2 problems"]
    assert status == 1


@rs.needs_chromium
def test_output_directory_untouched(tmp_path, out_dir):
    out_dir.mkdir(parents=True)
    keep = out_dir / "DECK-EI-slide-5.png"
    keep.write_bytes(rs.tiny_png_bytes())
    os.utime(keep, (1_000_000_000, 1_000_000_000))
    before = (keep.read_bytes(), keep.stat().st_mtime_ns)
    assert run_cli("render", _deck(tmp_path), "--report-only")[2] == 0
    assert sorted(p.name for p in out_dir.iterdir()) == ["DECK-EI-slide-5.png"]
    assert (keep.read_bytes(), keep.stat().st_mtime_ns) == before
