# Browser editing: Design (as-built)

> Spec: SPEC-0002
> Status: as-built
> Generated on: 2026-10-10 at 2521c331564328c9ca35fbfef372586cadbc12dd

## 1. Components

| Component | Responsibility | Location |
|---|---|---|
| Shell | Toolbar, iframe `#content-frame`, overlay, status dot | `src/mcp_htmleditor/static/editor.html` |
| Editor | All editing behavior, vanilla JS, no build step | `src/mcp_htmleditor/static/editor.js` |
| Slide layouts | `LAYOUT_SETS` per charter | `src/mcp_htmleditor/static/slide-layouts.js` |
| Document blocks | `DOC_BLOCKS` catalog | `src/mcp_htmleditor/static/doc-blocks.js` |

## 2. Flows

- Edit mode: `editBtn` click (`editor.js:84`) then `applyEditMode` (`:557`): `injectEditMode` (`:568`) sets `contentEditable='true'` and class `_mcp_editable` on `[data-editable~="text"]`, binds `input`/`blur`/`mouseup`/`keyup`/`focus`.
- Autosave: `onEditableInput` 800 ms debounce, `onEditableBlur` immediate, `scheduleSave` 600 ms (`:1394`..`:1396`). `saveContent` (`:1398`): removes `contenteditable` and `outline`/`cursor` on every `[contenteditable]` (`:1410`), hides `_mcp_format_bar`/`_mcp_insert_bar`, `detachDragArtifacts`, serializes `<!DOCTYPE html>` + `outerHTML`, restores attributes synchronously, then `selfSaving=true`, `POST /content`, refetches `/status` to adopt the new mtime, `selfSaving=false`, `markSaved()`.
- Reload guard: `pollStatus` (`:298`) reloads only when `mtimeChanged && !selfSaving && !hasPendingChanges` (`:318`) or after an agent update window.
- Undo/redo: `snapshotForUndo` (`:404`) pushes `captureDomSnapshot` (`:370`, same stripping as save, no doctype) before each structural mutation, 27 call sites; `restoreDomSnapshot` (`:425`) blurs the active element then rewrites the document with `doc.write`, guarded by `restoringFromUndo`; depth `UNDO_MAX_DEPTH = 50` (`:357`).
- Keydown: `handleUndoRedoKeydown` (`:451`) defers to native undo while `queryCommandEnabled('undo')` (`:467`). `blockNavKeysInEditMode` (`:549`).
- Arch drag: `enableArchNodeDrag` (`:1934`), `makeArchNodeDraggable` (`:1953`) writes `data-x`/`data-y` and inline `left`/`top`, sets `data-layout="manual"` when moved (`:1993`).

## 3. Interfaces

- Toolbar ids: `edit-mode-btn`, `undo-btn`, `redo-btn`, `present-btn`, `export-pptx-btn`, `export-docx-btn`, `btn-insert-before`, `btn-insert-after`, `btn-delete-slide`, `btn-insert-block-before`, `btn-insert-block-after` (`editor.html`).
- HTTP used: `GET /status`, `GET /content-frame`, `POST /content` `{html}`, `GET /export/{pptx,docx}`, `POST /arch-layout`.
- Editor artifacts: `_mcp_editable`, `_mcp_format_bar`, `_mcp_insert_bar`, `_mcp_editor_styles`, `_mcp_drag_handle`, drop indicator.

## 4. Data and state

In memory only: `editMode`, `hasPendingChanges`, `selfSaving`, `lastMtime`, `undoStack`, `redoStack`, `saveTimer`. No localStorage.

## 5. Configuration

Poll interval comes from `/status.poll_interval` (SPEC-0001 FR-019). Debounces are constants.

## 6. Observability

`console.warn` on save failure (`saveContent` catch) and edit-mode toggle failure. Polling errors are swallowed without log (`editor.js:301`, BL-0013).

## 7. Decisions (observed)

| ID | Decision | Evidence | Rationale |
|---|---|---|---|
| DEC-001 | Structural undo by whole document snapshots, typing left to native undo | `editor.js:370`, `editor.js:467` | `.agent_docs/html-conventions.md` § Undo/redo |
| DEC-002 | Strip editor artifacts client side before serializing, plus server side | `editor.js:1398`, `http_server.py:443` | not documented (defense in depth) |
| DEC-003 | Adopt own save mtime to avoid reload flash | `editor.js:1442` | inline comment: avoid reload that loses the caret |
| DEC-004 | Websites reuse document block UI but get no export | `editor.js:255` | inline comment, `skill/types/website.md` |

## 8. Requirement to code map

| Requirement | Files |
|---|---|
| SPEC-0002/FR-001..FR-003 | `editor.js:84`, `:568`, `:586`, `:803`, `:897` |
| SPEC-0002/FR-004..FR-008 | `editor.js:46`, `:55`, `:298`, `:318`, `:1394`..`:1452` |
| SPEC-0002/FR-009..FR-012 | `editor.js:93`, `:357`, `:404`, `:451`, `:521` |
| SPEC-0002/FR-013..FR-017 | `editor.js:938`, `:959`, `:1307`, `:1359`, `:1484`, `:1508`, `:1563`, `:1702`, `:1834`, `:1953` |
| SPEC-0002/FR-018..FR-020 | `editor.js:232`, `:255`, `:276`, `:549` |
