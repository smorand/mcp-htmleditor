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
