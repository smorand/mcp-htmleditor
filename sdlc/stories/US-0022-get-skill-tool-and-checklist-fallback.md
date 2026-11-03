# US-0022: `get_skill` tool and checklist fallback

> Spec: SPEC-0006 (sdlc/specs/SPEC-0006-progressive-skill/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0021
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Give an agent connected through the tool protocol the same text as the command line, and make the
architecture checklist fall back to the shipped copy when the user file is empty or unreadable.

## Requirements covered

- SPEC-0006/FR-NEW-002 (partial: the `arch-qa` checklist read at call time, shipped copy when the user file is empty or unreadable): The `arch-qa` topic contains the architecture checklist read from the user editable location at the time of the call, and the shipped checklist when the user has none; a user checklist larger than the shipped one is printed unchanged. IF the user checklist file is empty or unreadable THEN the shipped checklist is used.
- SPEC-0006/FR-NEW-004 (partial: the agent tool surface): IF the requested topic is unknown, empty, or not installed (or the core is not installed) THEN THE Skill SHALL print an error message naming the problem and SHALL NOT print any skill text. The same two messages are returned as an error by the agent tool. `get_skill(type)` does not read the core and succeeds when the core is missing.
- SPEC-0006/FR-NEW-006: WHEN an agent calls the tool `get_skill` THE Skill SHALL return the same text as `mcp-htmleditor skill`, and the same text as `mcp-htmleditor skill --type <topic>` when the argument `type` is given. No argument returns the core. An unknown, empty or not installed topic returns the messages of FR-NEW-004 as an error.

## Independent Test

`make test ARGS='tests/test_skill_tool.py'`: through `fastmcp.Client(mcp)`, `get_skill` with no argument
returns exactly the CliRunner stdout of `skill`; `get_skill(type="foo")` raises a tool error whose message
is the unknown topic message; an empty user checklist file yields the shipped checklist text.

## Design excerpt

### Decisions
- DEC-005 (SPEC-0006): "`arch_checks._repo_checks_dir()` returns `config.skill_dir() / "checks"`; `read_checklist()` skips blank or unreadable candidates; new `read_shipped_checklist()`." Name `_repo_checks_dir` is kept because `tests/test_arch_checks.py:44` monkeypatches it.
- DEC-008 (SPEC-0006): "`get_skill(type=None) -> str` returns the same string as the CLI stdout, final newline included; errors raise `ToolError(message)`."
- DEC-003 (SPEC-0006): one `SkillLibrary` serves CLI and tool, so equality is structural.

### Data model
none

### Contracts
```python
# arch_checks.py
def _repo_checks_dir() -> Path          # config.skill_dir() / "checks"
def read_checklist() -> str             # iterate the search path; skip a candidate that is not a file,
                                        # unreadable (OSError, UnicodeDecodeError) or blank; first usable
                                        # text; "" when none
def read_shipped_checklist() -> str     # reads only _repo_checks_dir(); "" on any failure
# An empty result makes SkillLibrary.topic_output("arch-qa") raise NotInstalledError
# (message: Skill topic "arch-qa" is not installed).

# mcp_server.py
@mcp.tool()
def get_skill(type: str | None = None) -> str:     # noqa: A002 - argument name "type" is the contract
    """Return the skill core, or one topic when type is given."""
    # trace_span("mcp.get_skill", {"skill.topic": type or "core"})
    # SkillError -> fastmcp.exceptions.ToolError(exc.message)
```
`build_library()` (US-0021) is used by the tool. The module docstring that says "7 tools" becomes "8 tools".
Messages: `Unknown skill topic "foo". Valid topics: create, export, templates, slides-carbon, slides-ei, medical, medical-sources, document, mail, website, gantt, arch-diagram, arch-qa, annotated-image, tables` and `Skill topic "gantt" is not installed`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/mcp_server.py` | modify (`get_skill`, docstring "8 tools") |
| `src/mcp_htmleditor/arch_checks.py` | modify (`_repo_checks_dir`, `read_checklist`, `read_shipped_checklist`) |
| `tests/test_skill_tool.py` | new |
| `tests/test_arch_checks.py` | modify (extend: blank and directory candidates skipped, `read_shipped_checklist`) |

### Existing patterns
- `src/mcp_htmleditor/mcp_server.py:30,80,92,111,132,149,165` (seven `@mcp.tool()` tools, `trace_span` usage at `:48`).
- `src/mcp_htmleditor/arch_checks.py:27-36,44-54,57-67` (search path, first existing file wins).
- `tests/test_arch_checks.py:22-26,44` (existing assertions and the `_repo_checks_dir` monkeypatch).
- async tests: `pytest-asyncio` auto mode; `skill_tree` fixture from US-0021.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Level E2E; Driver `fastmcp.Client(mcp)` in async tests, plus `CliRunner` for the equality; Location `tests/test_skill_tool.py`. Given "the shipped skill" runs on the `skill_tree` fixture (DEC-015).

### SPEC-0006/E2E-004: Core through the tool surface
- Given an agent connected through the tool protocol
- When it calls `get_skill` with no argument
- Then the returned text equals the output of `mcp-htmleditor skill`

### SPEC-0006/E2E-005: Topic through the tool surface
- Given an agent connected through the tool protocol
- When it calls `get_skill` with `type` set to `gantt`
- Then the returned text equals the output of `mcp-htmleditor skill --type gantt`

### SPEC-0006/E2E-008: Unknown topic through the tool surface
- Given an agent connected through the tool protocol
- When it calls `get_skill` with `type` set to `foo`
- Then it receives an error whose message is `Unknown skill topic "foo". Valid topics: create, export, templates, slides-carbon, slides-ei, medical, medical-sources, document, mail, website, gantt, arch-diagram, arch-qa, annotated-image, tables`

### SPEC-0006/E2E-025: Empty or unreadable user checklist
- Given the user's checklist location (`HTMLEDITOR_ARCH_CHECKS_DIR`) holds an empty file
- When the user runs `mcp-htmleditor skill --type arch-qa`
- Then the output holds the shipped checklist and the exit status is 0
- And with the checklist location being a directory instead of a file, the output and the exit status are the same

### SPEC-0006/E2E-026: Missing topic through both surfaces
- Given the skill tree where the `gantt` topic file has been removed
- When an agent calls `get_skill` with `type` set to `gantt`, and the user runs `mcp-htmleditor skill --type gantt`
- Then the agent receives an error whose message is `Skill topic "gantt" is not installed`
- And the command exits with status 1, that message is on the error output and nothing is on the standard output

Extra assertions (not spec ids): `get_skill` appears in `await mcp.list_tools()`; with the core removed `get_skill()` errors with `Skill core is not installed` while `get_skill(type="medical")` succeeds.

## Constraints

- Files not to touch: `src/mcp_htmleditor/skill_content.py`, `cli.py`, `config.py`, any `skill/*.md` content.
- Dependencies not to add: none.
- Patterns to avoid: writing to stdout in `mcp_server.py` (no `click.echo`, no `print`), a tool that strips the final newline, reading the core for `type`.
- Scope boundary: `registered_tool_names()` and the audit are US-0023 and US-0024.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_arch_checks.py` existing tests (`test_checklist_path_falls_back...`, `test_env_override...`, `test_missing_file...`, `test_read_checklist_returns_the_bundled_content`) and the seven existing tools unchanged.
- [ ] Docs updated: none here (README, AGENTS.md and architecture docs are updated by US-0034).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0022: get_skill tool and checklist fallback`, body `Spec: SPEC-0006` and `FR-NEW-002, FR-NEW-004, FR-NEW-006`.
