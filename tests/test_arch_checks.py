"""Tests for the user-editable arch-diagram QA checklist resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from mcp_htmleditor import arch_checks, config
from mcp_htmleditor import cli as cli_module
from mcp_htmleditor.cli import main
from mcp_htmleditor.skill_audit import find_stale
from mcp_htmleditor.skill_content import TOPIC_BUDGET_BYTES, build_library

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED_SKILL = REPO_ROOT / "skill"
TOPIC_FILE = SHIPPED_SKILL / "topics" / "arch-qa.md"
SHIPPED_CHECKLIST = SHIPPED_SKILL / "checks" / "arch-diagram-checklist.md"
ARCHIVE = REPO_ROOT / "docs" / "skill-archive"
PART_BUDGET_BYTES = 3800
ARCHIVED_CHECKLIST_BYTES = 11860  # the pre cut file at HEAD of US-0032 (the spec text says 11 856)
DASHES = ("\u2014", "\u2013")


@pytest.fixture
def no_global_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI group would install the process wide tracer, which tests/test_tracing.py owns."""
    monkeypatch.setattr(cli_module, "configure_tracing", lambda settings=None: None)


def test_checklist_path_falls_back_to_the_bundled_repo_copy() -> None:
    """With no user override and nothing installed yet, the bundled file resolves."""
    path = arch_checks.checklist_path()
    assert path.name == "arch-diagram-checklist.md"
    assert path.is_file()


def test_read_checklist_returns_the_bundled_content() -> None:
    """The bundled default mentions the two-pass bound, a load-bearing behaviour."""
    content = arch_checks.read_checklist()
    assert "2 passes" in content
    assert "arch-col" in content


def test_env_override_wins_over_the_bundled_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HTMLEDITOR_ARCH_CHECKS_DIR redirects both the search path and the read content."""
    custom = tmp_path / "my-checks"
    custom.mkdir()
    (custom / "arch-diagram-checklist.md").write_text("# Ma regle perso\n", encoding="utf-8")
    monkeypatch.setenv("HTMLEDITOR_ARCH_CHECKS_DIR", str(custom))
    config.reset_settings_cache()

    assert arch_checks.checklist_path() == custom / "arch-diagram-checklist.md"
    assert arch_checks.read_checklist() == "# Ma regle perso\n"


def test_missing_file_at_every_location_returns_empty_string(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No file anywhere: read_checklist degrades to an empty string, never raises."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setenv("HTMLEDITOR_ARCH_CHECKS_DIR", str(empty_dir))
    config.reset_settings_cache()
    monkeypatch.setattr(arch_checks, "_repo_checks_dir", lambda: empty_dir)

    assert arch_checks.read_checklist() == ""


def _use_checks(monkeypatch: pytest.MonkeyPatch, user_dir: Path, shipped_dir: Path) -> None:
    monkeypatch.setenv("HTMLEDITOR_ARCH_CHECKS_DIR", str(user_dir))
    config.reset_settings_cache()
    monkeypatch.setattr(arch_checks, "_repo_checks_dir", lambda: shipped_dir)


def _write_shipped(root: Path) -> Path:
    shipped = root / "shipped"
    shipped.mkdir()
    (shipped / arch_checks.CHECKLIST_FILENAME).write_text("- [ ] shipped item\n", encoding="utf-8")
    return shipped


def test_repo_checks_dir_follows_the_skill_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The shipped checks live under the configured skill directory."""
    monkeypatch.setenv("HTMLEDITOR_SKILL_DIR", str(tmp_path))
    config.reset_settings_cache()

    assert arch_checks._repo_checks_dir() == tmp_path / "checks"


def test_blank_user_checklist_falls_back_to_the_shipped_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user = tmp_path / "user"
    user.mkdir()
    (user / arch_checks.CHECKLIST_FILENAME).write_text("  \n\n", encoding="utf-8")
    _use_checks(monkeypatch, user, _write_shipped(tmp_path))

    assert arch_checks.read_checklist() == "- [ ] shipped item\n"


def test_directory_candidate_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user = tmp_path / "user"
    (user / arch_checks.CHECKLIST_FILENAME).mkdir(parents=True)
    _use_checks(monkeypatch, user, _write_shipped(tmp_path))

    assert arch_checks.read_checklist() == "- [ ] shipped item\n"


def test_undecodable_user_checklist_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user = tmp_path / "user"
    user.mkdir()
    (user / arch_checks.CHECKLIST_FILENAME).write_bytes(b"\xff\xfe\x00bad")
    _use_checks(monkeypatch, user, _write_shipped(tmp_path))

    assert arch_checks.read_checklist() == "- [ ] shipped item\n"


def test_larger_user_checklist_is_returned_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user = tmp_path / "user"
    user.mkdir()
    text = "- [ ] one\n" * 500
    (user / arch_checks.CHECKLIST_FILENAME).write_text(text, encoding="utf-8")
    _use_checks(monkeypatch, user, _write_shipped(tmp_path))

    assert arch_checks.read_checklist() == text


def test_read_shipped_checklist_ignores_the_user_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user = tmp_path / "user"
    user.mkdir()
    (user / arch_checks.CHECKLIST_FILENAME).write_text("user only\n", encoding="utf-8")
    _use_checks(monkeypatch, user, _write_shipped(tmp_path))

    assert arch_checks.read_shipped_checklist() == "- [ ] shipped item\n"


def test_read_shipped_checklist_is_empty_on_any_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shipped = tmp_path / "shipped"
    (shipped / arch_checks.CHECKLIST_FILENAME).mkdir(parents=True)
    _use_checks(monkeypatch, tmp_path / "none", shipped)

    assert arch_checks.read_shipped_checklist() == ""


