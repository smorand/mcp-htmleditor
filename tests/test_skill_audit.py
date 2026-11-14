"""Tests for `mcp-htmleditor skill-audit`: sizes, budgets, missing items, JSON (SPEC-0006)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from mcp_htmleditor import cli as cli_module
from mcp_htmleditor import mcp_server
from mcp_htmleditor.cli import main
from tests.conftest import SKILL_TOPICS, SkillTree

TOPIC_NAMES = [name for name, _ in SKILL_TOPICS]


@pytest.fixture(autouse=True)
def no_global_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The group callback configures the process wide tracer, which tests/test_tracing.py owns."""
    monkeypatch.setattr(cli_module, "configure_tracing", lambda settings=None: None)


@pytest.fixture(autouse=True)
def no_tool_or_routing_checks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """These tests cover sizes and budgets only: no registered tools, a clean routing skill."""
    routing = tmp_path / "routing-SKILL.md"
    routing.write_text("# Routing\n", encoding="utf-8")
    monkeypatch.setenv("HTMLEDITOR_ROUTING_SKILL", str(routing))
    monkeypatch.setattr(mcp_server, "registered_tool_names", lambda: [])


def audit(*args: str) -> Result:
    return CliRunner().invoke(main, ["skill-audit", *args], input="")


def set_topic_bytes(tree: SkillTree, name: str, size: int) -> None:
    """Rewrite a topic so that `skill --type <name>` prints exactly `size` bytes."""
    header = f"# Skill topic: {name}\n\n"
    tree.topic_path(name).write_text("x" * (size - len(header) - 1) + "\n", encoding="utf-8")


def set_core_bytes(tree: SkillTree, size: int, accents: int = 0) -> None:
    """Rewrite the core so that `skill` prints exactly `size` bytes."""
    text = "\u00e9" * accents + "x" * (size - 1 - 2 * accents)
    tree.write_core(text + "\n\n")


def lines(result: Result) -> list[str]:
    return result.stdout.splitlines()


def test_clean_tree_is_ok(skill_tree: SkillTree) -> None:
    result = audit()
    assert result.exit_code == 0
    out = lines(result)
    assert len(out) == 19
    assert out[-1] == "skill-audit: OK"
    assert out[0].startswith("core: ")
    assert out[0].endswith(" OK")
    assert [line.split(":")[0] for line in out[1:18]] == TOPIC_NAMES
    assert not any(line.startswith("PROBLEM") for line in out)
    core_size = len(CliRunner().invoke(main, ["skill"]).stdout_bytes)
    assert out[0] == f"core: {core_size} bytes, ~{-(-core_size // 4)} tokens (budget 7000) OK"


def test_e2e_009_topic_over_budget(skill_tree: SkillTree) -> None:
    set_topic_bytes(skill_tree, "gantt", 8001)
    printed = len(CliRunner().invoke(main, ["skill", "--type", "gantt"]).stdout_bytes)
    assert printed == 8001
    result = audit()
    out = lines(result)
    assert "gantt: 8001 bytes, ~2001 tokens (budget 8000) OVER" in out
    assert "PROBLEM topic gantt is over its budget (8001 > 8000)" in out
    assert out[-1] == "skill-audit: FAIL (1 problem)"
    assert result.exit_code == 1
    items = [line for line in out if ": " in line and "bytes" in line]
    assert len(items) == 18
    assert all(line.endswith(" OK") for line in items if not line.startswith("gantt:"))


def test_e2e_010_core_over_budget(skill_tree: SkillTree) -> None:
    set_core_bytes(skill_tree, 7001)
    result = audit()
    out = lines(result)
    assert "core: 7001 bytes, ~1751 tokens (budget 7000) OVER" in out
    assert "PROBLEM core is over its budget (7001 > 7000)" in out
    assert out[-1] == "skill-audit: FAIL (1 problem)"
    assert result.exit_code == 1


def test_e2e_016_boundaries_and_accents(skill_tree: SkillTree) -> None:
    set_core_bytes(skill_tree, 7000, accents=10)
    printed = CliRunner().invoke(main, ["skill"]).stdout_bytes
    assert len(printed) == 7000
    result = audit()
    assert lines(result)[0] == "core: 7000 bytes, ~1750 tokens (budget 7000) OK"
    assert result.exit_code == 0
    set_core_bytes(skill_tree, 7001, accents=10)
    result = audit()
    assert lines(result)[0] == "core: 7001 bytes, ~1751 tokens (budget 7000) OVER"
    assert result.exit_code == 1


