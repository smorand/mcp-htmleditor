# US-0087: Save ui, refresh, origin and header gate waits

> Spec: SPEC-0014 (sdlc/specs/SPEC-0014-lifecycle-test-reliability/)
> Nature: BUG
> Priority: P2
> Depends on: US-0084
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

The last four browser test files with fixed waits (E14): save UI 6, request refresh 6, origin 4, header gate 2.
Several of them assert a save on disk after `1500` ms (SPEC-0013/BT-031, SPEC-0005 non regression) or assert that
nothing happened after a fixed delay. This story rewrites each wait with the observation helper of US-0084,
awaits the cause before each absence, and marks the remaining ones as pacing.

## Requirements covered

- SPEC-0014/BR-008 (partial: the four files): The browser test suite SHALL assert every asynchronous result by observing it repeatedly, at most 100 ms apart, until it holds or 10 seconds have passed since the action that triggers it.
- SPEC-0014/BR-009 (partial: the four files): The browser test suite SHALL NOT assert that an asynchronous result is present after a fixed delay without the observation of BR-008.
- SPEC-0014/BR-010 (partial: the absence assertions of the four files): IF a browser test asserts that something did not happen (for example the preview was not reloaded) THEN it SHALL first await, per BR-008, the asynchronous step that could have caused it, then observe for a fixed settle delay of at least 1 second before asserting the absence.

## Independent Test

`make test ARGS='-k "save_ui or requests_refresh or http_origin or header_gate"'` (part of `make check`): every
test passes, and `rg -n 'wait_for_timeout\(' tests/test_save_ui_e2e.py tests/test_requests_refresh_e2e.py tests/test_http_origin_e2e.py tests/test_http_header_gate_e2e.py`
prints only lines carrying `# pacing:`.

## Design excerpt

### Decisions
- DEC-011 (SPEC-0014): "`tests/browser_wait.wait_until` observes, checks, and waits `page.wait_for_timeout(100)` between observations, until the check holds or 10 seconds have passed since the call; the failure is an `AssertionError` naming what was awaited and the last observed value. `wait_for_file` and `wait_for_js` are the two shapes used by the browser files."
- DEC-012 (SPEC-0014): "An absence is asserted after `wait_until` on the step that could cause it, then `settle(page)` (`page.wait_for_timeout(1000)`), then the assertion."
- DEC-014 (SPEC-0014): every kept `wait_for_timeout(` carries `# pacing: <reason>` (a spacing between two user actions, not followed by an assertion of its result). A measurement window, where the quantity under test is a count over a fixed duration (a polling period), is a kept wait with `# pacing: measurement window`: the duration is what is measured, not a delay before a result.

### Contracts
`tests/browser_wait.py` (US-0084): `wait_until`, `wait_for_js`, `wait_for_file`, `settle`.

### Paths
| Path | Action |
|---|---|
| `tests/test_save_ui_e2e.py` | modify: `:50`, `:115`, `:170`, `:222`, `:234`, `:236`; `SAVE_WAIT_MS` removed once unused |
| `tests/test_requests_refresh_e2e.py` | modify: `:97`, `:101`, `:110`, `:117`, `:132`, `:137` |
| `tests/test_http_origin_e2e.py` | modify: `:187`, `:233`, `:393`, `:397` |
| `tests/test_http_header_gate_e2e.py` | modify: `:400`, `:404` |

### Existing patterns
Classification of each wait, from the lines around it (read on 00f0d9e):
- Presence on disk after a save, becomes `wait_for_file`: save UI `:222` (`CouvertureQR`), `:236` (`CouvertureAB`; `:234` before typing `B` waits for the first save: observe `CouvertureA` on disk), origin `:397` and header gate `:404` (`AAA` in the served file: SPEC-0005 non regression and SPEC-0013/BT-031, whose "1500 ms waited" step becomes the observation, spec section 5), origin `:187` (saved content read after a save).
- Edit mode after a click (`150` ms): origin `:393`, header gate `:400`, save UI `:50`: observe an editable zone carrying `contenteditable`.
- Absence: save UI `:115` (no new POST and `X` not on disk: await the step that could have posted, for example the debounce attempt observed through the status dot or the conflict notice, then `settle(page)`), `:170` (`failed == [1]` presence observed first, then `window.__seen` is `False` after `settle`); origin `:233` (`MARKER` absent from `window.__result`: await `window.__result` set, then assert); request refresh `:137` (exactly one `GET /requests` since the mark: await the first one, `settle`, assert the count).
- Measurement windows in request refresh: `:101` (at least 10 `GET /status` in 2600 ms) and `:117` (`3 * POLL_MS + 400`): the period is the quantity under test; keep with `# pacing: measurement window`, and await their start condition (`:97`, `:110`, `:132`: the first poll observed) instead of a fixed delay.
- The helper: `tests/browser_wait.py`; an example rewrite is in `tests/test_autosave_focus_e2e.py` (US-0084). `_wait_dot` in `tests/test_save_ui_e2e.py` already observes the status dot: route it through `wait_for_js` if it polls slower than 100 ms.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

No new spec test id: this story's verdict is the existing tests of the four files passing with their assertions
unchanged, observation before every asynchronous read, settle after every awaited cause before an absence, and the
grep check of the Independent Test. Spec section 4.4 row: "Modified where the wait precedes an asynchronous result,
else Kept; BR-008 to BR-010 decide each wait; assertions unchanged." Spec section 5: SPEC-0013/BT-031 "1500 ms
waited" becomes the observation; its Then clause is unchanged.

### Support check of this story (not a spec id)
- Under an injected delay (local check during the story, not committed): `answer_saves_late(page, 2000)` at the start of `test_bt_031_browser_editor_keeps_saving` and `test_browser_editor_still_saves_polls_exports`, the tests still pass; record the run in the story report.

## Constraints

- Files not to touch: product code; the other browser files.
- Dependencies not to add: none.
- Patterns to avoid: `time.sleep`; a fixed wait before a presence assertion; changing an expected value or a measured threshold.
- Scope boundary: the guard test is US-0088.

## Definition of done

- [ ] RED evidence: for at least one rewritten wait per file, show the old line failing under an injected delay and the observation passing.
- [ ] Every existing test of the four files green; `make check` green; main stays green after the squash.
- [ ] Every remaining `wait_for_timeout(` in the four files carries `# pacing: <reason>`.
- [ ] Docs updated: none.
- [ ] Self review: full (tier 2), per wait: what it awaited, how it is observed now.
- [ ] One commit `US-0087: Save ui, refresh, origin and header gate waits`, body `Spec: SPEC-0014` and BR-008, BR-009, BR-010.
