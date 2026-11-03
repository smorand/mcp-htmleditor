# US-0024: Audit tool list check and stale statement check

> Spec: SPEC-0006 (sdlc/specs/SPEC-0006-progressive-skill/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0023
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Make `skill-audit` compare the `## Tools` section of the core with the tools the product registers at
audit time, scan the core, the topics and the installed routing skill for stale statements, and report
a missing routing skill. These are the checks that keep the skill accurate when later specs add tools.

## Requirements covered

- SPEC-0006/FR-NEW-007 (partial: problem order and the skip rule for a missing core; sizes landed in US-0023): Problems are printed in this order: for each item in index order (core first) its missing or over budget problem; then the tool list problems (listed but not provided, in the order of the `## Tools` lines, then provided but not listed, in registration order); then stale statements by location (core, topics in index order, routing skill), each location in the order of the stale statement list; then `routing skill not found`. When the core is not installed, the tool list check and the stale statement check of the core are skipped, so the only problem raised for the core is `core is not installed`.
- SPEC-0006/FR-NEW-008: WHEN the audit runs THE Skill SHALL report as a problem every tool that the core lists and that the product does not provide, and every tool that the product provides and that the core does not list. Only the names at the start of the lines of the core section `## Tools` are read. The tools the product provides are compared at audit time, so the list is correct whatever the number of tools. Texts: `PROBLEM tool "foo" is listed in the core but does not exist` and `PROBLEM tool "bar" exists but is not listed in the core`.
- SPEC-0006/FR-NEW-009: WHEN the audit runs THE Skill SHALL report as a problem each stale statement found in the core, in a topic or in the installed routing skill. The matching ignores letter case and matches whole words only (`16 types` and `16 outils` do not match `6 outils` or `15 types`); text inside fenced code blocks is ignored. The stale statements are: `GrapesJS`, `6 outils`, `15 types`, `localhost:7842`, `git commit`, `Défauts d'export mesurés`; and, in the core and in the installed routing skill only, any number directly followed by the word `outils` or `tools`. The words "never assume 7842" are not stale. `git commit` is detected inside and outside fenced code blocks; every other statement is ignored inside them. A whole word match means the statement is not directly preceded or followed by a letter, a digit or an underscore; whitespace inside a statement matches one or more whitespace characters; the apostrophe of `Défauts d'export mesurés` matches `'` and `’`. The location is `in core`, `in topic <name>` or `in routing skill`; the quoted statement is the matched text in lower case; one problem line is printed per distinct statement per location, however many times it occurs there. The routing skill checked is, in order, the installed file `~/.pi/agent/dynamic-skills/html-editor/SKILL.md` and, only when that file is absent, the routing skill file of the source tree the running tool was started from, whatever the current directory; when the installed file exists only it is checked; if neither exists the audit prints `PROBLEM routing skill not found` and counts one problem. Text: `PROBLEM stale statement "grapesjs" in topic gantt`.

## Independent Test

`make test ARGS='tests/test_skill_audit_checks.py'`: with `- frobnicate: does nothing` added to the `## Tools`
section of a skill tree core and `tool_names=registered_tool_names()`, `skill-audit` output contains
`PROBLEM tool "frobnicate" is listed in the core but does not exist`; `registered_tool_names()` returns
the real registered names, among them `get_skill`.

## Design excerpt

### Decisions
- DEC-009 (SPEC-0006): "`registered_tool_names()` in `mcp_server.py` wraps `asyncio.run(mcp.list_tools())`; the audit receives names as a parameter."
- DEC-010 (SPEC-0006): "Tool list parsing reads `- <name>:` line starts in the `## Tools` section of `core.md`; a story that registers a tool adds its line in that story; core shipped at most 6 000 bytes." Binding for SPEC-0007, 0008, 0009, 0010.
- DEC-011 (SPEC-0006): "Stale scanner is a regex list with whole word guards, fence stripping (backtick and tilde fences, unclosed fence runs to the end), `git commit` scanned unstripped, per location dedupe."
- DEC-012 (SPEC-0006): "Routing skill lookup: `HTMLEDITOR_ROUTING_SKILL` (default `~/.pi/agent/dynamic-skills/html-editor/SKILL.md`), else `source_routing_skill_path()` (`<repo>/dynamic-skills/html-editor/SKILL.md` from `__file__`, independent of the cwd); not bundled in the wheel."

### Data model
none (the `AuditItem` and `AuditReport` types from US-0023 are reused unchanged).

### Contracts
```python
# config.py
class Settings: routing_skill_override: Path | None     # HTMLEDITOR_ROUTING_SKILL, joins _PATH_FIELDS and _SIGNIFICANT_ENV_VARS
    @property
    def routing_skill_path(self) -> Path                # override, else ~/.pi/agent/dynamic-skills/html-editor/SKILL.md
def routing_skill_path() -> Path

# mcp_server.py
def registered_tool_names() -> list[str]
    # asyncio.run(mcp.list_tools()) names, registration order. Sync; must not be called from a running
    # event loop (documented in the docstring); async tests precompute the names before awaiting.

# skill_audit.py
def run_audit(library: SkillLibrary, tool_names: Sequence[str] = (), routing_text: str | None = None) -> AuditReport
def listed_tools(core_text: str) -> list[str]            # names at line start (- <name>:) in "## Tools" (ends at the next "## " heading or end of file)
def strip_fenced_blocks(text: str) -> str                # blanks ``` and ~~~ fences (CommonMark closing rule: closing fence same char, at least as long; unclosed fence runs to the end)
def find_stale(text: str, *, include_counts: bool) -> list[str]   # lower cased matched statements, list order then counts
def source_routing_skill_path() -> Path                  # <repo>/dynamic-skills/html-editor/SKILL.md from __file__
def read_routing_skill(installed: Path, source: Path) -> str | None   # installed wins when it exists; None when neither exists
```
Regexes: statement words escaped, whitespace becomes `\s+`, the apostrophe becomes `['’]`, bounded by `(?<!\w)` and `(?!\w)`, `re.IGNORECASE`. List order: `GrapesJS, 6 outils, 15 types, localhost:7842, git commit, Défauts d'export mesurés`. Count pattern `(?<!\w)\d+\s+(?:outils|tools)(?!\w)` only for core and routing skill (`include_counts=True`). `git commit` is scanned on the raw text, every other statement on the fence stripped text. Dedupe per location on the whitespace normalized lower case statement. `run_audit` skips tool and stale checks of the core when the core is missing; topics are always scanned (`include_counts=False`); the routing skill is scanned with `include_counts=True`. When `routing_text is None` the problem `routing skill not found` is added (last). Problem texts: `tool "foo" is listed in the core but does not exist`, `tool "bar" exists but is not listed in the core`, `stale statement "<lower>" in core | in topic <name> | in routing skill`, `routing skill not found`.

`cli.py` `skill_audit_cmd` passes `registered_tool_names()` and the routing text (`read_routing_skill(config.routing_skill_path(), source_routing_skill_path())`).

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/skill_audit.py` | modify (checks, new functions) |
| `src/mcp_htmleditor/cli.py` | modify (`skill-audit` passes tool names and routing text) |
| `src/mcp_htmleditor/mcp_server.py` | modify (`registered_tool_names`) |
| `src/mcp_htmleditor/config.py` | modify (`routing_skill_override`, `routing_skill_path`) |
| `tests/test_skill_audit_checks.py` | new (also holds the unit cases listed below) |

### Existing patterns
- `src/mcp_htmleditor/config.py:48,61,105` (`_PATH_FIELDS`, `_SIGNIFICANT_ENV_VARS`), `Makefile:37,190` (routing skill location `PI_SKILLS_DIR`).
- `skill_tree` fixture (`tools=` argument writes the `## Tools` lines) from US-0021; audit test style in `tests/test_skill_audit.py` (US-0023).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Level E2E; Driver `CliRunner` on `skill-audit` (tool names via the real `registered_tool_names()`, routing skill via `HTMLEDITOR_ROUTING_SKILL`), plus direct `run_audit` calls where a modified core is passed; Location `tests/test_skill_audit_checks.py`. Given "the shipped skill" runs on the `skill_tree` whose `## Tools` lists the real registered tools unless the case changes it (DEC-015). The routing skill is a temporary file with clean content unless the case says otherwise.

### SPEC-0006/E2E-011: A listed tool that does not exist
- Given the skill tree where the section `## Tools` of the core also holds the line `- frobnicate: does nothing`
- When the maintainer runs `mcp-htmleditor skill-audit`
- Then the output contains `PROBLEM tool "frobnicate" is listed in the core but does not exist`
- And the exit status is 1

### SPEC-0006/E2E-012: A tool missing from the core
- Given the skill tree where the line `- update_end: ...` is removed from the section `## Tools` of the core
- When the maintainer runs `mcp-htmleditor skill-audit`
- Then the output contains `PROBLEM tool "update_end" exists but is not listed in the core`
- And the exit status is 1

### SPEC-0006/E2E-018: Stale statement in lower case
- Given the skill tree where the `tables` topic contains the text `via grapesjs`
- When the maintainer runs `mcp-htmleditor skill-audit`
- Then the output contains `PROBLEM stale statement "grapesjs" in topic tables`
- And the exit status is 1

### SPEC-0006/E2E-019: A tool count in the core
- Given the skill tree where the core contains the sentence `Le serveur expose 8 outils`
- When the maintainer runs `mcp-htmleditor skill-audit`
- Then the output contains `PROBLEM stale statement "8 outils" in core`
- And the exit status is 1

### SPEC-0006/E2E-024: The forced commit inside a code block
- Given the skill tree where the `create` topic contains a fenced code block holding the line `git commit -m "x"`
- When the maintainer runs `mcp-htmleditor skill-audit`
- Then the output contains `PROBLEM stale statement "git commit" in topic create` and the exit status is 1
- And a fenced block holding the text `GrapesJS` in the same topic raises no problem

### SPEC-0006/E2E-027: Routing skill not found
- Given the skill tree, no installed routing skill file (`HTMLEDITOR_ROUTING_SKILL` points to a missing file), and the audit run outside a source checkout (`monkeypatch.setattr(skill_audit, "source_routing_skill_path", ...)` returns a missing path)
- When the maintainer runs `mcp-htmleditor skill-audit`
- Then the output contains `PROBLEM routing skill not found`, the last line is `skill-audit: FAIL (1 problem)` and the exit status is 1

Unit cases in the same file (not spec ids): `strip_fenced_blocks` with an unclosed fence, a `~~~` fence and a longer closing fence; `find_stale` word boundary (`16 outils` does not match `6 outils`, `16 types` does not match `15 types`, `15 types` does, apostrophe `’` in `Défauts d’export mesurés` matches), `never assume 7842` is not flagged, `include_counts=False` ignores `8 tools` in a topic; `listed_tools` stops at the next `## ` heading; `read_routing_skill` prefers the installed file; a core removed skips core tool and stale checks.

## Constraints

- Files not to touch: `skill_content.py`, `arch_checks.py`, any `skill/*.md` and `dynamic-skills/` content (the real routing skill is cleaned in US-0025).
- Dependencies not to add: none (no Markdown parser).
- Patterns to avoid: private FastMCP attributes (`_tool_manager`), a hand kept list of tools, calling `asyncio.run` from a running loop, bundling the routing skill in the wheel, deduplicating across locations.
- Scope boundary: no content change; the real tree is audited clean by US-0034.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_skill_audit.py` unchanged and green (the one argument `run_audit(library)` call form still works); `tests/test_settings.py` green with the new variable.
- [ ] Docs updated: none here (US-0034).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0024: Audit tool list check and stale statement check`, body `Spec: SPEC-0006` and `FR-NEW-007, FR-NEW-008, FR-NEW-009`.
