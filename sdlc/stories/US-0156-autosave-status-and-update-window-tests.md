# US-0156: browser tests for autosave, status dots and the agent update window

> Spec: SPEC-0027 (sdlc/specs/SPEC-0027-browser-test-coverage/)
> Nature: DEBT
> Priority: P1
> Depends on: US-0155
> min_tier: 2
> Files touched: 2
> Closes spec: no

## Objective
Add the browser tests of the rows that depend on timing and on an agent write: autosave delays and save on blur, the status dot colours (yellow during an agent update), no reload while pending or on its own save, and the overlay and single reload around an agent update window. No product code changes.

## Requirements covered
- SPEC-0027/DR-001 (partial: E2E-014, E2E-015, E2E-016 of SPEC-0002; E2E-004, E2E-005 of SPEC-0001): at least one browser test per untested row.
- SPEC-0027/DR-002: observed waits only, `# pacing:` on any kept `wait_for_timeout(`.
- SPEC-0027/DR-004: the existing suite passes unmodified.
- SPEC-0027/DR-005: strict xfail for a revealed product defect, no product edit.

## Independent Test
`make test ARGS='tests/test_autosave_timing_e2e.py tests/test_update_window_e2e.py tests/test_no_fixed_waits.py'` is green, then `make check`. Durations of the two files recorded in the commit body.

## Design excerpt
### Decisions
- DEC-003 (xfail rule), DEC-004 (one file per area). Timing assertions never use a lower time bound (flaky under load): they assert the old state at the moment of the keystroke and the new state within 3 s.
### Paths
| Path | Action |
|---|---|
| `tests/test_autosave_timing_e2e.py` | create |
| `tests/test_update_window_e2e.py` | create |
### Existing patterns
`tests/test_save_ui_e2e.py:45-70` (`fast_poll` sets `HTMLEDITOR_POLL_INTERVAL` to 100, `_open_in_edit_mode`, `_type_in_cover`, `_agent_writes_title` rewrites the cover title with a different mtime), `tests/test_autosave_focus_e2e.py` (the `save_delay` parametrization, prompt variant), `tests/test_width_visibility_e2e.py:53,124` (`OVERLAY_SHOWN`, `wait_for_js`), the state calls `update_start` and `update_end` of `src/mcp_htmleditor/mcp_server.py` through the real tools or the state object. Delays: input 800 ms (`editor-save.js:4`), structural 600 ms (`editor-save.js:6`), blur immediate (`editor-save.js:5`). Dot: `#toolbar-status`, colours `#42be65`, `#ff832b`, `#f1c21b` (`editor.js:49-51`), read back as `rgb(66, 190, 101)`, `rgb(255, 131, 43)`, `rgb(241, 194, 27)`. Overlay: `#update-overlay`.

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.

### SPEC-0027/DT-002: autosave delays and save on blur (E2E-014, FR-004 to FR-006)
- Level / Driver / Location: browser / Chromium / `tests/test_autosave_timing_e2e.py`
- Given a presentation in edit mode (real delays)
- When the human types one character in the cover title
- Then the status dot is orange (pending) and the file on disk still has the old title at that moment, and the file has the new title within 3 s (no lower time bound)
- When the human types, then moves focus to another zone
- Then the file on disk has the new text and the status dot is green within 3 s of the blur
- When the human completes a structural action (insert a slide)
- Then the file on disk has the new slide within 3 s

### SPEC-0027/DT-003: status dot colours including the agent update (E2E-015, FR-007)
- Given a presentation in edit mode
- Then `#toolbar-status` is `rgb(66, 190, 101)` when saved, `rgb(255, 131, 43)` while a change is pending, `rgb(241, 194, 27)` while an agent update is open (`update_start` through the server, then `update_end`), and `rgb(66, 190, 101)` again after the update closes

### SPEC-0027/DT-004: no reload for its own save or while changes are pending (E2E-016, FR-008)
- Given a presentation in edit mode with the frame's load count recorded
- When the human types and the page saves
- Then the frame is not reloaded (load count unchanged)
- When the human has a pending change and the file on disk is changed by an agent write with a new modification time before the save runs
- Then the frame is not reloaded while the change is pending

### SPEC-0027/DT-008: overlay while an agent update window is open (SPEC-0001 E2E-004, FR-004)
- Level / Driver / Location: browser / Chromium / `tests/test_update_window_e2e.py`
- Given a presentation open in the browser with the frame's load count recorded
- When the agent opens an update window and writes the file with a new modification time
- Then `#update-overlay` is shown (display `flex`) and the frame's load count does not change while the window stays open

### SPEC-0027/DT-009: exactly one reload after the update window closes (SPEC-0001 E2E-005, FR-004)
- Given the state of DT-008 (window open, file written)
- When the agent closes the update window
- Then the overlay is hidden and the frame reloads exactly once, showing the new title; no second reload follows within 2 s (`settle`)

## Constraints
- Files not to touch: everything under `src/`, `templates/`, `skill/`, and every existing test.
- Dependencies not to add: none.
- Patterns to avoid: lower time bounds; fixed waits without `# pacing:`.
- Scope boundary: undo depth and the budget doc are US-0157.

## Definition of done
- [ ] RED evidence recorded for any test that shows a product defect, then `xfail(strict=True)`.
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit.
- [ ] DEBT: the existing suite passes unmodified; exceptions: none.
- [ ] Self review: no product file touched, every wait observed.
- [ ] One commit `US-0156: browser tests for autosave, status dots and the agent update window`, body with `Summary:`, `Spec: SPEC-0027` and the requirement ids.
