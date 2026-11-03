# US-0049: Conflict choice, save failures and server loss in the editor

> Spec: SPEC-0009 (sdlc/specs/SPEC-0009-reliable-saves/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0048, US-0017
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

The editor page tracks `base_mtime`, sends it with each save, shows the conflict choice (`Reload`, `Keep mine`),
shows save failures, and shows a banner when the server is lost. No focus is ever taken by a notice.

## Requirements covered

- SPEC-0009/FR-NEW-003: WHEN a save is refused for a conflict THE Editor SHALL show the message `The file changed on disk. Reload to see the changes, or keep your version.` with the buttons `Reload` and `Keep mine`.
- SPEC-0009/FR-NEW-007 (partial: the editor display of a refused or failed save): IF a save targets a template, has an invalid length, or is too large THEN THE Editor SHALL refuse it with a precise status and leave the file unchanged. Business rule: a save request that fails at network level shows `Save failed: ` followed by the browser's error text and keeps the unsaved state. When a save is answered with a non success status other than 409, the editor shows `Save failed: <error text of the answer>`, keeps the unsaved state, and tries again at the next autosave.
- SPEC-0009/FR-NEW-009: WHILE three or more consecutive status polls have failed (a poll fails when the request fails, the answer status is not 200, or the body is not valid JSON) THE Editor SHALL show `Connection to the editor server lost`, and SHALL remove it at the next successful poll.

Business rules FR-NEW-003: `Reload` shows the file as it is on disk and drops the unsaved edits. `Keep mine` saves the browser's version with `force` true. No autosave is attempted while the message is shown.

Also applied from FR-NEW-002: `base_mtime` changes only when the page loads or reloads the file, after the page's own successful save (the `mtime` of the save answer, not of a later poll), after `Reload`, and after a successful `Keep mine` (the `mtime` of that answer). The first save after a page load uses the `mtime` read at load. If the page read no `mtime`, it sends no `base_mtime`. A status poll showing a different `mtime` while the page holds unsaved edits does not change it.

## Independent Test

`make check`: `tests/test_save_ui_e2e.py` passes (needs Chromium; skipped otherwise like the other browser tests). By hand:
edit in the browser, write the file from a shell, type again: the conflict message appears.

## Design excerpt

### Decisions

- DEC-013 (SPEC-0009): The browser keeps `baseMtime` apart from `lastMtime` (the poll's reload detector), adopting the save answer's `mtime` instead of the old extra `/status` read. The poll overwrote `lastMtime` even with unsaved edits, which the spec forbids for the conflict base.
- DEC-014 (SPEC-0009): Notices live in `#notices` in the shell page, with no focusable element except the two conflict buttons and no autofocus. The autosave must never move focus away from the edited zone (SPEC-0004); no `alert()` or `confirm()`.
- DEC-015 (SPEC-0009): Poll failures are counted in the browser (`!ok`, non 200, or invalid JSON each count); three consecutive failures show the notice, the next success clears it. Server loss is simulated in tests with `page.route` (the listening socket stays open after `stop_http_server`, so the server is not stopped).

### Data model

Browser state in `editor.js`: `baseMtime` (null until read), `conflictActive`, `conflictMtime`, `pollFailures`. Top level declarations are read only inside functions (SPEC-0012 rule). `baseMtime` is set: at start up and from the first poll that finds it null; to the answer's `mtime` after the page's own successful save; to `status.mtime` where the poll calls `reloadFrame`; to `conflictMtime` after `Reload`. A poll with unsaved edits never changes it.

### Contracts

`editor.html` gets one container `#notices` (`role="status"`, never focusable, no autofocus) holding:
- `#save-conflict`: text `The file changed on disk. Reload to see the changes, or keep your version.`, buttons `Reload`, `Keep mine`;
- `#save-error`: `Save failed: <text>`;
- `#connection-lost`: `Connection to the editor server lost`.

`saveContent(options)`: returns early when `conflictActive` and not `options.force`; sends `base_mtime` only when `baseMtime !== null`, `force: true` only for Keep mine; 200 updates `baseMtime` and `lastMtime` from the answer (the post save `/status` read is removed), hides the three notices, `markSaved`; 409 sets `conflictActive`, stores `conflictMtime` (answer `mtime`), shows the conflict notice, keeps the unsaved state; any other status or a network error shows `Save failed: <error text or message>` and keeps the unsaved state; the next autosave trigger sends again. Server answers used (from US-0048): 200 `{"ok":true,"mtime":M}`, 409 `{"ok":false,"error":"File changed on disk","mtime":M}`, 500 `{"error":"<strerror>"}`.

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-save.js` | edit (`saveContent`, notices) |
| `src/mcp_htmleditor/static/editor.js` | edit (state, start up, polling) |
| `src/mcp_htmleditor/static/editor.html` | edit (`#notices`) |
| `src/mcp_htmleditor/static/editor.css` | edit (notice styles) |
| `tests/test_save_ui_e2e.py` | create |

(`editor-save.js` exists after SPEC-0012's script split, US-0017; if `saveContent` still lives in `editor.js` at the time, edit it there and keep the file list otherwise.)

### Existing patterns

- Playwright harness, skip pattern and helpers: `tests/test_autosave_focus_e2e.py` (`_open_in_edit_mode`, `_click_end`, `SAVED_DOT_COLOR`), plus `needs_chromium` and `served_deck` from `tests/conftest.py` (US-0048). Poll interval forced with `HTMLEDITOR_POLL_INTERVAL=100`.
- Server loss simulated with `page.route("**/status", handler)` aborting a counted number of requests.
- Focus preservation on a failed save: `tests/test_autosave_focus_e2e.py::test_failed_save_keeps_focus` (`:196`).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures: DECK is an Euro-Information presentation `deck.html` of 8 slides, served by the editor. Read only folder tests skip as root and restore permissions in `finally`.

### SPEC-0009/E2E-008: Conflict message and Reload
- Level browser; Driver Playwright, agent write then typing; Location `tests/test_save_ui_e2e.py`
- Given the editor open on DECK in a browser; the agent writes a new title; the user types an edit
- When the autosave fires
- Then the page shows `The file changed on disk. Reload to see the changes, or keep your version.` with the buttons `Reload` and `Keep mine`, and no further save is sent while it is shown
- And clicking `Reload` shows the agent's title and removes the message

### SPEC-0009/E2E-017: Connection lost
- Level browser; Driver `page.route` abort; Location `tests/test_save_ui_e2e.py`
- Given the editor open on DECK
- When the server stops and three consecutive polls fail
- Then the page shows `Connection to the editor server lost`

### SPEC-0009/E2E-018: Connection back
- Level browser; Driver unroute; Location `tests/test_save_ui_e2e.py`
- Given the state of E2E-017
- When the server answers again
- Then the message disappears at the next successful poll

### SPEC-0009/E2E-027: One failed poll
- Level browser; Driver one aborted poll; Location `tests/test_save_ui_e2e.py`
- Given the editor open on DECK
- When one poll fails then the next two succeed
- Then the message `Connection to the editor server lost` never appears

### SPEC-0009/E2E-028: Keep mine fails
- Level browser; Driver Keep mine on a read only folder; Location `tests/test_save_ui_e2e.py`
- Given the conflict message shown (E2E-008) and the folder made read only (new files cannot be created)
- When the user clicks `Keep mine`
- Then the message stays and the page also shows `Save failed: ` followed by the error text of the answer, and the page is not marked saved

### SPEC-0009/E2E-032: Save failure shown in the editor
- Level browser; Driver read only folder, then writable; Location `tests/test_save_ui_e2e.py`
- Given the editor open on DECK and the folder made read only (new files cannot be created)
- When the autosave fires after an edit
- Then the page shows `Save failed: ` followed by the error text of the answer, stays in the unsaved state, and sends the save again at the next autosave once the file is writable again, after which the page is marked saved

## Constraints

- Files not to touch: `src/mcp_htmleditor/*.py`; existing tests (the notices never take focus, self saves must not trigger a reload).
- Dependencies not to add: none.
- Patterns to avoid: `alert()`, `confirm()`, `autofocus`, any focusable element in `#notices` other than the two conflict buttons; reading top level browser state at load time (SPEC-0012 rule).
- Scope boundary: `Keep mine` history reason is verified in US-0050 (E2E-009).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_autosave_focus_e2e.py` (incl. `test_failed_save_keeps_focus`), `tests/test_undo_redo_e2e.py`, `tests/test_website_template_e2e.py`, `tests/test_tab_title_e2e.py`, `tests/test_fullscreen_e2e.py`, `tests/test_http_origin_e2e.py` unchanged and green; the page's own save does not trigger a reload.
- [ ] Docs updated: none in this story (US-0051 carries them, DEC-019).
- [ ] Self review: full (focus never taken, `baseMtime` rules, three failure threshold, notice text exact, no scope creep).
- [ ] If the story registers an MCP tool: not applicable.
- [ ] One commit `US-0049: Conflict choice, save failures and server loss in the editor`, body `Spec: SPEC-0009` and `FR-NEW-003, FR-NEW-007, FR-NEW-009`.
