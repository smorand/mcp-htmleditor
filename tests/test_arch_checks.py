"""Tests for the user-editable arch-diagram QA checklist resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_htmleditor import arch_checks, config


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
