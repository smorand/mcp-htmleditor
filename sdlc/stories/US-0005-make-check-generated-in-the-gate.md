# US-0005: `make check-generated` in the quality gate and docs

> Spec: SPEC-0011 (sdlc/specs/SPEC-0011-generated-files-freshness/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0004
> min_tier: 2
> Files touched: 5
> Closes spec: yes

## Objective

Add the `check-generated` make target that runs both freshness checks (always both, even when the first fails) and make it the first step of `make check`. Prove that check mode writes nothing across both tools, and document the new command.

## Requirements covered

- SPEC-0011/FR-NEW-003: WHEN a maintainer runs `make check-generated` THE Build SHALL run both checks, print their lines, and fail when either fails, and `make check` SHALL run `check-generated` as one of its steps.
- SPEC-0011/FR-NEW-004: The Tool SHALL NOT write, create or delete any file when run with `--check`. (partial: the combined checksum proof over `templates/` and `tools/` with stale and missing files, and the make path; the per tool byte checks are in US-0004)

## Independent Test

Command: `make check-generated` on committed files. Observable: three lines on the standard output and the exit status. Expected: `templates/bootstrap/slides-ei-empty.html: fresh`, `templates/reference/slides/medical.html: fresh`, `templates/reference/slides/example-medical-complete.html: fresh`, exit 0. Independent assertion (in the tests): after editing both medical copies in a temporary copy, the make exit status is not 0, all three lines are present, and the sha256 of every file is unchanged (checksums computed by the test before the run, not by the tools).

## Design excerpt

### Decisions
- DEC-005 (SPEC-0011): `check-generated` runs both tools regardless of the first failure and is the first prerequisite of `check`. Rationale: E2E-006 needs all lines; first position gives fail fast and avoids test-cov recursion in E2E-010. Alternative rejected: last step (slow feedback, recursive test).
- DEC-004 (SPEC-0011): tests copy tools and templates into `tmp_path` and run subprocesses.

### Data model
None.

### Contracts
Makefile (the recipe must run both tools and exit non zero if either failed):
```make
## check-generated: Verify generated template files are fresh (writes nothing)
check-generated:
	@rc=0; uv run python tools/gen_ei_bootstrap.py --check || rc=1; uv run python tools/sync_medical_css.py --check || rc=1; exit $$rc
```
and `check: check-generated lint format-check typecheck security test-cov` (currently `check: lint format-check typecheck security test-cov`, `Makefile:139`); `check-generated` is added to `.PHONY` (`Makefile:4`). Place the target next to `bootstrap-ei` and `sync-medical-css` (`Makefile:241-247`) and update the `## check:` comment to mention the freshness step. Tool output lines are the ones defined by US-0004: `<path>: fresh`, `<path>: stale (first difference at line N); run: make <target>`, `<path>: missing; run: make <target>`.

Test driver for make tests (DEC-004): copy `tools/`, the 5 template files, `Makefile` and `pyproject.toml` into `tmp_path`, run `make check-generated` with env `UV_NO_SYNC=1` and `UV_PROJECT_ENVIRONMENT=<repo .venv>` so uv reuses the existing environment, `subprocess.run(..., cwd=tmp_path, timeout=120)`.

### Paths
| Path | Action |
|---|---|
| Makefile | modify |
| tests/test_generated_freshness.py | modify (file created by US-0004) |
| AGENTS.md | modify: commands list (lines 20-21) add `make check-generated`; the gate line (line 15) mentions the new step |
| README.md | modify: bootstrap section near lines 260-269, document `--check` / `make check-generated` |
| .agent_docs/makefile.md | modify: Project specific table (line 91) add `check-generated`, and the `check` row |

### Existing patterns
- `Makefile` targets `bootstrap-ei`, `sync-medical-css` (`:241-247`) and `check` (`:139`).
- Test harness and fixture from `tests/test_generated_freshness.py` (US-0004). Test conventions: `.agent_docs/testing.md`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0011/E2E-003: Make target, all fresh
- Level: functional e2e; Driver: `make check-generated` on the copy, fresh; Location: tests/test_generated_freshness.py
- **Given** the repository files as committed
- **When** the maintainer runs `make check-generated`
- **Then** the three `fresh` lines of E2E-001 and E2E-002 are printed and the exit status is 0

### SPEC-0011/E2E-006: Both stale through make
- Level: functional e2e; Driver: both medical copies edited, `make check-generated`, assert checksums; Location: tests/test_generated_freshness.py
- **Given** the style block changed in both medical copies, and the Euro-Information bootstrap fresh
- **When** the maintainer runs `make check-generated`
- **Then** the output holds the `fresh` line for the bootstrap and two `stale (first difference at line N); run: make sync-medical-css` lines, and the make exit status is not 0
- **And** no tracked file changed

### SPEC-0011/E2E-009: Check mode never writes
- Level: functional e2e; Driver: sha256 of every file under `templates/` and `tools/` and the file list, before and after, with stale and missing files; Location: tests/test_generated_freshness.py
- **Given** the repository with stale and missing generated files (as in E2E-004, E2E-005 and E2E-008) and the checksums of every file under `templates/` and `tools/` recorded
- **When** both tools are run with `--check`
- **Then** the checksums and the list of files are identical afterwards

### SPEC-0011/E2E-010: The quality gate includes the check
- Level: functional e2e; Driver: `make check` on a stale copy; `make -n check` on a fresh copy; Location: tests/test_generated_freshness.py
- **Given** a stale Euro-Information bootstrap
- **When** the maintainer runs `make check`
- **Then** the output contains the `stale` line of E2E-004 and the exit status is not 0; the same run on fresh files prints `templates/bootstrap/slides-ei-empty.html: fresh` among its steps
- Design note (documented deviation, recursion): the stale half runs the real `make check`, which stops at `check-generated` (first prerequisite) before `test-cov` starts. The fresh half is verified by `make -n check`, asserting `check-generated` is listed before `lint`; executing a fresh full gate inside pytest would recurse into `test-cov`. The fresh lines themselves are covered by E2E-003.

## Constraints

- Files not to touch: `tools/*` (done in US-0004), `tests/test_medical_template.py`, `src/`, `templates/`, `.agent_docs/testing.md` (optional note only if a new pattern needs recording).
- Dependencies not to add: none.
- Patterns to avoid: making `check-generated` stop after the first failing tool (E2E-006 needs all lines); putting it last in `check`; a test that executes a fresh full `make check`.
- Scope boundary: nothing else; no auto regeneration, no check of other Euro-Information files (out of scope in the spec).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: every US-0004 test, `make bootstrap-ei` and `make sync-medical-css` behavior, `tests/test_medical_template.py`.
- [ ] Docs updated: `AGENTS.md` (commands list and gate line), `README.md` (bootstrap section), `.agent_docs/makefile.md` (Project specific table and `check` row).
- [ ] Self review: full at tier 2.
- [ ] The spec's full acceptance set green (E2E-001 to E2E-011), and every requirement of SPEC-0011 (FR-NEW-001 to FR-NEW-004) cited by at least one story with status done or landed.
- [ ] One commit `US-0005: make check-generated in the quality gate and docs`, body `Spec: SPEC-0011` and `FR-NEW-003, FR-NEW-004`.
