"""US-0067: large decks and documentation (SPEC-0008 E2E-023, E2E-027, E2E-029 and the documentation checks)."""

from __future__ import annotations

import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tests import render_support as rs
from tests.deck_support import run_cli as _run_cli
from tests.deck_support import write_deck

ROOT = Path(__file__).resolve().parents[1]
SLIDE_COUNT = 40
BUDGET_SECONDS = 30.0  # FR-NEW-007


def run_cli(*args: str) -> tuple[str, str, int]:
    """Run the CLI in its own thread (the Playwright sync API refuses a running event loop)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_cli, *args).result()


def timed_cli(*args: str) -> tuple[str, str, int, float]:
    """Run the CLI and return its streams, its status and the seconds it took (``time.monotonic``)."""
    started = time.monotonic()
    stdout, stderr, status = run_cli(*args)
    return stdout, stderr, status, time.monotonic() - started


def report_seconds(record_property, name: str, seconds: float) -> None:
    """Keep the measure in the junit properties and show it with ``-s``."""
    record_property(name, f"{seconds:.2f}")
    sys.stderr.write(f"{name}: {seconds:.2f} s\n")


@pytest.fixture(autouse=True)
def out_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    return tmp_path / "tmp" / "htmleditor-render"


def _deck(tmp_path, *, with_images: bool = False) -> str:
    if with_images:
        pics = tmp_path / "pics"
        pics.mkdir()
        (pics / "ok.png").write_bytes(rs.tiny_png_bytes())
    return write_deck(tmp_path / "BIG.html", rs.big_deck(SLIDE_COUNT, with_images=with_images))


# speed on a deck of 40 slides


@rs.needs_chromium
def test_e2e_023_report_only_on_forty_slides(tmp_path, record_property):
    stdout, stderr, status, seconds = timed_cli("render", _deck(tmp_path), "--report-only")
    report_seconds(record_property, "E2E-023 report-only, 40 slides", seconds)
    assert (stdout, stderr, status) == ("report: OK\n", "", 0)
    assert seconds < BUDGET_SECONDS


@rs.needs_chromium
def test_e2e_027_report_on_the_last_slide_of_forty(tmp_path, out_dir, record_property):
    stdout, stderr, status, seconds = timed_cli("render", _deck(tmp_path), "--slide", "slide-39", "--report")
    report_seconds(record_property, "E2E-027 report slide-39, 40 slides", seconds)
    expected = out_dir / "BIG-slide-39.png"
    assert stdout == f"Rendered slide-39 to {expected} (480x270)\nreport: OK\n"
    assert (stderr, status) == ("", 0)
    assert seconds < BUDGET_SECONDS


@rs.needs_chromium
def test_e2e_029_report_only_on_forty_slides_with_images(tmp_path, record_property):
    stdout, stderr, status, seconds = timed_cli("render", _deck(tmp_path, with_images=True), "--report-only")
    report_seconds(record_property, "E2E-029 report-only, 40 slides with images", seconds)
    assert (stdout, stderr, status) == ("report: OK\n", "", 0)
    assert seconds < BUDGET_SECONDS


# documentation


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_readme_documents_render_and_the_browser_install():
    readme = _text("README.md")
    assert "mcp-htmleditor render" in readme
    assert "make install-browser" in readme


def test_agents_indexes_the_render_notes():
    agents = _text("AGENTS.md")
    assert any(line.startswith("| `.agent_docs/render.md` |") for line in agents.splitlines()), (
        "no index row for .agent_docs/render.md"
    )
    assert (ROOT / ".agent_docs" / "render.md").is_file()


def test_observability_names_the_render_spans():
    observability = _text(".agent_docs/observability.md")
    for span in ("render.session", "render.cleanup", "mcp.render"):
        assert span in observability


def test_skill_core_tools_lists_render():
    core = _text("skill/core.md")
    tools = core.split("## Tools", 1)[1].split("\n## ", 1)[0]
    assert any(line.startswith("- render:") for line in tools.splitlines())
