# US-0121: serve files next to the open deck

> Spec: SPEC-0023 (sdlc/specs/SPEC-0023-breathe-template/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0117
> min_tier: 1
> Files touched: 2
> Closes spec: no

## Objective
Let the editor show pictures, media, fonts and styles stored next to the deck, without ever answering a file outside the deck's folder.

## Requirements covered
- SPEC-0023/FR-NEW-009
- SPEC-0023/FR-NEW-010

## Independent Test
`make test ARGS='tests/test_http_deck_files_e2e.py'`: the exploit tests read the answers and the log.

## Design excerpt
### Decisions
- DEC-008 gate first, lexical and resolved containment, allow list, nosniff, SVG sandbox (SPEC-0023 design.md)
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/http_server.py` | modify |
| `tests/test_http_deck_files_e2e.py` | create |

## Acceptance tests
> 100% must pass through `make check`. The Given/When/Then of each test is in the spec, Section 9.

- SPEC-0023/E2E-021 to E2E-025, E2E-071
- SPEC-0023/E2E-SEC-001 to E2E-SEC-006, E2E-SEC-010

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
- [ ] One commit `US-0121: <title>` on `feat/breathe-template`, body with `Summary:`, `Spec: SPEC-0023` and the ids.
