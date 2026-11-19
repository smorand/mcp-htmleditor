# US-0157: undo depth test and the test step budget rule

> Spec: SPEC-0027 (sdlc/specs/SPEC-0027-browser-test-coverage/)
> Nature: DEBT
> Priority: P1
> Depends on: US-0155, US-0156
> min_tier: 2
> Files touched: 2
> Closes spec: yes

## Objective
Add the undo depth browser test (the last untested row), state the measured test step budget in `.agent_docs/testing.md`, record that the six new files stay within 60 s, and close SPEC-0027 with its full acceptance set.

## Requirements covered
- SPEC-0027/DR-001 (partial: E2E-017 of SPEC-0002; the closing audit checks all nine rows): at least one browser test per untested row.
- SPEC-0027/DR-002: observed waits only.
- SPEC-0027/DR-003: `.agent_docs/testing.md` states that the `make check` test step is measured at about 575 s on a quiet machine, that its cap is 650 s, and that the tests of this spec cost at most 60 s together.
- SPEC-0027/DR-004: the existing suite passes unmodified.
- SPEC-0027/DR-005: strict xfail for a revealed defect.

## Independent Test
`make test ARGS='tests/test_undo_depth_e2e.py'` is green, `rg -n "330 s" .agent_docs/testing.md` prints nothing, `make check` is green, and the six new files run in at most 60 s together (`make test ARGS='<six files> --durations=0'`).

## Design excerpt
### Decisions
- DEC-002: cap 650 s, measured baseline 575 s, tests of this spec at most 60 s together. DEC-003, DEC-004 as in the sibling stories.
### Paths
| Path | Action |
|---|---|
| `tests/test_undo_depth_e2e.py` | create |
| `.agent_docs/testing.md` | modify: the heading at line 36 `### Test step budget (at most 330 s)` becomes `### Test step budget (at most 650 s)`; the text at line 38 states the 575 s baseline measured on 2026-11-18 and the 650 s cap (a step above the cap at load average above 30 stays machine noise, re run once before trimming); add after the SPEC-0016 and SPEC-0017 lines `SPEC-0027 browser tests at most 60 s together`; add a file map row for the six new files (`test_format_insert_bars_e2e.py`, `test_autosave_timing_e2e.py`, `test_undo_depth_e2e.py`, `test_typing_keys_e2e.py`, `test_export_buttons_e2e.py`, `test_update_window_e2e.py`) |
Keep `.agent_docs/testing.md` within the 220 line rule (`tests/test_agent_docs_size.py`): merge or shorten rows if needed.
### Existing patterns
`tests/test_undo_redo_e2e.py` (undo and redo of block inserts in a document, buttons `#undo-btn` and `#redo-btn`, `UNDO_MAX_DEPTH = 50` at `src/mcp_htmleditor/static/editor.js:487`, redo cleared by a new snapshot at `editor-undo.js:45`).

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.

### SPEC-0027/DT-005: undo depth and redo cleared by a new action (E2E-017, FR-011)
- Level / Driver / Location: browser / Chromium / `tests/test_undo_depth_e2e.py`
- Given a document in edit mode and 51 structural actions performed in a row (block inserts)
- When the human undoes as many times as the button stays enabled
- Then exactly 50 steps are undone and `#undo-btn` is then disabled
- When the human redoes one step, then performs a new structural action
- Then `#redo-btn` is disabled

### SPEC-0027/DT-010: the rules hold on the new files
- Level / Driver: structural / `make test`
- Then `tests/test_no_fixed_waits.py` and `tests/test_browser_wait.py` pass unchanged with the six new files present, and every `wait_for_timeout(` in them carries `# pacing:`

### SPEC-0027/DT-011: the budget is stated and respected
- Level / Driver: structural / `rg` and `--durations=0`
- Then `.agent_docs/testing.md` contains `650 s`, `575 s` and `SPEC-0027 browser tests at most 60 s together`, does not contain `at most 330 s`, and the sum of the durations of the six files is at most 60 s (the sum is written in the commit body)

## Constraints
- Files not to touch: everything under `src/`, `templates/`, `skill/`, every existing test, every file under `sdlc/specs/`.
- Dependencies not to add: none.
- Scope boundary: the other eight rows are in US-0155 and US-0156.

## Definition of done
- [ ] RED evidence recorded for a test that shows a product defect, then `xfail(strict=True)`.
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit.
- [ ] Spec converge: every test of SPEC-0027 (DT-001 to DT-011) green, every requirement DR-001 to DR-005 cited by at least one story with status done or landed.
- [ ] DEBT: the existing suite passes unmodified; exceptions: none.
- [ ] Docs updated: `.agent_docs/testing.md`.
- [ ] One commit `US-0157: undo depth test and the test step budget rule`, body with `Summary:`, `Spec: SPEC-0027` and the requirement ids.
