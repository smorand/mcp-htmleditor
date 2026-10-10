# Background autosave takes focus away from the zone being typed in: Bug Specification

> Generated on: 2026-10-10
> Id: SPEC-0004
> Nature: BUG
> Depth: S
> Depth evidence: 1 module (browser editor), 1 defective behavior, 4 requirements, no public contract change, no data model change
> Status: specified
> Verdict: authority exists
> Defect class: n/a (code violates a clear authority)
> Severity: High
> From backlog: BL-0008
> Security: n/a
> CVSS: n/a
> Affected: every version with client side autosave, at least up to 2521c33
> Fixed in: n/a

## 1. Defect

### BUG-001: A background save moves keyboard focus out of the editable zone
- **Observed behavior:** In edit mode, when an autosave runs, keyboard focus in the edited
  document moves from the editable zone to the document body. The caret stays drawn inside the
  zone, but the next keystrokes go nowhere and are lost. Reproduced in Chromium on 2026-10-10:
  focus was `H1[ce]` before the save and `BODY` after it; text typed after the save was absent
  from the zone.
- **Expected per authority:** User statement (2026-10-10, verbatim): "We need to continue to be
  able to write and the auto save, happening background, must not have any effect on the current
  work." Consistent with the design intent written in the code, "Never reload because of our own
  save: that would flash the iframe and lose the caret" (`src/mcp_htmleditor/static/editor.js:316`),
  and with legacy NFR 7.3 "sans rechargement de l'iframe sur ses propres sauvegardes (anti-flicker)"
  (`git show 2521c33:specs/2026-08-07_16-31-00-mcp-htmleditor-retrospective.md`, line 436).
- **Reproduction:** Serve the `doc` template, turn edit mode on, click the title zone, press End,
  type `AAA`, wait 1500 ms, type `BBB`. Expected: title ends with `AAABBB`, title still focused.
  Actual: title ends with `AAA`, focus on the body.
- **Root cause:** `saveContent` removes the `contenteditable` attribute from every editable element,
  the focused one included, to serialize the page (`src/mcp_htmleditor/static/editor.js:1410`).
  Removing that attribute from the focused element makes the browser move focus to the body;
  setting `contentEditable` back afterwards (`src/mcp_htmleditor/static/editor.js:1429`) does not give
  focus back, and `saveContent` neither records nor restores focus or selection
  (`src/mcp_htmleditor/static/editor.js:1398` to `:1452`). Verified in isolation: on a bare page,
  `removeAttribute('contenteditable')` on the focused `h1` changes `document.activeElement` from
  `H1` to `BODY`, and it stays `BODY` after `contentEditable = 'true'`.
- **Contributing factors:** Autosave fires 800 ms after the last keystroke
  (`src/mcp_htmleditor/static/editor.js:1394`), so every ordinary typing pause triggers it; 600 ms after
  a structural action (`:1396`); immediately on leaving a zone (`:1395`), at which point the focus
  has already reached the next zone, which is then stripped too. No test covers focus across a
  save (SPEC-0002/E2E-014 `untested`).
- **Impact:** Every human editing session, every document type (presentation, document, website).
  Keystrokes typed after each pause are silently lost; the user must click back after every save.
  No workaround other than typing without pauses.
- **Rollback posture:** The save itself must keep working and keep writing a clean file; a revert
  of the fix restores today's behavior with no data format impact.

## 2. Expected Behavior

#### BR-001 [EARS-UB]: Focus untouched by a background save
> The editor SHALL NOT change the element holding keyboard focus in the edited document when a save runs.

- **Source:** restored from the user statement quoted in BUG-001.
- **Inputs:** any save: typing pause, structural action, leaving a zone.
- **Outputs:** `document.activeElement` of the `#content-frame` document is the same element before
  and after the save completes.
- **Business Rules:** applies to whichever element has focus when the save starts, including a zone
  just entered by leaving another one.
