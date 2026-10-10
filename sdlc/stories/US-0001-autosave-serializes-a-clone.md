# US-0001: Autosave serializes a clone and never moves focus

> Spec: SPEC-0004 (sdlc/specs/SPEC-0004-autosave-focus-loss/)
> Nature: BUG
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 4
> Closes spec: yes

## Objective

While a human types in the browser editor, every autosave (800 ms after the last keystroke) moves
keyboard focus to the page body and the next keystrokes are lost. After this story a save never
mutates the live page, so typing, caret, selection and focus are untouched.

## Requirements covered

- SPEC-0004/BR-001: The editor SHALL NOT change the element holding keyboard focus in the edited document when a save runs.
- SPEC-0004/BR-002: The editor SHALL NOT change the caret position or the selected range in the edited document when a save runs.
- SPEC-0004/BR-003: WHEN the user types in an editable zone after a save has run THE editor SHALL insert every character at the caret of that zone, in typing order.
- SPEC-0004/BR-004: The editor SHALL write a file without `contenteditable` attributes and without `_mcp_` ids or classes on every save.

## Independent Test

`make test ARGS='-k autosave_focus'`: the new file `tests/test_autosave_focus_e2e.py` passes against a
real HTTP server and real Chromium. Key assertion (not a mock): after typing `AAA`, waiting 1500 ms and
typing `BBB` in the title, the page text is `Titre du documentAAABBB`, the iframe's
`document.activeElement` is the `h1`, and the file on disk contains `Titre du documentAAA`.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0004): "`saveContent` serializes a deep clone of `doc.documentElement` and strips
  editor artifacts on the clone only; the live DOM is never mutated by a save."
- DEC-002 (SPEC-0004): "Do not save and restore focus or selection around an in place strip": the
  strip fires `blur`, whose handler `onEditableBlur` (`editor.js:1395`) re-enters `saveContent`.
- DEC-003 (SPEC-0004): new tests in `tests/test_autosave_focus_e2e.py`, harness copied from
  `tests/test_undo_redo_e2e.py`, not imported.
- DEC-004 (SPEC-0004): `captureDomSnapshot` (`editor.js:370`) is not changed.

### Root cause (fact)
`src/mcp_htmleditor/static/editor.js:1410` removes `contenteditable` from every editable element,
the focused one included; the browser moves focus to `BODY`; setting it back at `:1429` does not
refocus.

### Contracts
- `POST /content` body `{"html": "<!DOCTYPE html>\n" + serialized}`: unchanged.
- On `clone = doc.documentElement.cloneNode(true)`: every `[contenteditable]` loses the attribute and
  its inline `outline`/`cursor`; `#_mcp_format_bar` and `#_mcp_insert_bar` get `style.display =
  'none'`; `._mcp_drag_handle` and `._mcp_drop_indicator` are removed; class `_mcp_drag_host` is
  removed. Serialized string `'<!DOCTYPE html>\n' + clone.outerHTML`.
- Unchanged after serialization: `selfSaving = true`, `fetch('/content', POST)`, refetch `/status`
  and adopt `mtime`, `selfSaving = false`, `markSaved()`, `saveTimer = null`, `catch` resets
  `selfSaving` and `console.warn`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor.js` | modify `saveContent` (lines 1398 to 1452): replace the strip and restore block (1403 to 1433) |
| `tests/test_autosave_focus_e2e.py` | create |
| `.agent_docs/html-conventions.md` | § Editor artifacts: add that client saves serialize a clone and never mutate the live DOM |
| `.agent_docs/testing.md` | test file map: add `test_autosave_focus_e2e.py` |

### Existing patterns
- E2E harness: `tests/test_undo_redo_e2e.py` (`_chromium_cache_dir`, `needs_chromium`, `_free_port`,
  `_plain_document`, `_start`, fixture `doc_server`, `_inner`, `_enable_edit_mode`, fixture
  `reset_state` from `tests/conftest.py`).
- Artifact names: `detachDragArtifacts` at `editor.js:1906`.

## Acceptance tests

> 100% must pass, run through `make check` (or `make test ARGS='-k ...'`). Never run test files ad hoc.

Common: Level functional e2e; Driver Playwright Chromium + real HTTP server; Location
`tests/test_autosave_focus_e2e.py`; Preconditions: `doc` bootstrap copied to `tmp_path/doc.html`
(title `h1` text `Titre du document`, `h2` `Introduction`), edit mode on via `#edit-mode-btn`.
"Focused" means `document.getElementById('content-frame').contentDocument.activeElement`. Cleanup:
`stop_http_server()` in the fixture.

