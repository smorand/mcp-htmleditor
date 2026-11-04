# US-0068: Resync the Euro-Information reference deck with its generated bootstrap

> Spec: SPEC-0011 (sdlc/specs/SPEC-0011-generated-files-freshness/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 2
> Closes spec: no

## Objective

The committed `templates/bootstrap/slides-ei-empty.html` is not what `tools/gen_ei_bootstrap.py` produces from `templates/reference/slides/euro-information.html`: it carries 30 more lines (the `arch-lane`, `arch-col` and `arch-edge-badge` rules, bootstrap lines 205 to 234) that were added to the bootstrap by hand. SPEC-0011 E2E-001 requires the committed bootstrap to be fresh, so the reference (the source of truth) takes the missing rules and generation reproduces the committed file byte for byte. Inserted by `/sdlc-implement` (Section 6 drift) while implementing US-0004; it runs before US-0004.

## Requirements covered

- SPEC-0011/FR-NEW-001 (partial: the committed bootstrap is fresh, the precondition of the check): WHEN a maintainer runs `python tools/gen_ei_bootstrap.py --check` THE Tool SHALL compare the bootstrap file with what generation would write and report it. Business rule: exit status 0 only when fresh.

## Independent Test

`make test` runs the new `tests/test_ei_bootstrap_generation.py`: it copies `tools/gen_ei_bootstrap.py` and the two templates into a temporary directory, runs the tool without option there, and asserts the generated bootstrap equals the committed one byte for byte. The committed file is read from the repository, so the assertion is independent of the tool's own output.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0011): the reference deck is the single source of the EI charter CSS (header of `tools/gen_ei_bootstrap.py`); the bootstrap is derived. A rule that exists only in the bootstrap is drift: it moves into the reference.

### Data model
None.

### Contracts
`python tools/gen_ei_bootstrap.py` (no option) writes `templates/bootstrap/slides-ei-empty.html`; after this story its output equals the committed file.

### Paths
| Path | Action |
|---|---|
| templates/reference/slides/euro-information.html | modify: insert the 30 lines `/* Lane (swimlane) ... */` to the end of the `.arch-edge-badge` rule, taken verbatim from `templates/bootstrap/slides-ei-empty.html`, between the `.agenda-list td.num` rule and the `/* ── Mode présentation` comment |
| tests/test_ei_bootstrap_generation.py | create |

### Existing patterns
- `tests/test_templates.py`; `tests/test_medical_template.py` (copies of the CSS compared with their source).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0011/E2E-001 (precondition): the committed bootstrap equals its generation
- Level: integration; Driver: subprocess `tools/gen_ei_bootstrap.py` in a temp copy; Location: tests/test_ei_bootstrap_generation.py
- **Given** the repository files as committed
- **When** the generator is run without option on a temporary copy of `tools/gen_ei_bootstrap.py`, `templates/reference/slides/euro-information.html` and `templates/bootstrap/slides-ei-empty.html`
- **Then** the regenerated `slides-ei-empty.html` equals the committed file byte for byte
- **And** the reference deck still has exactly one `.agenda-list td.num` rule and exactly one `/* ── Mode présentation` comment

## Constraints

- Files not to touch: `templates/bootstrap/*`, `tools/*`, `src/*`.
- Dependencies not to add: none.
- Scope boundary: the `--check` mode and the make target belong to US-0004 and US-0005.

## Definition of done

- [ ] RED evidence recorded for the new test before the reference change.
- [ ] The acceptance test green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_templates.py`, `tests/test_medical_template.py` and the export tests pass unmodified; the exported PPTX of the reference is unchanged (the added rules are CSS only).
- [ ] Docs updated: none.
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0068: Resync the Euro-Information reference deck with its generated bootstrap`, body `Spec: SPEC-0011` and `FR-NEW-001`.
