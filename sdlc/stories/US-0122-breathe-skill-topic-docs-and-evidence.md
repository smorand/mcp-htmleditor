# US-0122: breathe skill topic, docs and evidence

> Spec: SPEC-0023 (sdlc/specs/SPEC-0023-breathe-template/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0120, US-0121
> min_tier: 1
> Files touched: 8
> Closes spec: no (moved to US-0123, inserted by the converge on 2026-11-14)

## Objective
Teach agents the Breathe rules through a skill topic, update the documentation, and record the visual evidence of the reference deck in HTML and PPTX. Closes SPEC-0023 (converge).

## Requirements covered
- SPEC-0023/FR-NEW-018

## Independent Test
`mcp-htmleditor skill --type breathe` prints the topic; `mcp-htmleditor skill-audit` reports no problem; the evidence folder holds 23 HTML and 23 PPTX pictures.

## Design excerpt
### Decisions
- n/a (documentation) (SPEC-0023 design.md)
### Paths
| Path | Action |
|---|---|
| `skill/topics/breathe.md`, `skill/core.md` | create / modify |
| `src/mcp_htmleditor/skill_content.py` | modify |
| skill tests (16 topics) | modify |
| `README.md`, `AGENTS.md`, `.agent_docs/*`, `dynamic-skills/html-editor/SKILL.md` | modify |
| `sdlc/specs/SPEC-0023-breathe-template/evidence/` | create |

## Acceptance tests
> 100% must pass through `make check`. The Given/When/Then of each test is in the spec, Section 9.

- SPEC-0023/E2E-041 to E2E-043, E2E-055
- SPEC-0023/E2E-027 evidence pictures
- SPEC-0023/converge: the full acceptance set of SPEC-0023

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
- [ ] One commit `US-0122: <title>` on `feat/breathe-template`, body with `Summary:`, `Spec: SPEC-0023` and the ids.
