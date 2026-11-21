# US-0169: the layout reload keeps the undo history

> Spec: SPEC-0031 (sdlc/specs/SPEC-0031-arch-edit-undo-kept/)
> Nature: BUG
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 5
> Closes spec: yes

## Objective
After adding or removing a node or creating an edge in a declarative diagram, Undo and Redo work: the reload that follows the layout run no longer empties the history. Closes SPEC-0031.

## Requirements covered
- SPEC-0031/BR-001: WHEN the person adds a node, removes a node or creates an edge in a declarative diagram and the layout run rewrites the file THE editor SHALL show the diagram with its recomputed positions and SHALL keep the undo and redo history it had, with the edit as the last undo step. A layout run that changes nothing causes no reload and no change.
- SPEC-0031/BR-002: Undo restores the diagram as it was before the edit and saves it.
- SPEC-0031/BR-003: Redo shows the edit again and saves it.
- SPEC-0031/BR-004: a reload for any reason other than the editor's own layout run (an agent write, another file) still empties the history.

## Independent Test
`make test ARGS='tests/test_arch_edit_undo_e2e.py tests/test_style_text_marks_e2e.py'` green, `make check` green. BT-001 reads `#undo-btn` disabled before the change.

## Design excerpt
### Decisions
DEC-001 keep the history across the editor's own layout reload; DEC-002 a 5 second window opened only when `diagrams_updated > 0`.
### Contracts
`src/mcp_htmleditor/static/editor.js`: `let keepUndoUntil = 0;` next to `undoStack` (line ~489); in `onFrameLoad` replace the final `resetUndoStacks();` (line ~351, after the `restoringFromUndo` early return) by `if (Date.now() < keepUndoUntil) { keepUndoUntil = 0; updateUndoRedoButtons(); } else resetUndoStacks();`.
`src/mcp_htmleditor/static/editor-menus.js` `saveThenLayout` (line 36): `const ARCH_LAYOUT_RELOAD_MS = 5000;` at module level; after `const body = await res.json();` add `if (body.diagrams_updated > 0) keepUndoUntil = Date.now() + ARCH_LAYOUT_RELOAD_MS;`.
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor.js` | modify |
| `src/mcp_htmleditor/static/editor-menus.js` | modify |
| `tests/test_arch_edit_undo_e2e.py` | create |
| `tests/test_style_text_marks_e2e.py` | modify (BT-018, declared by the spec) |
| `.agent_docs/testing.md` | modify (file map row; keep within 220 lines) |
### Existing patterns
`tests/test_style_text_marks_e2e.py` (`_open_slide_3`, `_start_connect`, `dispatch_event("click")` on `[data-id="n2"]`, `width_page` fixture, Deck S via `serve_deck_s`), `tests/test_undo_redo_e2e.py` (`#undo-btn`, `#redo-btn`), `tests/test_style_text_actions_e2e.py` (agent write helper idea: rewrite the file with a later mtime as `tests/test_save_ui_e2e.py::_agent_writes_title`).

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc. Deck S as in SPEC-0020 (`tests/style_text_support.py`), slide 3, edit mode on; the label prompt accepted empty (`page.once("dialog", ...)`).
### SPEC-0031/BT-001: the undo button stays enabled after an edge is created (reproduction)
- Fails today because `editor.js:351` empties the stacks on the layout reload.
- When the person creates an edge from `Serveur MCP` to `Base`, waits until the file holds `data-type="arch-edge"` and the page has reloaded (the page's diagram holds the edge and `n1` has a `left` declaration from the layout) / Then `#undo-btn` is enabled
### SPEC-0031/BT-002: Undo removes the edge, Redo brings it back
- When the person clicks `#undo-btn` / Then the file has no `arch-edge` and the page's diagram has none; when the person clicks `#redo-btn` / Then both hold the edge again
### SPEC-0031/BT-003: undo of a node added to a declarative diagram
- When the person right clicks the declarative diagram, chooses `＋ Ajouter nœud (rangée existante ou nouvelle)`, answers the prompts (label `Cache`, then the choice that creates a node in the existing row), waits for the reload / Then clicking `#undo-btn` leaves no `Cache` in the file and in the page
### SPEC-0031/BT-004: an agent write still empties the history (non regression)
- After the edge and the layout reload, wait 5 seconds (the window), then an agent write (rewrite the file with a later modification time) reloads the page / Then `#undo-btn` is disabled
### SPEC-0031/BT-005: the earlier history is kept
- Insert a slide with `#btn-insert-after` and the first picker card, then create the edge: two clicks on `#undo-btn` revert the edge then the slide
### SPEC-0031/BT-006: SPEC-0020 BT-018 as written (modified test)
- `test_bt018_connect_mode_the_undo_snapshot_holds_no_mark` gains: after the edge is in the file, wait for the reload, click `#undo-btn`, wait until the file has no `arch-edge`; then `n1`'s style holds exactly one `outline` (`outline:1px dashed #8D8D8D`), the file has no `crosshair` and no `data-mcp-mark`, `<body>` has no `style`. Update its docstring (the undo step now runs).

## Constraints
- Files not to touch: `editor-undo.js`, `http_server.py`, templates, other tests.
- Dependencies not to add: none.

## Definition of done
- [ ] RED evidence for BT-001, BT-002, BT-003, BT-005, BT-006 before the fix.
- [ ] Every test above green; `node --check src/mcp_htmleditor/static/*.js` clean; `make check` green on the work branch after this commit.
- [ ] Spec converge: every test of SPEC-0031 green, every requirement BR-001 to BR-004 covered.
- [ ] Docs updated: `.agent_docs/testing.md`.
- [ ] One commit `US-0169: the layout reload keeps the undo history`, body with `Summary:`, `Spec: SPEC-0031` and the requirement ids.
