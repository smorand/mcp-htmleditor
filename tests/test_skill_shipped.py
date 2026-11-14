"""Gates on the shipped skill tree: the core, the routing skill and all 16 topic files (SPEC-0006)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from mcp_htmleditor import arch_checks
from mcp_htmleditor.skill_content import TOPIC_NAMES, SkillLibrary

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
    "outline",
    "get_slide",
    "patch",
}
TEMPLATE_KEYS = ("ei", "carbon", "medical", "breathe", "doc", "doc-perso", "doc-ei", "mail", "website")
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
    "breathe": "templates/reference/slides/breathe.html",
    "document": "templates/reference/documents/report-standard.html",
    "mail": "templates/reference/documents/mail-carbon-example.html",
    "website": "templates/reference/websites/ibm-carbon.html",
}
ARCHIVE_FILES = (
    "index.md",
    "slides.md",
    "medical.md",
    "workflow-create.md",
    "workflow-export.md",
    "workflow-templates.md",
    "workflow-arch-qa.md",
    "document.md",
    "mail.md",
    "website.md",
    "tables.md",
    "gantt.md",
    "annotated-image.md",
    "arch-diagram.md",
    "arch-diagram-checklist.md",
)
DASHES = ("\u2014", "\u2013")


def _library() -> SkillLibrary:
    return SkillLibrary(SKILL_DIR, arch_checks.read_shipped_checklist)


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
    """SPEC-0006/E2E-001: `skill` on the real tree prints the core with tools and the 16 topic lines."""
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


def _topic_problems(skill_dir: Path, topic: str) -> list[str]:
    """Every gate a shipped topic must satisfy; a missing file is a problem, never skipped."""
    from mcp_htmleditor.skill_audit import find_stale

    if not (skill_dir / "topics" / f"{topic}.md").is_file():
        return [f"{topic}: file missing"]
    text = SkillLibrary(skill_dir, arch_checks.read_shipped_checklist).topic_output(topic)
    lines = text.splitlines()
    problems: list[str] = []
    if len(text.encode("utf-8")) > TOPIC_BUDGET_BYTES:
        problems.append(f"{topic}: over budget")
    if lines[0] != f"# Skill topic: {topic}":
        problems.append(f"{topic}: wrong title line")
    if not text.endswith("\n") or text.endswith("\n\n"):
        problems.append(f"{topic}: wrong final newline")
    problems += [f"{topic}: stale {word}" for word in find_stale(text, include_counts=False)]
    if any(dash in text for dash in DASHES):
        problems.append(f"{topic}: dash")
    references = [line for line in lines if line.startswith("Reference:")]
    expected = [f"Reference: {REFERENCES[topic]}"] if topic in REFERENCES else []
    if references != expected or (expected and lines[-1] != expected[0]):
        problems.append(f"{topic}: Reference line {references}")
    problems += [f"{topic}: anchor {anchor!r} missing" for anchor in _anchors().get(topic, []) if anchor not in text]
    return problems


def _copy_tree(tmp_path: Path) -> Path:
    target = tmp_path / "skill"
    shutil.copytree(SKILL_DIR, target)
    return target


def _run_audit(monkeypatch: pytest.MonkeyPatch, skill_dir: Path) -> Result:
    """Run `skill-audit` on skill_dir with the source routing skill and no installed one."""
    from mcp_htmleditor import cli as cli_module
    from mcp_htmleditor import config as config_module
    from mcp_htmleditor.cli import main

    monkeypatch.setenv("HTMLEDITOR_SKILL_DIR", str(skill_dir))
    monkeypatch.setenv("HTMLEDITOR_ROUTING_SKILL", str(ROUTING_SKILL))
    monkeypatch.setattr(cli_module, "configure_tracing", lambda settings=None: None)
    config_module.reset_settings_cache()
    try:
        return CliRunner().invoke(main, ["skill-audit"], input="")
    finally:
        config_module.reset_settings_cache()


def test_every_topic_file_exists() -> None:
    """All 16 topic files ship; a missing one is a failure, never skipped."""
    assert len(TOPIC_NAMES) == 16
    missing = [name for name in TOPIC_NAMES if not (SKILL_DIR / "topics" / f"{name}.md").is_file()]
    assert missing == []


@pytest.mark.parametrize("topic", TOPIC_NAMES)
def test_shipped_topic_gates(topic: str) -> None:
    assert _topic_problems(SKILL_DIR, topic) == []


def test_topic_gate_catches_a_missing_file(tmp_path: Path) -> None:
    tree = _copy_tree(tmp_path)
    (tree / "topics" / "gantt.md").unlink()
    assert _topic_problems(tree, "gantt") == ["gantt: file missing"]


def test_topic_gate_catches_a_stale_word(tmp_path: Path) -> None:
    tree = _copy_tree(tmp_path)
    path = tree / "topics" / "mail.md"
    path.write_text(path.read_text(encoding="utf-8").rstrip() + "\nGrapesJS\n", encoding="utf-8")
    assert "mail: stale grapesjs" in _topic_problems(tree, "mail")


def test_reference_line_only_on_reference_topics() -> None:
    with_reference = {
        t for t in TOPIC_NAMES if (SKILL_DIR / "topics" / f"{t}.md").read_text("utf-8").count("\nReference:")
    }
    assert with_reference == set(REFERENCES)
    assert len(REFERENCES) == 7


def test_anchors_cover_every_topic_but_arch_qa() -> None:
    anchors = _anchors()
    assert set(anchors) == set(TOPIC_NAMES) - {"arch-qa"}
    assert all(anchors[name] for name in anchors)


def test_all_equals_core_plus_topics(real_tree: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """E2E-003 on the real tree: core then the 16 topics, one empty line between parts."""
    from mcp_htmleditor import config as config_module
    from mcp_htmleditor.cli import main

    monkeypatch.setenv("HTMLEDITOR_ARCH_CHECKS_DIR", str(tmp_path / "no-user-checklist"))
    config_module.reset_settings_cache()
    library = _library()
    expected = "\n".join([library.core_output(), *(library.topic_output(t) for t in TOPIC_NAMES)])
    result = CliRunner().invoke(main, ["skill", "--all"])
    assert result.exit_code == 0
    assert result.stdout == expected
    parts = [library.core_output(), *(library.topic_output(t) for t in TOPIC_NAMES)]
    assert len(result.stdout_bytes) == sum(len(p.encode("utf-8")) for p in parts) + len(parts) - 1


def test_legacy_files_gone_and_archive_present() -> None:
    assert not (SKILL_DIR / "SKILL.md").exists()
    assert not (SKILL_DIR / "types").exists()
    assert list(SKILL_DIR.glob("workflow-*.md")) == []
    archive = REPO / "docs" / "skill-archive"
    for name in ARCHIVE_FILES:
        assert (archive / name).is_file(), name


def test_e2e_006_clean_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """SPEC-0006/E2E-006: the real tree audit prints 16 OK lines and a clean verdict."""
    result = _run_audit(monkeypatch, SKILL_DIR)
    out = result.stdout.splitlines()
    assert result.exit_code == 0, result.stdout
    assert out[-1] == "skill-audit: OK"
    items = out[:-1]
    assert [line.split(":")[0] for line in items] == ["core", *TOPIC_NAMES]
    assert all(line.endswith(" OK") for line in items)
    assert not any(line.startswith("PROBLEM") for line in out)


def test_audit_fails_when_a_topic_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tree = _copy_tree(tmp_path)
    (tree / "topics" / "tables.md").unlink()
    result = _run_audit(monkeypatch, tree)
    assert result.exit_code == 1
    assert result.stdout.splitlines()[-1].startswith("skill-audit: FAIL")


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


def _sentences(text: str) -> Iterator[str]:
    for line in text.splitlines():
        yield from re.split(r"\. |: ", line)


def test_no_topic_states_a_fullscreen_gap_on_the_carbon_reference(real_tree: None) -> None:
    """SPEC-0016/BT-024: no sentence holds `ibm-carbon` with `:fullscreen` or `plein écran`; the 540 px clause stays."""
    offenders = [
        f"{path.name}: {sentence}"
        for path in sorted((SKILL_DIR / "topics").glob("*.md"))
        for sentence in _sentences(path.read_text(encoding="utf-8"))
        if "ibm-carbon" in sentence and (":fullscreen" in sentence or "plein écran" in sentence)
    ]
    assert offenders == []

    from mcp_htmleditor.cli import main

    result = CliRunner().invoke(main, ["skill", "--type", "slides-carbon"])
    assert result.exit_code == 0
    assert "dépassent 540 px" in result.stdout
    assert any("ibm-carbon.html" in s and "dépassent 540 px" in s for s in _sentences(result.stdout))
    assert not any(":fullscreen" in s for s in _sentences(result.stdout) if "ibm-carbon" in s)
    assert len(result.stdout.encode("utf-8")) <= TOPIC_BUDGET_BYTES


POINTER_WORDS = (
    ("L", re.compile(r"\bL\b")),
    ("Pointeur", re.compile(r"Pointeur")),
    ("click", re.compile(r"click|clic")),
    ("ring", re.compile(r"ring|entoure")),
    ("starts off", re.compile(r"starts off|démarre éteint")),
    ("file", re.compile(r"\bfile\b|fichier")),
)


def _pointer_sentence_gaps(text: str) -> list[str]:
    """Words missing from the best sentence (split on `. ` and line ends) that names the pointer."""
    best: list[str] | None = None
    for sentence in _sentences(text):
        missing = [name for name, word in POINTER_WORDS if not word.search(sentence)]
        if best is None or len(missing) < len(best):
            best = missing
    return best if best is not None else [name for name, _ in POINTER_WORDS]


def test_readme_and_slides_topic_each_state_the_pointer_in_one_sentence(real_tree: None) -> None:
    """SPEC-0017/E2E-034: one sentence of each text names L, Pointeur, click, ring, starts off and file."""
    from mcp_htmleditor.cli import main

    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "### Presenting" in readme
    presenting = readme.split("### Presenting", 1)[1].split("\n### ", 1)[0]
    result = CliRunner().invoke(main, ["skill", "--type", "slides-carbon"])
    assert result.exit_code == 0
    assert _pointer_sentence_gaps(presenting) == []
    assert _pointer_sentence_gaps(result.stdout) == []
    assert len(result.stdout.encode("utf-8")) <= TOPIC_BUDGET_BYTES
