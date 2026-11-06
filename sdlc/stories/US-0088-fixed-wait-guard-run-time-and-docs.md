# US-0088: Fixed wait guard, run time and documentation

> Spec: SPEC-0014 (sdlc/specs/SPEC-0014-lifecycle-test-reliability/)
> Nature: BUG
> Priority: P2
> Depends on: US-0082, US-0083, US-0085, US-0086, US-0087
> min_tier: 2
> Files touched: 3
> Closes spec: yes

## Objective

The 68 fixed waits spread by copy from one file to the next (E14). This story adds a guard that fails the gate on
any new unjustified fixed wait in a browser test, checks that the default run stays within its time budget after
all SPEC-0014 changes, finishes the documentation index, and runs the spec's full acceptance set.

## Requirements covered

- SPEC-0014/BR-009: The browser test suite SHALL NOT assert that an asynchronous result is present after a fixed delay without the observation of BR-008.
- SPEC-0014/BR-008 (partial: the audit that no browser file reads an asynchronous result without observation): The browser test suite SHALL assert every asynchronous result by observing it repeatedly, at most 100 ms apart, until it holds or 10 seconds have passed since the action that triggers it.

## Independent Test

`make test ARGS='-k no_fixed_waits'` (part of `make check`): the guard passes on the tree; a throwaway copy of a
browser test file written under `tmp_path` with an added `page.wait_for_timeout(500)` line and no comment makes the
guard's checking function report that file and line (red before this story: the guard does not exist).

## Design excerpt

### Decisions
- DEC-014 (SPEC-0014): "A guard test `tests/test_no_fixed_waits.py` reads every `tests/test_*_e2e.py` and fails on each `wait_for_timeout(` line that does not carry a trailing comment `# pacing: <reason>` (a spacing between two user actions, not followed by an assertion of its result); the settle delay lives only in `tests/browser_wait.py`."
- DEC-009 (SPEC-0014): the literal value checks BT-003, BT-016, BT-017 are `slow`; the default run carries short counterparts so the gate stays under 330 s.

### Contracts
```python
# tests/test_no_fixed_waits.py (new)
PACING_COMMENT = re.compile(r"#\s*pacing:\s*\S")

def unjustified_waits(path: Path) -> list[int]: ...   # line numbers of wait_for_timeout( without PACING_COMMENT
```
The guard parametrizes over `sorted((REPO / "tests").glob("test_*_e2e.py"))` and asserts
`unjustified_waits(path) == []`, the message naming the file and the lines.

### Paths
| Path | Action |
|---|---|
| `tests/test_no_fixed_waits.py` | create |
| `.agent_docs/testing.md` | modify: consolidate the SPEC-0014 sections (time limits, stdio session, browser waits, pacing rule, port range foreign tests), files table rows for the new modules, keep under about 200 lines |
| `AGENTS.md` | modify: test commands block: `make test ARGS='-m slow'` also runs the literal time limit and stdio bound checks; one line on `tests/browser_wait.py` and the pacing rule |

### Existing patterns
- Source scanning tests: `tests/test_deck_tools_surface.py` `_ids_by_test` (reads test sources with `ast`).
- Documentation pattern: `.agent_docs/testing.md` dated sections, files table.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0014/BT-022: Default run time
- Level / Driver / Location: functional, measurement (protects the gate's cost); `make check` with `ARGS` not available on `check`, so the measure is `make test ARGS='-p no:cacheprovider -q --durations=8'` on an unloaded machine, then `make check`; reported in the story's closing record
- When `make check` runs on an unloaded machine
- Then the test step lasts no more than 330 seconds (today 279.55 s, E22) and every test passes
- If it lasts more: report the durations table and stop (a story regressed the budget); do not raise the limit.

### Guard tests of this story (not spec ids)
- `test_browser_files_have_no_unjustified_fixed_wait[<file>]` for each `tests/test_*_e2e.py`: green on the tree.
- `test_the_guard_reports_an_uncommented_wait`: a file under `tmp_path` with `page.wait_for_timeout(500)` on line 3 and `page.wait_for_timeout(1000)  # pacing: between two keys` on line 4 gives `[3]`.

### Spec converge (this story closes SPEC-0014)
Run and record: `make check` (default set: BT-001, BT-002, BT-004, BT-010 to BT-015, BT-018, BT-020, BT-021, the
short counterparts), then `make test ARGS='-m slow -k "suite_time_limit or stdio_support"'` (BT-003, BT-016,
BT-017 literal values), and BT-022 above.

## Constraints

- Files not to touch: product code; the browser test files (if the guard finds an uncommented wait, the story that owned the file regressed: fix the comment or the wait here only if the wait is pacing, else report).
- Dependencies not to add: none.
- Patterns to avoid: an allow list of files or line numbers in the guard.
- Scope boundary: nothing new beyond the guard and the documentation.

## Definition of done

- [ ] RED evidence recorded for the guard (`test_the_guard_reports_an_uncommented_wait` before `unjustified_waits` exists).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: every browser test file passes; `rg -n 'wait_for_timeout\(' tests | rg -v '# pacing:' | rg -v browser_wait.py` prints nothing.
- [ ] Closes spec only: the spec's full acceptance set green (BT-001, BT-002, BT-003, BT-004, BT-010 to BT-018, BT-020 to BT-022), and every requirement of SPEC-0014 (BR-001 to BR-016) cited by at least one story with status done or landed.
- [ ] Docs updated: `.agent_docs/testing.md`, `AGENTS.md`.
- [ ] Self review: full (tier 2).
- [ ] One commit `US-0088: Fixed wait guard, run time and documentation`, body `Spec: SPEC-0014` and BR-008, BR-009.
