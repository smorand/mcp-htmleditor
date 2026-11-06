# US-0085: Undo and redo tests observe and pass with late saves

> Spec: SPEC-0014 (sdlc/specs/SPEC-0014-lifecycle-test-reliability/)
> Nature: BUG
> Priority: P1
> Depends on: US-0084
> min_tier: 2
> Files touched: 2
> Closes spec: no

## Objective

The undo and redo tests wait a fixed 300 ms after each insert, undo and redo before reading the DOM once (E13), and
`test_undo_redo_document_block_insert` already failed at random in US-0026 (BL-0024). This story rewrites the 23
waits of `tests/test_undo_redo_e2e.py` with the observation helper of US-0084 and runs every test of the file with
saves answered at once and 2000 ms late, which completes BR-011 and makes BT-002 green.

## Requirements covered

- SPEC-0014/BR-008 (partial: `tests/test_undo_redo_e2e.py`): The browser test suite SHALL assert every asynchronous result by observing it repeatedly, at most 100 ms apart, until it holds or 10 seconds have passed since the action that triggers it.
- SPEC-0014/BR-009 (partial: `tests/test_undo_redo_e2e.py`): The browser test suite SHALL NOT assert that an asynchronous result is present after a fixed delay without the observation of BR-008.
- SPEC-0014/BR-011: The tests of `tests/test_autosave_focus_e2e.py` and `tests/test_undo_redo_e2e.py` SHALL pass when every `POST /content` answer reaches the browser 2000 ms late.

## Independent Test

`make test ARGS='-k "undo_redo or autosave_focus"'` (part of `make check`): every test of both files passes in both
`save_delay` variants; `test_undo_redo_document_block_insert[chromium-late]` passes (red with the 300 ms waits
under late saves whenever the DOM change follows a save round trip).

## Design excerpt

### Decisions
- DEC-011 (SPEC-0014): "`tests/browser_wait.wait_until` observes, checks, and waits `page.wait_for_timeout(100)` between observations, until the check holds or 10 seconds have passed since the call; the failure is an `AssertionError` naming what was awaited and the last observed value. `wait_for_file` and `wait_for_js` are the two shapes used by the browser files."
- DEC-013 (SPEC-0014): "a fixture `save_delay` parametrized `[0, 2000]` (ids `prompt`, `late`) is a parameter of every existing test and applies the route when not 0." Same fixture shape as `tests/test_autosave_focus_e2e.py` (US-0084): define it in this file with `answer_saves_late` from `tests/browser_wait.py`; if both files end up with an identical fixture body, move it to `tests/browser_wait.py` as a plain function `apply_save_delay(page, ms)` called by each file's two line fixture (zero duplication).
- DEC-014 (SPEC-0014): every kept `wait_for_timeout(` carries `# pacing: <reason>`.

### Contracts
`tests/browser_wait.py` (US-0084): `wait_until(page, observe, holds, *, what, bound=10.0)`,
`wait_for_js(page, expression, expected, *, what)`, `settle(page)`, `answer_saves_late(page, delay_ms=2000)`,
`LATE_SAVE_MS = 2000`.

### Paths
| Path | Action |
|---|---|
| `tests/test_undo_redo_e2e.py` | modify: 23 waits, `save_delay` on the 8 tests |
| `tests/browser_wait.py` | modify only if the shared `apply_save_delay` of DEC-013 is extracted (then 2 files) |

### Existing patterns
- The 23 waits (`rg -n 'wait_for_timeout\(' tests/test_undo_redo_e2e.py`): `:161` (`_enable_edit_mode`, 150 ms: observe the undo button displayed, as `test_undo_redo_buttons_hidden_outside_edit_mode` reads it), and `:197` to `:400` (300 ms or 200 ms after a drag, a key press, a menu click: each becomes `wait_until` on the very value the next line reads, for example `wait_for_js(page, "...dataset.x", original_x, what="node x after undo")`, or a count of blocks/rows/slides that must change). When the next read asserts a value different from before (a move happened), observe "differs from the previous value" with `holds=lambda v: v != original_x`.
- `_inner(page, js_expression)` (`:152`) builds the iframe expression; reuse it inside `observe` lambdas.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0014/BT-002: Autosave and undo tests pass with late saves
- Level / Driver / Location: functional e2e; Playwright Chromium tests that answer every `POST /content` 2000 ms late (browser side route delay, `answer_saves_late`) and run the scenarios of every test of `tests/test_autosave_focus_e2e.py` and `tests/test_undo_redo_e2e.py` (the `late` variant of each); both files
- Red before the fix because: the fixed 1500 ms and 300 ms waits read the result before the round trip ends (E10 to E13).
- Given the delay above
- When the scenario of `test_several_saves_lose_nothing` runs (type `1`, wait 1000 ms, type `2`, wait 1000 ms, type `3`)
- Then `D` contains `Titre du document123`, and every other scenario passes with its existing assertion (for example the status dot colour equals `rgb(66, 190, 101)`)
- Evidence: `make test ARGS='-k "undo_redo or autosave_focus" -k late'` lists 17 tests, all passed.

## Constraints

- Files not to touch: product code; the other browser files.
- Dependencies not to add: none.
- Patterns to avoid: `time.sleep`; a fixed wait before a DOM read; changing an expected value.
- Scope boundary: the guard test is US-0088.

## Definition of done

- [ ] RED evidence recorded: at least one `late` variant fails with the old 300 ms waits (or, if none does on this machine, the record says so and shows the 800 ms injected reproduction of BL-0024 for `test_undo_redo_document_block_insert`).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the 8 undo and redo tests keep their assertions.
- [ ] Every remaining `wait_for_timeout(` in the file carries `# pacing: <reason>`.
- [ ] Docs updated: none (the helper is documented by US-0084).
- [ ] Self review: full (tier 2), run time of the file before and after reported.
- [ ] One commit `US-0085: Undo and redo tests observe and pass with late saves`, body `Spec: SPEC-0014` and BR-008, BR-009, BR-011.
