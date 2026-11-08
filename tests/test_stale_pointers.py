"""Structural guards against pointers to removed skill files or moved editor code (SPEC-0018)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner

REPO = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO / "skill"
TOPICS_DIR = SKILL_DIR / "topics"
STATIC_DIR = REPO / "src" / "mcp_htmleditor" / "static"

WALK_ROOTS = ("src", "tests", "templates", "tools", "skill", "dynamic-skills", ".agent_docs", "docs")
WALK_FILES = ("README.md", "AGENTS.md", "Makefile", "Dockerfile")
SUFFIXES = {".py", ".js", ".html", ".css", ".md", ".json", ".toml", ".yml", ".yaml"}
BARE_NAMES = {"Makefile", "Dockerfile"}
SKIPPED_DIRS = {"__pycache__"}
SKIPPED_PREFIX = REPO / "docs" / "skill-archive"
ALLOWED_FILES = {REPO / "tests" / "test_arch_checks.py", Path(__file__).resolve()}

REMOVED_TOKENS = ("skill/" + "types/", "skill/" + "workflow-", ".pi/" + "skills/")
OLD_SPECS = re.compile(r"(?<![\w/])specs/(\*\.md|BACKLOG\.md)")
TOPIC_PATH = re.compile(r"skill/topics/([a-z][a-z-]*)\.md")
TOPIC_COMMAND = re.compile(r"skill --type ([a-z][a-z-]*)")

FORM_A = re.compile(r"(?:voir|see|Voir|See) ([\w-]+\.js)(?:'s)? `{0,2}(\w+)")
FORM_B = re.compile(r"(?:voir|see|Voir|See) `{0,2}(\w+)`{0,2} in (?:static/)?([\w-]+\.js)")
FORM_C = re.compile(r"`{0,2}(\w+)\(\)`{0,2} (?:in `{0,2}|\()(?:static/)?([\w-]+\.js)")

BADGE_SENTENCE = "Le badge est exporté en PPTX (cercle numéroté)."


def _is_walked(path: Path) -> bool:
    if path in ALLOWED_FILES or path.is_relative_to(SKIPPED_PREFIX):
        return False
    if SKIPPED_DIRS.intersection(path.parts):
        return False
    return path.suffix in SUFFIXES or path.name in BARE_NAMES


def _walked_files() -> Iterator[Path]:
    for name in WALK_FILES:
        path = REPO / name
        if path.is_file():
            yield path
    for root in WALK_ROOTS:
        for path in sorted((REPO / root).rglob("*")):
            if path.is_file() and _is_walked(path):
                yield path


def _lines(path: Path) -> Iterator[tuple[int, str]]:
    yield from enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1)


def _location(path: Path, number: int) -> str:
    return f"{path.relative_to(REPO)}:{number}"


def _is_doc_with_spec_rule(path: Path) -> bool:
    return (path.name in {"AGENTS.md", "README.md"} and path.parent == REPO) or path.parent == REPO / ".agent_docs"


def test_no_removed_skill_path_survives() -> None:
    hits = []
    for path in _walked_files():
        checks_specs = _is_doc_with_spec_rule(path)
        for number, line in _lines(path):
            if any(token in line for token in REMOVED_TOKENS) or (checks_specs and OLD_SPECS.search(line)):
                hits.append(_location(path, number))
    assert hits == [], f"{len(hits)} stale pointer lines:\n" + "\n".join(hits)


def test_every_skill_pointer_resolves() -> None:
    stems = {path.stem for path in TOPICS_DIR.glob("*.md")}
    broken = []
    for path in _walked_files():
        for number, line in _lines(path):
            names = TOPIC_PATH.findall(line) + TOPIC_COMMAND.findall(line)
            broken.extend(f"{_location(path, number)}: {name}" for name in names if name not in stems)
    assert broken == []


def _script_scan_files() -> Iterator[Path]:
    package = REPO / "src" / "mcp_htmleditor"
    yield from sorted(package.rglob("*.py"))
    yield from sorted(STATIC_DIR.glob("*.js"))
    yield from sorted(STATIC_DIR.glob("*.css"))
    yield from (path for path in sorted((REPO / "tests").glob("*.py")) if path != Path(__file__).resolve())


def _script_pointers(line: str) -> Iterator[tuple[str, str]]:
    for script, name in FORM_A.findall(line):
        yield script, name
    for name, script in FORM_B.findall(line):
        yield script, name
    for name, script in FORM_C.findall(line):
        yield script, name


def test_script_comment_pointers_resolve() -> None:
    matches = 0
    broken = []
    for path in _script_scan_files():
        for number, line in _lines(path):
            for script, name in _script_pointers(line):
                matches += 1
                target = STATIC_DIR / script
                if not target.is_file() or f"function {name}(" not in target.read_text(encoding="utf-8"):
                    broken.append(f"{_location(path, number)}: {script} {name}")
    assert matches > 0
    assert broken == []


@pytest.fixture
def real_tree(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from mcp_htmleditor import cli as cli_module
    from mcp_htmleditor import config as config_module

    monkeypatch.setenv("HTMLEDITOR_SKILL_DIR", str(SKILL_DIR))
    monkeypatch.setattr(cli_module, "configure_tracing", lambda settings=None: None)
    config_module.reset_settings_cache()
    yield
    config_module.reset_settings_cache()


@pytest.mark.usefixtures("real_tree")
def test_arch_diagram_topic_states_the_exported_badge() -> None:
    from mcp_htmleditor.cli import main

    result = CliRunner().invoke(main, ["skill", "--type", "arch-diagram"])
    assert result.exit_code == 0
    assert BADGE_SENTENCE in result.stdout
    assert "n'est pas converti" not in result.stdout
