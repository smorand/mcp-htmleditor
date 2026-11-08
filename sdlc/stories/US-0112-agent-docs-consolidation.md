# US-0112: Agent docs consolidation

> Spec: SPEC-0018 (sdlc/specs/SPEC-0018-documentation-and-stale-pointers/)
> Nature: DEBT
> Priority: P2
> Depends on: US-0111
> min_tier: 1
> Files touched: 6
> Closes spec: yes

## Objective

Four agent docs exceed the 200 line rule (`html-conventions.md` 300, `testing.md` 254, `architecture.md` 220, `agent-editing.md` 201), duplicate facts (fullscreen, pointer) and keep dated run logs. This story consolidates them to at most 200 lines each without losing a current fact, adds the size test that keeps the rule, and closes SPEC-0018. Judgement heavy (what is a current fact, where its one home is): `min_tier: 1`.

## Requirements covered

- SPEC-0018/DR-005: Each of `.agent_docs/html-conventions.md`, `testing.md`, `architecture.md`, `agent-editing.md` SHALL hold at most 200 lines and at most its byte count of Section 1 DBT-004.
- SPEC-0018/DR-006: The consolidation SHALL NOT drop a backticked token (text between single backquotes) present in the four files before the change unless the token is present after it in `.agent_docs/*.md` or `AGENTS.md`, or the story report lists it as removed with the `file:LINE` proving it false today.
- SPEC-0018/DR-007 (partial: this story's edits): The system SHALL produce, for every input covered by the existing test suite, byte identical observable output before and after this change, except the documentation text named in DEC-002 and DEC-003.

## Independent Test

`make test ARGS='-k agent_docs_size'`: DT-013 red before (300 and 254 lines), green after. `wc -l -c` on the four files: each at most 200 lines and at most 21420, 24774, 21056, 17738 bytes respectively (output pasted in the report). The DR-006 token method prints an empty missing list, or each missing token is justified with `file:LINE`. `make check` green.

## Design excerpt

### Decisions

- DEC-004 (SPEC-0018): Add a docs size test (DT-013) at 220 lines, not 200: 20 lines of slack make it a trigger for consolidation, not a blocker for every edit.
- DEC-006 (SPEC-0018): one story for the pointers, one for the consolidation; each closes its own tests.
- DEC-008 (SPEC-0018): this story adds the § Files rows of `tests/test_stale_pointers.py` and `tests/test_agent_docs_size.py` to `.agent_docs/testing.md`.
- DEC-009 (SPEC-0018): SPEC-0019 US-0115 appends five rows to `testing.md` § Files after this story; leave room under 220 lines.

### Method of DR-006 (run once, output in the report)

`git show HEAD:.agent_docs/<f>.md | rg -o '\x60[^\x60]+\x60' | sort -u > /tmp/before-<f>` for each of the four files (HEAD = the base before this story's edits), then for each token check `rg -F -q -- "<token>" .agent_docs AGENTS.md`; the list of missing tokens must be empty or each one justified.

Moves allowed: dedup across files (one home per fact, the other file points to it by `§` heading), dated history (closing run numbers, superseded measurements) reduced to the current rule it supports, merged headings. Every `AGENTS.md` index row stays true.

Known duplication: fullscreen `html-conventions.md:53` and `architecture.md:128`; pointer `html-conventions.md:107` and `architecture.md:141`; dated closing runs `testing.md:223` (SPEC-0016) and `:230` (SPEC-0017). Keep as current rules: the 330 s test step cap, the re run once rule at load above 30, the per spec browser budgets.

### Paths

| Path | Action |
|---|---|
| `.agent_docs/html-conventions.md`, `.agent_docs/testing.md`, `.agent_docs/architecture.md`, `.agent_docs/agent-editing.md` | consolidate |
| `AGENTS.md` | documentation index rows, only if a section moved |
| `tests/test_agent_docs_size.py` | create: DT-013 |

### Existing patterns

- Small structural test reading repository files: `tests/test_no_fixed_waits.py`.
- File map format: `.agent_docs/testing.md:74` (`| File | Covers |`).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0018/DT-013: Agent docs stay within the size rule
- Level / Driver / Location: structural / line count / `tests/test_agent_docs_size.py`
- Given every `.agent_docs/*.md`
- When the test counts lines
- Then each has at most 220 lines (DEC-004); the failure message names each file and its count
- Red before the fix because: `html-conventions.md` has 300 lines and `testing.md` 254.

### Spec converge (closing story)
- The full SPEC-0018 acceptance set green under `make check`: DT-010, DT-011, DT-012, DT-014 (US-0111), DT-013 (this story); Section 8.1 criterion.
- Requirement coverage audit: DR-001 to DR-004 cited by US-0111 (landed), DR-005, DR-006 by this story, DR-007 by both.

## Constraints

- Files not to touch: any file outside the six of Paths; `tests/test_stale_pointers.py` (only listed in § Files).
- No fact dropped silently: every missing token of the DR-006 method is justified in the report.
- No dated entry rewritten as if current: history reduces to the rule it supports.
- Dependencies not to add: any. Scope boundary: SPEC-0019 rows in `testing.md` belong to US-0115.

## Definition of done

- [ ] RED evidence recorded for DT-013 before the consolidation.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] `wc -l -c` of the four files pasted: at most 200 lines each, bytes at most 21420, 24774, 21056, 17738.
- [ ] DR-006 method output pasted, missing list empty or justified.
- [ ] Non regression: no test reads these docs except DT-013; the suite stays green.
- [ ] DEBT: the existing suite passes unmodified, exceptions: none in this story (the 5 SPEC-0018 Section 8.4 edits landed in US-0111).
- [ ] Docs updated: the four agent docs, `testing.md` § Files rows for `test_stale_pointers.py` and `test_agent_docs_size.py`, `AGENTS.md` index if needed.
- [ ] Self review: full.
- [ ] Closes spec: the full SPEC-0018 acceptance set green, every requirement of SPEC-0018 cited by a landed or done story.
- [ ] One commit `US-0112: Agent docs consolidation`, body `Spec: SPEC-0018` and `DR-005, DR-006, DR-007`.
