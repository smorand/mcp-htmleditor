"""SPEC-0017 (US-0105): ``tools/sync_deck_pointer.py`` copies the pointer block to every presentation template.

The tool runs in process through ``sync(root, check)`` on a small templates root in ``tmp_path``, never on
the repository. One test runs it as a subprocess on the real repository (only the source holds the block).
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = "tools/sync_deck_pointer.py"
BEGIN = "<!-- deck-pointer:begin -->"
END = "<!-- deck-pointer:end -->"
SOURCE_REL = "bootstrap/slides-empty.html"
STALE_REL = "reference/slides/stale.html"
FRESH_REL = "reference/slides/fresh.html"
PLAIN_REL = "reference/slides/plain.html"
DOCUMENT_REL = "reference/documents/doc.html"

BLOCK = f'{BEGIN}\n<script id="deck-pointer-script">window.togglePointer = function () {{}};</script>\n{END}'
OLD_BLOCK = f'{BEGIN}\n<script id="deck-pointer-script">/* old */</script>\n{END}'


def page(doc_type: str, block: str | None) -> str:
    body = f"<h1>x</h1>\n{block}\n" if block is not None else "<h1>x</h1>\n"
    return f'<!DOCTYPE html>\n<html lang="en" data-doc-type="{doc_type}">\n<body>\n{body}</body>\n</html>\n'


@pytest.fixture
def tool(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(REPO_ROOT / "tools"))
    sys.modules.pop("sync_deck_pointer", None)
    return importlib.import_module("sync_deck_pointer")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A templates root: the source, a stale and a fresh target, a plain presentation and a document."""
    templates = tmp_path / "templates"
    files = {
        SOURCE_REL: page("presentation", BLOCK),
        STALE_REL: page("presentation", OLD_BLOCK),
        FRESH_REL: page("presentation", BLOCK),
        PLAIN_REL: page("presentation", None),
        DOCUMENT_REL: page("document", OLD_BLOCK),
    }
    for rel, text in files.items():
        path = templates / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return templates


def snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*.html"))}


def test_check_reports_stale_and_fresh_targets_and_writes_nothing(
    tool: ModuleType, root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = snapshot(root)

    code = tool.sync(root, True)

    out = capsys.readouterr().out
    assert code == 1
    assert f"templates/{STALE_REL}: stale (first difference at line 6); run: make sync-deck-pointer\n" in out
    assert f"templates/{FRESH_REL}: fresh\n" in out
    assert snapshot(root) == before


def test_sync_rewrites_the_stale_block_then_check_passes(
    tool: ModuleType, root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert tool.sync(root, False) == 0

    assert (root / STALE_REL).read_text(encoding="utf-8") == page("presentation", BLOCK)
    capsys.readouterr()
    assert tool.sync(root, True) == 0
    out = capsys.readouterr().out
    assert f"templates/{STALE_REL}: fresh\n" in out
    assert "stale (" not in out


def test_files_without_the_markers_or_not_presentations_are_untouched(tool: ModuleType, root: Path) -> None:
    before = snapshot(root)

    assert tool.sync(root, False) == 0

    after = snapshot(root)
    for rel in (SOURCE_REL, PLAIN_REL, DOCUMENT_REL, FRESH_REL):
        assert after[rel] == before[rel], rel
    assert after[STALE_REL] != before[STALE_REL]


def test_check_lists_neither_the_source_nor_the_untargeted_files(
    tool: ModuleType, root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tool.sync(root, True)

    out = capsys.readouterr().out
    for rel in (SOURCE_REL, PLAIN_REL, DOCUMENT_REL):
        assert rel not in out


def test_target_with_begin_but_no_end_is_an_error_naming_it(tool: ModuleType, root: Path) -> None:
    (root / STALE_REL).write_text(page("presentation", BEGIN), encoding="utf-8")

    with pytest.raises(SystemExit) as raised:
        tool.sync(root, False)

    assert STALE_REL in str(raised.value)
    assert END in str(raised.value)


def test_source_without_the_block_is_an_error_naming_it(tool: ModuleType, root: Path) -> None:
    (root / SOURCE_REL).write_text(page("presentation", None), encoding="utf-8")

    for check in (True, False):
        with pytest.raises(SystemExit) as raised:
            tool.sync(root, check)
        assert SOURCE_REL in str(raised.value)


def test_a_banner_comment_quoting_the_html_tag_does_not_make_a_document_a_target(tool: ModuleType, root: Path) -> None:
    text = f'<!-- <html data-doc-type="presentation"> -->\n{page("document", OLD_BLOCK)}'
    (root / DOCUMENT_REL).write_text(text, encoding="utf-8")

    assert tool.sync(root, False) == 0

    assert (root / DOCUMENT_REL).read_text(encoding="utf-8") == text


def test_real_templates_check_passes_because_only_the_source_holds_the_block() -> None:
    result = subprocess.run(  # noqa: S603  # fixed argv: this interpreter and a repo tool
        [sys.executable, TOOL, "--check"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60, check=False
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "stale" not in result.stdout
    assert "missing" not in result.stdout


def test_makefile_wires_the_tool_into_sync_and_check_generated() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "sync-deck-pointer:\n\t@uv run python tools/sync_deck_pointer.py\n" in makefile
    assert "uv run python tools/sync_deck_pointer.py --check || rc=1; exit $$rc" in makefile
