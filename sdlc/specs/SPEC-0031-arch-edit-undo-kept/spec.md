# A diagram edit stays undoable after the layout run: Bug Specification

> Generated on: 2026-11-20
> Id: SPEC-0031
> Nature: BUG
> Depth: S
> Depth evidence: 1 module (editor scripts), 4 requirements, no public contract or data change
> Status: implemented
> Verdict: authority exists
> Defect class: n/a (code violates a clear authority)
> Severity: Low
> From backlog: BL-0050
> Security: n/a
> CVSS: n/a
> Affected: every release since the declarative diagram editing (add node, remove node, create edge)
> Fixed in: unreleased

BUG / depth S: 1 module (editor scripts), 4 requirements, no contract change. Security: n/a (checked: no authentication or
authorization bypass, injection, data exposure, traversal or advisory).

## 1. Defect

### BUG-001: after a declarative diagram edit the undo history is empty

- **Observed behavior:** the person adds a node, removes a node or creates an edge in a declarative diagram; each action takes an
  undo snapshot, saves, then asks the server to recompute the diagram's positions (`saveThenLayout`,
  `src/mcp_htmleditor/static/editor-menus.js:36-47`, called at `:97`, `:113`, `:168`). The server rewrites the file; the poll sees
  the new modification time as an external change and reloads the frame (`src/mcp_htmleditor/static/editor.js:465-475`); the load
  empties the undo and redo history (`editor.js:351`, `src/mcp_htmleditor/static/editor-undo.js:169-170`). `#undo-btn` is then
  disabled and Ctrl+Z does nothing.
- **Expected per authority:** SPEC-0002/FR-009 (`sdlc/specs/SPEC-0002-browser-editing/spec.md:87`): "WHEN the human presses Ctrl or Cmd
  with Z, or the undo button, THE system SHALL revert the last structural action and save; Ctrl or Cmd with Shift Z, Ctrl Y, or the
  redo button reapplies it", and SC-002 (`:60-63`): structural actions on a diagram "save and can be undone". The editor itself takes
  the snapshot for these edits (`editor-menus.js:68`, `:159`, and the node removal).
- **Reproduction (Chromium, 2026-11-20, Deck S of `tests/style_text_support.py`, slide 3):** edit mode on, right click `Serveur MCP`,
  `➜ Créer une arête depuis ce nœud`, click `Base`, accept the empty label, wait until the file holds `arch-edge`. Expected: `#undo-btn`
  enabled. Actual: disabled, `undoStack` holds 0 entries.
- **Root cause:** `src/mcp_htmleditor/static/editor.js:351` calls `resetUndoStacks()` for every load that is not an Undo or Redo
  restore, including the reload the editor itself causes by asking the server to rewrite the file (`editor-menus.js:39`).
- **Contributing factors:** the reload on an external write is what shows the recomputed positions; no flag tells the load
  that the write was the editor's own.
- **Impact:** every person editing a declarative diagram: the last node or edge cannot be undone, and any earlier undo history of the
  session is lost at the same time. Workaround: `restore` of an earlier version.
- **Rollback posture:** a revert restores today's behavior; files written in between stay valid.

## 2. Expected Behavior

#### BR-001 [EARS-E]: The layout run keeps the history
> WHEN the person adds a node, removes a node or creates an edge in a declarative diagram and the layout run rewrites the file
> THE editor SHALL show the diagram with its recomputed positions and SHALL keep the undo and redo history it had, with the edit
> as the last undo step.
- **Source:** restored from SPEC-0002/FR-009 and SC-002.
- **Business Rules:** the history is kept only for the reload that follows the editor's own layout run; a layout run that changes nothing
  causes no reload and no change of the history.

#### BR-002 [EARS-E]: Undo reverts the edit
> WHEN the person presses Undo after such an edit THE editor SHALL restore the diagram as it was before the edit (no added node, no
> added edge, the removed node back) and save it.
- **Source:** restored from SPEC-0002/FR-009.

#### BR-003 [EARS-E]: Redo reapplies it
> WHEN the person presses Redo after that Undo THE editor SHALL show the edit again (the node or the edge) and save it.
- **Source:** restored from SPEC-0002/FR-009.

