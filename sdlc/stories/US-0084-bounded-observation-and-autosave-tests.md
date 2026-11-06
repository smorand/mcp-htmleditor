# US-0084: Bounded observation and the autosave tests

> Spec: SPEC-0014 (sdlc/specs/SPEC-0014-lifecycle-test-reliability/)
> Nature: BUG
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

The autosave tests wait a fixed 1500 ms then read the file or the status dot once (E10 to E12): any save round
trip longer than the margin fails the gate while the editor is correct (BUG-002). This story adds the shared
observation helper (observe every 100 ms at most, up to 10 s, report the last value), the settle step for
absences, and the late save route, then rewrites the 13 waits of `tests/test_autosave_focus_e2e.py` and runs every
test of that file with saves answered at once and 2000 ms late.

## Requirements covered

- SPEC-0014/BR-008 (partial: the helper, and `tests/test_autosave_focus_e2e.py`): The browser test suite SHALL assert every asynchronous result by observing it repeatedly, at most 100 ms apart, until it holds or 10 seconds have passed since the action that triggers it.
- SPEC-0014/BR-009 (partial: `tests/test_autosave_focus_e2e.py`): The browser test suite SHALL NOT assert that an asynchronous result is present after a fixed delay without the observation of BR-008.
- SPEC-0014/BR-010 (partial: the settle helper and `test_self_save_does_not_reload_the_preview`): IF a browser test asserts that something did not happen (for example the preview was not reloaded) THEN it SHALL first await, per BR-008, the asynchronous step that could have caused it, then observe for a fixed settle delay of at least 1 second before asserting the absence.
- SPEC-0014/BR-011 (partial: `tests/test_autosave_focus_e2e.py`): The tests of `tests/test_autosave_focus_e2e.py` and `tests/test_undo_redo_e2e.py` SHALL pass when every `POST /content` answer reaches the browser 2000 ms late.

Business rules (spec): on failure the assertion reports the last observed value (for example the file text or the
colour string), as today's single read does. "Asynchronous result" means a state the editor reaches after a timer
or a network round trip: file content after an autosave, status dot colour, DOM after an insert, undo or redo, a
reload of the preview.

## Independent Test

`make test ARGS='-k "autosave_focus or browser_wait"'` (part of `make check`): every test of
`tests/test_autosave_focus_e2e.py` passes in both `save_delay` variants (`prompt`, `late`); in the `late` variant
`test_several_saves_lose_nothing[chromium-late]` finds `Titre du document123` in `D` (red today with the fixed
waits: it reads `Titre du document12`).

## Design excerpt

### Decisions
- DEC-011 (SPEC-0014): "`tests/browser_wait.wait_until` observes, checks, and waits `page.wait_for_timeout(100)` between observations, until the check holds or 10 seconds have passed since the call (the call is made right after the triggering action); the failure is an `AssertionError` naming what was awaited and the last observed value (`repr`). `wait_for_file` and `wait_for_js` are the two shapes used by the browser files." In the sync Playwright API route handlers and events run only inside a Playwright call, so `time.sleep` would freeze the late save route.
- DEC-012 (SPEC-0014): "An absence is asserted after `wait_until` on the step that could cause it, then `settle(page)` (`page.wait_for_timeout(1000)`), then the assertion."
- DEC-013 (SPEC-0014): "Late saves: `answer_saves_late(page, 2000)` routes `**/content`; a `POST` is sent on with `route.fetch()`, the handler sleeps 2 seconds, then `route.fulfill(response=...)`; other methods `continue_()`. In `tests/test_autosave_focus_e2e.py` and `tests/test_undo_redo_e2e.py`, a fixture `save_delay` parametrized `[0, 2000]` (ids `prompt`, `late`) is a parameter of every existing test and applies the route when not 0." A route registered later by a test (the abort of `test_failed_save_keeps_focus`) wins.
- DEC-014 (SPEC-0014): every `wait_for_timeout(` kept in a browser test file carries a trailing comment `# pacing: <reason>` (a spacing between two user actions, not followed by an assertion of its result); the settle delay lives only in `tests/browser_wait.py`. The guard test that enforces it is US-0088.

### Contracts
```python
# tests/browser_wait.py (new)
OBSERVE_INTERVAL_SECONDS = 0.1
OBSERVE_BOUND_SECONDS = 10.0
SETTLE_SECONDS = 1.0
LATE_SAVE_MS = 2000
T = TypeVar("T")


def wait_until(
    page: Page, observe: Callable[[], T], holds: Callable[[T], bool], *, what: str, bound: float = OBSERVE_BOUND_SECONDS
) -> T:
    ...
    # observes first, then page.wait_for_timeout(OBSERVE_INTERVAL_SECONDS * 1000) between observations,
    # deadline time.monotonic() + bound taken at the call; on expiry, one last observation, then
    # AssertionError(f"{what} not reached within {bound:g} s, last value: {value!r}")


def wait_for_file(
    page: Page, path: Path, needle: str
) -> str: ...  # holds: needle in path.read_text(encoding="utf-8"); what: f"{path.name} containing {needle!r}"
def wait_for_js(
    page: Page, expression: str, expected: object, *, what: str
) -> object: ...  # holds: page.evaluate(expression) == expected
def settle(page: Page) -> None: ...  # page.wait_for_timeout(SETTLE_SECONDS * 1000)
def answer_saves_late(page: Page, delay_ms: int = LATE_SAVE_MS) -> None: ...
```
```python
# tests/test_autosave_focus_e2e.py
@pytest.fixture(params=[0, LATE_SAVE_MS], ids=["prompt", "late"])
def save_delay(request: pytest.FixtureRequest, page: Page) -> int: ...  # answer_saves_late(page, ms) when ms
```

