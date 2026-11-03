# Freshness check of generated template files: functional specification

> Id: SPEC-0011
> Nature: FEAT
> Depth: S
> Depth evidence: one observable behavior (a freshness check), one area (build tooling), no public contract change, no persisted data change
> Status: designed
> Generated on: 2026-11-03
> Project: existing
> From backlog: n/a
> Depends on: none
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary

Three template files are generated or copied from a source file. If someone edits a source and forgets to
regenerate, the copies drift and nothing stops the release. This increment adds a freshness check for the
three files and runs it in the quality gate.

## 2. Current State

### 2.1 What users can do today

- `make bootstrap-ei` regenerates the Euro-Information slides bootstrap from its reference deck. The tool
  has no check mode.
- `make sync-medical-css` copies the medical charter style into two reference decks. The tool has a
  `--check` option that prints `ok: <path>` or `DIVERGED: <path>` and a hint, and exits 1 on divergence.
- `make check` (lint, format check, type check, security scan, tests with coverage) runs neither tool. A
  test compares the medical copies; nothing compares the Euro-Information bootstrap.

### 2.2 Specs governing this area

None changes this area. SPEC-0001 FR-009 is not concerned.

### 2.3 What is verified today

A test fails when the medical copies diverge from their source. Nothing verifies the Euro-Information
bootstrap.

## 3. Scope

### 3.1 In scope

A `--check` mode for the Euro-Information generator, a common output format for both checks, a make target,
and its inclusion in the quality gate.

### 3.2 Out of scope, and why

- Other Euro-Information files that embed the same style (document and example decks): they have no
  generator, so no source of truth to compare with.
- Auto-regeneration during the check: the check never writes.

### 3.3 Constraints imposed by the context

None.

## 5. Usage scenarios

### SC-001: Checking before a release
**Actor:** Maintainer
**Flow:**
1. The maintainer runs `make check-generated` → one line per generated file, `fresh` or `stale` with the first differing line and the command to run.
**Postconditions:** no file was written.
**Exceptions:**
- EXC-001a: a file is stale → exit status 1.
- EXC-001b: a generated file is missing → line `missing`, exit status 1.
- EXC-001c: a source is missing → error, exit status 1.

### SC-002: The quality gate
**Actor:** Maintainer
**Flow:**
1. The maintainer runs `make check` → it also runs the freshness check and stops if a file is stale.

## 6. Functional requirements

### 6.1 New

#### FR-NEW-001 [EARS-E]: Euro-Information bootstrap check
> WHEN a maintainer runs `python tools/gen_ei_bootstrap.py --check` THE Tool SHALL compare the bootstrap file with what generation would write and report it.

- **Business rules:** the line is `templates/bootstrap/slides-ei-empty.html: fresh`, or `templates/bootstrap/slides-ei-empty.html: stale (first difference at line N); run: make bootstrap-ei`, or `templates/bootstrap/slides-ei-empty.html: missing; run: make bootstrap-ei`. N is the 1 based number of the first differing line; when one text is the start of the other, N is the number of lines of the shorter plus 1. A missing source prints `error: source not found: templates/reference/slides/euro-information.html` on the error output, nothing on the standard output. Exit status 0 only when fresh, 1 otherwise.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-002 [EARS-E]: Medical copies check
> WHEN a maintainer runs `python tools/sync_medical_css.py --check` THE Tool SHALL report, for each of the two reference decks, whether its style block equals that of the medical bootstrap.

- **Business rules:** lines `templates/reference/slides/medical.html: fresh` / `... : stale (first difference at line N); run: make sync-medical-css` / `... : missing; run: make sync-medical-css`, then the same for `templates/reference/slides/example-medical-complete.html`, in that order. N is the line number in the target file of the first line of its style block that differs from the source's (same rule for prefixes as FR-NEW-001). A missing source prints `error: source not found: templates/bootstrap/slides-medical-empty.html`. This output replaces the former `ok:` / `DIVERGED:` lines and trailing hint of `--check`. Without `--check` the tool keeps its present behavior and output (`ok:`, `updated:`, `skip (absent):`). Exit status 0 only when both are fresh, 1 otherwise.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-003 [EARS-E]: Gate
> WHEN a maintainer runs `make check-generated` THE Build SHALL run both checks, print their lines, and fail when either fails, and `make check` SHALL run `check-generated` as one of its steps.