def test_topic_boundary_8000_passes(skill_tree: SkillTree) -> None:
    set_topic_bytes(skill_tree, "mail", 8000)
    result = audit()
    assert "mail: 8000 bytes, ~2000 tokens (budget 8000) OK" in lines(result)
    assert result.exit_code == 0


def test_e2e_017_user_checklist_never_audited(
    skill_tree: SkillTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checks = tmp_path / "user-checks"
    checks.mkdir()
    (checks / "arch-diagram-checklist.md").write_text("- [ ] " + "y" * 9000 + "\n", encoding="utf-8")
    monkeypatch.setenv("HTMLEDITOR_ARCH_CHECKS_DIR", str(checks))
    from mcp_htmleditor import config as config_module

    config_module.reset_settings_cache()
    result = audit()
    assert result.exit_code == 0
    assert any(line.startswith("arch-qa: ") and line.endswith(" OK") for line in lines(result))


def test_e2e_020_json(skill_tree: SkillTree) -> None:
    set_topic_bytes(skill_tree, "mail", 8001)
    result = audit("--json")
    assert result.exit_code == 1
    assert result.stdout.count("\n") == 1
    data = json.loads(result.stdout)
    assert list(data) == ["items", "problems", "verdict"]
    assert len(data["items"]) == 18
    assert data["items"][0]["name"] == "core"
    assert all(set(item) == {"name", "bytes", "tokens", "budget", "status"} for item in data["items"])
    mail = next(item for item in data["items"] if item["name"] == "mail")
    assert mail == {"name": "mail", "bytes": 8001, "tokens": 2001, "budget": 8000, "status": "OVER"}
    assert data["problems"] == ["topic mail is over its budget (8001 > 8000)"]
    assert data["verdict"] == "FAIL"


def test_json_ok(skill_tree: SkillTree) -> None:
    result = audit("--json")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["problems"] == []
    assert data["verdict"] == "OK"
    assert data["items"][0]["budget"] == 7000


def test_json_keeps_non_ascii_unescaped(skill_tree: SkillTree) -> None:
    skill_tree.remove("website")
    result = audit("--json")
    assert "\\u" not in result.stdout


def test_e2e_023_missing_topic(skill_tree: SkillTree) -> None:
    skill_tree.remove("website")
    result = audit()
    out = lines(result)
    assert 'PROBLEM topic "website" is not installed' in out
    assert "website: MISSING" in out
    assert len([line for line in out if "bytes" in line]) == 17
    assert out[-1] == "skill-audit: FAIL (1 problem)"
    assert result.exit_code == 1


def test_missing_topic_json(skill_tree: SkillTree) -> None:
    skill_tree.remove("website")
    data = json.loads(audit("--json").stdout)
    website = next(item for item in data["items"] if item["name"] == "website")
    assert website == {"name": "website", "bytes": None, "tokens": None, "budget": 8000, "status": "MISSING"}
    assert data["problems"] == ['topic "website" is not installed']


def test_e2e_028_core_not_installed(skill_tree: SkillTree) -> None:
    skill_tree.remove("core")
    skill = CliRunner().invoke(main, ["skill"])
    assert skill.exit_code == 1
    assert skill.stderr == "Skill core is not installed\n"
    result = audit()
    out = lines(result)
    assert out[0] == "core: MISSING"
    assert "PROBLEM core is not installed" in out
    assert len([line for line in out if "bytes" in line]) == 17
    assert out[-1] == "skill-audit: FAIL (1 problem)"
    assert result.exit_code == 1


def test_plural_problems(skill_tree: SkillTree) -> None:
    skill_tree.remove("core")
    skill_tree.remove("gantt")
    set_topic_bytes(skill_tree, "mail", 8001)
    out = lines(audit())
    assert out[-1] == "skill-audit: FAIL (3 problems)"
    problems = [line for line in out if line.startswith("PROBLEM ")]
    assert problems == [
        "PROBLEM core is not installed",
        "PROBLEM topic mail is over its budget (8001 > 8000)",
        'PROBLEM topic "gantt" is not installed',
    ]
