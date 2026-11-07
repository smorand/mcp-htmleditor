# US-0092: Interrupted drags, saves during a drag, conflicts

> Spec: SPEC-0015 (sdlc/specs/SPEC-0015-text-max-width-handle/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0091
> min_tier: 1
> Files touched: 4
> Closes spec: no

## Objective

A width drag never corrupts the file: a cancelled drag or a reload in the middle changes nothing, an autosave of
typing during the drag writes the old width with the typing, an agent write during the drag ends in the existing
conflict choice, and a stopped server leaves the change pending with the existing notices. After any sequence the file
differs only in the styles the author set. Silent pitfalls: the poll would reload the frame on an external write
during a drag, and the blur save fires as soon as the bar is pressed.

## Requirements covered

- SPEC-0015/FR-NEW-010: The editor SHALL NOT save the width bar, its readout, any marker of the pointed text, or a width still being dragged.
- SPEC-0015/FR-NEW-011: IF a drag of the width bar is cancelled by the system THEN THE editor SHALL show the text at the width it had before the drag and save nothing.
- SPEC-0015/FR-NEW-012: The editor SHALL NOT change, through a width action, any text, any other element, or the written form of any other declaration of the text's style.
- SPEC-0015/FR-NEW-013: The editor SHALL save a width change through the same save as every other edit, with its status, conflict notice and error notice.
- SPEC-0015/NFR-003: The saved file SHALL NOT hold an editing marker after any sequence of width actions, undos, redos, reloads and conflicts (FR-NEW-010).

Business rules (spec, verbatim): FR-NEW-010 "a save that happens during a drag (for example the autosave of typing
done just before) writes the width the text had before the drag. After any width action the only difference in the
file is the text's style as stated in FR-NEW-005 or FR-NEW-007." FR-NEW-011 "a reload of the document during a drag
(an agent update ending) cancels the drag the same way: the reloaded file is shown and the editor saves nothing."
FR-NEW-012 "a colour written as `#0F62FE` stays `#0F62FE`. Typing done before the drag is kept and saved."
FR-NEW-013 user visible text (existing): conflict notice
`The file changed on disk. Reload to see the changes, or keep your version.`; connection notice
`Connection to the editor server lost`.

## Independent Test

`make test ARGS='-k width_failures'`: the eight tests below pass; each reads the file on disk and the notices of the
shell (`#save-conflict`, `#save-error`, `#connection-lost`), for example after a cancelled drag the file is byte
identical and Undo is disabled.

## Design excerpt

### Decisions
- DEC-004 (SPEC-0015): "`withWidthPreviewSuspended(fn)`: while a drag preview is applied, it sets the original attribute text back (or removes the attribute when it was absent), runs `fn` synchronously, then re-applies the preview [...]. `runSave` wraps its `cloneNode(true)`; `captureDomSnapshot` wraps its `outerHTML`." (both done by US-0089 and US-0090; this story proves them.)
- DEC-007 (SPEC-0015), cancel part: "`pointercancel` and a `lostpointercapture` not preceded by `pointerup` cancel: original text back, readout hidden, nothing saved."
- DEC-008 (SPEC-0015): "`pollStatus` (`editor.js:309`): when the update overlay is shown it calls `widthBarOnAgentUpdate()` (cancel, hide); the external change test becomes `mtimeChanged && !selfSaving && !hasPendingChanges && !widthDragActive()`, so an agent write during a drag does not reload the frame and the release save meets the SPEC-0009 conflict (409, notice). `onFrameLoad` (`editor.js:199`) calls `widthBarOnFrameLoad()` first: the drag is dropped without touching the new document and the bar hides until the pointer moves." Rejected alternative: `markPending` at the press (the typing autosave during the drag calls `markSaved()` and would re-enable the reload).
- DEC-009 (SPEC-0015): no new route; "a pending change after a failed save stays pending and is written by the next successful save (E2E-039)."
- DEC-011 (SPEC-0015): shared module page, one server per test; this file sets `HTMLEDITOR_POLL_INTERVAL=100` (as `tests/test_save_ui_e2e.py:47`) so three failed polls take about 300 ms.