- **Scenario:** SC-001, SC-002
- **Priority:** Must

#### FR-NEW-004 [EARS-UB]: No writing in check mode
> The Tool SHALL NOT write, create or delete any file when run with `--check`.

- **Scenario:** SC-001
- **Priority:** Must

## 8. Edge cases

| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Empty states | generated file missing | `missing; run: ...`, exit 1 | E2E-008 |
| Boundary values | difference on the last line / one text a prefix of the other | N per rule | E2E-004, E2E-005 |
| Dependency failures | source missing | error, nothing on standard output | E2E-007 |
| Partial operations | one medical copy stale, one fresh | one stale line, one fresh line | E2E-005 |

## 9. Acceptance tests (the contract)

### 9.1 Summary

| Test | Category | Requirements | Priority |
|---|---|---|---|
| E2E-001 | journey | FR-NEW-001 | Critical |
| E2E-002 | journey | FR-NEW-002 | Critical |
| E2E-003 | journey | FR-NEW-003 | Critical |
| E2E-004 | failure | FR-NEW-001, 004 | Critical |
| E2E-005 | failure | FR-NEW-002, 004 | Critical |
| E2E-006 | failure | FR-NEW-002, 003, 004 | High |
| E2E-007 | failure | FR-NEW-001 | High |
| E2E-008 | failure | FR-NEW-001 | High |
| E2E-009 | edge | FR-NEW-004 | High |
| E2E-010 | failure | FR-NEW-003 | Critical |
| E2E-011 | edge | FR-NEW-002 | Medium |

Coverage: happy 3, failure 6, edge 2 (11 tests). Happy to failure ratio 1:2 (beats 1:1).

### 9.2 New tests

#### E2E-001: Fresh Euro-Information bootstrap
- **Given** the repository files as committed
- **When** the maintainer runs `python tools/gen_ei_bootstrap.py --check`
- **Then** the output is exactly `templates/bootstrap/slides-ei-empty.html: fresh` and the exit status is 0
- **Priority:** Critical

#### E2E-002: Fresh medical copies
- **Given** the repository files as committed
- **When** the maintainer runs `python tools/sync_medical_css.py --check`
- **Then** the output is exactly the two lines `templates/reference/slides/medical.html: fresh` and `templates/reference/slides/example-medical-complete.html: fresh`, exit status 0
- **Priority:** Critical

#### E2E-003: Make target, all fresh
- **Given** the repository files as committed
- **When** the maintainer runs `make check-generated`
- **Then** the three `fresh` lines of E2E-001 and E2E-002 are printed and the exit status is 0
- **Priority:** Critical

#### E2E-004: Stale Euro-Information bootstrap
- **Given** line 120 of `templates/bootstrap/slides-ei-empty.html` changed (a word replaced)
- **When** the maintainer runs `python tools/gen_ei_bootstrap.py --check`
- **Then** the output is `templates/bootstrap/slides-ei-empty.html: stale (first difference at line 120); run: make bootstrap-ei`, exit status 1
- **And** the bootstrap file is byte for byte as it was before the run
- **And** with the last line of the bootstrap removed, N is the number of its remaining lines plus 1
- **Priority:** Critical

#### E2E-005: One stale medical copy
- **Given** the style block of `templates/reference/slides/medical.html` changed on the line that is line 40 of that file
- **When** the maintainer runs `python tools/sync_medical_css.py --check`
- **Then** the output is `templates/reference/slides/medical.html: stale (first difference at line 40); run: make sync-medical-css` then `templates/reference/slides/example-medical-complete.html: fresh`, exit status 1
- **And** neither file changed
- **Priority:** Critical

#### E2E-006: Both stale through make
- **Given** the style block changed in both medical copies, and the Euro-Information bootstrap fresh
- **When** the maintainer runs `make check-generated`
- **Then** the output holds the `fresh` line for the bootstrap and two `stale (first difference at line N); run: make sync-medical-css` lines, and the make exit status is not 0
- **And** no tracked file changed
- **Priority:** High