- **Exact names:** iframe `#content-frame`; editable zones `[data-editable~="text"]`; edit mode
  button `#edit-mode-btn`.

#### BR-002 [EARS-UB]: Caret and selection untouched by a background save
> The editor SHALL NOT change the caret position or the selected range in the edited document when a save runs.

- **Source:** restored from the user statement quoted in BUG-001 ("no effect on the current work").
- **Outputs:** anchor node, anchor offset, focus node and focus offset of the document selection are
  identical before and after the save.

#### BR-003 [EARS-E]: Typing continues across a save
> WHEN the user types in an editable zone after a save has run THE editor SHALL insert every character at the caret of that zone, in typing order.

- **Source:** restored from the user statement quoted in BUG-001 ("continue to be able to write").

#### BR-004 [EARS-U]: The saved file stays clean
> The editor SHALL write a file without `contenteditable` attributes and without `_mcp_` ids or classes on every save.

- **Source:** restored from SPEC-0001/FR-005 (unchanged adjacent behavior, restated because the
  fix touches the same save).

## 3. Edge Cases

| Case | Expected behavior | Requirement |
|---|---|---|
| Caret in the middle of the text | Next character inserted at the same offset | BR-002, BR-003 |
| A word is selected when the save runs | Selection kept; typing replaces exactly that word | BR-002 |
| User leaves zone A by clicking zone B (save on leave) | Focus stays in B, typing lands in B | BR-001, BR-003 |
| Several pauses in a row (several saves) | Every character typed between them is kept | BR-003 |
| Save fails (server stopped) | Focus and caret unchanged as well | BR-001, BR-002 |
| No zone focused (structural action from toolbar) | Nothing to preserve; save behaves as today | BR-004 |

## 4. Tests

Driver for every browser test: pytest with Playwright Chromium, same harness as
`tests/test_undo_redo_e2e.py` (real HTTP server on a free port, `doc` template copied to a temp dir).

### 4.1 End to end reproduction (mandatory)
#### BT-001: Typing after an autosave keeps going into the same zone
- **Reproduces:** BUG-001
- **Driver:** Playwright Chromium against the real HTTP server
- **Fails today because:** the save removes `contenteditable` from the focused title, focus moves to the body and `BBB` is dropped.
- Given the `doc` template served, `#edit-mode-btn` clicked, the title `h1[data-editable~="text"]` ("Titre du document") clicked and End pressed
- When the user types `AAA`, waits 1500 ms, then types `BBB`
- Then the file on disk contains `Titre du documentAAA` (the save ran)
- And the title text in the page is exactly `Titre du documentAAABBB`
- And `document.activeElement` in `#content-frame` is that `h1`

### 4.2 New behavior
#### BT-010: Caret offset survives a save
- **Validates:** BR-002, BR-003
- Given edit mode on, title clicked, Home pressed, ArrowRight pressed 5 times (caret after `Titre`)
- When the user types `X`, waits 1500 ms, types `Y`
- Then the title text is exactly `TitreXY du document`

#### BT-011: Selection survives a save
- **Validates:** BR-002
- Given edit mode on, title clicked, End pressed, Shift+ArrowLeft pressed 8 times (selects `document`), then `Z` typed and Shift+ArrowLeft pressed once (selects `Z`)
- When 1500 ms pass and the user types `W`
- Then the title text is exactly `Titre du W`

#### BT-012: Leaving a zone saves without stealing the next zone's focus
- **Validates:** BR-001, BR-003
- Given edit mode on, title clicked, End pressed, `A1` typed
- When the user clicks the `h2` zone ("Introduction"), presses End and types `B1` within 100 ms
- Then the `h2` text is exactly `IntroductionB1`
- And `document.activeElement` in `#content-frame` is that `h2`
- And within 1500 ms the file on disk contains `Titre du documentA1`