### Contracts
`function widthDragActive()` (new global, `editor-width.js`). Notices (`editor.html:54` to `:62`): `#save-conflict`,
`#save-error` (text `Save failed: <browser message>`), `#connection-lost`. Server stop and restart on the same port:
`stop_http_server()`, `start_http_server(file, port=P)` (the stop releases the port since SPEC-0014).
A system cancel in a test: `page.evaluate` dispatching `new PointerEvent('pointercancel', {pointerId: 1, bubbles: true})`
on `#width-bar` while the mouse button is down (Playwright's mouse uses pointer id 1).

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-width.js` | modify: cancel on `pointercancel` and `lostpointercapture`, `widthDragActive`, drag dropped on frame load and agent update |
| `src/mcp_htmleditor/static/editor.js` | modify: `pollStatus` external change guard |
| `tests/width_support.py` | modify: `markers_in(path)` (ids, classes, attributes starting with `_mcp` or `contenteditable`, the bar ids) |
| `tests/test_width_failures_e2e.py` | create |

### Existing patterns
- Conflict and connection notices in tests: `tests/test_save_ui_e2e.py` (`LOST_TEXT`, poll interval 100).
- Agent update from a test: `mcp_htmleditor.state.get_state().set_update_flag(True)`, write the file, `set_update_flag(False)`.
- Stripper reference: `_EDITOR_ARTIFACTS` in `src/mcp_htmleditor/http_server.py:52` (read only).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

All: functional e2e, Playwright Chromium, shared module page, `HTMLEDITOR_POLL_INTERVAL=100`,
`tests/test_width_failures_e2e.py`, fixture D1 on slide 2, edit mode on.

### SPEC-0015/E2E-017: Nothing of the editor in the file
- Given D1 / When the author drags A to 650, presses Right on it, double clicks H, Undoes, Redoes and reloads
- Then compared with D1 on disk the file differs only in the style of A and H; it contains no element, class, id or attribute added by the editor, and the readout text `px` appears nowhere outside a style

### SPEC-0015/E2E-018: An autosave during the drag keeps the old width
- Given D1, the author types `!` at the end of paragraph J
- When within half a second they press A's bar, move it 100 pixels right, hold still until the typing save lands (observe the file holding `Hors charte!` with `wait_for_file`, replacing the spec's 2 second hold), then move back 50 and let go
- Then read during the hold, the file has J `Hors charte!` and A `max-width:600px`; after letting go A reads `max-width:650px` and J still `Hors charte!`

### SPEC-0015/E2E-019: A cancelled drag changes nothing
- Given D1 / When the author drags A's bar 100 pixels right and the system cancels the pointer (for example the window loses the pointer)
- Then A is 600 wide again, the file is unchanged, Undo stays disabled

### SPEC-0015/E2E-026: File changed on disk during a drag
- Given D1, the author is dragging A's bar / When the agent writes the file (paragraph J now `Changé`) and the author lets go at 650 (after `wait_for_js` shows the shell's `lastMtime` equal to the new file mtime, so the poll has seen the write)
- Then the notice `The file changed on disk. Reload to see the changes, or keep your version.` shows; the file still holds the agent's version

### SPEC-0015/E2E-027: Server unreachable
- Given D1, the editor server stopped / When the author drags A to 650 and lets go
- Then the save error notice shows (its text is the browser's network message, unchanged by this feature), the status stays pending (dot `rgb(255, 131, 43)`), A stays 650 wide on screen; after three failed polls `Connection to the editor server lost` shows

### SPEC-0015/E2E-032: Typing before the drag is kept
- Given D1 / When the author types `!` at the end of A, then at once drags A's bar until the readout shows `650 px`
- Then the file's A reads `Chiffres clés du trimestre!` with style `max-width:650px`

### SPEC-0015/E2E-036: A reload during the drag
- Given D1, the author is dragging A's bar, readout `700 px` / When the agent ends an update that changed paragraph J to `Changé` and the editor reloads the document, then the author lets go
- Then the page shows J `Changé` and A at 600; the file holds A `max-width:600px`; no save by the editor happened and Undo is disabled

### SPEC-0015/E2E-039: Reset with the server unreachable
- Given D1, the editor server stopped / When the author double clicks A's bar
- Then A is 800 wide on screen, the save error notice shows and the status stays pending
- And once the server is back (restarted on the same port), the next save writes A without style attribute (trigger: the author types `!` at the end of J, whose autosave sends the whole document)

## Constraints

- Files not to touch: `http_server.py` (no strip entry is needed: nothing of the bar is in the framed document), `editor-save.js` beyond US-0089.
- Dependencies not to add: none.
- Patterns to avoid: `markPending` as the drag guard (DEC-008 rejected it); a fixed hold in E2E-018; restoring the old block's style after a frame load (the old document is gone).
- Scope boundary: agent read, lint and guidance are US-0093.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (E2E-026 red: the frame reloads and no conflict notice shows; E2E-019 red: the text stays at the preview width).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_save_ui_e2e.py`, `tests/test_autosave_focus_e2e.py`, `tests/test_save_safety_e2e.py`, `tests/test_strip_idempotent.py`, and the earlier width files.
- [ ] Run time: `make test ARGS='-k width_failures --durations=0'` recorded; the file takes at most 8 s.
- [ ] Docs updated: none in this story (US-0093).
- [ ] Self review: full (tier 1), naming every path that serializes the framed document (`rg -n "outerHTML|cloneNode\(true\)" src/mcp_htmleditor/static/*.js`) and showing each goes through `withWidthPreviewSuspended`.
- [ ] One commit `US-0092: Interrupted drags, saves during a drag, conflicts`, body `Spec: SPEC-0015` and FR-NEW-010, FR-NEW-011, FR-NEW-012, FR-NEW-013, NFR-003.
