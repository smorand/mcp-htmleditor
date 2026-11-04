"""Gates on the shipped skill tree: the core, the routing skill and every topic file that exists (SPEC-0006)."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner

from mcp_htmleditor import arch_checks
from mcp_htmleditor.skill_content import SkillLibrary

REPO = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO / "skill"
ROUTING_SKILL = REPO / "dynamic-skills" / "html-editor" / "SKILL.md"
ANCHORS_FILE = REPO / "tests" / "data" / "skill_anchors.json"

CORE_TITLE = "# mcp-htmleditor skill (core)"
CORE_SHIPPED_BYTES = 6000
CORE_BUDGET_BYTES = 7000
TOPIC_BUDGET_BYTES = 8000
LANDING_TOOLS = {
    "start_server",
    "stop_server",
    "get_status",
    "open_file",
    "update_start",
    "update_end",
    "layout_arch_diagram",
    "get_skill",
}
TEMPLATE_KEYS = ("ei", "carbon", "medical", "doc", "doc-perso", "doc-ei", "mail", "website")
CORE_STRINGS = (
    "update_start",
    "update_end",
    "data-type",
    "data-id",
    "data-title",
    'data-editable="text"',
    "base64",
    "get_status",
    "mcp-htmleditor new",
)
REFERENCES = {
    "slides-carbon": "templates/reference/slides/ibm-carbon.html",
    "slides-ei": "templates/reference/slides/example-ei-complete.html",
    "medical": "templates/reference/slides/medical.html",
    "document": "templates/reference/documents/report-standard.html",
    "mail": "templates/reference/documents/mail-carbon-example.html",
    "website": "templates/reference/websites/ibm-carbon.html",
}
DASHES = ("\u2014", "\u2013")


def _library() -> SkillLibrary:
    return SkillLibrary(SKILL_DIR, arch_checks.read_shipped_checklist)


def _existing_topics() -> list[str]:
    from mcp_htmleditor.skill_content import TOPIC_NAMES

    return [name for name in TOPIC_NAMES if (SKILL_DIR / "topics" / f"{name}.md").is_file()]


def _anchors() -> dict[str, list[str]]:
    if not ANCHORS_FILE.is_file():
        return {}
    return json.loads(ANCHORS_FILE.read_text(encoding="utf-8"))


@pytest.fixture
def real_tree(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from mcp_htmleditor import cli as cli_module
    from mcp_htmleditor import config as config_module

    monkeypatch.setenv("HTMLEDITOR_SKILL_DIR", str(SKILL_DIR))
    monkeypatch.setattr(cli_module, "configure_tracing", lambda settings=None: None)
    config_module.reset_settings_cache()
    yield
    config_module.reset_settings_cache()


def test_core_by_default(real_tree: None) -> None:
    """SPEC-0006/E2E-001: `skill` on the real tree prints the core with tools and the 15 topic lines."""
    from mcp_htmleditor.cli import main
    from mcp_htmleditor.mcp_server import registered_tool_names
    from mcp_htmleditor.skill_audit import listed_tools
    from mcp_htmleditor.skill_content import TOPICS

    result = CliRunner().invoke(main, ["skill"])

    assert result.exit_code == 0
    out = result.stdout
    assert len(out.encode("utf-8")) <= CORE_BUDGET_BYTES
    assert out.splitlines()[0] == CORE_TITLE
    assert "## Tools" in out.splitlines()
    names = listed_tools(out)
    assert set(registered_tool_names()) == set(names)
    assert set(names) >= LANDING_TOOLS
    for name in LANDING_TOOLS:
        assert any(line.startswith(f"- {name}: ") for line in out.splitlines())
    index = [line for line in out.splitlines() if ". Load: mcp-htmleditor skill --type " in line]
    assert index == [f"{t.name}: {t.description}. Load: mcp-htmleditor skill --type {t.name}" for t in TOPICS]
    assert (
        "medical: Rules for medical slides: layouts, light and dark surfaces, widths, readability, height budget. "
        "Load: mcp-htmleditor skill --type medical"
    ) in index


def test_core_file_gates() -> None:
    from mcp_htmleditor.skill_audit import find_stale

    path = SKILL_DIR / "core.md"
    assert path.is_file()
    assert path.stat().st_size <= CORE_SHIPPED_BYTES
    text = _library().core_output()
    assert len(text.encode("utf-8")) <= CORE_BUDGET_BYTES
    assert text.splitlines()[0] == CORE_TITLE
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert find_stale(text, include_counts=True) == []
    assert not any(dash in text for dash in DASHES)
    for needle in (*CORE_STRINGS, *TEMPLATE_KEYS):
        assert needle in text, needle
    assert "`ei`" in text or "ei," in text


def test_core_workflow_and_rules() -> None:
    text = _library().core_output()
    numbered = [line for line in text.splitlines() if re.match(r"\d+\. ", line)]
    assert len(numbered) == 14  # 8 absolute rules plus 6 workflow steps
    assert "commit" not in text.lower()


def test_routing_skill_content() -> None:
    """SPEC-0006/E2E-021."""
    from mcp_htmleditor.skill_audit import find_stale

    text = ROUTING_SKILL.read_text(encoding="utf-8")
    assert "mcp-htmleditor skill --type" in text
    assert "Lis entièrement" not in text
    assert find_stale(text, include_counts=True) == []


def test_install_skill_copies_routing_skill(tmp_path: Path) -> None:
    """SPEC-0006/E2E-022."""
    target = tmp_path / "installed"
    result = subprocess.run(  # noqa: S603 - fixed argument list, repo Makefile
        ["make", "install-skill", f"PI_SKILLS_DIR={target}"],  # noqa: S607 - make from PATH
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (target / "SKILL.md").read_bytes() == ROUTING_SKILL.read_bytes()


def test_shipped_topics_gates() -> None:
    """Topic gates, run on the topic files that exist (zero today is fine)."""
    from mcp_htmleditor.skill_audit import find_stale

    anchors = _anchors()
    library = _library()
    for topic in _existing_topics():
        text = library.topic_output(topic)
        lines = text.splitlines()
        assert len(text.encode("utf-8")) <= TOPIC_BUDGET_BYTES, topic
        assert lines[0] == f"# Skill topic: {topic}", topic
        assert text.endswith("\n") and not text.endswith("\n\n"), topic
        assert find_stale(text, include_counts=False) == [], topic
        references = [line for line in lines if line.startswith("Reference:")]
        if topic in REFERENCES:
            assert references == [f"Reference: {REFERENCES[topic]}"], topic
            assert lines[-1] == references[0], topic
        else:
            assert references == [], topic
        for anchor in anchors.get(topic, []):
            assert anchor in text, (topic, anchor)


def test_anchored_topics_have_a_topic_file() -> None:
    """Every key of the anchors file has a shipped topic file that satisfies its gates and anchors."""
    from mcp_htmleditor.skill_audit import find_stale

    library = _library()
    for topic, anchors in _anchors().items():
        assert (SKILL_DIR / "topics" / f"{topic}.md").is_file(), topic
        text = library.topic_output(topic)
        assert len(text.encode("utf-8")) <= TOPIC_BUDGET_BYTES, topic
        assert find_stale(text, include_counts=False) == [], topic
        assert not any(dash in text for dash in DASHES), topic
        for anchor in anchors:
            assert anchor in text, (topic, anchor)
