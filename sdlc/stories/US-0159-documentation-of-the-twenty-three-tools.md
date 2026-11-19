# US-0159: documentation of the twenty three tools

> Spec: SPEC-0028 (sdlc/specs/SPEC-0028-breathe-inline-tool/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0158
> min_tier: 2
> Files touched: 3
> Closes spec: yes

## Objective
The documentation states twenty three agent operations and names `breathe_inline`. Closes SPEC-0028: its full acceptance set must be green.

## Requirements covered
- SPEC-0028/FR-NEW-005 (partial: the documentation): the documentation SHALL state the new number of operations.

## Independent Test
`rg -n "twenty two|22 tools" README.md AGENTS.md .agent_docs/architecture.md src/mcp_htmleditor/mcp_server.py` prints nothing; `make check` green; every SPEC-0028 test (E2E-001 to E2E-008) green.

## Design excerpt
### Paths
| Path | Action |
|---|---|
| `README.md` | modify: line 766 `FastMCP server with 22 tools` becomes 23; the CLI and tool lists mention `breathe_inline` where `breathe-inline` is documented |
| `AGENTS.md` | modify: line 167 `twenty two tools` becomes `twenty three tools` and the name `breathe_inline` is added to the list |
| `.agent_docs/architecture.md` | modify: line 27 `FastMCP, 22 tools (...)` becomes 23 with `breathe_inline` |
Keep `.agent_docs/*.md` within 220 lines (`tests/test_agent_docs_size.py`).

## Acceptance tests
No new test. The story closes the spec: E2E-001 to E2E-008 of SPEC-0028 (US-0158) stay green and `make check` is green.

## Constraints
- Files not to touch: source and tests.
- Scope boundary: nothing else.

## Definition of done
- [ ] `make check` green on the work branch after this commit.
- [ ] Spec converge: every test of SPEC-0028 green, every requirement FR-NEW-001 to FR-NEW-005 and FR-MOD-001 cited by a story with status done or landed.
- [ ] One commit `US-0159: documentation of the twenty three tools`, body with `Summary:`, `Spec: SPEC-0028` and the requirement ids.
