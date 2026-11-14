# US-0123: breathe converge gaps

> Spec: SPEC-0023 (sdlc/specs/SPEC-0023-breathe-template/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0122
> min_tier: 1
> Files touched: 6
> Closes spec: yes

## Objective
Inserted by the converge of SPEC-0023 (Phase 5, 2026-11-14): close the gaps the independent coverage audit found on
the work branch, so every requirement is implemented and tested as the spec states.

## Requirements covered
- SPEC-0023/FR-NEW-005 (an inserted layout keeps the asset name of its empty picture)
- SPEC-0023/FR-NEW-008 (write failure, one marker only, end marker before begin; deck and folder unchanged)
- SPEC-0023/FR-NEW-014 (box geometry, text start and width, cover crop, letter spacing, missing and vector pictures)
- SPEC-0023/FR-NEW-016 (a slide render over 30 seconds takes the degraded export)
- SPEC-0023/FR-NEW-017 (E2E-054; the samples in the subset run by make check)
- SPEC-0023/FR-MOD-003 (E2E-070, the English placeholder after the French texts)

## Evidence (audit of 2026-11-14)
- No test for the picker's empty picture name; `tools/sync_breathe_layouts.py:70` does it.
- `breathe/inline.py`: write failure untested; in link mode the `assets` folder created for the copies stays after a
  write failure (NFR-007).
- `export/pptx_paint.py`: `set_default_timeout` does not bound `page.evaluate`, so a hanging slide blocks the export.
- E2E-054 and E2E-070 announced by US-0116 and US-0117 but not written.

## Acceptance tests
- SPEC-0023/E2E-054, SPEC-0023/E2E-070 (as specified)
- New checks under the existing ids: E2E-008 (picture name kept), E2E-016 and E2E-SEC-008 family (write failure,
  marker cases), E2E-027 (boxes, text, crop, spacing), E2E-031 (missing linked and vector pictures), E2E-062 (a slide
  over the bound).

## Definition of done
- [ ] RED evidence for the defects (leftover folder, unbounded slide) before the fix.
- [ ] `make check` green on the work branch after this commit.
- [ ] Converge: an independent audit of every SPEC-0023 requirement returns no gap.
- [ ] One commit `US-0123: breathe converge gaps`.
