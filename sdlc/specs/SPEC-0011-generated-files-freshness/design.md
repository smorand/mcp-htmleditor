# SPEC-0011: Freshness check of generated template files, design

> Spec: sdlc/specs/SPEC-0011-generated-files-freshness/spec.md
> Nature: FEAT / Depth: S / Security: n/a / Designed on: 2026-11-03 / Target tier: 2 (default)

## 1. Stack and skills

Existing stack, unchanged (pyproject.toml): Python >= 3.13 (`pyproject.toml:target-version py313`), uv, hatchling, Click >= 8.0 (CLI of the product, a documented deviation from the Typer rule, kept), FastMCP, pytest + pytest-cov (fail under 80), mypy strict (covers `src/` only, Makefile `typecheck`), ruff (`src = ["src","tests","tools"]`, pyproject.toml:57), bandit on `src/`.
Rules applied: `make` is the only entry point; no new dependency; the tools are stdlib scripts under `tools/` (no Settings, no tracing: they are build scripts outside the MCP process, ruff already relaxes rules for `tools/**`, pyproject.toml:124); the tools print to stdout by design (CLI output, never the MCP process); `%` logging not applicable (no logging).

## 2. Approaches

**Chosen: pure helper module `tools/freshness.py` + `--check` in each tool.** Each tool builds its expected text in memory, the helper compares and formats the line. One format in one place, no write path in check mode. Pros: zero duplication, trivially unit-checkable. Cons: `tools/` gets a module imported by sibling scripts (works because `python tools/x.py` puts `tools/` on `sys.path[0]`). Scope: 3 tool files.

Rejected: (a) a pytest test comparing the bootstrap (no output format, not runnable standalone, not a make step). (b) A new `tools/check_generated.py` that imports both tools: needs both tools importable as packages, duplicates their path constants, and the spec requires `--check` on each tool. (c) Run each tool then `git diff --exit-code`: writes files, violates FR-NEW-004.

## 3. Architecture

```
make check-generated
  -> uv run python tools/gen_ei_bootstrap.py --check
  -> uv run python tools/sync_medical_css.py --check
tool --check: build expected text (no write) -> freshness.report_line(...) -> print -> exit code
```
`make check` gets `check-generated` as its first prerequisite (fail fast, see DEC-005).

## 4. Data model

None (no persisted data). Value: a result line `<relpath>: fresh | stale (first difference at line N); run: make <target> | missing; run: make <target>`.

## 5. Contracts and interfaces

