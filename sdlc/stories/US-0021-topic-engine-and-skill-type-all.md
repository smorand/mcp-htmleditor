# US-0021: Topic engine and `skill --type/--all`

> Spec: SPEC-0006 (sdlc/specs/SPEC-0006-progressive-skill/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0020
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Replace the single block print of `mcp-htmleditor skill` with a library that renders the core, one
topic, or everything from `skill/core.md` and `skill/topics/<topic>.md`, with exact error messages and
exit codes, the `--type` and `--all` options, the `HTMLEDITOR_SKILL_DIR` test seam and a `skill_tree`
fixture. The shipped content is migrated by later stories; this story is proven on a temporary tree.

## Requirements covered

- SPEC-0006/FR-NEW-002 (partial: topic output only, first line, no core repeated; the arch-qa checklist part lands in US-0022): WHEN a user runs `mcp-htmleditor skill --type <topic>` with one of the 15 topics THE Skill SHALL print that topic only, at most 8 000 bytes.
- SPEC-0006/FR-NEW-003: WHEN a user runs `mcp-htmleditor skill --all` THE Skill SHALL print the core followed by every topic in the index order. Business rule: the output of `--all` is the core output followed by each topic output in index order, each separated from the next by one empty line, and ending with one newline. The user's checklist is part of it.
- SPEC-0006/FR-NEW-004 (partial: command line surface; the tool surface lands in US-0022): IF the requested topic is unknown, empty, or not installed (or the core is not installed) THEN THE Skill SHALL print an error message naming the problem and SHALL NOT print any skill text. Exit status 2 for an unknown or empty topic, 1 for a topic that is not installed. The error output is exactly one line, followed by a newline, with no usage text, and the standard output is empty. `--type <topic>` and `get_skill(type)` do not read the core and succeed when the core is missing; `--all` with the core missing fails with `Skill core is not installed` (exit 1) before any topic; with several missing parts the first in index order (core first) is reported.
- SPEC-0006/FR-NEW-005: The Skill command SHALL NOT accept `--type` and `--all` in the same call. The call fails with a usage error (exit status 2) and prints no skill text. This check runs before the topic validation: `--type foo --all` prints this message, not the unknown topic message. `--type` counts as given even with an empty value: `--type "" --all` prints `Error: --type and --all cannot be used together` and exits with status 2.

## Independent Test

`make test ARGS='tests/test_skill_content.py'`: on a generated skill tree, `skill --type medical` prints
`# Skill topic: medical` first and no core line; `skill --all` equals core plus the 15 topics joined by
one empty line; `--type foo` writes the unknown topic message on stderr, exit 2, empty stdout.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0006): "Layout is `skill/core.md`, `skill/topics/<topic>.md`, `skill/checks/arch-diagram-checklist.md`; topic files hold the body only." The first line `# Skill topic: <t>` is produced by code.
- DEC-002 (SPEC-0006): "`TOPICS` registry (name and description, index order) lives in `skill_content.py`; the index in `core.md` is literal text checked against it by a gate test."
- DEC-003 (SPEC-0006): "`SkillLibrary` (frozen, slots) with injected `skill_dir` and `read_checklist`; `core_output`, `topic_output`, `all_output` return the exact stdout text including the final newline; `--all` is the outputs joined with `\n`."
- DEC-004 (SPEC-0006): "New setting `HTMLEDITOR_SKILL_DIR` (`skill_dir_override`, `config.skill_dir()` owns the bundled candidates moved from `skill_content.py`)."
- DEC-006 (SPEC-0006): "Errors are `SkillError` subclasses carrying message and exit code; the CLI writes the message with `click.echo(..., err=True)` and exits with `click.exceptions.Exit(code)`", never `UsageError` or `ClickException` (they add text).
- DEC-007 (SPEC-0006): "The exclusive options check runs first, `--type ""` counts as given (`topic is not None`)."

### Data model
```python
@dataclass(frozen=True, slots=True)
class Topic:
    name: str
    description: str    # exact text of the index table below
```
No persistent data.

### Contracts
Rendering (all return the exact stdout text, final newline included):
- Core: `core.md` stripped of trailing whitespace plus `\n`.
- Topic: `# Skill topic: <t>\n\n` plus the topic file stripped plus `\n`. For `arch-qa` (checklist part, completed in US-0022): workflow text, an empty line, then the checklist stripped.
- All: core output, then each topic output in index order, joined by `\n` (one empty line between parts, one final newline). Nothing is returned before all parts rendered; first missing part raises (core first).

