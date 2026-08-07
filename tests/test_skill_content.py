"""Tests for skill content assembly and CLI skill command."""

from __future__ import annotations

from mcp_htmleditor.skill_content import build_skill_content


def test_build_skill_content_includes_index_and_subdocs() -> None:
    """The assembled skill contains the index title and sub-document markers."""
    content = build_skill_content()
    assert "mcp-htmleditor" in content
    # Index heading from SKILL.md
    assert "## Description" in content
    # At least one sub-document marker is injected
    assert "===== workflow-create.md =====" in content or "workflow-create" in content
    # Non-trivial length (index + several sub-docs concatenated)
    assert len(content) > 2000