def _bytes(path: Path) -> int:
    return len(path.read_bytes())


def test_shipped_parts_respect_their_size_bounds() -> None:
    assert _bytes(TOPIC_FILE) <= PART_BUDGET_BYTES
    assert _bytes(SHIPPED_CHECKLIST) <= PART_BUDGET_BYTES


def test_shipped_arch_qa_output_with_the_shipped_checklist_fits_the_topic_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HTMLEDITOR_SKILL_DIR", raising=False)
    config.reset_settings_cache()
    library = build_library(read_checklist=arch_checks.read_shipped_checklist)
    text = library.topic_output("arch-qa")
    shipped = SHIPPED_CHECKLIST.read_text(encoding="utf-8")
    assert text == f"# Skill topic: arch-qa\n\n{TOPIC_FILE.read_text(encoding='utf-8').strip()}\n\n{shipped.strip()}\n"

    assert len(text.encode("utf-8")) <= TOPIC_BUDGET_BYTES
    assert text.splitlines()[0] == "# Skill topic: arch-qa"
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert "2 passes" in text and "arch-col" in text
    assert not [line for line in text.splitlines() if line.startswith("Reference:")]


def test_shipped_checklist_keeps_its_load_bearing_words() -> None:
    text = SHIPPED_CHECKLIST.read_text(encoding="utf-8")

    assert "2 passes" in text
    assert "arch-col" in text
    assert "- [ ] " in text
    assert "# Skill topic:" not in text


def test_topic_file_keeps_the_protocol_names() -> None:
    text = TOPIC_FILE.read_text(encoding="utf-8")

    for name in (
        "mcp-htmleditor arch-layout",
        "layout_arch_diagram",
        "mcp-htmleditor arch-checklist",
        "2 passes maximum",
        "mcp-htmleditor skill --type create",
        "mcp-htmleditor skill --type arch-diagram",
    ):
        assert name in text, name
    assert "# Skill topic:" not in text


@pytest.mark.parametrize("path", [TOPIC_FILE, SHIPPED_CHECKLIST])
def test_arch_qa_texts_have_no_stale_statement_nor_dash(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    assert find_stale(text, include_counts=False) == []
    assert not any(dash in text for dash in DASHES)
    assert "skill/workflow-arch-qa.md" not in text
    assert "skill/types/" not in text


def test_workflow_text_and_original_checklist_are_archived() -> None:
    assert not (SHIPPED_SKILL / "workflow-arch-qa.md").exists()
    assert (ARCHIVE / "workflow-arch-qa.md").stat().st_size > 0
    assert _bytes(ARCHIVE / "arch-diagram-checklist.md") == ARCHIVED_CHECKLIST_BYTES


def _use_user_location(monkeypatch: pytest.MonkeyPatch, user: Path) -> None:
    monkeypatch.setenv("HTMLEDITOR_ARCH_CHECKS_DIR", str(user))
    config.reset_settings_cache()


@pytest.mark.parametrize("kind", ["empty", "directory"])
def test_e2e_025_unusable_user_location_resolves_to_the_shipped_checklist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_global_tracing: None, kind: str
) -> None:
    """Empty file or directory at the user location: the shipped (cut) checklist is read, the command exits 0."""
    user = tmp_path / "user-checks"
    user.mkdir()
    target = user / arch_checks.CHECKLIST_FILENAME
    if kind == "empty":
        target.write_text("", encoding="utf-8")
    else:
        target.mkdir()
    _use_user_location(monkeypatch, user)

    assert arch_checks.read_checklist() == SHIPPED_CHECKLIST.read_text(encoding="utf-8")
    assert arch_checks.read_checklist() == arch_checks.read_shipped_checklist()
    result = CliRunner().invoke(main, ["arch-checklist"])
    assert result.exit_code == 0
    assert "2 passes" in result.stdout
    skill = CliRunner().invoke(main, ["skill", "--type", "arch-qa"])
    assert skill.exit_code == 0
    assert SHIPPED_CHECKLIST.read_text(encoding="utf-8").strip() in skill.stdout
    assert "2 passes" in skill.stdout and "arch-col" in skill.stdout


def test_e2e_025_larger_user_checklist_is_printed_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_global_tracing: None
) -> None:
    user = tmp_path / "user-checks"
    user.mkdir()
    text = "- [ ] one\n" * 900
    (user / arch_checks.CHECKLIST_FILENAME).write_text(text, encoding="utf-8")
    _use_user_location(monkeypatch, user)

    assert len(text) > _bytes(SHIPPED_CHECKLIST)
    assert arch_checks.read_checklist() == text
    result = CliRunner().invoke(main, ["arch-checklist"])
    assert result.exit_code == 0
    assert text.strip() in result.stdout
    skill = CliRunner().invoke(main, ["skill", "--type", "arch-qa"])
    assert skill.exit_code == 0
    assert skill.stdout.endswith(f"\n\n{text.strip()}\n")


def test_skill_audit_measures_arch_qa_with_the_shipped_checklist(
    monkeypatch: pytest.MonkeyPatch, no_global_tracing: None
) -> None:
    monkeypatch.delenv("HTMLEDITOR_SKILL_DIR", raising=False)
    config.reset_settings_cache()
    text = build_library(read_checklist=arch_checks.read_shipped_checklist).topic_output("arch-qa")
    result = CliRunner().invoke(main, ["skill-audit"])
    line = next(row for row in result.stdout.splitlines() if "arch-qa" in row)
    assert str(len(text.encode("utf-8"))) in line.replace(" ", "").replace(",", "")
    assert line.rstrip().endswith("OK")