`tools/freshness.py`:
```python
def first_difference_line(expected: str, actual: str, offset: int = 0) -> int:
    """1-based line of the first differing line, +offset; prefix case: len(shorter lines)+1+offset."""
def report_line(relpath: str, expected: str, actual: str | None, make_target: str, offset: int = 0) -> tuple[str, bool]:
    """Return (line, is_fresh). actual None -> '<relpath>: missing; run: make <target>'."""
def source_missing_error(relpath: str) -> str:   # 'error: source not found: <relpath>'
```
Compare with `str.splitlines()`; if all common lines equal and lengths differ, N = min(len)+1 (a text ending only in a different trailing newline counts as differing: compared on `splitlines(keepends=True)` so it yields the shorter's line count + 1).

`tools/gen_ei_bootstrap.py`: extract `def generate(src: str) -> str` from `main` (the chevron match, slide cut, replacements, existing lines 52-90 logic; behavior of normal mode unchanged, still prints `ecrit ...`). New `main(argv: list[str]) -> int` with `--check`:
- source absent: stderr `error: source not found: templates/reference/slides/euro-information.html`, stdout empty, return 1 (checked before reading; this also applies in normal mode only for `--check`, normal mode keeps its present behavior).
- else prints `report_line("templates/bootstrap/slides-ei-empty.html", generate(src), OUT text or None, "bootstrap-ei")`; return 0 iff fresh. Never calls `write_text`.

`tools/sync_medical_css.py` `--check` branch (normal branch untouched): for each target in order: absent -> `missing; run: make sync-medical-css`; else `report_line(rel, reference, current_block, "sync-medical-css", offset=line_of_block_start - 1)` where `line_of_block_start = text[:match.start()].count("\n") + 1` (needs the match start: add `style_block_span(path) -> tuple[str, int]`, `style_block` keeps its signature). Missing source: stderr `error: source not found: templates/bootstrap/slides-medical-empty.html`, return 1. The `ok:`/`DIVERGED:`/hint lines disappear from `--check` only. Non `--check` mode prints `ok:`, `updated:`, `skip (absent):` as today (`tools/sync_medical_css.py:52-62`).

Makefile:
```make
## check-generated: Verify generated template files are fresh (writes nothing)
check-generated:
	@uv run python tools/gen_ei_bootstrap.py --check
	@uv run python tools/sync_medical_css.py --check
```
Both commands must run even if the first fails (E2E-006 expects all three lines): use `@rc=0; uv run python tools/gen_ei_bootstrap.py --check || rc=1; uv run python tools/sync_medical_css.py --check || rc=1; exit $$rc`. `check: check-generated lint format-check typecheck security test-cov`; add `check-generated` to `.PHONY`.

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| tools/freshness.py | create | DEC-001 | STORY-A |
| tools/gen_ei_bootstrap.py | modify | DEC-002 | STORY-A |
| tools/sync_medical_css.py | modify | DEC-003 | STORY-A |
| tests/test_generated_freshness.py | create (A), modify (B) | DEC-004 | STORY-A, STORY-B |
| Makefile | modify | DEC-005 | STORY-B |
| AGENTS.md | modify | spec 14.3 | STORY-B |
| README.md | modify | spec 14.3 | STORY-B |
| .agent_docs/makefile.md | modify | spec 14.3 | STORY-B |

Affected existing tests: `tests/test_medical_template.py` keep (byte comparison of the CSS, independent of tool output; it does not call the tool, grep shows no `tools` reference). `tests/test_skill_content.py` keep. Docs: AGENTS.md (commands list line 20-21, add `make check-generated`; gate line 15 mentions the new step), README.md (bootstrap section near lines 260-269), `.agent_docs/makefile.md` (Project specific table, line 91, and the `check` row), `.agent_docs/testing.md` optional note on the tools test pattern.

## 7. Compatibility and risks

- Normal-mode output of both tools unchanged (E2E-011). `--check` output of medical changes by spec.
- Risk: `generate()` refactor alters generated bytes. Mitigation: E2E-001 compares the committed bootstrap to `generate()` output; any drift fails.
- Risk: `make check` recursion if a test ran `make check`. Mitigation: DEC-005 fail fast and tests use `make check-generated` plus `make -n check`.
- Risk: line endings; files read with `encoding="utf-8"` and compared as read; same as the tools' writers.
- Failure mode: if the bootstrap is stale only by trailing newline, N = lines+1 (documented in the helper).

## 9. Test strategy

All in `tests/test_generated_freshness.py`, level functional e2e: a fixture copies `tools/` and the 5 template files into `tmp_path` (same relative layout, so `ROOT = parents[1]` of the copied tool resolves inside the copy), runs `sys.executable tools/<tool> --check` via `subprocess.run(..., timeout=60)` with `cwd=tmp_path`. Make tests copy the Makefile and pyproject.toml too and run `make check-generated` with env `UV_NO_SYNC=1` and `UV_PROJECT_ENVIRONMENT=<repo .venv>` so uv reuses the existing environment. Test data is derived by editing copied files (no inline fixtures). No browser, so no needs_chromium.

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| SPEC-0011/E2E-001 | functional e2e | subprocess gen_ei --check on copy | tests/test_generated_freshness.py | STORY-A |
| SPEC-0011/E2E-002 | functional e2e | subprocess sync_medical --check | same | STORY-A |
| SPEC-0011/E2E-004 | functional e2e | edit line 120, truncate last line, assert bytes unchanged | same | STORY-A |
| SPEC-0011/E2E-005 | functional e2e | edit style line that is file line 40 of medical.html | same | STORY-A |
| SPEC-0011/E2E-007 | functional e2e | remove EI source | same | STORY-A |
| SPEC-0011/E2E-008 | functional e2e | remove bootstrap, then medical.html | same | STORY-A |
| SPEC-0011/E2E-011 | functional e2e | run without option on stale copy | same | STORY-A |
| SPEC-0011/E2E-003 | functional e2e | `make check-generated` on copy, fresh | same | STORY-B |
| SPEC-0011/E2E-006 | functional e2e | both medical stale via make, `git status` free: assert checksums | same | STORY-B |
| SPEC-0011/E2E-009 | functional e2e | sha256 of every file under templates/ and tools/ before/after on stale+missing | same | STORY-B |
| SPEC-0011/E2E-010 | functional e2e | stale: `make check` stops at the stale line, exit != 0 (check-generated runs first so test-cov never starts); fresh: `make -n check` lists `check-generated` before `lint` (running a fresh `make check` inside pytest would recurse into test-cov) | same | STORY-B |

Note on E2E-010 fresh half: verified by dry run, not by executing the full gate; stated deviation for the recursion reason above. Fresh-file lines themselves are covered by E2E-003.

## 10. Decisions log

- **DEC-001:** shared pure helper `tools/freshness.py`. **Obliged by:** SPEC-0011/FR-NEW-001, FR-NEW-002. **Rationale:** one line format and one first-difference rule for both tools. **Alternatives considered:** duplicate code in each tool (rejected: zero duplication rule); new aggregate script (rejected, see section 2). **Source:** design. **Evidence:** tools/gen_ei_bootstrap.py:96-99, tools/sync_medical_css.py:40-62.
- **DEC-002:** extract `generate(src) -> str` from EI `main`, check compares it before any write. **Obliged by:** SPEC-0011/FR-NEW-001, FR-NEW-004. **Rationale:** the text must exist before writing. **Alternatives considered:** run generation to a temp file (rejected: writes). **Source:** spec 14.3. **Evidence:** tools/gen_ei_bootstrap.py:52-96.
- **DEC-003:** medical `--check` branch replaced, line offset from the style block start in the target. **Obliged by:** SPEC-0011/FR-NEW-002. **Rationale:** spec defines N in target file coordinates. **Alternatives considered:** line within the block (rejected: contradicts E2E-005). **Source:** spec constraint. **Evidence:** tools/sync_medical_css.py:34-46.
- **DEC-004:** tests copy tools and templates into tmp_path and run subprocesses. **Obliged by:** SPEC-0011/FR-NEW-004. **Rationale:** stale files can be created without touching the repo; spec 14.3 demands it. **Alternatives considered:** import tool modules and monkeypatch paths (rejected: not what the maintainer runs). **Source:** spec 14.3. **Evidence:** tests/test_medical_template.py has no tool invocation.
- **DEC-005:** `check-generated` runs both tools regardless of the first failure and is the first prerequisite of `check`. **Obliged by:** SPEC-0011/FR-NEW-003. **Rationale:** E2E-006 needs all lines; first position gives fail fast and avoids test-cov recursion in E2E-010. **Alternatives considered:** last step (rejected: slow feedback, recursive test). **Source:** design. **Evidence:** Makefile:139.

## 11. Stories

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| STORY-A | `--check` mode for both generators | P1 | FR-NEW-001, FR-NEW-002, FR-NEW-004 | main | 2 | no |
| STORY-B | `make check-generated` in the quality gate and docs | P1 | FR-NEW-003, FR-NEW-004 | STORY-A | 2 | yes |

Slicing note: 11 tests over the minimal 2 stories (7 + 4); a third story would fall below the 5 test floor and a split by tool would leave the shared helper untestable alone.
