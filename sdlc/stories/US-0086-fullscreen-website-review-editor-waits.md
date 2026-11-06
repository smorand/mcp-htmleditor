# US-0086: Fullscreen, website, review and request editor waits

> Spec: SPEC-0014 (sdlc/specs/SPEC-0014-lifecycle-test-reliability/)
> Nature: BUG
> Priority: P2
> Depends on: US-0084
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Four more browser test files read an asynchronous result after a fixed delay (E14): fullscreen 9 waits, website 2,
review apply 1, request editor 2. This story rewrites each wait that precedes an asynchronous result with the
observation helper of US-0084, awaits the cause before each absence assertion, and marks the remaining ones as
pacing, so these files give the same verdict on a slow machine.

## Requirements covered

- SPEC-0014/BR-008 (partial: the four files): The browser test suite SHALL assert every asynchronous result by observing it repeatedly, at most 100 ms apart, until it holds or 10 seconds have passed since the action that triggers it.
- SPEC-0014/BR-009 (partial: the four files): The browser test suite SHALL NOT assert that an asynchronous result is present after a fixed delay without the observation of BR-008.
- SPEC-0014/BR-010 (partial: the absence assertions of the four files): IF a browser test asserts that something did not happen (for example the preview was not reloaded) THEN it SHALL first await, per BR-008, the asynchronous step that could have caused it, then observe for a fixed settle delay of at least 1 second before asserting the absence.

## Independent Test

`make test ARGS='-k "fullscreen or website_template or review_apply or requests_editor"'` (part of `make check`):
every test passes, and `rg -n 'wait_for_timeout\(' tests/test_fullscreen_e2e.py tests/test_website_template_e2e.py tests/test_review_apply_e2e.py tests/test_requests_editor_e2e.py`
prints only lines carrying `# pacing:` (or nothing).

## Design excerpt

### Decisions
- DEC-011 (SPEC-0014): "`tests/browser_wait.wait_until` observes, checks, and waits `page.wait_for_timeout(100)` between observations, until the check holds or 10 seconds have passed since the call; the failure is an `AssertionError` naming what was awaited and the last observed value. `wait_for_file` and `wait_for_js` are the two shapes used by the browser files."
- DEC-012 (SPEC-0014): "An absence is asserted after `wait_until` on the step that could cause it, then `settle(page)` (`page.wait_for_timeout(1000)`), then the assertion."
- DEC-014 (SPEC-0014): every kept `wait_for_timeout(` carries `# pacing: <reason>` (a spacing between two user actions, not followed by an assertion of its result).

### Contracts
`tests/browser_wait.py` (US-0084): `wait_until`, `wait_for_js`, `wait_for_file`, `settle`.

### Paths
| Path | Action |
|---|---|
| `tests/test_fullscreen_e2e.py` | modify: `:161`, `:205`, `:221`, `:229`, `:232`, `:235`, `:244`, `:248`, `:252` |
| `tests/test_website_template_e2e.py` | modify: `:95`, `:125` |
| `tests/test_review_apply_e2e.py` | modify: `:144` |
| `tests/test_requests_editor_e2e.py` | modify: `:292`, `:295` |

### Existing patterns
Classification of each wait, from the line that follows it (read on 00f0d9e):
- Presence after the wait, becomes `wait_for_js` on that exact expression and value: fullscreen `:161` (`doc.fullscreenElement.tagName == "HTML"`), `:205` (`document.fullscreenElement.id == "content-frame"`), `:229`, `:232`, `:235`, `:248` (`_progress(page)` equals `2 / 3`, `3 / 3`, `2 / 3`, `3 / 3`), `:252` (`document.fullscreenElement` becomes `null`: a presence of the exit state, observed); website `:95` (computed `display` of `#export-pptx-btn` equals `none`); request editor `:292` (`#requests-side` hidden) and `:295` (visible again), observed with `wait_until(page, lambda: page.is_visible("#requests-side"), ...)`.
- Waits before a further action, not before an assertion: fullscreen `:221`, `:244` (entering fullscreen before forcing focus or pressing a key: observe the fullscreen state reached rather than pacing, since the next action depends on it); website `:125` (before clicking a tab: observe the previous tab's panel active).
- Absence: review apply `:144` asserts `window.__xss` is `None` and no `img` in `#suggestions-list`: await the step that could inject (the suggestions list rendered, for example its item count equals the expected one), then `settle(page)`, then assert.
- The helper: `tests/browser_wait.py`; an example rewrite is in `tests/test_autosave_focus_e2e.py` (US-0084).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

No new spec test id: this story's verdict is the existing tests of the four files passing with their assertions
unchanged, the observation helper used before every asynchronous read, and the grep check of the Independent Test.
Spec section 4.4 row: "Modified where the wait precedes an asynchronous result, else Kept; BR-008 to BR-010 decide
each wait; assertions unchanged."

### Support check of this story (not a spec id)
- Under an injected delay (local check during the story, not committed): `answer_saves_late(page, 2000)` added at the start of `test_review_apply_e2e.py` and `test_requests_editor_e2e.py` scenarios that save, the tests still pass; record the run in the story report.

## Constraints

- Files not to touch: product code; the other browser files.
- Dependencies not to add: none.
- Patterns to avoid: `time.sleep`; a fixed wait before a presence assertion; changing an expected value.
- Scope boundary: the guard test is US-0088.

## Definition of done

- [ ] RED evidence: for at least one rewritten wait per file, show the old line failing under an injected delay (for example `page.wait_for_timeout` shortened to 0 for that line) and the observation passing.
- [ ] Every existing test of the four files green; `make check` green; main stays green after the squash.
- [ ] Every remaining `wait_for_timeout(` in the four files carries `# pacing: <reason>`.
- [ ] Docs updated: none.
- [ ] Self review: full (tier 2), per wait: what it awaited, how it is observed now.
- [ ] One commit `US-0086: Fullscreen, website, review and request editor waits`, body `Spec: SPEC-0014` and BR-008, BR-009, BR-010.
