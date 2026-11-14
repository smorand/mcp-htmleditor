"""SPEC-0023 (US-0122): the ``breathe`` skill topic and its place in the core (E2E-041 to E2E-043, E2E-055)."""

from __future__ import annotations

import pytest

from mcp_htmleditor import config as config_module
from mcp_htmleditor.skill_content import TOPIC_BUDGET_BYTES, TOPIC_NAMES
from tests.deck_support import run_cli

INDEX_LINE = (
    "breathe: Rules for Breathe slides: layouts, airway stages, icons, sizing, notes, embedding, PPTX export. "
    "Load: mcp-htmleditor skill --type breathe"
)
KEYS = "`ei, carbon, medical, breathe, doc, doc-perso, doc-ei, mail, website`"


@pytest.fixture(autouse=True)
def shipped_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_skill_shipped import SKILL_DIR

    monkeypatch.setenv("HTMLEDITOR_SKILL_DIR", str(SKILL_DIR))
    config_module.reset_settings_cache()


def test_topic_and_index() -> None:
    """E2E-041."""
    core, _, code = run_cli("skill")
    assert code == 0
    assert INDEX_LINE in core.splitlines()
    assert KEYS in core
    topic, _, code = run_cli("skill", "--type", "breathe")
    assert code == 0
    for command in (
        "mcp-htmleditor new breathe",
        "mcp-htmleditor breathe-inline",
        "--link",
        "mcp-htmleditor lint",
        "mcp-htmleditor export pptx",
        "make install-browser",
    ):
        assert command in topic, command


def test_index_order_puts_breathe_after_medical_sources() -> None:
    assert TOPIC_NAMES.index("breathe") == TOPIC_NAMES.index("medical-sources") + 1


def test_unknown_topic_lists_breathe() -> None:
    """E2E-042."""
    stdout, stderr, code = run_cli("skill", "--type", "breath")
    assert (stdout, code) == ("", 2)
    assert stderr.strip() == f'Unknown skill topic "breath". Valid topics: {", ".join(TOPIC_NAMES)}'
    assert len(TOPIC_NAMES) == 17


def test_topic_within_budget() -> None:
    """E2E-043."""
    stdout, _, code = run_cli("skill-audit")
    assert code == 0
    line = next(line for line in stdout.splitlines() if line.startswith("breathe: "))
    assert line.endswith(" OK")
    assert int(line.split()[1]) < TOPIC_BUDGET_BYTES


def test_topic_and_all_together() -> None:
    """E2E-055."""
    stdout, stderr, code = run_cli("skill", "--type", "breathe", "--all")
    assert (stdout, stderr.strip(), code) == ("", "Error: --type and --all cannot be used together", 2)
