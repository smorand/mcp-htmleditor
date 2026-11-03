# US-0023: `skill-audit` sizes, budgets, missing items, JSON

> Spec: SPEC-0006 (sdlc/specs/SPEC-0006-progressive-skill/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0022
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective

Add `mcp-htmleditor skill-audit`: one line per item (core, then each topic) with bytes, estimated
tokens, budget and verdict, problems for over budget and missing items, a final verdict, status codes
usable in a build gate, and `--json`. The tool list and stale statement checks land in US-0024.

## Requirements covered

- SPEC-0006/FR-NEW-002 (partial: the `arch-qa` audit line measures the shipped checklist, never a user one): The shipped checklist is at most 3 800 bytes and the shipped arch-qa workflow text at most 3 800 bytes, so that the `arch-qa` output, with its first line and separators, is at most 8 000 bytes. A user checklist larger than the shipped one is printed unchanged.
- SPEC-0006/FR-NEW-004 (partial: the audit reports a missing core without stopping): IF the requested topic is unknown, empty, or not installed (or the core is not installed) THEN THE Skill SHALL print an error message naming the problem and SHALL NOT print any skill text. `--all` with the core missing fails with `Skill core is not installed` (exit 1) before any topic.
- SPEC-0006/FR-NEW-007 (partial: item lines, over budget and missing problems, final verdict, JSON; the tool list and stale statement problems are added by US-0024): WHEN a maintainer runs `mcp-htmleditor skill-audit` THE Skill SHALL print one line per item (the core, then each topic in index order) with its size in bytes, its estimated tokens, its budget and its verdict, then one line per problem found, then a final verdict, and exit with status 0 when no problem is found and 1 otherwise. The size of `arch-qa` is measured on the shipped checklist and the shipped arch-qa workflow text, never on a user checklist. Size counts every byte the command writes on the standard output, including its single final newline. Size is the number of bytes of the UTF 8 text the corresponding command prints; estimated tokens are the size divided by 4, rounded up. Budgets: core 7 000 bytes, each topic 8 000 bytes; a size equal to the budget passes, one byte more is `OVER`. A topic that is not installed prints the item line `<topic>: MISSING` and counts as one problem. If the core is not installed the audit prints the item line `core: MISSING`, the line `PROBLEM core is not installed`, and still audits the topics. An item over its budget also prints `PROBLEM <item> is over its budget (<bytes> > <budget>)` where `<item>` is `core` or `topic <name>`, and counts as one problem. Item line `core: 6120 bytes, ~1530 tokens (budget 7000) OK` or `... OVER`; final line `skill-audit: OK` or `skill-audit: FAIL (3 problems)` (`1 problem` in the singular). With `--json` the same facts are printed as one JSON object `{"items":[{"name","bytes","tokens","budget","status"}],"problems":[strings],"verdict":"OK"|"FAIL"}`; `status` is `OK`, `OVER` or `MISSING`; a missing item has `bytes` and `tokens` null and its budget value; each string of `problems` is the matching `PROBLEM` line without the `PROBLEM ` prefix; the exit status is the same. The audit is usable in a build gate through the status codes (no prompt is ever shown).
- SPEC-0006/FR-NEW-010: IF a topic of the index is not installed THEN THE Skill audit SHALL report it as a problem and SHALL still audit the other items. Text: `PROBLEM topic "gantt" is not installed`.

## Independent Test

`make test ARGS='tests/test_skill_audit.py'`: on a skill tree with `gantt` grown to 8 001 bytes,
`skill-audit` prints `gantt: 8001 bytes, ~2001 tokens (budget 8000) OVER`, the line
`PROBLEM topic gantt is over its budget (8001 > 8000)`, last line `skill-audit: FAIL (1 problem)`, exit 1;
the bytes counted equal `len(CliRunner.invoke(skill --type gantt).stdout_bytes)`.

## Design excerpt

### Decisions
- DEC-013 (SPEC-0006): "The audit renders items through the same `*_output()` with a library whose checklist reader is `read_shipped_checklist`; token estimate `ceil(bytes/4)`; boundary `size <= budget` passes."
- DEC-014 (SPEC-0006): "`skill-audit` has no `make` target; the real tree audit runs inside `make test` (E2E-006)."
- DEC-006 (SPEC-0006): same exit code and message constants as US-0021; the audit reuses them.
- DEC-015 (SPEC-0006): tests with a modified shipped tree run on the generated `skill_tree`.

### Data model
```python
@dataclass(frozen=True, slots=True)
class AuditItem:  # skill_audit.py
    name: str  # "core" or the topic name
    size_bytes: int | None
    tokens: int | None  # ceil(size_bytes / 4)
    budget: int  # 7000 or 8000
    status: str  # "OK" | "OVER" | "MISSING"


@dataclass(frozen=True, slots=True)
class AuditReport:
    items: tuple[AuditItem, ...]
    problems: tuple[str, ...]  # text after "PROBLEM "
    # verdict "OK" when no problem else "FAIL"; exit status 0 / 1
```

### Contracts
```python
# skill_audit.py (this story)
def run_audit(library: SkillLibrary) -> AuditReport      # US-0024 adds tool_names and routing_text
def format_text(report: AuditReport) -> str
def format_json(report: AuditReport) -> str              # json.dumps({...}, ensure_ascii=False), one line

# cli.py
@main.command("skill-audit")
@click.option("--json", "as_json", is_flag=True, help="Machine readable report.")
def skill_audit_cmd(as_json: bool) -> None: ...          # prints format_text or format_json, exit 0 or 1
```
The audit builds its library with `build_library(read_checklist=arch_checks.read_shipped_checklist)`. Size is `len(output.encode("utf-8"))` of `core_output()` and `topic_output(name)`. Problem order: for each item in index order (core first) its missing or over budget problem. Problem texts: `core is not installed`, `topic "<name>" is not installed`, `core is over its budget (<bytes> > <budget>)`, `topic <name> is over its budget (<bytes> > <budget>)`. Text report: one line per item, then `PROBLEM <text>` lines, then the final line. Missing item line: `<name>: MISSING`. Missing items carry `bytes` and `tokens` null in JSON.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/skill_audit.py` | new |
| `src/mcp_htmleditor/cli.py` | modify (`skill-audit` command) |
| `tests/test_skill_audit.py` | new |

### Existing patterns
- `SkillLibrary`, `TOPICS`, `CORE_BUDGET_BYTES`, `TOPIC_BUDGET_BYTES` from `src/mcp_htmleditor/skill_content.py` (US-0021); `arch_checks.read_shipped_checklist` (US-0022).
- `tests/conftest.py` `skill_tree` fixture (US-0021) with `grow`, `write_core`, `remove`.
- CliRunner usage in `tests/test_skill_content.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Level E2E; Driver `CliRunner` on `skill-audit` over the `skill_tree` fixture (DEC-015); Location `tests/test_skill_audit.py`.

### SPEC-0006/E2E-009: A topic over its budget
- Given the skill tree where the `gantt` topic has been grown to 8 001 bytes
- When the maintainer runs `mcp-htmleditor skill-audit`
- Then the line of `gantt` reads `gantt: 8001 bytes, ~2001 tokens (budget 8000) OVER`
- And the output contains `PROBLEM topic gantt is over its budget (8001 > 8000)`
- And the last line is `skill-audit: FAIL (1 problem)` and the exit status is 1
- And every other item line still ends with `OK`

### SPEC-0006/E2E-010: A core over its budget
- Given the skill tree where the core has been grown to 7 001 bytes
- When the maintainer runs `mcp-htmleditor skill-audit`
- Then the line of `core` reads `core: 7001 bytes, ~1751 tokens (budget 7000) OVER`
- And the output contains `PROBLEM core is over its budget (7001 > 7000)`
- And the last line is `skill-audit: FAIL (1 problem)` and the exit status is 1

### SPEC-0006/E2E-016: Budget boundaries and accented text
- Given the skill tree where the core has been set to exactly 7 000 bytes of which 20 bytes come from 10 accented letters `é` (2 bytes each)
- When the maintainer runs `mcp-htmleditor skill-audit`
- Then the `core` line reads `core: 7000 bytes, ~1750 tokens (budget 7000) OK`
- And after adding one more ASCII character the line reads `core: 7001 bytes, ~1751 tokens (budget 7000) OVER`
- And the audit ran without any prompt, with its standard input closed

### SPEC-0006/E2E-017: A customised checklist
- Given the user's checklist location holds a file whose first line is `- [ ] Check the logo is visible`
- When the user runs `mcp-htmleditor skill --type arch-qa`, then `mcp-htmleditor skill --all`, and an agent calls `get_skill` with `type` set to `arch-qa`
- Then all three outputs contain `- [ ] Check the logo is visible`
- And after the user removes the file, the next call prints the shipped checklist instead
- And with a user checklist of 9 000 bytes, `mcp-htmleditor skill --type arch-qa` prints it unchanged and `mcp-htmleditor skill-audit` still reports the `arch-qa` line `OK`

### SPEC-0006/E2E-020: Machine readable audit
- Given the skill tree where the `mail` topic is 8 001 bytes
- When the maintainer runs `mcp-htmleditor skill-audit --json`
- Then the output is one JSON object with 16 entries (core and 15 topics), each holding name, bytes, tokens, budget and status
- And the entry for `mail` has bytes 8001, tokens 2001, budget 8000, status `OVER`
- And `problems` is `["topic mail is over its budget (8001 > 8000)"]` and `verdict` is `FAIL`
- And the exit status is 1

### SPEC-0006/E2E-023: A missing topic during the audit
- Given the skill tree where the `website` topic file has been removed
- When the maintainer runs `mcp-htmleditor skill-audit`
- Then the output contains `PROBLEM topic "website" is not installed` and the item line `website: MISSING`
- And the other 14 topics and the core still have their item lines
- And the last line is `skill-audit: FAIL (1 problem)` and the exit status is 1

### SPEC-0006/E2E-028: Core not installed
- Given the skill tree where the core file has been removed
- When the user runs `mcp-htmleditor skill`, an agent calls `get_skill` without argument, and the maintainer runs `mcp-htmleditor skill-audit`
- Then the command prints `Skill core is not installed` on the error output and exits with status 1, and the agent receives an error with that message
- And the audit prints `core: MISSING` and `PROBLEM core is not installed`, still prints the 15 topic lines, and ends with `skill-audit: FAIL (1 problem)` and status 1

## Constraints

- Files not to touch: `skill_content.py`, `arch_checks.py`, `mcp_server.py`, `config.py`, any `skill/*.md`.
- Dependencies not to add: none.
- Patterns to avoid: measuring files instead of rendered output, reading the user checklist in the audit, a prompt or stdin read, `print`.
- Scope boundary: no tool list problem, no stale statement problem, no routing skill (US-0024). The pre-existing check "the user checklist is printed unchanged" (E2E-017 parts one and two) relies on US-0021 and US-0022.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_skill_content.py` and `tests/test_skill_tool.py` unchanged and green.
- [ ] Docs updated: none here (user docs are updated by US-0034).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0023: skill-audit sizes, budgets, missing items, JSON`, body `Spec: SPEC-0006` and `FR-NEW-002, FR-NEW-004, FR-NEW-007, FR-NEW-010`.