#### BR-004 [EARS-UB]: Other reloads still empty the history
> The editor SHALL empty the undo and redo history when the document is reloaded for any reason other than its own layout run (an
> agent write, another file).
- **Source:** restored from the existing contract (`editor.js:340-342`: a snapshot never crosses a change of document).

## 3. Edge Cases

| Case | Expected behavior | Requirement |
|------|-------------------|-------------|
| layout run changes no position | no reload, history unchanged | BR-001 |
| an agent writes the file right after the person's edit | history emptied (the document is not the one the snapshots describe) | BR-004 |
| two diagram edits in a row | two undo steps | BR-001 |
| edit of a legacy diagram (no layout run) | unchanged behavior | BR-001 |

## 4. Tests

#### BT-001 (end to end reproduction): the undo button stays enabled after an edge is created
- **Reproduces:** BUG-001
- **Driver:** Playwright Chromium against a real editor server (`tests/style_text_support.py` Deck S, slide 3)
- **Fails today because:** `editor.js:351` empties the stacks on the layout reload (`#undo-btn` disabled).
- Given Deck S served, slide 3, edit mode on
- When the person creates an edge from `Serveur MCP` to `Base` (empty label) and waits until the file holds the edge and the page has reloaded the diagram
- Then `#undo-btn` is enabled

#### BT-002: Undo removes the edge, Redo brings it back
- **Validates:** BR-002, BR-003. When the person clicks `#undo-btn` Then the file has no `arch-edge` and the page's diagram has none; when the person clicks `#redo-btn` Then both hold the edge again.

#### BT-003: Undo of a node added to a declarative diagram
- **Validates:** BR-001, BR-002. When the person adds a node `Cache` (menu `＋ Ajouter nœud (rangée existante ou nouvelle)`) to the diagram and waits for the reload, then clicks `#undo-btn` Then the file has no `Cache` and the page's diagram has no `Cache`.

#### BT-004: An agent write still empties the history (non regression)
- **Validates:** BR-004. After an edge is created and the layout reload, an agent write (new modification time) reloads the page and `#undo-btn` is disabled.

#### BT-005: The earlier history is kept
- **Validates:** BR-001. After typing a structural change (inserting a slide) then creating an edge, two Undo clicks revert the edge then the slide.

#### BT-006: SPEC-0020 BT-018 as written
- **Validates:** BR-002. The test of SPEC-0020 BT-018 (`tests/test_style_text_marks_e2e.py`) gains the undo step the spec wrote: after the edge, `#undo-btn` is clicked, the file has no `arch-edge`, `n1`'s style holds one `outline:1px dashed #8D8D8D`, no `crosshair`, no `data-mcp-mark`, `<body>` has no `style`.

### Existing tests asserting the current behavior
| Test file | Test name | Action | Reason |
|-----------|-----------|--------|--------|
| `tests/test_style_text_marks_e2e.py` | `test_bt018_connect_mode_the_undo_snapshot_holds_no_mark` | Modified | gains the undo step (BT-006); its docstring states the undo step could not run |
| `tests/test_undo_redo_e2e.py` | all | Kept | no layout run in these fixtures |

## 5. Existing Specs Affected
SPEC-0002/FR-009 and SC-002 (restored). SPEC-0020 BT-018: the deviation recorded in its implementation (the undo step could not run) is lifted; SPEC-0020 is not modified.

## 6. Assumptions
- **Assumption:** "its own layout run" means the reload that follows a `/arch-layout` answer reporting that diagrams were updated; a longer delay than 5 seconds between the answer and the reload ends the exception.
- **Proposed backlog entries (not written):** none.

## 7. Implementability Checklist
Depth S, inline: no technical decision (root cause `file:LINE` only); each name spelled (`#undo-btn`, `#redo-btn`, menu entries); no forced choice; every BT specified and end to end; EARS clean; right tool (behavior changes, no new capability); every claim cited.

| Verdict | IMPLEMENTABLE |
|---|---|
| Open F failures | 0 |
| A failures | none |
