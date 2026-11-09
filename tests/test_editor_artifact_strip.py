"""DT-012 (SPEC-0019 DR-003): the editor artifacts are stripped by one function, used by the undo and the save."""

from __future__ import annotations

import re
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "src" / "mcp_htmleditor" / "static"
STRIP_DEFINITION = "function stripEditorArtifacts("
STRIP_CALL = "stripEditorArtifacts("
CE_REMOVAL = "removeAttribute('contenteditable')"
NEXT_FUNCTION = re.compile(r"^(?:async )?function ", re.MULTILINE)


def _scripts() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(STATIC_DIR.glob("*.js"))}


def _body(declaration: str) -> str:
    """Text from ``declaration`` to the next line starting with a function declaration at column 0."""
    holders = [text for text in _scripts().values() if declaration in text]
    assert len(holders) == 1, f"{declaration} defined {len(holders)} times"
    text = holders[0]
    start = text.index(declaration)
    following = NEXT_FUNCTION.search(text, start + len(declaration))
    return text[start : following.start() if following else len(text)]


def test_artifact_strip_is_defined_once_in_editor_save() -> None:
    definitions = {name: text.count(STRIP_DEFINITION) for name, text in _scripts().items() if STRIP_DEFINITION in text}
    assert definitions == {"editor-save.js": 1}, f"definitions found: {definitions}"


def test_artifact_strip_is_used_by_snapshot_and_save() -> None:
    for declaration in ("function captureDomSnapshot(", "async function runSave("):
        body = _body(declaration)
        assert STRIP_CALL in body, f"{declaration} does not call {STRIP_CALL}"
        assert CE_REMOVAL not in body, f"{declaration} still strips contenteditable itself"


def test_artifact_strip_contenteditable_removals() -> None:
    removals = {name: text.count(CE_REMOVAL) for name, text in _scripts().items() if CE_REMOVAL in text}
    assert removals == {"editor-save.js": 1, "editor-drag.js": 1}, f"removals found: {removals}"
