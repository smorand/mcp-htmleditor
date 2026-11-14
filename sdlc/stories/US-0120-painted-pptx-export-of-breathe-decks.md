# US-0120: painted PPTX export of breathe decks

> Spec: SPEC-0023 (sdlc/specs/SPEC-0023-breathe-template/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0119
> min_tier: 1
> Files touched: 5
> Closes spec: no

## Objective
Export a Breathe deck to a PPTX that looks like the rendered slides, with editable text and the speaker notes, from every surface, and still write a usable PPTX when Chromium is missing.

## Requirements covered
- SPEC-0023/FR-NEW-014
- SPEC-0023/FR-NEW-015
- SPEC-0023/FR-NEW-016
- SPEC-0023/FR-NEW-022
- SPEC-0023/FR-NEW-020 (export half)

## Independent Test
`mcp-htmleditor export pptx templates/reference/slides/breathe.html /tmp/r.pptx` writes 23 painted slides within 60 s.

## Design excerpt
### Decisions
- DEC-005 painted pass in `to_pptx` (SPEC-0023 design.md)
- DEC-006 Chromium measure, timeouts, reasons (SPEC-0023 design.md)
- DEC-007 notes by `_write_notes` (SPEC-0023 design.md)
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/export/pptx_paint.py` | create |
| `src/mcp_htmleditor/export/to_pptx.py` | modify |
| `src/mcp_htmleditor/export/pptx_chrome.py` | modify |
| `tests/test_breathe_pptx.py` | create |

## Acceptance tests
> 100% must pass through `make check`. The Given/When/Then of each test is in the spec, Section 9.

- SPEC-0023/E2E-026 to E2E-033
- SPEC-0023/E2E-046, E2E-050, E2E-057 (export half)
- SPEC-0023/E2E-062, E2E-066

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
- [ ] One commit `US-0120: <title>` on `feat/breathe-template`, body with `Summary:`, `Spec: SPEC-0023` and the ids.