### Paths
| Path | Action |
|---|---|
| `tests/browser_wait.py` | create |
| `tests/test_browser_wait.py` | create: helper unit tests (no browser: a stub object with `wait_for_timeout(ms)` that advances nothing but sleeps) |
| `tests/test_autosave_focus_e2e.py` | modify: 13 waits, `save_delay` on the 9 tests, BT-014 |
| `.agent_docs/testing.md` | modify: "Browser waits (2026-11, SPEC-0014)" section and files table |

### Existing patterns
- The 13 waits (`rg -n 'wait_for_timeout\(' tests/test_autosave_focus_e2e.py`): `:79` (edit mode after the click: observe `#edit-mode-btn` active or an editable zone with `contenteditable`), `:113`, `:130`, `:145`, `:162`, `:176`, `:196`, `:209`, `:236`, `:238` (`SAVE_WAIT_MS`: each becomes `wait_for_file` on the text just typed, or `wait_for_js` on the status dot colour `rgb(66, 190, 101)` for `:238`), `:172`, `:174` (`1000` between typing `1`, `2`, `3`: pacing, kept with `# pacing:`), `:225` (`2500` in the self save test: BR-010, see BT-015). `test_failed_save_keeps_focus` (`:145`): the save is aborted, so nothing reaches the file; its wait becomes an observation of the attempt (a `page.on("requestfailed")` counter or the status dot leaving the saved colour) before typing `R`.
- `SAVE_WAIT_MS` disappears from this file once unused.
- The BUG-002 reproduction pattern (route delay, observation of the file): `/tmp/spec14/test_slow_save.py` as quoted in the spec; the late route must answer late, not send late.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Conventions (Spec section 4): `D` is the served copy of the `doc` bootstrap (fixture `served`); Playwright
Chromium (`needs_chromium`). Assertions of the existing tests stay as they are; only how the result is awaited
changes. Location `tests/test_autosave_focus_e2e.py` unless stated.

### SPEC-0014/BT-014: Bounded observation reports the last value
- Level / Driver / Location: functional e2e; Playwright Chromium, `browser_wait`; `tests/test_autosave_focus_e2e.py` (a test without the `save_delay` parameter)
- Given the autosave scenario of BT-002 with every `POST /content` aborted (as `test_failed_save_keeps_focus` does)
- When a test asserts, through `wait_for_file`, that `D` contains `Titre du documentQ` (after typing `Q` at the end of the title)
- Then it fails between 10 and 12 seconds after typing (measured with `time.monotonic()` around `pytest.raises(AssertionError)`), and its failure text includes the current content of `D` (which holds `Titre du document` without `Q`)

### SPEC-0014/BT-015: Absence awaited after its cause
- Level / Driver / Location: functional e2e; Playwright Chromium; `tests/test_autosave_focus_e2e.py` (`test_self_save_does_not_reload_the_preview[chromium-late]`)
- Given every `POST /content` answered 2000 ms late
- When the scenario of `test_self_save_does_not_reload_the_preview` runs
- Then it observes `D` containing `Titre du documentAAA` before asserting the probe (`wait_for_file`, then the late answer itself awaited through `wait_for_js` on the status dot `rgb(66, 190, 101)`, then `settle(page)`), and the probe equals `1`

### Support tests of this story (not spec ids), `tests/test_browser_wait.py`
- `wait_until` returns the first value that holds, after the expected number of observations; the stub records waits of 100 ms each.
- `wait_until` with a check that never holds and `bound=0.5` raises `AssertionError` whose text contains `what` and the `repr` of the last value, after 0.5 to 1.5 seconds.
- Every recorded wait is at most 100 ms (BR-008 interval).

## Constraints

- Files not to touch: product code under `src/`; the other browser test files (US-0085 to US-0087).
- Dependencies not to add: none.
- Patterns to avoid: `time.sleep` in an observation loop; Playwright `expect` with its default polling; a fixed wait before a presence assertion; changing an existing assertion's expected value.
- Scope boundary: the guard test is US-0088; the undo file is US-0085.

## Definition of done

- [ ] RED evidence recorded: the `late` variant of `test_several_saves_lose_nothing` fails with the old waits before they are rewritten.
- [ ] Every acceptance test above green; all 9 existing tests green in both variants; `make check` green; main stays green after the squash.
- [ ] Non regression: SPEC-0004 BT-001, BT-010 to BT-014, BT-020 to BT-022 keep their Then clauses (spec section 5).
- [ ] Every remaining `wait_for_timeout(` in the file carries `# pacing: <reason>`.
- [ ] Docs updated: `.agent_docs/testing.md` (helper, constants, late saves, the pacing comment rule).
- [ ] Self review: full (tier 2), including the run time of this file before and after (`make test ARGS='-k autosave_focus --durations=0'`), reported.
- [ ] One commit `US-0084: Bounded observation and the autosave tests`, body `Spec: SPEC-0014` and BR-008, BR-009, BR-010, BR-011.
