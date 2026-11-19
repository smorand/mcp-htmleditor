# SPEC-0028: Breathe embedding as an agent tool, design

> Spec: sdlc/specs/SPEC-0028-breathe-inline-tool/spec.md
> Nature: FEAT
> Depth: S
> Security: n/a
> Designed on: 2026-11-19
> Target tier: 2 (default)

## 1. Stack and skills
Existing stack (Python 3.13, FastMCP, `make check`), no new dependency. Skill loaded: python (`make` only, `trace_span` on external calls, settings only through `Settings`; nothing new here).

## 2. Approaches
### Chosen: a thin tool next to the others that calls the existing `embed_assets`
Pros: one implementation shared with the command, same errors. Cons: none. Scope: `mcp_server.py`.
### Rejected: run the command in a subprocess
Slower, loses the structured result (DEC-001).

## 3. Architecture
`mcp_server.py` gets `breathe_inline(file, link)` following `lint` and `export` (`mcp_server.py:324-400`): a `trace_span`, the call to `breathe.inline.embed_assets`, `DeckError` turned into `ToolError`.

## 4. Data model
None.

## 5. Contracts and interfaces
Tool `breathe_inline(file: str, link: bool = False) -> dict[str, Any]`. Result: `{"ok": True, "summary": <InlineOutcome.summary()>, "classes": int, "pictures": int, "copied": int, "size_kb": int, "folder": str}`. Errors: `ToolError(str(DeckError))`, the message of the command line without `error: `. Skill line in `skill/core.md` `## Tools`: `- breathe_inline: Embed (or with link, link to assets/) the decoration and pictures a Breathe deck uses; same result line and errors as the command breathe-inline.`

## 6. File structure impact
| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/mcp_server.py` | modify: the tool, the module docstring count 22 to 23 | FR-NEW-001..004 | US-0158 |
| `skill/core.md` | modify: one `## Tools` line | FR-NEW-005 | US-0158 |
| `tests/test_deck_tools_surface.py` | modify: `FINAL_TOOLS` gets `breathe_inline`, `len(names) == 23` | FR-MOD-001, E2E-008 | US-0158 |
| `tests/test_breathe_inline_tool.py` | create | E2E-001..007 | US-0158 |
| `README.md`, `AGENTS.md`, `.agent_docs/architecture.md` | modify: 22 to 23 and the tool name in the lists | FR-NEW-005 | US-0159 |
Affected existing tests: `tests/test_deck_tools_surface.py::test_the_server_core_and_audit_agree_on_the_final_tools` modified (declared by the spec, E2E-008).

## 7. Compatibility and risks
Additive. `skill-audit` fails if the tool and the skill line are not in the same commit: both are in US-0158. Rollback: revert.

## 9. Test strategy
| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| E2E-001..007 | functional e2e | `fastmcp.Client` on the real server object and `run_cli` for parity | `tests/test_breathe_inline_tool.py` | US-0158 |
| E2E-008 | functional | `registered_tool_names()` and `skill-audit` | `tests/test_deck_tools_surface.py` | US-0158 |
Test data: the Breathe fixtures of `tests/breathe_support.py` (`breathe_deck`, `legacy_deck`) and the shipped Breathe template for E2E-004.

## 10. Decisions log
- **DEC-001:** the tool calls `embed_assets` in process and returns the summary line plus the counts. **Obliged by:** SPEC-0028/FR-NEW-001, FR-NEW-002. **Alternatives considered:** a subprocess of the command. **Source:** design. **Evidence:** `breathe/inline.py:76`.
- **DEC-002:** `DeckError` becomes `ToolError(str(exc))`. **Obliged by:** SPEC-0028/FR-NEW-003. **Source:** existing code. **Evidence:** `mcp_server.py:340-344`.
- **DEC-003:** no update window around the write, as for the command. **Obliged by:** SPEC-0028/FR-NEW-001 (same as the command), scope 3.2. **Source:** spec.
- **DEC-004:** span `mcp.breathe_inline` with `file.path` and `breathe.link` (no document content). **Obliged by:** n/a (no code impact on behavior): observability rule of `AGENTS.md`. **Source:** project convention.
- **DEC-005:** the repeat is idempotent because `embed_assets` rewrites a delimited block; tested, no code. **Obliged by:** SPEC-0028/FR-NEW-004. **Evidence:** `breathe/inline.py:30-31` (`BEGIN`/`END`).

## 11. Stories
| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0158 | the breathe_inline tool, its skill line and tests | P1 | FR-NEW-001..005 (skill line), FR-MOD-001 | main | 2 | no |
| US-0159 | documentation of the twenty three tools | P2 | FR-NEW-005 | US-0158 | 2 | yes |