```python
# config.py
def skill_dir() -> Path   # HTMLEDITOR_SKILL_DIR, else repo skill/, else package skill/ (moved from skill_content)
class Settings: skill_dir_override: Path | None   # joins _PATH_FIELDS and _SIGNIFICANT_ENV_VARS

# skill_content.py (replaces build_skill_content, _skill_dir, _SUBDOCS)
TOPICS: tuple[Topic, ...]; TOPIC_NAMES: tuple[str, ...]
CORE_BUDGET_BYTES = 7000; TOPIC_BUDGET_BYTES = 8000
class SkillError(Exception): message: str; exit_code: int
class UnknownTopicError(SkillError): ...   # exit 2
class NotInstalledError(SkillError): ...   # exit 1
@dataclass(frozen=True, slots=True)
class SkillLibrary:
    skill_dir: Path
    read_checklist: Callable[[], str]
    def core_output(self) -> str
    def topic_output(self, topic: str) -> str     # validates the name first
    def all_output(self) -> str
def build_library(read_checklist: Callable[[], str] | None = None) -> SkillLibrary
    # default: config.skill_dir(), arch_checks.read_checklist

# cli.py
@main.command("skill")
@click.option("--type", "topic", default=None, help="Print one topic instead of the core.")
@click.option("--all", "show_all", is_flag=True, help="Print the core then every topic.")
def skill_cmd(topic: str | None, show_all: bool) -> None: ...
```
Order in `skill_cmd`: (1) `topic is not None and show_all`: stderr `Error: --type and --all cannot be used together`, exit 2. (2) library calls; `SkillError` caught: stderr is the message plus newline, stdout empty, exit `exc.exit_code`. Write with `click.echo(text, nl=False)` on success. Logging stays on stderr at WARNING so stderr holds exactly one line.

Messages (constants in `skill_content.py`):

| Case | stderr | Exit |
|---|---|---|
| unknown or empty topic | `Unknown skill topic "foo". Valid topics: create, export, templates, slides-carbon, slides-ei, medical, medical-sources, document, mail, website, gantt, arch-diagram, arch-qa, annotated-image, tables` | 2 |
| topic file missing | `Skill topic "gantt" is not installed` | 1 |
| core missing | `Skill core is not installed` | 1 |
| both options | `Error: --type and --all cannot be used together` | 2 |

Topics in index order with their descriptions (index line shape `<topic>: <description>. Load: mcp-htmleditor skill --type <topic>`):

| Topic | Description |
|---|---|
| create | Create and edit a file: workflows, rules for text, slides and images |
| export | Export to PPTX and DOCX: what is kept, approximated, lost |
| templates | Build a template from an existing PPTX or DOCX |
| slides-carbon | Rules for IBM Carbon slides |
| slides-ei | Rules for Euro-Information slides |
| medical | Rules for medical slides: layouts, light and dark surfaces, widths, readability, height budget |
| medical-sources | Medical slides: citing sources and anonymising patient images |
| document | Rules for Word-like documents and their DOCX export |
| mail | Rules for HTML mails |
| website | Rules for single page websites |
| gantt | Rules for Gantt charts |
| arch-diagram | Rules for architecture diagrams |
| arch-qa | Visual quality review of architecture diagrams and its checklist |
| annotated-image | Rules for annotated images |
| tables | Rules for tables |

`skill_tree` fixture (tests/conftest.py): builds a valid temporary skill tree: `core.md` (index lines from `TOPICS`, `## Tools` from a `tools=` argument, default empty), 15 small topics, `checks/arch-diagram-checklist.md`; sets `HTMLEDITOR_SKILL_DIR` with `monkeypatch.setenv`, resets the settings cache, and points `HTMLEDITOR_ARCH_CHECKS_DIR` to an empty temporary directory. Helpers: `core_path`, `topic_path(name)`, `checklist_path`, `remove(name)`, `grow(path, to_bytes)` (appends ASCII), `write_core(text)`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/config.py` | modify (`skill_dir`, `skill_dir_override`, `_PATH_FIELDS`, `_SIGNIFICANT_ENV_VARS`) |
| `src/mcp_htmleditor/skill_content.py` | rewrite |
| `src/mcp_htmleditor/cli.py` | modify (`skill` options) |
| `tests/conftest.py` | modify (`skill_tree` fixture) |
| `tests/test_skill_content.py` | rewrite: the old tests import `build_skill_content` and assert the legacy `## Description` block, both disappear; intent covered by E2E-002 and E2E-003 |

