# US-0114: Single editor artifact strip

> Spec: SPEC-0019 (sdlc/specs/SPEC-0019-code-and-test-debts/)
> Nature: DEBT
> Priority: P1
> Depends on: main
> min_tier: 1
> Files touched: 3
> Closes spec: no

## Objective

The undo snapshot and the save each carry their own copy of the list of editor artifacts to strip; a fix to one misses the other (BL-0014, BL-0034 waits on it). This story defines the strip once, `stripEditorArtifacts(root)`, used by both callers, with byte identical snapshot strings and saved HTML. `min_tier: 1`: the live document must be restored exactly after the snapshot, and only the existing browser suites catch a miss.

## Requirements covered

- SPEC-0019/DR-003: The editor scripts SHALL define the strip of editor artifacts once, as `function stripEditorArtifacts(root)` in `src/mcp_htmleditor/static/editor-save.js`, applying in this order: for each `[contenteditable]` under `root`, remove the attribute and set `style.outline` and `style.cursor` to `''`; set `style.display = 'none'` on `#_mcp_format_bar` and `#_mcp_insert_bar` found under `root`; `detachDragArtifacts(root)`; and SHALL return a function that restores each `contentEditable`, `outline`, `cursor`, each bar `display` and calls `reattachDragArtifacts` with the detached state.
- SPEC-0019/DR-006 (partial: this story's edits): The system SHALL produce, for every input covered by the existing test suite, byte identical observable output before and after this change, the undo snapshot string and the HTML posted by a save included; the only text change is the sentence of DR-005 in the `slides-carbon` topic output.

## Independent Test

`make test ARGS='-k artifact_strip'`: DT-012 red before, green after. `node --check src/mcp_htmleditor/static/*.js` clean. `make test ARGS='-k "undo or save or autosave"'` green with those test files unmodified (they compare the snapshot and saved HTML in a real browser). `make check` green.

## Design excerpt

### Decisions

- DEC-003 (SPEC-0019): The shared strip returns a restore function instead of always cloning; cloning in `captureDomSnapshot` would change focus and `blur` events during a snapshot (behavior change).
- DEC-008 (SPEC-0019): `min_tier: 1` for this step.
- DEC-010 (SPEC-0019): new comments follow SPEC-0018 DT-012: a pointer `see <script>.js <name>` or `<name>() in <script>.js` names the script that defines `function <name>(`.

### Contracts

- New `function stripEditorArtifacts(root)` in `editor-save.js`, global (classic scripts loaded by `editor.html:115-127`); returns `restore()`.
- **Selector rule:** bars found with `root.querySelectorAll('#_mcp_format_bar, #_mcp_insert_bar')` (works on a document and on a detached element; `getElementById` does not exist on an element).
- `captureDomSnapshot(doc)` new form: `const restore = stripEditorArtifacts(doc); const html = withWidthPreviewSuspended(() => doc.documentElement.outerHTML); restore(); return html;`
- `runSave` new form: `const clone = withWidthPreviewSuspended(() => doc.documentElement.cloneNode(true)); stripEditorArtifacts(clone); stripPresentingState(clone);` (the returned function is ignored; `stripPresentingState` stays in `runSave` only).
- Reused unchanged: `detachDragArtifacts(doc)` (`editor-drag.js:129`), `reattachDragArtifacts(state)` (`editor-drag.js:140`).

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-save.js` | add `stripEditorArtifacts`; `runSave` `:27-33` calls it |
| `src/mcp_htmleditor/static/editor-undo.js` | `captureDomSnapshot` `:28-53` calls it |
| `tests/test_editor_artifact_strip.py` | create: DT-012 |

### Existing patterns

- Today's two copies: `editor-undo.js:27-56` (live mutation and restore), `editor-save.js:26-34` (clone).
- camelCase functions, as the rest of `static/`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0019/DT-012: One strip definition
- Level / Driver / Location: structural / text of `src/mcp_htmleditor/static/*.js` / `tests/test_editor_artifact_strip.py`
- Then `function stripEditorArtifacts(` appears exactly once, in `editor-save.js`; the bodies of `function captureDomSnapshot(` and `async function runSave(` (text from the declaration to the next line starting with `function ` or `async function ` at column 0) each contain `stripEditorArtifacts(` and neither contains `removeAttribute('contenteditable')`; across all static scripts `removeAttribute('contenteditable')` appears exactly twice: once in `editor-save.js` (inside `stripEditorArtifacts`) and once in `editor-drag.js` (unchanged)
- Red before the fix because: `stripEditorArtifacts` is absent (today `removeAttribute('contenteditable')` is in `editor-save.js:28`, `editor-undo.js:34`, `editor-drag.js:211`).
- Behavior parity: carried by `tests/test_undo_redo_e2e.py`, `tests/test_save_ui_e2e.py`, `tests/test_autosave_focus_e2e.py`, `tests/test_save_safety_e2e.py`, unmodified.

## Constraints

- Files not to touch: `editor-drag.js`, every existing test file.
- Restore exactly what was changed, in reverse order (drag artifacts reattached, bars `display` and each `contentEditable`, `outline`, `cursor` set back to their prior values).
- No clone in `captureDomSnapshot` (DEC-003).
- Dependencies not to add: any. Scope boundary: BL-0034 (the fix waiting on this) is not part of this story.

## Definition of done

- [ ] RED evidence recorded for DT-012 before the production change.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the four browser suites above unmodified and green.
- [ ] DEBT: the existing suite passes unmodified, exceptions: none in this story (the 4 SPEC-0019 removals belong to US-0113).
- [ ] Docs updated: none in this story (test file map in US-0115).
- [ ] Self review: full.
- [ ] One commit `US-0114: Single editor artifact strip`, body `Spec: SPEC-0019` and `DR-003, DR-006`.
