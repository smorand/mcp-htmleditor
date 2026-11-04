"""Shared pytest fixtures for mcp-htmleditor tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from mcp_htmleditor import config as config_module
from mcp_htmleditor import state as state_module


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    """Drop the memoized Settings around each test.

    Settings are memoized on an environment signature, so a test that sets
    HTMLEDITOR_* variables must not hand its instance over to the next one.
    """
    config_module.reset_settings_cache()
    yield
    config_module.reset_settings_cache()


@pytest.fixture(autouse=True)
def isolate_state_dir(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HTMLEDITOR_STATE_DIR at a per test directory, so no test touches the real ~/.local/state."""
    state_dir = tmp_path_factory.mktemp("state") / "mcp-htmleditor"
    monkeypatch.setenv("HTMLEDITOR_STATE_DIR", str(state_dir))
    config_module.reset_settings_cache()
    return state_dir


@pytest.fixture
def reset_state() -> Iterator[None]:
    """Reset the EditorState singleton around each test.

    EditorState is a process-wide singleton keyed on a class attribute.
    Tests must start from a clean instance so state does not leak between
    cases.
    """
    state_module.EditorState._instance = None
    state_module.EditorState._initialized = False
    yield
    state_module.EditorState._instance = None
    state_module.EditorState._initialized = False


@pytest.fixture
def fresh_state(reset_state: None) -> state_module.EditorState:
    """Return a freshly initialized EditorState singleton."""
    return state_module.get_state()


@pytest.fixture
def html_file(tmp_path: Path) -> Path:
    """Write a minimal HTML file into tmp_path and return its path."""
    path = tmp_path / "doc.html"
    path.write_text(
        "<!DOCTYPE html>\n<html><head><title>t</title></head><body><p>hello</p></body></html>",
        encoding="utf-8",
    )
    return path


SKILL_TOPICS: tuple[tuple[str, str], ...] = (
    ("create", "Create and edit a file: workflows, rules for text, slides and images"),
    ("export", "Export to PPTX and DOCX: what is kept, approximated, lost"),
    ("templates", "Build a template from an existing PPTX or DOCX"),
    ("slides-carbon", "Rules for IBM Carbon slides"),
    ("slides-ei", "Rules for Euro-Information slides"),
    (
        "medical",
        "Rules for medical slides: layouts, light and dark surfaces, widths, readability, height budget",
    ),
    ("medical-sources", "Medical slides: citing sources and anonymising patient images"),
    ("document", "Rules for Word-like documents and their DOCX export"),
    ("mail", "Rules for HTML mails"),
    ("website", "Rules for single page websites"),
    ("gantt", "Rules for Gantt charts"),
    ("arch-diagram", "Rules for architecture diagrams"),
    ("arch-qa", "Visual quality review of architecture diagrams and its checklist"),
    ("annotated-image", "Rules for annotated images"),
    ("tables", "Rules for tables"),
)

SKILL_CORE_TITLE = "# mcp-htmleditor skill (core)"


class SkillTree:
    """A generated skill tree (core, 15 topics, checklist) rooted in a temporary directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.core_path = root / "core.md"
        self.checklist_path = root / "checks" / "arch-diagram-checklist.md"

    def topic_path(self, name: str) -> Path:
        return self.root / "topics" / f"{name}.md"

    def write_core(self, text: str) -> None:
        self.core_path.write_text(text, encoding="utf-8")

    def remove(self, name: str) -> None:
        """Remove a topic file, or the core when name is 'core'."""
        path = self.core_path if name == "core" else self.topic_path(name)
        path.unlink()

    def grow(self, path: Path, to_bytes: int) -> None:
        """Append ASCII text until the file holds to_bytes bytes."""
        missing = to_bytes - path.stat().st_size
        if missing > 0:
            with path.open("a", encoding="ascii") as handle:
                handle.write("x" * missing)


@pytest.fixture
def skill_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SkillTree:
    """Build a valid temporary skill tree and point the settings at it."""

    def build(tools: str = "") -> SkillTree:
        tree = SkillTree(tmp_path / "skill")
        (tree.root / "topics").mkdir(parents=True)
        tree.checklist_path.parent.mkdir(parents=True)
        index = "\n".join(
            f"{name}: {description}. Load: mcp-htmleditor skill --type {name}" for name, description in SKILL_TOPICS
        )
        tree.write_core(f"{SKILL_CORE_TITLE}\n\n## Index\n\n{index}\n\n## Tools\n\n{tools}\n\n")
        for name, _ in SKILL_TOPICS:
            tree.topic_path(name).write_text(f"## Rules for {name}\n\nBody of {name}.\n\n\n", encoding="utf-8")
        tree.checklist_path.write_text("- [ ] checklist item\n\n", encoding="utf-8")
        return tree

    tree = build()
    monkeypatch.setenv("HTMLEDITOR_SKILL_DIR", str(tree.root))
    monkeypatch.setenv("HTMLEDITOR_ARCH_CHECKS_DIR", str(tmp_path / "empty-checks"))
    config_module.reset_settings_cache()
    return tree
