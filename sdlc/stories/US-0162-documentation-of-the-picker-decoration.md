# US-0162: documentation of the picker decoration

> Spec: SPEC-0029 (sdlc/specs/SPEC-0029-picker-embeds-decoration/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0161
> min_tier: 2
> Files touched: 4
> Closes spec: yes

## Objective
The docs say that the picker adds the decoration itself, and name the route. Closes SPEC-0029: its full acceptance set must be green.

## Requirements covered
- SPEC-0029/FR-NEW-001 (documentation part): the inserted slide shows its decoration at once.

## Independent Test
`make check` green; `rg -n "until .*breathe-inline|no background until" README.md skill/topics/breathe.md .agent_docs/breathe.md` shows no statement left that the inserted layout needs the command; every SPEC-0029 test (E2E-001 to E2E-015) green.

## Design excerpt
### Paths
| Path | Action |
|---|---|
| `README.md` | modify: the Breathe section says an inserted layout brings its decoration (embedded or linked like the deck) and that the command remains for pictures and other edits |
| `skill/topics/breathe.md` | modify: same statement, keep the file within its budget (`mcp-htmleditor skill-audit` must pass) |
| `.agent_docs/breathe.md` | modify: the map: route `POST /breathe-assets`, `decoration_rules`, `addBreatheDecoration`, the notice `#decoration-error`; remove the gotcha "inserted layout has no background" if present |
| `.agent_docs/architecture.md` | modify: one line for the route next to `/arch-layout` |
Keep every `.agent_docs/*.md` within 220 lines (`tests/test_agent_docs_size.py`).

## Acceptance tests
No new test. The story closes the spec: E2E-001 to E2E-015 (US-0161) and the route tests (US-0160) stay green.

## Constraints
- Files not to touch: source and tests.

## Definition of done
- [ ] `make check` green on the work branch after this commit.
- [ ] Spec converge: every test of SPEC-0029 green, every requirement FR-NEW-001 to FR-NEW-006 and FR-MOD-001 cited by a story with status done or landed.
- [ ] One commit `US-0162: documentation of the picker decoration`, body with `Summary:`, `Spec: SPEC-0029` and the requirement ids.
