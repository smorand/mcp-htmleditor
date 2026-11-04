"""SPEC-0009 FR-NEW-004 / E2E-023 on the real DECK: the server's HTML cleaning is idempotent.

``clean(clean(x)) == clean(x)`` for every shipped template and the three charter decks, so a save of the
bytes the server itself wrote is recognised as identical (no mtime change, no history version).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from mcp_htmleditor.http_server import _strip_editor_artifacts
from tests.conftest import ServedDeck
from tests.deck_support import deck_carbon, deck_ei, deck_med

ROOT = Path(__file__).resolve().parents[1] / "templates"
TEMPLATES = sorted([*(ROOT / "bootstrap").glob("*.html"), *(ROOT / "reference").rglob("*.html")])


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: str(p.relative_to(ROOT)))
def test_cleaning_a_template_is_idempotent(path: Path) -> None:
    once = _strip_editor_artifacts(path.read_text(encoding="utf-8"))
    assert _strip_editor_artifacts(once) == once


@pytest.mark.parametrize("build", [deck_ei, deck_carbon, deck_med])
def test_cleaning_a_built_deck_is_idempotent(build: Callable[[], str]) -> None:
    once = _strip_editor_artifacts(build())
    assert _strip_editor_artifacts(once) == once


def test_e2e_023_second_identical_save_of_the_deck_is_a_noop(served_deck: ServedDeck) -> None:
    """The first save may normalise the file; saving the bytes now on disk must change nothing."""
    text = served_deck.path.read_text(encoding="utf-8")
    assert served_deck.save({"html": text, "base_mtime": served_deck.status()["mtime"]}).status == 200
    cleaned = served_deck.path.read_text(encoding="utf-8")
    mtime = served_deck.path.stat().st_mtime
    reply = served_deck.save({"html": cleaned, "base_mtime": mtime})
    assert (reply.status, reply.body) == (200, {"ok": True, "mtime": mtime})
    assert served_deck.path.read_text(encoding="utf-8") == cleaned
