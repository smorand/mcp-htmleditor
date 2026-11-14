# US-0117: breathe charter key, detection, starting point, lint

> Spec: SPEC-0023 (sdlc/specs/SPEC-0023-breathe-template/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0116
> min_tier: 1
> Files touched: 8
> Closes spec: no

## Objective
Add the `breathe` key with its own marker, recognised the same way by lint, export and picker, its one slide starting point, and its lint tables, while medical decks stay exactly as they are.

## Requirements covered
- SPEC-0023/FR-NEW-001
- SPEC-0023/FR-NEW-002
- SPEC-0023/FR-NEW-003
- SPEC-0023/FR-NEW-011
- SPEC-0023/FR-NEW-012
- SPEC-0023/FR-NEW-013
- SPEC-0023/FR-NEW-019
- SPEC-0023/FR-NEW-020 (lint half)
- SPEC-0023/FR-NEW-021 (starting point)
- SPEC-0023/FR-MOD-001
- SPEC-0023/FR-MOD-002
- SPEC-0023/FR-MOD-003

## Independent Test
`make test ARGS='tests/test_breathe_charter.py'`; `mcp-htmleditor new breathe x.html && mcp-htmleditor lint x.html` prints exactly the L006 line.

## Design excerpt
### Decisions
- DEC-001 detection rule in `export/charters.py` (SPEC-0023 design.md)
- DEC-002 keep `med-*` (SPEC-0023 design.md)
- DEC-003 registry order (SPEC-0023 design.md)
- DEC-004 foreign class names (SPEC-0023 design.md)
- DEC-017 F key line removed, presenter synced (SPEC-0023 design.md)
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/export/charters.py` | modify |
| `src/mcp_htmleditor/deck/__init__.py` | modify |
| `src/mcp_htmleditor/export/pptx_style.py` | modify |
| `src/mcp_htmleditor/deck/charter_rules.py`, `deck/lint.py` | modify |
| `src/mcp_htmleditor/static/slide-layouts.js` | modify (detectTemplate) |
| `templates/bootstrap/slides-breathe-empty.html` | create |
| `skill/core.md` | modify (key list) |
| `tests/test_breathe_charter.py`, `tests/breathe_support.py` | create |
| declared existing tests | modify |

## Acceptance tests
> 100% must pass through `make check`. The Given/When/Then of each test is in the spec, Section 9.

- SPEC-0023/E2E-001 to E2E-006
- SPEC-0023/E2E-034 to E2E-037
- SPEC-0023/E2E-044, E2E-045, E2E-048, E2E-049, E2E-056
- SPEC-0023/E2E-058 to E2E-061
- SPEC-0023/E2E-067, E2E-068
- SPEC-0023/E2E-070, E2E-073
- SPEC-0023/E2E-046 and E2E-057 (lint half)

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
- [ ] One commit `US-0117: <title>` on `feat/breathe-template`, body with `Summary:`, `Spec: SPEC-0023` and the ids.
