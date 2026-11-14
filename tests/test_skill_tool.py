"""The get_skill tool returns the CLI text and the CLI error messages (SPEC-0006)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from fastmcp import Client
from fastmcp.exceptions import ToolError

from .conftest import SkillTree

UNKNOWN_FOO = (
    'Unknown skill topic "foo". Valid topics: create, export, templates, slides-carbon, slides-ei, medical, '
    "medical-sources, breathe, document, mail, website, gantt, arch-diagram, arch-qa, annotated-image, tables, editor"
)


@pytest.fixture(autouse=True)
def _no_global_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI group would install the process wide tracer, which test_tracing configures itself."""
    from mcp_htmleditor import cli as cli_module

    monkeypatch.setattr(cli_module, "configure_tracing", lambda settings=None: None)


def _cli(*args: str) -> tuple[int, str]:
    from mcp_htmleditor.cli import main

    result = CliRunner().invoke(main, ["skill", *args])
    return result.exit_code, result.stdout


def _run(work: Callable[[Client], Awaitable[Any]]) -> Any:
    """Run work against a real client in its own thread: the e2e suite keeps a loop running in this one."""
    from mcp_htmleditor.mcp_server import mcp

    async def session() -> Any:
        async with Client(mcp) as client:
            return await work(client)

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, session()).result()


def _call(**arguments: str) -> str:
    async def work(client: Client) -> str:
        result = await client.call_tool("get_skill", arguments)
        return str(result.content[0].text)  # type: ignore[union-attr] # first block is TextContent for a str tool

    return str(_run(work))


def _tool_names() -> set[str]:
    async def work(client: Client) -> set[str]:
        return {tool.name for tool in await client.list_tools()}

    return set(_run(work))


def test_core_through_the_tool_equals_the_cli(skill_tree: SkillTree) -> None:
    status, expected = _cli()

    assert status == 0
    assert _call() == expected
    assert expected.endswith("\n")


def test_topic_through_the_tool_equals_the_cli(skill_tree: SkillTree) -> None:
    status, expected = _cli("--type", "gantt")

    assert status == 0
    assert _call(type="gantt") == expected


def test_unknown_topic_is_a_tool_error(skill_tree: SkillTree) -> None:
    with pytest.raises(ToolError) as caught:
        _call(type="foo")

    assert UNKNOWN_FOO in str(caught.value)


def test_empty_topic_is_a_tool_error(skill_tree: SkillTree) -> None:
    with pytest.raises(ToolError) as caught:
        _call(type="")

    assert 'Unknown skill topic ""' in str(caught.value)


def test_missing_topic_through_both_surfaces(skill_tree: SkillTree) -> None:
    from mcp_htmleditor.cli import main

    skill_tree.remove("gantt")
    with pytest.raises(ToolError) as caught:
        _call(type="gantt")
    result = CliRunner().invoke(main, ["skill", "--type", "gantt"])

    assert 'Skill topic "gantt" is not installed' in str(caught.value)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.strip() == 'Skill topic "gantt" is not installed'


def test_missing_core_errors_but_topics_still_work(skill_tree: SkillTree) -> None:
    skill_tree.remove("core")

    with pytest.raises(ToolError) as caught:
        _call()

    assert "Skill core is not installed" in str(caught.value)
    assert "Body of medical." in _call(type="medical")


def test_get_skill_is_listed() -> None:
    names = _tool_names()

    assert "get_skill" in names


@pytest.mark.parametrize("kind", ["empty", "directory"])
def test_unusable_user_checklist_falls_back_to_the_shipped_one(
    skill_tree: SkillTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    from mcp_htmleditor import arch_checks, config

    user = tmp_path / "user-checks"
    user.mkdir()
    target = user / arch_checks.CHECKLIST_FILENAME
    if kind == "empty":
        target.write_text("", encoding="utf-8")
    else:
        target.mkdir()
    monkeypatch.setenv("HTMLEDITOR_ARCH_CHECKS_DIR", str(user))
    config.reset_settings_cache()

    status, _ = _cli("--type", "arch-qa")

    assert status == 0
    assert arch_checks.read_checklist() == skill_tree.checklist_path.read_text(encoding="utf-8")
