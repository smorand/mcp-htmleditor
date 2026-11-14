# US-0119: breathe reference deck and picker layouts

> Spec: SPEC-0023 (sdlc/specs/SPEC-0023-breathe-template/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0118
> min_tier: 1
> Files touched: 6
> Closes spec: no

## Objective
Ship the 23 slide reference deck and offer its layouts in the editor's picker, generated from it so they never drift.

## Requirements covered
- SPEC-0023/FR-NEW-004
- SPEC-0023/FR-NEW-005
- SPEC-0023/FR-NEW-021 (reference deck)

## Independent Test
`make check-generated` passes; in the editor a Breathe deck's picker lists 23 entries.

## Design excerpt
### Decisions
- DEC-015 generated block in `slide-layouts.js` (SPEC-0023 design.md)
- DEC-016 inline decoration refreshed by the sync tool (SPEC-0023 design.md)
### Paths
| Path | Action |
|---|---|
| `templates/reference/slides/breathe.html` | create |
| `tools/sync_breathe_layouts.py` | create |
| `src/mcp_htmleditor/static/slide-layouts.js` | modify (generated block) |
| `Makefile` | modify |
| `tests/test_breathe_reference.py` | create |

## Acceptance tests
> 100% must pass through `make check`. The Given/When/Then of each test is in the spec, Section 9.

- SPEC-0023/E2E-007 to E2E-010
- SPEC-0023/E2E-047
- SPEC-0023/E2E-051 to E2E-053

## Constraints
- Files not to touch: the medical, Carbon and Euro-Information templates and their exporter paths.
- Dependencies not to add: none beyond the design (Pillow dev only).
- Scope boundary: the other stories of SPEC-0023.

## Definition of done
- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit.
- [ ] Non regression: the ten golden PPTX fingerprints (`tests/test_export_golden.py`), every medical, Carbon and
      Euro-Information lint and export test unchanged.
- [ ] Docs updated where the story changes usage.
- [ ] Self review: full (tier 1).
- [ ] One commit `US-0119: <title>` on `feat/breathe-template`, body with `Summary:`, `Spec: SPEC-0023` and the ids.