### Existing patterns
- `src/mcp_htmleditor/config.py:48,61,105` (`_PATH_FIELDS`, `_SIGNIFICANT_ENV_VARS`), `skill_content.py:15-24` (candidate directories moved to `config.skill_dir`).
- `src/mcp_htmleditor/cli.py:38-47` (current `skill` command).
- `tests/conftest.py` (`reset_settings` autouse, `html_file`); `tests/test_settings.py:16` clears every name of `_SIGNIFICANT_ENV_VARS`, so the new variable is covered.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

DEC-015: the Given "the shipped skill" runs on the generated `skill_tree` (the real content is migrated by US-0026 to US-0033 and audited by US-0034). Level E2E; Driver `click.testing.CliRunner` (stdout and stderr separate); Location `tests/test_skill_content.py`.

### SPEC-0006/E2E-002: One topic only
- Given the skill tree
- When the user runs `mcp-htmleditor skill --type medical`
- Then the output is at most 8 000 bytes
- And `mcp-htmleditor skill --type medical` alone is accepted (exit status 0)
- And its first line is `# Skill topic: medical`, and it contains neither `# mcp-htmleditor skill (core)` nor `# Skill topic: gantt`

### SPEC-0006/E2E-003: Full print
- Given the skill tree
- When the user runs `mcp-htmleditor skill --all`
- Then `--all` alone is accepted (exit status 0) and the output equals the core output followed by the output of `--type` for each of the 15 topics in index order, each separated from the next by one empty line, and ends with one newline

### SPEC-0006/E2E-007: Unknown topic on the command line
- Given the skill tree
- When the user runs `mcp-htmleditor skill --type foo`
- Then the error output is `Unknown skill topic "foo". Valid topics: create, export, templates, slides-carbon, slides-ei, medical, medical-sources, document, mail, website, gantt, arch-diagram, arch-qa, annotated-image, tables` and the exit status is 2
- And nothing is printed on the standard output

### SPEC-0006/E2E-013: A missing topic with the full print
- Given the skill tree where the `gantt` topic file has been removed (`skill_tree.remove("gantt")`)
- When the user runs `mcp-htmleditor skill --all`
- Then the error output is `Skill topic "gantt" is not installed` and the exit status is 1
- And nothing is printed on the standard output
- And `mcp-htmleditor skill --type medical` still prints the medical topic

### SPEC-0006/E2E-014: Both options at once
- Given the skill tree
- When the user runs `mcp-htmleditor skill --type gantt --all`
- Then the error output is exactly `Error: --type and --all cannot be used together` and the exit status is 2
- And nothing is printed on the standard output
- And `mcp-htmleditor skill --type foo --all` and `mcp-htmleditor skill --type "" --all` print the same message and exit with status 2
- And the error output of each of these calls is exactly that one line, with no usage text

### SPEC-0006/E2E-015: Empty topic name
- Given the skill tree
- When the user runs `mcp-htmleditor skill --type ""`
- Then the error output starts with `Unknown skill topic "". Valid topics: create, export,` and the exit status is 2
- And `mcp-htmleditor skill --type gantt` alone still succeeds with exit status 0

Extra assertions in the same file (not spec ids): with the core removed, `skill` prints `Skill core is not installed` exit 1 and `skill --type medical` still succeeds; `--all` with core and gantt both removed reports the core.

## Constraints

- Files not to touch: `src/mcp_htmleditor/mcp_server.py`, `src/mcp_htmleditor/arch_checks.py`, any `skill/*.md` content, `Makefile`, `pyproject.toml`.
- Dependencies not to add: none.
- Patterns to avoid: `os.environ` reads (settings only through `Settings`), `print`, `click.UsageError` or `ClickException` for skill errors, any legacy fallback to the old `skill/*.md` files (DEC-016), silently skipping a missing part.
- Scope boundary: no `get_skill` tool, no checklist fallback change, no audit (US-0022 to US-0024). The click `skill` command prints nothing but the rendered text; logging stays on stderr.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_settings.py`, `tests/test_config.py` and every other existing test pass unmodified; the interim state (shipped tree not yet migrated) is accepted by DEC-016.
- [ ] Docs updated: none in this story (AGENTS.md, README.md and `.agent_docs/` are updated by US-0034).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0021: Topic engine and skill --type/--all`, body `Spec: SPEC-0006` and `FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-005`.
