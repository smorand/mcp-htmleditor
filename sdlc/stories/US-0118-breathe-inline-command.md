# US-0118: breathe-inline command

> Spec: SPEC-0023 (sdlc/specs/SPEC-0023-breathe-template/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0117
> min_tier: 1
> Files touched: 4
> Closes spec: no

## Objective
Give authors and agents one command that embeds the decoration and pictures a Breathe deck uses, as text or as files next to the deck, safely (plain asset names, nothing outside the deck's folder).

## Requirements covered
- SPEC-0023/FR-NEW-006
- SPEC-0023/FR-NEW-007
- SPEC-0023/FR-NEW-008
- SPEC-0023/FR-NEW-023
- SPEC-0023/FR-NEW-025
- SPEC-0023/FR-NEW-024 (embedding half)

## Independent Test
`make test ARGS='tests/test_breathe_inline.py'`; on a copy of the starting point `mcp-htmleditor breathe-inline x.html` prints `x.html: 4 background and icon classes, 1 pictures embedded, <K> KB`.

## Design excerpt
### Decisions
- DEC-009 service, catalogue, check order, history reason, name rule, link containment (SPEC-0023 design.md)
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/breathe/__init__.py`, `breathe/inline.py` | create |
| `src/mcp_htmleditor/cli.py` | modify |
| `tests/test_breathe_inline.py` | create |

## Acceptance tests
> 100% must pass through `make check`. The Given/When/Then of each test is in the spec, Section 9.

- SPEC-0023/E2E-011 to E2E-020
- SPEC-0023/E2E-063 to E2E-065, E2E-069, E2E-072
- SPEC-0023/E2E-SEC-007, E2E-SEC-008, E2E-SEC-009, E2E-SEC-011, E2E-SEC-012

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
- [ ] One commit `US-0118: <title>` on `feat/breathe-template`, body with `Summary:`, `Spec: SPEC-0023` and the ids.
