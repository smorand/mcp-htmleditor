"""Tests for the tool list and stale statement checks of `skill-audit` (SPEC-0006 FR-NEW-007/008/009)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from mcp_htmleditor import cli as cli_module
from mcp_htmleditor import config as config_module
from mcp_htmleditor import skill_audit
from mcp_htmleditor.cli import main
from mcp_htmleditor.mcp_server import registered_tool_names
from mcp_htmleditor.skill_audit import (
    find_stale,
    listed_tools,
    read_routing_skill,
    run_audit,
    source_routing_skill_path,
    strip_fenced_blocks,
)
from mcp_htmleditor.skill_content import build_library
from tests.conftest import SKILL_CORE_TITLE, SKILL_TOPICS, SkillTree

REAL_TOOLS = registered_tool_names()


@pytest.fixture(autouse=True)
def no_global_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The group callback configures the process wide tracer, which tests/test_tracing.py owns."""
    monkeypatch.setattr(cli_module, "configure_tracing", lambda settings=None: None)


@pytest.fixture
def routing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clean installed routing skill, pointed at through HTMLEDITOR_ROUTING_SKILL."""
    path = tmp_path / "routing" / "SKILL.md"
    path.parent.mkdir()
    path.write_text("# Routing\n\nLoad the core with get_skill.\n", encoding="utf-8")
    monkeypatch.setenv("HTMLEDITOR_ROUTING_SKILL", str(path))
    config_module.reset_settings_cache()
    return path


def write_core(
    tree: SkillTree, *, extra_tools: tuple[str, ...] = (), drop: tuple[str, ...] = (), prose: str = ""
) -> None:
    """Rewrite the core so that `## Tools` lists the real registered tools (minus drop, plus extra)."""
    names = [name for name in REAL_TOOLS if name not in drop]
    lines = [f"- {name}: does something" for name in names] + [f"- {entry}" for entry in extra_tools]
    index = "\n".join(f"{n}: {d}. Load: mcp-htmleditor skill --type {n}" for n, d in SKILL_TOPICS)
    tree.write_core(f"{SKILL_CORE_TITLE}\n\n## Index\n\n{index}\n\n{prose}## Tools\n\n" + "\n".join(lines) + "\n\n")


def audit(*args: str) -> Result:
    return CliRunner().invoke(main, ["skill-audit", *args], input="")


def problems(result: Result) -> list[str]:
    return [line for line in result.stdout.splitlines() if line.startswith("PROBLEM ")]


@pytest.fixture
def clean(skill_tree: SkillTree, routing: Path) -> SkillTree:
    write_core(skill_tree)
    return skill_tree


def test_registered_tool_names_are_the_real_ones() -> None:
    names = registered_tool_names()
    assert "get_skill" in names
    assert names[0] == "start_server"
    assert len(names) == len(set(names))


def test_clean_tree_with_real_tools_is_ok(clean: SkillTree) -> None:
    result = audit()
    assert problems(result) == []
    assert result.exit_code == 0
    assert result.stdout.splitlines()[-1] == "skill-audit: OK"


def test_e2e_011_listed_tool_does_not_exist(clean: SkillTree) -> None:
    write_core(clean, extra_tools=("frobnicate: does nothing",))
    result = audit()
    assert 'PROBLEM tool "frobnicate" is listed in the core but does not exist' in result.stdout
    assert result.exit_code == 1


def test_e2e_012_tool_missing_from_core(clean: SkillTree) -> None:
    write_core(clean, drop=("update_end",))
    result = audit()
    assert 'PROBLEM tool "update_end" exists but is not listed in the core' in result.stdout
    assert result.exit_code == 1


def test_e2e_018_stale_statement_lower_case(clean: SkillTree) -> None:
    clean.topic_path("tables").write_text("Edit via GrapesJS here.\n\n", encoding="utf-8")
    result = audit()
    assert 'PROBLEM stale statement "grapesjs" in topic tables' in result.stdout
    assert result.exit_code == 1


def test_e2e_019_tool_count_in_core(clean: SkillTree) -> None:
    write_core(clean, prose="Le serveur expose 8 outils\n\n")
    result = audit()
    assert 'PROBLEM stale statement "8 outils" in core' in result.stdout
    assert result.exit_code == 1


def test_e2e_024_forced_commit_inside_code_block(clean: SkillTree) -> None:
    body = 'Rules.\n\n```bash\ngit commit -m "x"\n```\n\n```\nGrapesJS\n```\n'
    clean.topic_path("create").write_text(body, encoding="utf-8")
    result = audit()
    assert problems(result) == ['PROBLEM stale statement "git commit" in topic create']
    assert result.exit_code == 1


def test_e2e_027_routing_skill_not_found(
    skill_tree: SkillTree, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_core(skill_tree)
    monkeypatch.setenv("HTMLEDITOR_ROUTING_SKILL", str(tmp_path / "missing" / "SKILL.md"))
    config_module.reset_settings_cache()
    monkeypatch.setattr(skill_audit, "source_routing_skill_path", lambda: tmp_path / "nowhere" / "SKILL.md")
    result = audit()
    assert "PROBLEM routing skill not found" in result.stdout
    assert result.stdout.splitlines()[-1] == "skill-audit: FAIL (1 problem)"
    assert result.exit_code == 1


def test_stale_statement_in_routing_skill(clean: SkillTree, routing: Path) -> None:
    routing.write_text("Il y a 6 outils et 12 tools. localhost:7842\n", encoding="utf-8")
    assert problems(audit()) == [
        'PROBLEM stale statement "6 outils" in routing skill',
        'PROBLEM stale statement "localhost:7842" in routing skill',
        'PROBLEM stale statement "12 tools" in routing skill',
    ]


def test_problem_order(skill_tree: SkillTree, routing: Path) -> None:
    write_core(skill_tree, extra_tools=("zeta: x", "alpha: y"), drop=("get_status", "open_file"), prose="GrapesJS\n\n")
    skill_tree.topic_path("gantt").write_text("localhost:7842\n", encoding="utf-8")
    header = "# Skill topic: mail\n\n"
    skill_tree.topic_path("mail").write_text("x" * (8100 - len(header) - 1) + "\n", encoding="utf-8")
    routing.write_text("15 types\n", encoding="utf-8")
    assert problems(audit()) == [
        "PROBLEM topic mail is over its budget (8100 > 8000)",
        'PROBLEM tool "zeta" is listed in the core but does not exist',
        'PROBLEM tool "alpha" is listed in the core but does not exist',
        'PROBLEM tool "get_status" exists but is not listed in the core',
        'PROBLEM tool "open_file" exists but is not listed in the core',
        'PROBLEM stale statement "grapesjs" in core',
        'PROBLEM stale statement "localhost:7842" in topic gantt',
        'PROBLEM stale statement "15 types" in routing skill',
    ]


def test_core_removed_skips_core_checks(skill_tree: SkillTree, routing: Path) -> None:
    skill_tree.remove("core")
    skill_tree.topic_path("gantt").write_text("GrapesJS\n", encoding="utf-8")
    assert problems(audit()) == [
        "PROBLEM core is not installed",
        'PROBLEM stale statement "grapesjs" in topic gantt',
    ]


def test_run_audit_without_routing_text_reports_it_last(clean: SkillTree) -> None:
    library = build_library()
    report = run_audit(library, REAL_TOOLS, None)
    assert report.problems == ("routing skill not found",)
    assert run_audit(library, REAL_TOOLS, "clean").problems == ()


def test_run_audit_one_argument_form_still_works(clean: SkillTree) -> None:
    report = run_audit(build_library())
    assert report.problems[-1] == "routing skill not found"


def test_one_line_per_statement_per_location(clean: SkillTree) -> None:
    clean.topic_path("create").write_text("GrapesJS grapesjs GRAPESJS\n", encoding="utf-8")
    clean.topic_path("export").write_text("grapesjs\n", encoding="utf-8")
    assert problems(audit()) == [
        'PROBLEM stale statement "grapesjs" in topic create',
        'PROBLEM stale statement "grapesjs" in topic export',
    ]


def test_strip_fenced_blocks_unclosed_fence_runs_to_the_end() -> None:
    assert "secret" not in strip_fenced_blocks("a\n```\nsecret\nmore")
    assert strip_fenced_blocks("a\n```\nsecret").startswith("a\n")


def test_strip_fenced_blocks_tilde_fence() -> None:
    out = strip_fenced_blocks("before\n~~~\nhidden\n~~~\nafter")
    assert "hidden" not in out
    assert "before" in out
    assert "after" in out


def test_strip_fenced_blocks_longer_closing_fence_and_mismatch() -> None:
    out = strip_fenced_blocks("```\nhidden\n`````\nvisible")
    assert "hidden" not in out
    assert "visible" in out
    still_open = strip_fenced_blocks("````\nhidden\n```\nalso hidden\n````\nvisible")
    assert "also hidden" not in still_open
    assert "visible" in still_open
    assert "hidden" not in strip_fenced_blocks("```\nhidden\n~~~\nstill\n```\nvisible")


def test_find_stale_word_boundaries() -> None:
    assert find_stale("16 outils", include_counts=False) == []
    assert find_stale("16 types", include_counts=False) == []
    assert find_stale("15 types", include_counts=False) == ["15 types"]
    assert find_stale("115 types, 6 outilsx", include_counts=False) == []
    assert find_stale("Défauts d’export mesurés", include_counts=False) == ["défauts d’export mesurés"]
    assert find_stale("Défauts d'export  mesurés", include_counts=False) == ["défauts d'export mesurés"]
    assert find_stale("Défauts d'export\nmesurés", include_counts=False) == ["défauts d'export mesurés"]


def test_find_stale_ignores_never_assume_7842_and_fences() -> None:
    assert find_stale("never assume 7842", include_counts=False) == []
    assert find_stale("```\nGrapesJS\n```", include_counts=False) == []
    assert find_stale("```\ngit commit -m x\n```", include_counts=False) == ["git commit"]


def test_find_stale_counts_only_when_asked() -> None:
    assert find_stale("8 tools", include_counts=False) == []
    assert find_stale("8 tools and 3 Outils", include_counts=True) == ["8 tools", "3 outils"]
    assert find_stale("6 outils", include_counts=True) == ["6 outils"]


def test_find_stale_list_order_then_counts() -> None:
    text = "git commit and GrapesJS, 9 tools, 6 outils"
    assert find_stale(text, include_counts=True) == ["grapesjs", "6 outils", "git commit", "9 tools"]


def test_listed_tools_stops_at_next_heading() -> None:
    core = (
        "## Index\n- nope: x\n\n## Tools\n\n- one: a\n- two_b: b\nprose - three: c\n  - four: d\n## Other\n- five: e\n"
    )
    assert listed_tools(core) == ["one", "two_b"]
    assert listed_tools("no tools here") == []
    assert listed_tools("## Tools\n- last: x") == ["last"]


def test_read_routing_skill_prefers_installed(tmp_path: Path) -> None:
    installed = tmp_path / "installed.md"
    source = tmp_path / "source.md"
    source.write_text("source", encoding="utf-8")
    assert read_routing_skill(installed, source) == "source"
    installed.write_text("installed", encoding="utf-8")
    assert read_routing_skill(installed, source) == "installed"
    assert read_routing_skill(tmp_path / "a", tmp_path / "b") is None


def test_source_routing_skill_path_ignores_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = source_routing_skill_path()
    assert path.parts[-3:] == ("dynamic-skills", "html-editor", "SKILL.md")
    assert path.is_absolute()


def test_routing_skill_path_setting(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("HTMLEDITOR_ROUTING_SKILL", raising=False)
    config_module.reset_settings_cache()
    assert config_module.routing_skill_path() == Path.home() / ".pi/agent/dynamic-skills/html-editor/SKILL.md"
    monkeypatch.setenv("HTMLEDITOR_ROUTING_SKILL", str(tmp_path / "x.md"))
    config_module.reset_settings_cache()
    assert config_module.routing_skill_path() == tmp_path / "x.md"


def test_fenced_block_indented_inside_a_list_is_ignored() -> None:
    assert find_stale("- item\n      ```\n      GrapesJS\n      ```\n", include_counts=False) == []


def test_registered_tool_names_works_with_a_running_event_loop() -> None:
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    from mcp_htmleditor.mcp_server import registered_tool_names

    async def call() -> list[str]:
        return registered_tool_names()

    with ThreadPoolExecutor(max_workers=1) as pool:  # own thread: other tests may leave a loop in this one
        assert pool.submit(lambda: asyncio.run(call())).result() == registered_tool_names()