#### BT-013: Several saves in a row lose nothing
- **Validates:** BR-003
- Given edit mode on, title clicked, End pressed
- When the user types `1`, waits 1000 ms, types `2`, waits 1000 ms, types `3`, waits 1500 ms
- Then the title text is exactly `Titre du document123` and the file on disk contains `Titre du document123`

#### BT-014: Failed save keeps focus
- **Validates:** BR-001
- Given edit mode on, title clicked, End pressed, and the page route `POST /content` aborted by Playwright
- When the user types `Q`, waits 1500 ms, types `R`
- Then the title text is exactly `Titre du documentQR` and the `h1` is the active element

### 4.3 Non regression
#### BT-020: Saved file has no editing markers
- **Protects:** BR-004, SPEC-0001/FR-005
- Given BT-001 has run
- Then the file on disk contains no `contenteditable` substring and no `_mcp_` substring

#### BT-021: No preview reload on self save
- **Protects:** SPEC-0002/FR-008
- Given edit mode on and `window.__probe = 1` set in the `#content-frame` window
- When the user types `AAA` in the title and waits 2500 ms (save plus at least one poll)
- Then `window.__probe` in the `#content-frame` window is still `1`

#### BT-022: Status dot returns to saved
- **Protects:** SPEC-0002/FR-007
- Given BT-001 has run and 1500 ms more have passed
- Then `#toolbar-status` has computed color `rgb(66, 190, 101)`

#### BT-023: Existing browser suites unchanged
- **Protects:** SPEC-0002 undo/redo, website and tab title behaviors
- Given the fix applied
- When `make test` runs
- Then every test of `tests/test_undo_redo_e2e.py`, `tests/test_website_template_e2e.py`, `tests/test_tab_title_e2e.py` and `tests/test_fullscreen_e2e.py` passes unmodified

### 4.4 Existing tests asserting the current behavior
| Test file | Test name | Action | Reason |
|---|---|---|---|
| `tests/test_undo_redo_e2e.py` | all 8 tests | Kept | structural undo, not focus; must stay green (BT-023) |
| `tests/test_http_helpers.py` | `test_strip_removes_contenteditable` and 6 sibling `test_strip_*` | Kept | server side cleaning, unaffected |
| `tests/test_website_template_e2e.py` | both tests | Kept | edit mode toggling, unaffected; no existing test asserts the focus loss |

## 5. Existing Specs Affected

- SPEC-0002/FR-004 to FR-008 (autosave timing, status, no reload): unchanged; this spec adds the
  focus and caret guarantee they did not state. SPEC-0002/E2E-014 stays `untested` for timings.
- SPEC-0001/FR-005: restated as BR-004, unchanged.

## 6. Assumptions

- **Assumption:** the guarantee covers saves only. Structural actions (insert, delete, drag, undo)
  replace or rebuild DOM by design and may move focus; undo already blurs on purpose
  (`src/mcp_htmleditor/static/editor.js:428`). The undo snapshot shares the stripping pattern
  (BL-0014) and is out of this spec. Shapes BR-001.
- **Assumption:** severity High, not Medium as filed in BL-0008: keystrokes are lost silently on
  every typing pause.
- **Backlog entries created by this run:** none. Consumed: BL-0008.

## 7. Implementability Checklist

All PASS, checked on the file as written: 1 no technical decision; 2 no buried requirement; 3 names spelled (`#content-frame`, `#edit-mode-btn`, `[data-editable~="text"]`, `#toolbar-status`, `POST /content`, 800/600 ms); 4 no forced choice; 5 every BT complete; 6 BT-001 end to end, red on 2026-10-10; 7ante not a security defect; 8 no hidden prerequisite; 9 EARS clean; 10 right tool, 4 BR at S; 11 within S budget; 12 claims cited at 2521c33; 13 writer and server cleaning read, template text read at `templates/bootstrap/document-empty.html:61` and `:67`; 14 every BR cites its authority.

| Verdict | IMPLEMENTABLE |
|---|---|
| Open F failures | 0 |
| A failures | amended in place: 0; moved to backlog: none |