#### E2E-007: Euro-Information source missing
- **Given** `templates/reference/slides/euro-information.html` removed
- **When** the maintainer runs `python tools/gen_ei_bootstrap.py --check`
- **Then** the error output is `error: source not found: templates/reference/slides/euro-information.html`, the standard output is empty, the exit status is 1, and the bootstrap is unchanged
- **Priority:** High

#### E2E-008: Generated file missing
- **Given** `templates/bootstrap/slides-ei-empty.html` removed
- **When** the maintainer runs `python tools/gen_ei_bootstrap.py --check`
- **Then** the output is `templates/bootstrap/slides-ei-empty.html: missing; run: make bootstrap-ei`, exit status 1, and the file is not created
- **And** with `templates/reference/slides/medical.html` removed instead, `sync_medical_css.py --check` prints `templates/reference/slides/medical.html: missing; run: make sync-medical-css`, then the `fresh` line of the other copy, exit status 1
- **Priority:** High

#### E2E-009: Check mode never writes
- **Given** the repository with stale and missing generated files (as in E2E-004, E2E-005 and E2E-008) and the checksums of every file under `templates/` and `tools/` recorded
- **When** both tools are run with `--check`
- **Then** the checksums and the list of files are identical afterwards
- **Priority:** High

#### E2E-010: The quality gate includes the check
- **Given** a stale Euro-Information bootstrap
- **When** the maintainer runs `make check`
- **Then** the output contains the `stale` line of E2E-004 and the exit status is not 0; the same run on fresh files prints `templates/bootstrap/slides-ei-empty.html: fresh` among its steps
- **Priority:** Critical

#### E2E-011: Normal mode unchanged
- **Given** the medical copy of E2E-005 changed
- **When** the maintainer runs `python tools/sync_medical_css.py` without option
- **Then** it prints `updated: templates/reference/slides/medical.html` and `ok: templates/reference/slides/example-medical-complete.html`, rewrites the stale copy, exit status 0
- **Priority:** Medium

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, 002, 004 | E2E-001, 002 | E2E-004, 005, 006, 007, 008 | E2E-009, 011 |
| SC-002 | FR-NEW-003 | E2E-003 | E2E-010 | none |

Requirements to tests: FR-NEW-001 (001, 004, 007, 008); 002 (002, 005, 006, 011); 003 (003, 006, 010); 004 (004, 005, 006, 009).

## 12. Glossary

| Term | Definition | Context |
|---|---|---|
| Generated file | A file produced or copied from a source file by a tool | Build tooling |
| Fresh | Equal to what the tool would write | Build tooling |
| Stale | Different from what the tool would write | Build tooling |

## 13. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 0 | 0 | IMPLEMENTABLE (inline checklist) |

**Amendments applied:** none
**No implementation detail outside Section 14:** PASS (tool and make target names are the maintainer's commands)

## 14. Evidence appendix

### 14.1 Current State evidence

| Claim (Section 2) | Evidence |
|---|---|
| EI generator has no check mode | `tools/gen_ei_bootstrap.py:96-99` (only writes via `OUT.write_text`) |
| medical tool `--check` and its output | `tools/sync_medical_css.py:12,40-62` |
| `make check` does not call the tools | `Makefile:139`; targets `bootstrap-ei` and `sync-medical-css` at `Makefile:241-247` |
| medical copies compared by a test | `tests/test_medical_template.py` (named by the docstring of `tools/sync_medical_css.py:5-6`) |

Test command: `make test`; gate `make check`.

### 14.3 Design inputs

- `gen_ei_bootstrap.py` has no function returning the generated text: its `main` writes directly (`tools/gen_ei_bootstrap.py`); the check needs the text before writing. Detection signal: E2E-004.
- Tests for these tools run them as subprocesses on a copy of the repository files. Detection signal: E2E-004 to E2E-010 cannot be written otherwise.
- Documents to update: `AGENTS.md`, `.agent_docs/makefile.md`, `README.md`.