### SPEC-0004/BT-001: Typing after an autosave keeps going into the same zone (`test_typing_after_autosave_stays_in_the_zone`)
- Given the title clicked and End pressed
- When the user types `AAA`, waits 1500 ms, then types `BBB`
- Then `doc.html` on disk contains `Titre du documentAAA`
- And the title `innerText` is exactly `Titre du documentAAABBB`
- And the focused element is that `h1`
- Red before the fix because: focused element is `BODY` and title text is `Titre du documentAAA`.

### SPEC-0004/BT-010: Caret offset survives a save (`test_caret_offset_survives_a_save`)
- Given the title clicked, Home pressed, ArrowRight pressed 5 times
- When the user types `X`, waits 1500 ms, types `Y`
- Then the title text is exactly `TitreXY du document`

### SPEC-0004/BT-011: Selection survives a save (`test_selection_survives_a_save`)
- Given the title clicked, End, Shift+ArrowLeft x8, `Z` typed, Shift+ArrowLeft x1
- When 1500 ms pass and the user types `W`
- Then the title text is exactly `Titre du W`

### SPEC-0004/BT-012: Leaving a zone keeps focus in the next zone (`test_leaving_a_zone_keeps_focus_in_the_next_zone`)
- Given the title clicked, End, `A1` typed
- When the user clicks the `h2`, presses End and types `B1` within 100 ms
- Then the `h2` text is exactly `IntroductionB1` and the focused element is that `h2`
- And within 1500 ms `doc.html` contains `Titre du documentA1`

### SPEC-0004/BT-013: Several saves lose nothing (`test_several_saves_lose_nothing`)
- Given the title clicked, End
- When the user types `1`, waits 1000 ms, types `2`, waits 1000 ms, types `3`, waits 1500 ms
- Then the title text is exactly `Titre du document123` and `doc.html` contains `Titre du document123`

### SPEC-0004/BT-014: Failed save keeps focus (`test_failed_save_keeps_focus`)
- Given `page.route("**/content", ...)` aborting POST requests (GET continues), title clicked, End
- When the user types `Q`, waits 1500 ms, types `R`
- Then the title text is exactly `Titre du documentQR` and the focused element is the `h1`

### SPEC-0004/BT-020: Saved file has no editing markers (`test_saved_file_has_no_editing_markers`)
- Given the BT-001 steps
- Then `doc.html` contains no `contenteditable` substring and no `_mcp_` substring

### SPEC-0004/BT-021: No preview reload on self save (`test_self_save_does_not_reload_the_preview`)
- Given `window.__probe = 1` set in the `#content-frame` window
- When the user types `AAA` in the title and waits 2500 ms
- Then `window.__probe` in the `#content-frame` window is `1`

### SPEC-0004/BT-022: Status dot returns to saved (`test_status_dot_returns_to_saved`)
- Given the BT-001 steps and 1500 ms more
- Then `#toolbar-status` computed `color` is `rgb(66, 190, 101)`

### SPEC-0004/BT-023: Existing browser suites unchanged
- Level regression suite; Driver `make test`
- Then every test of `tests/test_undo_redo_e2e.py`, `tests/test_website_template_e2e.py`,
  `tests/test_tab_title_e2e.py`, `tests/test_fullscreen_e2e.py` passes unmodified

## Constraints

- Files not to touch: `src/mcp_htmleditor/http_server.py`, `captureDomSnapshot` and every other function of `editor.js`, existing test files.
- Dependencies not to add: none allowed.
- Patterns to avoid: saving or restoring focus or selection; calling `focus()` or `blur()` from `saveContent`.
- Gate: baseline `make check` is red for reasons outside this story (BL-0004). Land only with `make check` green: fix BL-0004 first, or run with ports 7840 to 7849 free and report the format failure as pre-existing.
- Scope boundary: undo snapshot duplication is BL-0014.

## Definition of done

- [ ] RED evidence recorded for BT-001 (and every new test that is red) before changing `editor.js`.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_undo_redo_e2e.py`, `tests/test_website_template_e2e.py`, `tests/test_tab_title_e2e.py`, `tests/test_fullscreen_e2e.py`, `tests/test_http_helpers.py` pass unmodified; `node --check src/mcp_htmleditor/static/*.js` passes.
- [ ] Docs updated: `.agent_docs/html-conventions.md` § Editor artifacts, `.agent_docs/testing.md` test map.
- [ ] Self review: full.
- [ ] Closes spec: BT-001, BT-010 to BT-014, BT-020 to BT-023 green; BR-001 to BR-004 cited by this story, status done or landed.
- [ ] One commit `US-0001: Autosave serializes a clone and never moves focus`, body `Spec: SPEC-0004` and `BR-001, BR-002, BR-003, BR-004`.
