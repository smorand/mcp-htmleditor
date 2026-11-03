# US-0004: `--check` mode for both generators

> Spec: SPEC-0011 (sdlc/specs/SPEC-0011-generated-files-freshness/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Give `tools/gen_ei_bootstrap.py` a `--check` mode and rewrite the `--check` output of `tools/sync_medical_css.py`, both through one shared pure helper `tools/freshness.py` so the line format and the first difference rule exist once. Check mode never writes, creates or deletes a file.

## Requirements covered

- SPEC-0011/FR-NEW-001: WHEN a maintainer runs `python tools/gen_ei_bootstrap.py --check` THE Tool SHALL compare the bootstrap file with what generation would write and report it. Business rules: the line is `templates/bootstrap/slides-ei-empty.html: fresh`, or `templates/bootstrap/slides-ei-empty.html: stale (first difference at line N); run: make bootstrap-ei`, or `templates/bootstrap/slides-ei-empty.html: missing; run: make bootstrap-ei`. N is the 1 based number of the first differing line; when one text is the start of the other, N is the number of lines of the shorter plus 1. A missing source prints `error: source not found: templates/reference/slides/euro-information.html` on the error output, nothing on the standard output. Exit status 0 only when fresh, 1 otherwise.
- SPEC-0011/FR-NEW-002: WHEN a maintainer runs `python tools/sync_medical_css.py --check` THE Tool SHALL report, for each of the two reference decks, whether its style block equals that of the medical bootstrap. Business rules: lines `templates/reference/slides/medical.html: fresh` / `... : stale (first difference at line N); run: make sync-medical-css` / `... : missing; run: make sync-medical-css`, then the same for `templates/reference/slides/example-medical-complete.html`, in that order. N is the line number in the target file of the first line of its style block that differs from the source's (same rule for prefixes as FR-NEW-001). A missing source prints `error: source not found: templates/bootstrap/slides-medical-empty.html`. This output replaces the former `ok:` / `DIVERGED:` lines and trailing hint of `--check`. Without `--check` the tool keeps its present behavior and output (`ok:`, `updated:`, `skip (absent):`). Exit status 0 only when both are fresh, 1 otherwise.
- SPEC-0011/FR-NEW-004: The Tool SHALL NOT write, create or delete any file when run with `--check`. (partial: per tool, asserted by the byte checks of E2E-004, E2E-005, E2E-007, E2E-008; the combined checksum test E2E-009 is in US-0005)

## Independent Test

Command: `make test` (the new file `tests/test_generated_freshness.py` is part of it; never run it ad hoc). Observable: the subprocess output of each tool run on a copy of the repository files in a temporary directory. Expected: on committed files `python tools/gen_ei_bootstrap.py --check` prints exactly `templates/bootstrap/slides-ei-empty.html: fresh` (exit 0) and `python tools/sync_medical_css.py --check` prints the two `fresh` lines (exit 0); with line 120 of the bootstrap copy edited it prints `... stale (first difference at line 120); run: make bootstrap-ei` (exit 1) and the copy is byte for byte unchanged. The staleness is produced by editing a copy, so the assertion is on the independent line number of the edit, not on the tool's own output.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0011): shared pure helper `tools/freshness.py`. Rationale: one line format and one first-difference rule for both tools. Alternatives rejected: duplicate code in each tool; a new aggregate script.
- DEC-002 (SPEC-0011): extract `generate(src) -> str` from EI `main`, check compares it before any write. Rationale: the text must exist before writing.
- DEC-003 (SPEC-0011): medical `--check` branch replaced, line offset from the style block start in the target. Rationale: the spec defines N in target file coordinates (not the line within the block).
- DEC-004 (SPEC-0011): tests copy tools and templates into `tmp_path` and run subprocesses. Rationale: stale files can be created without touching the repository.

### Data model
None (no persisted data). Value: a result line `<relpath>: fresh | stale (first difference at line N); run: make <target> | missing; run: make <target>`.

### Contracts
`tools/freshness.py`:
```python
def first_difference_line(expected: str, actual: str, offset: int = 0) -> int:
    """1-based line of the first differing line, +offset; prefix case: len(shorter lines)+1+offset."""
def report_line(relpath: str, expected: str, actual: str | None, make_target: str, offset: int = 0) -> tuple[str, bool]:
    """Return (line, is_fresh). actual None -> '<relpath>: missing; run: make <target>'."""
def source_missing_error(relpath: str) -> str:   # 'error: source not found: <relpath>'
```
Compare with `str.splitlines(keepends=True)`; if all common lines are equal and the lengths differ, N = min(len)+1 (a text differing only by its trailing newline therefore counts as differing, N = shorter's line count + 1).

`tools/gen_ei_bootstrap.py`: extract `def generate(src: str) -> str` from `main` (the chevron match, slide cut, replacements; existing `main` body lines 40 to 90). Normal mode behavior unchanged, still prints `ecrit ...`. New `main(argv: list[str]) -> int` with `--check`:
- source absent: stderr `error: source not found: templates/reference/slides/euro-information.html`, stdout empty, return 1 (checked before reading; only in `--check`; normal mode keeps its present behavior).
- else prints `report_line("templates/bootstrap/slides-ei-empty.html", generate(src), <OUT text or None>, "bootstrap-ei")`; return 0 iff fresh. Never calls `write_text`. The entry point becomes `raise SystemExit(main(sys.argv[1:]))`.

`tools/sync_medical_css.py` `--check` branch (normal branch untouched): for each target in order: absent -> `<rel>: missing; run: make sync-medical-css`; else `report_line(rel, reference, current_block, "sync-medical-css", offset=line_of_block_start - 1)` where `line_of_block_start = text[:match.start()].count("\n") + 1`. Add `style_block_span(path) -> tuple[str, int]` returning the block and its match start; `style_block(path) -> str` keeps its signature. Missing source: stderr `error: source not found: templates/bootstrap/slides-medical-empty.html`, stdout empty, return 1. The `ok:` / `DIVERGED:` / trailing hint lines disappear from `--check` only. Without `--check` it prints `ok:`, `updated:`, `skip (absent):` as today (`tools/sync_medical_css.py:52-62`).

### Paths
| Path | Action |
|---|---|
| tools/freshness.py | create |
| tools/gen_ei_bootstrap.py | modify |
| tools/sync_medical_css.py | modify |
| tests/test_generated_freshness.py | create |

### Existing patterns
- `tools/sync_medical_css.py` (`_STYLE_RE`, `style_block`, `TARGETS`, `REPO`); `tools/gen_ei_bootstrap.py` (`REF`, `OUT`, `ROOT`).
- Tools are stdlib scripts that print to stdout by design; `python tools/x.py` puts `tools/` on `sys.path[0]`, so `import freshness` works. No logging, no Settings.
- Test conventions: `.agent_docs/testing.md`; non-browser tests, no `needs_chromium` marker.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Common driver (DEC-004): a fixture copies `tools/` and the 5 template files (`templates/bootstrap/slides-ei-empty.html`, `templates/reference/slides/euro-information.html`, `templates/bootstrap/slides-medical-empty.html`, `templates/reference/slides/medical.html`, `templates/reference/slides/example-medical-complete.html`) into `tmp_path` with the same relative layout, and runs `sys.executable tools/<tool> --check` via `subprocess.run(..., cwd=tmp_path, timeout=60)`. Stale data is produced by editing the copies.

### SPEC-0011/E2E-001: Fresh Euro-Information bootstrap
- Level: functional e2e; Driver: subprocess `gen_ei_bootstrap.py --check` on the copy; Location: tests/test_generated_freshness.py
- **Given** the repository files as committed
- **When** the maintainer runs `python tools/gen_ei_bootstrap.py --check`
- **Then** the output is exactly `templates/bootstrap/slides-ei-empty.html: fresh` and the exit status is 0

### SPEC-0011/E2E-002: Fresh medical copies
- Level: functional e2e; Driver: subprocess `sync_medical_css.py --check`; Location: tests/test_generated_freshness.py
- **Given** the repository files as committed
- **When** the maintainer runs `python tools/sync_medical_css.py --check`
- **Then** the output is exactly the two lines `templates/reference/slides/medical.html: fresh` and `templates/reference/slides/example-medical-complete.html: fresh`, exit status 0

### SPEC-0011/E2E-004: Stale Euro-Information bootstrap
- Level: functional e2e; Driver: edit line 120, truncate last line, assert bytes unchanged; Location: tests/test_generated_freshness.py
- **Given** line 120 of `templates/bootstrap/slides-ei-empty.html` changed (a word replaced)
- **When** the maintainer runs `python tools/gen_ei_bootstrap.py --check`
- **Then** the output is `templates/bootstrap/slides-ei-empty.html: stale (first difference at line 120); run: make bootstrap-ei`, exit status 1
- **And** the bootstrap file is byte for byte as it was before the run
- **And** with the last line of the bootstrap removed, N is the number of its remaining lines plus 1

### SPEC-0011/E2E-005: One stale medical copy
- Level: functional e2e; Driver: edit the style line that is file line 40 of medical.html; Location: tests/test_generated_freshness.py
- **Given** the style block of `templates/reference/slides/medical.html` changed on the line that is line 40 of that file
- **When** the maintainer runs `python tools/sync_medical_css.py --check`
- **Then** the output is `templates/reference/slides/medical.html: stale (first difference at line 40); run: make sync-medical-css` then `templates/reference/slides/example-medical-complete.html: fresh`, exit status 1
- **And** neither file changed

### SPEC-0011/E2E-007: Euro-Information source missing
- Level: functional e2e; Driver: remove the EI source from the copy; Location: tests/test_generated_freshness.py
- **Given** `templates/reference/slides/euro-information.html` removed
- **When** the maintainer runs `python tools/gen_ei_bootstrap.py --check`
- **Then** the error output is `error: source not found: templates/reference/slides/euro-information.html`, the standard output is empty, the exit status is 1, and the bootstrap is unchanged

### SPEC-0011/E2E-008: Generated file missing
- Level: functional e2e; Driver: remove the bootstrap, then medical.html; Location: tests/test_generated_freshness.py
- **Given** `templates/bootstrap/slides-ei-empty.html` removed
- **When** the maintainer runs `python tools/gen_ei_bootstrap.py --check`
- **Then** the output is `templates/bootstrap/slides-ei-empty.html: missing; run: make bootstrap-ei`, exit status 1, and the file is not created
- **And** with `templates/reference/slides/medical.html` removed instead, `sync_medical_css.py --check` prints `templates/reference/slides/medical.html: missing; run: make sync-medical-css`, then the `fresh` line of the other copy, exit status 1

### SPEC-0011/E2E-011: Normal mode unchanged
- Level: functional e2e; Driver: run `sync_medical_css.py` without option on the stale copy; Location: tests/test_generated_freshness.py
- **Given** the medical copy of E2E-005 changed
- **When** the maintainer runs `python tools/sync_medical_css.py` without option
- **Then** it prints `updated: templates/reference/slides/medical.html` and `ok: templates/reference/slides/example-medical-complete.html`, rewrites the stale copy, exit status 0

## Constraints

- Files not to touch: `tests/test_medical_template.py`, `tests/test_skill_content.py`, `Makefile`, docs, everything under `src/` and `templates/`.
- Dependencies not to add: none (stdlib only).
- Patterns to avoid: any write path reachable in `--check` (no temp file, no `write_text`, no `mkdir`); duplicating the line format outside `tools/freshness.py`; changing the bytes `generate()` produces (E2E-001 compares the committed bootstrap with it).
- Scope boundary: the `check-generated` make target, the `check` prerequisite, the combined no write checksum test (E2E-009) and all docs belong to US-0005.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: normal mode output of both tools unchanged (E2E-011); `tests/test_medical_template.py` and `tests/test_skill_content.py` pass unmodified; `ruff` accepts `tools/` and `tests/`.
- [ ] Docs updated: none in this story (AGENTS.md, README.md, `.agent_docs/makefile.md` are updated by US-0005).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0004: --check mode for both generators`, body `Spec: SPEC-0011` and `FR-NEW-001, FR-NEW-002, FR-NEW-004`.
