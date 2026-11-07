"""SPEC-0015 E2E-028, E2E-029, E2E-034, E2E-035 and E2E-041 (US-0093): the agent side of the text width bar.

E2E-028 and E2E-041 drag the bar in real headless Chromium against a real editor server (module page shared,
DEC-011), then read the file with the agent tools in process. The others run the command line in a child process
on the repository ``skill/`` tree, as ``tests/test_skill_shipped.py`` does.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

from mcp_htmleditor.deck.lint import lint_file
from mcp_htmleditor.deck.read import get_slide
from tests.browser_wait import wait_for_file
from tests.conftest import ServedDeck, needs_chromium
from tests.width_support import (
    PARAGRAPH,
    deck_d1,
    drag_bar,
    element_starting_with,
    open_editor,
    width_page,
    write_fixture,
)

pytestmark = needs_chromium

__all__ = ["width_page"]

REPO = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO / "skill"
SLIDE_2 = "slide-1"
PALETTE_PROBLEM = "colour #123456 is not in the carbon palette"
CORE_SHA256 = "171b191f41e9b11f0d608caf0255b6f37d07f89e7025a450f61839106660d4dd"
TOPIC_BUDGET_BYTES = 8000
CREATE_LINE = (
    "- Largeur d'un texte: barre sur son bord droit (glisser par pas de 10px, Alt au pixel, flèches; "
    "double clic: largeur du modèle). Écrit `max-width:Npx` dans son `style`."
)
EXPORT_LINE = (
    "- Le `max-width` d'un texte (barre de largeur de l'éditeur): la zone de texte garde la largeur de son bloc."
)


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HTMLEDITOR_SKILL_DIR": str(SKILL_DIR)}
    return subprocess.run(  # noqa: S603  # fixed argument list, no shell
        [sys.executable, "-m", "mcp_htmleditor", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO,
        timeout=60,
        check=False,
    )


def _section(output: str, heading: str, next_prefix: str) -> list[str]:
    """Lines after ``heading`` and before the next line starting with ``next_prefix``."""
    lines = output.splitlines()
    assert heading in lines, f"{heading!r} missing from the topic"
    rest = lines[lines.index(heading) + 1 :]
    end = next((n for n, line in enumerate(rest) if line.startswith(next_prefix)), len(rest))
    return rest[:end]


def _problems(path: Path) -> list[tuple[str, str, str | None, str]]:
    report = lint_file(str(path))
    return [(p["code"], p["severity"], p["slide"], p["message"]) for p in report["problems"]]


def _style_in_slide_2(path: Path, text: str) -> str | None:
    style = element_starting_with(get_slide(str(path), SLIDE_2), text).get("style")
    return None if style is None else str(style)


def test_width_agent_reads_declaration_lint_unchanged(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-028: after J's bar moves 150 px left the agent reads `color:#123456; max-width:650px`, lint is unchanged."""
    deck = serve_deck(write_fixture(tmp_path, deck_d1()))
    before = _problems(deck.path)
    assert any(PALETTE_PROBLEM in message for _, _, _, message in before), before
    open_editor(width_page, deck.port)

    drag_bar(width_page, PARAGRAPH["J"], -150)

    wait_for_file(width_page, deck.path, "max-width:650px")
    assert _style_in_slide_2(deck.path, "Hors charte") == "color:#123456; max-width:650px"
    after = _problems(deck.path)
    assert after == before
    assert any(PALETTE_PROBLEM in message for _, _, _, message in after)


def test_width_agent_creating_topic_line() -> None:
    """E2E-029: `skill --type create` holds the width line under "Ce que l'humain peut faire"."""
    result = _cli("skill", "--type", "create")

    assert result.returncode == 0, result.stderr
    section = _section(result.stdout, "## Ce que l'humain peut faire", "## ")
    assert CREATE_LINE in section
    assert result.stdout.count(CREATE_LINE) == 1


def test_width_agent_export_topic_line() -> None:
    """E2E-034: `skill --type export` holds the ignored width line under "Perdu"."""
    result = _cli("skill", "--type", "export")

    assert result.returncode == 0, result.stderr
    section = _section(result.stdout, "### Perdu", "#")
    assert EXPORT_LINE in section
    assert result.stdout.count(EXPORT_LINE) == 1


def test_width_agent_budgets_kept() -> None:
    """E2E-035: skill-audit exits 0, both topics fit 8000 bytes, the core is byte identical."""
    result = _cli("skill-audit", "--json")

    assert result.returncode == 0, result.stdout + result.stderr
    for topic in ("create", "export"):
        output = _cli("skill", "--type", topic).stdout
        assert len(output.encode("utf-8")) <= TOPIC_BUDGET_BYTES, topic
    json.loads(result.stdout)
    assert hashlib.sha256((SKILL_DIR / "core.md").read_bytes()).hexdigest() == CORE_SHA256


def test_width_agent_percent_written_by_agent(
    width_page: Page, tmp_path: Path, serve_deck: Callable[[Path], ServedDeck]
) -> None:
    """E2E-041: P written with `max-width:50%` (400 px) dragged 47 px right: `max-width:450px`, seen by the agent."""
    deck = serve_deck(write_fixture(tmp_path, deck_d1()))
    open_editor(width_page, deck.port)

    drag_bar(width_page, PARAGRAPH["P"], 47)

    wait_for_file(width_page, deck.path, "max-width:450px")
    assert _style_in_slide_2(deck.path, "Agent") == "max-width:450px"
