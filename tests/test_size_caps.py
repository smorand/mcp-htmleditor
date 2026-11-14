"""Size caps of the split exporter and editor scripts (SPEC-0012 DR-004, DR-006)."""

from __future__ import annotations

from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "mcp_htmleditor"
EXPORT = SOURCE / "export"
STATIC = SOURCE / "static"

TO_PPTX_CAP = 600
NEW_MODULE_CAP = 450
SCRIPT_CAP = 500

NEW_EXPORT_MODULES = (
    "pptx_model.py",
    "pptx_text.py",
    "pptx_images.py",
    "pptx_arch.py",
    "pptx_gantt.py",
    "pptx_blocks.py",
    "pptx_flow.py",
    "pptx_chrome.py",
    "pptx_paint.py",
    "pptx_paint_js.py",
    "pptx_paint_shapes.py",
    "pptx_paint_style.py",
    "pptx_paint_tables.py",
    "pptx_paint_text.py",
)
EDITOR_SCRIPTS = (
    "editor.js",
    "editor-undo.js",
    "editor-edit.js",
    "editor-format.js",
    "editor-menus.js",
    "editor-save.js",
    "editor-slides.js",
    "editor-blocks.js",
    "editor-drag.js",
)


def count_lines(path: Path) -> int:
    """Return the number of lines of a text file."""
    return len(path.read_text(encoding="utf-8").splitlines())


def test_to_pptx_stays_under_its_cap() -> None:
    """The composed builder entry file holds at most 600 lines."""
    assert count_lines(EXPORT / "to_pptx.py") <= TO_PPTX_CAP


@pytest.mark.parametrize("name", NEW_EXPORT_MODULES)
def test_new_export_module_stays_under_its_cap(name: str) -> None:
    """Each new exporter module holds at most 450 lines."""
    assert count_lines(EXPORT / name) <= NEW_MODULE_CAP


@pytest.mark.parametrize("name", EDITOR_SCRIPTS)
def test_editor_script_stays_under_its_cap(name: str) -> None:
    """editor.js and each new editor script hold at most 500 lines."""
    assert count_lines(STATIC / name) <= SCRIPT_CAP
