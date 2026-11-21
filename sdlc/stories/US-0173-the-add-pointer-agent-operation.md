# US-0173: the add_pointer agent operation, skill and documentation

> Spec: SPEC-0034 (sdlc/specs/SPEC-0034-add-pointer-to-old-decks/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0172
> min_tier: 2
> Files touched: 8
> Closes spec: yes

## Objective
An agent adds the pointer through `add_pointer(file)` with the command's file result and messages; the skill and the docs list twenty four operations. Closes SPEC-0034.

## Requirements covered
- SPEC-0034/FR-NEW-006, FR-NEW-008, FR-MOD-001.

## Independent Test
`make test ARGS='tests/test_add_pointer_tool.py tests/test_deck_tools_surface.py tests/test_skill_shipped.py'` green, `make check` green.

## Design excerpt
### Decisions
Tool beside `breathe_inline`; skill bytes freed by shortening wording in `skill/core.md` (cap 6000, now 5995).
### Contracts
`src/mcp_htmleditor/mcp_server.py`: `@mcp.tool() def add_pointer(file: str) -> dict[str, Any]` returns `{"ok": True, "summary": outcome.summary(), "added": outcome.added}`; `ToolError(str(exc))` on `DeckError`; span `mcp.add_pointer`. `skill/core.md` `## Tools`: `- add_pointer: Add the presentation pointer to an older deck.` (alphabetical or order as the other lines; follow the file). Docs: tool count twenty three → twenty four and the command line in `README.md`, `AGENTS.md` (key commands, MCP sentence), `.agent_docs/architecture.md`, `.agent_docs/agent-editing.md`, `.agent_docs/html-conventions.md` § Presentation pointer (older decks, the command); keep each `.agent_docs` file within 220 lines.
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/mcp_server.py` | modify |
| `skill/core.md` | modify |
| `tests/test_add_pointer_tool.py` | create |
| `tests/test_deck_tools_surface.py` | modify |
| `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`, `.agent_docs/agent-editing.md`, `.agent_docs/html-conventions.md` | modify |
### Existing patterns
`tests/test_breathe_inline_tool.py` (tool vs command parity), `tests/test_deck_tools_surface.py` (the count and skill list), `skill-audit`.

## Acceptance tests
> 100% must pass, run through `make check`.
### SPEC-0034/E2E-006: the agent interface
- Given two copies of the older Carbon deck (`tests.pointer_old_deck_support`) / When the tool runs on one and the command on the other / Then bytes identical, the tool's `summary` equals the command's stdout line, `added` is true; on a complete deck `added` false; the refusals of E2E-004 and E2E-005 (missing file, template, document, no `btn-present`) raise `ToolError` with the message of the command without `error: `
### SPEC-0034/E2E-008: the list of agent operations (modified)
- The tool set is twenty four names with `add_pointer`; `skill/core.md` lists exactly them and stays within 6000 bytes; `mcp-htmleditor skill-audit` exits 0
### SPEC-0034/E2E-009: a deck without the pointer still opens
- An older deck opened in the editor shows no `#pointer-btn` (the shell control stays hidden) and `L` does nothing, as before
