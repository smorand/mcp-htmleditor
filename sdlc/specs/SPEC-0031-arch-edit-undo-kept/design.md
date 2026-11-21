# SPEC-0031: A diagram edit stays undoable after the layout run, design

> Spec: sdlc/specs/SPEC-0031-arch-edit-undo-kept/spec.md
> Nature: BUG
> Depth: S
> Security: n/a
> Designed on: 2026-11-20
> Target tier: 2 (default)

## 1. Stack and skills
Existing stack: vanilla JS editor scripts, Playwright e2e (`make check`). No dependency. Skill python: `make` only.

## 2. Approaches
### Chosen: mark the reload the layout run causes and skip the history reset for that one load
`saveThenLayout` knows the server rewrote the file (the answer carries `diagrams_updated`). It opens a short window during which the next frame load keeps the undo and redo stacks. The snapshots are full documents taken before the edit, so they stay valid after the positions change.
### Rejected: apply the recomputed positions without reloading
The server only writes the file; the page would need the positions back and a second diff path (DEC-001).

## 3. Architecture
`editor-menus.js` `saveThenLayout` sets `keepUndoUntil = Date.now() + 5000` when the answer's `diagrams_updated` is above 0. `editor.js` `onFrameLoad` calls `resetUndoStacks()` only when `Date.now() >= keepUndoUntil`; otherwise it clears the window (`keepUndoUntil = 0`) and refreshes the undo and redo buttons.

## 4. Data model
None.

## 5. Contracts and interfaces
`let keepUndoUntil = 0;` (module variable next to `undoStack` in `editor.js`). In `onFrameLoad`, after the `restoringFromUndo` early return: `if (Date.now() < keepUndoUntil) { keepUndoUntil = 0; updateUndoRedoButtons(); } else resetUndoStacks();`. In `saveThenLayout` after `const body = await res.json();`: `if (body.diagrams_updated > 0) keepUndoUntil = Date.now() + ARCH_LAYOUT_RELOAD_MS;` with `const ARCH_LAYOUT_RELOAD_MS = 5000;`. The window is set only after the layout answer, and the reload follows on the next poll.

## 6. File structure impact
| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/static/editor-menus.js` | modify: `saveThenLayout` | BR-001 | US-0169 |
| `src/mcp_htmleditor/static/editor.js` | modify: `keepUndoUntil`, `onFrameLoad` | BR-001, BR-004 | US-0169 |
| `tests/test_arch_edit_undo_e2e.py` | create | BT-001..BT-005 | US-0169 |
| `tests/test_style_text_marks_e2e.py` | modify: BT-018 gains its undo step (BT-006) | BR-002 | US-0169 |
| `.agent_docs/testing.md` | modify: file map | docs | US-0169 |
Affected existing tests: `test_bt018_connect_mode_the_undo_snapshot_holds_no_mark` (modified, declared in the spec).

## 7. Compatibility and risks
An agent write inside the 5 second window after an edit keeps the history instead of emptying it (spec edge case, accepted: the window is short). Rollback: revert.

## 9. Test strategy
| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| BT-001..BT-005 | functional e2e | Chromium, real server, file on disk | `tests/test_arch_edit_undo_e2e.py` | US-0169 |
| BT-006 | functional e2e (modified) | same | `tests/test_style_text_marks_e2e.py` | US-0169 |

## 10. Decisions log
- **DEC-001:** keep the history across the editor's own layout reload instead of reapplying positions in the page. **Obliged by:** SPEC-0031/BR-001. **Alternatives considered:** apply positions without reload. **Source:** design. **Evidence:** `editor.js:465-475`, `http_server.py:755`.
- **DEC-002:** a 5 second window opened only when `diagrams_updated > 0`. **Obliged by:** SPEC-0031/BR-001 (no reload, no change when nothing is updated), BR-004. **Source:** design.

## 11. Stories
| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0169 | the layout reload keeps the undo history | P1 | BR-001..BR-004 | main | 2 | yes |
