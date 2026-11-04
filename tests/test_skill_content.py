"""Tests for the skill topic engine and the `skill --type/--all` command (SPEC-0006)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from mcp_htmleditor import cli as cli_module
from mcp_htmleditor import config as config_module
from mcp_htmleditor import skill_content
from mcp_htmleditor.cli import main
from tests.conftest import SKILL_CORE_TITLE, SKILL_TOPICS, SkillTree

TOPIC_NAMES = [name for name, _ in SKILL_TOPICS]
UNKNOWN_MESSAGE = (
    'Unknown skill topic "foo". Valid topics: create, export, templates, slides-carbon, slides-ei, medical, '
    "medical-sources, document, mail, website, gantt, arch-diagram, arch-qa, annotated-image, tables"
)
BOTH_MESSAGE = "Error: --type and --all cannot be used together"


@pytest.fixture(autouse=True)
def no_global_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The group callback configures the process wide tracer, which tests/test_tracing.py owns."""
    monkeypatch.setattr(cli_module, "configure_tracing", lambda settings=None: None)


def run(*args: str) -> Result:
    return CliRunner().invoke(main, ["skill", *args])


def assert_failure(result: Result, message: str, code: int) -> None:
    assert result.exit_code == code
    assert result.stdout == ""
    assert result.stderr == message + "\n"


def test_topics_registry_matches_the_index_table() -> None:
    topics = getattr(skill_content, "TOPICS", ())
    assert [(t.name, t.description) for t in topics] == list(SKILL_TOPICS)
    assert tuple(getattr(skill_content, "TOPIC_NAMES", ())) == tuple(TOPIC_NAMES)
    assert getattr(skill_content, "CORE_BUDGET_BYTES", None) == 7000
    assert getattr(skill_content, "TOPIC_BUDGET_BYTES", None) == 8000


def test_e2e_002_one_topic_only(skill_tree: SkillTree) -> None:
    result = run("--type", "medical")
    assert result.exit_code == 0
    assert len(result.stdout.encode()) <= 8000
    assert result.stdout.splitlines()[0] == "# Skill topic: medical"
    assert "# mcp-htmleditor skill (core)" not in result.stdout
    assert "# Skill topic: gantt" not in result.stdout
    assert result.stdout == "# Skill topic: medical\n\n## Rules for medical\n\nBody of medical.\n"


def test_e2e_003_all_is_core_then_topics(skill_tree: SkillTree) -> None:
    result = run("--all")
    assert result.exit_code == 0
    parts = [run().stdout, *(run("--type", name).stdout for name in TOPIC_NAMES)]
    assert result.stdout == "\n".join(parts)
    assert result.stdout.endswith("\n")
    assert not result.stdout.endswith("\n\n")
    assert result.stdout.startswith(SKILL_CORE_TITLE)
    assert result.stdout.count("\n\n# Skill topic: ") == 15
    assert "checklist item" not in result.stdout


def test_core_output_is_stripped_with_one_newline(skill_tree: SkillTree) -> None:
    result = run()
    assert result.exit_code == 0
    assert result.stdout == skill_tree.core_path.read_text(encoding="utf-8").rstrip() + "\n"


def test_e2e_007_unknown_topic(skill_tree: SkillTree) -> None:
    assert_failure(run("--type", "foo"), UNKNOWN_MESSAGE, 2)


def test_e2e_015_empty_topic(skill_tree: SkillTree) -> None:
    result = run("--type", "")
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr.startswith('Unknown skill topic "". Valid topics: create, export,')
    assert result.stderr.count("\n") == 1
    assert run("--type", "gantt").exit_code == 0


def test_e2e_013_missing_topic_with_all(skill_tree: SkillTree) -> None:
    skill_tree.remove("gantt")
    assert_failure(run("--all"), 'Skill topic "gantt" is not installed', 1)
    medical = run("--type", "medical")
    assert medical.exit_code == 0
    assert medical.stdout.startswith("# Skill topic: medical\n")


def test_missing_topic_with_type(skill_tree: SkillTree) -> None:
    skill_tree.remove("gantt")
    assert_failure(run("--type", "gantt"), 'Skill topic "gantt" is not installed', 1)


@pytest.mark.parametrize("args", [("--type", "gantt"), ("--type", "foo"), ("--type", "")])
def test_e2e_014_both_options(skill_tree: SkillTree, args: tuple[str, str]) -> None:
    assert_failure(run(*args, "--all"), BOTH_MESSAGE, 2)
    assert_failure(run("--all", *args), BOTH_MESSAGE, 2)


def test_core_missing(skill_tree: SkillTree) -> None:
    skill_tree.remove("core")
    assert_failure(run(), "Skill core is not installed", 1)
    assert_failure(run("--all"), "Skill core is not installed", 1)
    ok = run("--type", "medical")
    assert ok.exit_code == 0
    assert ok.stdout.startswith("# Skill topic: medical\n")


def test_all_reports_the_first_missing_part_in_index_order(skill_tree: SkillTree) -> None:
    skill_tree.remove("core")
    skill_tree.remove("gantt")
    assert_failure(run("--all"), "Skill core is not installed", 1)


def test_all_reports_first_missing_topic_in_index_order(skill_tree: SkillTree) -> None:
    skill_tree.remove("tables")
    skill_tree.remove("export")
    assert_failure(run("--all"), 'Skill topic "export" is not installed', 1)


def test_topic_file_content_is_stripped(skill_tree: SkillTree) -> None:
    skill_tree.topic_path("tables").write_text("\n\nBody\n\n\n", encoding="utf-8")
    assert run("--type", "tables").stdout == "# Skill topic: tables\n\nBody\n"


def test_library_uses_injected_checklist_reader(skill_tree: SkillTree) -> None:
    library = skill_content.build_library(read_checklist=lambda: "checklist")
    assert library.skill_dir == skill_tree.root
    assert library.topic_output("create").startswith("# Skill topic: create\n")
    with pytest.raises(skill_content.UnknownTopicError) as unknown:
        library.topic_output("nope")
    assert unknown.value.exit_code == 2
    skill_tree.remove("create")
    with pytest.raises(skill_content.NotInstalledError) as missing:
        library.topic_output("create")
    assert missing.value.exit_code == 1
    assert isinstance(missing.value, skill_content.SkillError)
    assert missing.value.message == 'Skill topic "create" is not installed'


def test_skill_dir_setting_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTMLEDITOR_SKILL_DIR", str(tmp_path))
    config_module.reset_settings_cache()
    assert config_module.skill_dir() == tmp_path
    assert config_module.get_settings().skill_dir_override == tmp_path


def test_skill_dir_default_is_the_bundled_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HTMLEDITOR_SKILL_DIR", raising=False)
    config_module.reset_settings_cache()
    assert config_module.skill_dir().name == "skill"
    assert "HTMLEDITOR_SKILL_DIR" in config_module._SIGNIFICANT_ENV_VARS
    assert "skill_dir_override" in config_module._PATH_FIELDS
