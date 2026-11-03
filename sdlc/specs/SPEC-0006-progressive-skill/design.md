# SPEC-0006: Progressive skill loading and skill budget audit, design

> Spec: sdlc/specs/SPEC-0006-progressive-skill/spec.md
> Nature: FEAT
> Depth: L
> Security: n/a
> Designed on: 2026-11-03
> Target tier: 2 (default)

## 1. Stack and skills

Existing stack, nothing new to install (no NEEDS DECISION):

| Item | Version / source | Use here |
|---|---|---|
| Python | `requires-python >=3.13` (`pyproject.toml:8`) | all code |
| click | `>=8.0`, locked 8.4.2 | `skill` options, `skill-audit` command |
| fastmcp | `>=2.0`, locked 3.4.6 (`uv.lock`) | `get_skill` tool, `ToolError`, tool listing |
| pydantic-settings | `>=2.7` | two new `Settings` fields |
| pytest, pytest-asyncio (`auto`), pytest-cov | dev group | tests, gate 80 % |
| ruff, mypy strict, bandit | dev group | `make check` |

Python skill rules applied: `make` only (no new target, DEC-018); configuration only through
`Settings` in `config.py` (two new variables, DEC-004 and DEC-012, never `os.environ`); nothing on
stdout in the MCP process (`get_skill` returns text, the audit is a CLI command, `mcp_server.py`
gets no `click.echo`); `trace_span("mcp.get_skill", ...)` like the seven existing tools; local file
reads are not external calls, so no span in the library or the audit; mypy strict (frozen
`@dataclass(slots=True)` value objects, full annotations); ruff (`%` logging, no `print`, f-strings
only, `T20`, `PTH`); Click stays the CLI (the global "Typer only" rule is overridden by the existing
project decision, `AGENTS.md` Overview).

Binding facts from the codebase:

* `skill` assembles everything today: `src/mcp_htmleditor/cli.py:38-47`, `skill_content.py:15-70`.
* Skill directory has two fixed candidates, no override: `skill_content.py:15-24`.
* Missing sub documents are skipped silently: `skill_content.py:58-61`.
* Checklist search path and the "first existing file wins, even empty" behavior:
  `arch_checks.py:27-36,44-54,57-67`.
* Seven tools registered with `@mcp.tool()`: `mcp_server.py:30,80,92,111,132,149,165`; FastMCP
  3.4.6 `await mcp.list_tools()` returns them in registration order (checked by running it).
* Path settings go through `_PATH_FIELDS` and `_SIGNIFICANT_ENV_VARS`: `config.py:48,61,105`.
* Routing skill installed by `make install-skill` with `PI_SKILLS_DIR ?=`: `Makefile:37,186-191`.
* Wheel already ships the whole `skill/` tree: `pyproject.toml:48-52` (force include), so new files
  under `skill/` need no packaging change; `Dockerfile:19` copies `skill/` too.
* SPEC-0012 landed before this spec (exports split, charters registry); nothing in this design
  depends on it. `cli.py` is shared with later specs.

## 2. Approaches

### Approach 1: Files per topic, one library object, audit as a separate module (chosen)

`skill/core.md` plus `skill/topics/<topic>.md`; a `SkillLibrary` value object (skill directory and a
checklist reader injected) renders core, one topic, or everything, each returning the exact bytes the
command prints; `skill_audit.py` measures those same outputs and runs the tool list and stale checks.
The CLI and the tool are thin adapters. Test seams: `HTMLEDITOR_SKILL_DIR`, `HTMLEDITOR_ROUTING_SKILL`,
the existing `HTMLEDITOR_ARCH_CHECKS_DIR`, an injected tool name list.

* Pro: size measured on the real output by construction (FR-NEW-007), one code path for CLI and tool
  (FR-NEW-006 equality is structural), every E2E can run against a temporary skill tree.
* Con: 15 plus 1 files to author and a registry in code (`TOPICS`) duplicated by the literal index in
  `core.md` (guarded by a test).

### Approach 2: One Markdown file per topic holding front matter, index generated from it

Each topic carries `description:` front matter; the core index is generated at render time with a
`{{TOPIC_INDEX}}` placeholder.

* Pro: no duplicate between registry and index.
* Con: the core file is no longer the literal output, which breaks the way the spec's tests grow it
  to exactly 7 000 then 7 001 bytes (E2E-010, E2E-016) and makes the budget depend on generation;
  front matter parsing is new surface for a fixed list of 15 names that the spec calls a product
  contract. Rejected.

### Approach 3: Keep the legacy files, split by section markers at run time

Keep `skill/*.md` and cut them by `<!-- topic: x -->` markers.

* Pro: no content migration commit.
* Con: the budgets (8 000 bytes) cannot be met without cutting text, and the priority rule requires
  authored cuts; markers keep the 198 KB in the wheel and make "the removed text is kept in project
  documentation" meaningless. Rejected.

**Decision: Approach 1.** The content migration (cutting 198 KB into a 7 000 byte core and 15
topics of at most 8 000 bytes) is real authoring work and is designed as stories F to M (Section 11).

## 3. Architecture

```
 agent / maintainer
   |                                   |
   | mcp-htmleditor skill [--type T|--all]      | mcp-htmleditor skill-audit [--json]
   v                                   v
 cli.py (click, thin)                cli.py
   |  validate options (DEC-006/007)   |  build_library(shipped checklist)
   |  stdout/stderr + exit codes       |  registered_tool_names()  <--- mcp_server.py
   v                                   v
 skill_content.SkillLibrary  <------ skill_audit.run_audit(library, tool_names, routing_text)
   |  core_output() / topic_output(t) / all_output()       |  sizes, budgets, tools, stale scan
   |  reads  <skill_dir>/core.md                            |  routing skill: installed file,
   |         <skill_dir>/topics/<t>.md                      |  else source tree (DEC-012)
   |         arch-qa: + checklist (injected reader)         v
   v                                                    AuditReport -> text | JSON, exit 0/1
 config.skill_dir()  = HTMLEDITOR_SKILL_DIR or bundled (repo skill/ or package skill/)
 arch_checks.read_checklist()         user file (valid, non empty) else shipped copy
 arch_checks.read_shipped_checklist() <skill_dir>/checks/arch-diagram-checklist.md only

 mcp_server.get_skill(type=None) --> same SkillLibrary.core_output()/topic_output() --> str
                                     SkillError --> fastmcp ToolError(message)
```

Rendering contract (all in DEC-003): every `*_output()` returns the exact text written on stdout,
including its single final newline. Core: `core.md` stripped of trailing whitespace plus `\n`.
Topic: `# Skill topic: <t>\n\n` plus the topic file stripped plus `\n` (the first line is added by the
code, never stored in the file, so the name has one source). `arch-qa`: workflow text, an empty line,
then the checklist stripped. All: the outputs joined by `\n`, which yields exactly one empty line
between parts and one final newline. The CLI writes the string with `click.echo(text, nl=False)`; the
tool returns the same string.

Where the tool list lives (binding for SPEC-0007, 0008, 0009, 0010): file `skill/core.md`, section
`## Tools` (ends at the next `## ` heading or end of file), one line per tool of the shape
`- <name>: <description>`. A story that registers a tool adds one such line at the end of that
section in the same story; `skill-audit` (and the gate test of story E) fail otherwise. The core is
written at most 6 000 bytes in story E so later specs keep about 1 000 bytes of headroom under the
7 000 byte budget.

## 4. Data model

No persistent data. Value objects (frozen, `slots=True`):

```python
@dataclass(frozen=True, slots=True)
class Topic:            # skill_content.py
    name: str
    description: str    # exact text of the spec's index table

@dataclass(frozen=True, slots=True)
class AuditItem:        # skill_audit.py
    name: str           # "core" or the topic name
    size_bytes: int | None
    tokens: int | None  # ceil(size_bytes / 4)
    budget: int         # 7000 or 8000
    status: str         # "OK" | "OVER" | "MISSING"

@dataclass(frozen=True, slots=True)
class AuditReport:
    items: tuple[AuditItem, ...]
    problems: tuple[str, ...]      # text after "PROBLEM "
    # verdict "OK" when no problem else "FAIL"; exit status 0 / 1
```

Files on disk after the migration:

| Path | Content |
|---|---|
| `skill/core.md` | the core (rules, workflow, `## Tools`, topic index), at most 6 000 bytes shipped |
| `skill/topics/<topic>.md` | 15 files, body only (no `# Skill topic:` line), `arch-qa.md` is the workflow text, at most 3 800 bytes |
| `skill/checks/arch-diagram-checklist.md` | shipped checklist, at most 3 800 bytes (cut from 11 856) |
| `docs/skill-archive/*.md` | the former full sources, moved with `git mv` (removed text kept), not shipped |
| `tests/data/skill_anchors.json` | `{topic: [verbatim substrings the topic must contain]}` (DEC-017) |

Settings added: `skill_dir_override` (`HTMLEDITOR_SKILL_DIR`, directory) and
`routing_skill_override` (`HTMLEDITOR_ROUTING_SKILL`, file); property `routing_skill_path` defaults
to `~/.pi/agent/dynamic-skills/html-editor/SKILL.md`. Both join `_PATH_FIELDS` and
`_SIGNIFICANT_ENV_VARS`. They are maintainer and test seams; the spec's "no user override directory
for the skill text" (3.2) stays true because they are documented as such and not in user docs.

## 5. Contracts and interfaces

### 5.1 Command line (click)

```python
@main.command("skill")
@click.option("--type", "topic", default=None, help="Print one topic instead of the core.")
@click.option("--all", "show_all", is_flag=True, help="Print the core then every topic.")
def skill_cmd(topic: str | None, show_all: bool) -> None: ...

@main.command("skill-audit")
@click.option("--json", "as_json", is_flag=True, help="Machine readable report.")
def skill_audit_cmd(as_json: bool) -> None: ...
```

`skill_cmd` order: (1) `topic is not None and show_all` (an empty `--type ""` counts as given):
stderr `Error: --type and --all cannot be used together`, exit 2. (2) `SkillLibrary` calls, any
`SkillError` is caught: stderr = the message plus newline, stdout empty, exit `exc.exit_code`.
Errors are written with `click.echo(msg, err=True)` then `raise click.exceptions.Exit(code)`, never
`click.UsageError` or `ClickException` (they add `Usage:` or `Error: ` text the spec forbids except for
the exclusive options line, which carries `Error: ` by spec). Logging stays on stderr at WARNING so
stderr holds exactly one line (asserted in E2E-014).

Exact messages (constants in `skill_content.py`):

| Case | stderr | Exit |
|---|---|---|
| unknown or empty topic | `Unknown skill topic "foo". Valid topics: create, export, templates, slides-carbon, slides-ei, medical, medical-sources, document, mail, website, gantt, arch-diagram, arch-qa, annotated-image, tables` | 2 |
| topic file missing | `Skill topic "gantt" is not installed` | 1 |
| core missing | `Skill core is not installed` | 1 |
| both options | `Error: --type and --all cannot be used together` | 2 |

`--all` renders core first then topics in index order and raises on the first missing part (core
first); nothing is written before all parts rendered. `--type` and `get_skill(type)` never read the
core.

`skill_audit_cmd` prints `format_text(report)` or `format_json(report)` and exits 0 or 1. Text:
one line per item (`core: 6120 bytes, ~1530 tokens (budget 7000) OK`, `... OVER`, or
`gantt: MISSING`), then the `PROBLEM ...` lines in the spec's order, then `skill-audit: OK` or
`skill-audit: FAIL (N problems)` (`1 problem`). JSON: `json.dumps({"items": [...], "problems": [...],
"verdict": ...}, ensure_ascii=False)` on one line; missing items have `bytes` and `tokens` null.

### 5.2 Modules and signatures

`config.py` (story A and D):

```python
def skill_dir() -> Path:   # HTMLEDITOR_SKILL_DIR, else repo skill/, else package skill/ (moved from skill_content)
class Settings: skill_dir_override: Path | None; routing_skill_override: Path | None
    @property
    def routing_skill_path(self) -> Path
def routing_skill_path() -> Path
```

`skill_content.py` (story A; replaces `build_skill_content`, `_skill_dir`, `_SUBDOCS`):

```python
TOPICS: tuple[Topic, ...]            # 15, index order, spec descriptions verbatim
TOPIC_NAMES: tuple[str, ...]
CORE_BUDGET_BYTES = 7000; TOPIC_BUDGET_BYTES = 8000

class SkillError(Exception):        # .message: str, .exit_code: int
class UnknownTopicError(SkillError): # exit 2
class NotInstalledError(SkillError): # exit 1

@dataclass(frozen=True, slots=True)
class SkillLibrary:
    skill_dir: Path
    read_checklist: Callable[[], str]
    def core_output(self) -> str
    def topic_output(self, topic: str) -> str      # validates the name first
    def all_output(self) -> str

def build_library(read_checklist: Callable[[], str] | None = None) -> SkillLibrary
    # default: config.skill_dir(), arch_checks.read_checklist
```

`arch_checks.py` (story B): `_repo_checks_dir()` returns `config.skill_dir() / "checks"` (name kept:
`tests/test_arch_checks.py:44` monkeypatches it);
`read_checklist()` iterates the search path, skips a candidate that is not a file, unreadable
(`OSError`, `UnicodeDecodeError`) or blank, returns the first usable text, `""` when none;
`read_shipped_checklist() -> str` reads only `_repo_checks_dir()`, `""` on any failure. An empty
result makes `topic_output("arch-qa")` raise `NotInstalledError`.

`mcp_server.py`:

```python
@mcp.tool()
def get_skill(type: str | None = None) -> str:     # noqa: A002 - argument name "type" is the contract
    """Return the skill core, or one topic when type is given."""
    # trace_span("mcp.get_skill", {"skill.topic": type or "core"}); SkillError -> ToolError(exc.message)

def registered_tool_names() -> list[str]:          # story D; asyncio.run(mcp.list_tools()), registration order
```

`registered_tool_names` is sync and must not be called from a running event loop (documented in its
docstring); the audit CLI is sync, and async tests compute names before awaiting.

`skill_audit.py` (stories C and D):

```python
def run_audit(library: SkillLibrary, tool_names: Sequence[str] = (), routing_text: str | None = None) -> AuditReport
def format_text(report: AuditReport) -> str
def format_json(report: AuditReport) -> str
def listed_tools(core_text: str) -> list[str]            # names at line start in "## Tools"
def strip_fenced_blocks(text: str) -> str                # blanks ``` and ~~~ fences (CommonMark closing rule)
def find_stale(text: str, *, include_counts: bool) -> list[str]   # lower cased matched statements, list order then counts
def source_routing_skill_path() -> Path                  # <repo>/dynamic-skills/html-editor/SKILL.md from __file__
def read_routing_skill(installed: Path, source: Path) -> str | None   # installed wins; None when neither
```

Signature note: story C ships `run_audit(library)` with no tool or stale checks yet; story D adds the
two parameters (and its callers). `run_audit` order of problems is the spec's (items, tools, stale by
location, routing not found). Stale regexes: statement words escaped, whitespace becomes `\s+`, the
apostrophe becomes `['’]`, bounded by `(?<!\w)` and `(?!\w)`, `re.IGNORECASE`; list
`GrapesJS, 6 outils, 15 types, localhost:7842, git commit, Défauts d'export mesurés`; count pattern
`(?<!\w)\d+\s+(?:outils|tools)(?!\w)` only for core and routing skill; `git commit` scanned on the raw
text, all others on the fence stripped text; dedupe per location on the whitespace normalized lower
case statement. The audit measures size as `len(output.encode("utf-8"))` of the same `*_output()`
call, with a library whose checklist reader is `read_shipped_checklist` (never the user file).

### 5.3 MCP tool surface

`get_skill(type: str | None = None) -> str`: no argument, the core; `type` set, that topic; errors
raise `fastmcp.exceptions.ToolError(message)` with the messages of 5.1. Returned text equals the CLI
stdout byte for byte, final newline included (DEC-008).

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/config.py` | modify (`skill_dir`, `skill_dir_override`) | FR-NEW-002, FR-NEW-004 | STORY-A |
| `src/mcp_htmleditor/skill_content.py` | rewrite | FR-NEW-001 to 005 | STORY-A |
| `src/mcp_htmleditor/cli.py` | modify (`skill` options) | FR-NEW-001, 003, 004, 005 | STORY-A |
| `tests/conftest.py` | modify (`skill_tree` fixture) | test seam of 14.3 | STORY-A |
| `tests/test_skill_content.py` | rewrite (see below) | FR-NEW-002 to 005 | STORY-A |
| `src/mcp_htmleditor/mcp_server.py` | modify (`get_skill`, docstring "8 tools") | FR-NEW-006 | STORY-B |
| `src/mcp_htmleditor/arch_checks.py` | modify | FR-NEW-002 | STORY-B |
| `tests/test_skill_tool.py` | new | FR-NEW-004, 006 | STORY-B |
| `tests/test_arch_checks.py` | modify | FR-NEW-002 | STORY-B, STORY-M |
| `src/mcp_htmleditor/skill_audit.py` | new | FR-NEW-007 to 010 | STORY-C, STORY-D |
| `src/mcp_htmleditor/cli.py` | modify (`skill-audit`) | FR-NEW-007 | STORY-C, STORY-D |
| `tests/test_skill_audit.py` | new | FR-NEW-007, 010 | STORY-C |
| `src/mcp_htmleditor/mcp_server.py` | modify (`registered_tool_names`) | FR-NEW-008 | STORY-D |
| `src/mcp_htmleditor/config.py` | modify (`routing_skill_override`) | FR-NEW-009 | STORY-D |
| `tests/test_skill_audit_checks.py` | new | FR-NEW-008, 009 | STORY-D |
| `skill/core.md` | new | FR-NEW-001 | STORY-E |
| `skill/SKILL.md` | move to `docs/skill-archive/index.md` | FR-NEW-001, 002 (text kept) | STORY-E |
| `dynamic-skills/html-editor/SKILL.md` | modify | FR-NEW-001, 009 | STORY-E |
| `dynamic-skills/README.md` | modify | FR-NEW-001 | STORY-E |
| `tests/test_skill_shipped.py` | new, then extended | FR-NEW-001, 002, 007 to 009 | STORY-E, STORY-N |
| `skill/topics/slides-carbon.md`, `slides-ei.md` | new | FR-NEW-002 | STORY-F |
| `skill/types/slides.md` | move to `docs/skill-archive/slides.md` | FR-NEW-002 | STORY-F |
| `tests/data/skill_anchors.json` | new, extended per story | FR-NEW-002 | STORY-F to L |
| `skill/topics/medical.md`, `medical-sources.md` | new | FR-NEW-002 | STORY-G |
| `skill/types/medical.md` | move to `docs/skill-archive/medical.md` | FR-NEW-002 | STORY-G |
| `skill/topics/create.md`, `export.md` | new | FR-NEW-002 | STORY-H |
| `skill/workflow-create.md`, `skill/workflow-export.md` | move to `docs/skill-archive/` | FR-NEW-002 | STORY-H |
| `skill/topics/document.md`, `mail.md` | new | FR-NEW-002 | STORY-I |
| `skill/types/document.md`, `skill/types/mail.md` | move to `docs/skill-archive/` | FR-NEW-002 | STORY-I |
| `skill/topics/website.md`, `tables.md` | new | FR-NEW-002 | STORY-J |
| `skill/types/website.md`, `skill/types/tables.md` | move to `docs/skill-archive/` | FR-NEW-002 | STORY-J |
| `skill/topics/gantt.md`, `annotated-image.md` | new | FR-NEW-002 | STORY-K |
| `skill/types/gantt.md`, `skill/types/annotated-image.md` | move to `docs/skill-archive/` | FR-NEW-002 | STORY-K |
| `skill/topics/arch-diagram.md`, `templates.md` | new | FR-NEW-002 | STORY-L |
| `skill/types/arch-diagram.md`, `skill/workflow-templates.md` | move to `docs/skill-archive/` | FR-NEW-002 | STORY-L |
| `skill/topics/arch-qa.md` | new | FR-NEW-002 | STORY-M |
| `skill/workflow-arch-qa.md` | move to `docs/skill-archive/` | FR-NEW-002 | STORY-M |
| `skill/checks/arch-diagram-checklist.md` | modify (cut to 3 800 bytes) | FR-NEW-002 | STORY-M |
| `docs/skill-archive/arch-diagram-checklist.md` | new (copy of the 11 856 byte original) | FR-NEW-002 | STORY-M |
| `AGENTS.md`, `README.md`, `.agent_docs/architecture.md`, `.agent_docs/testing.md` | modify | spec 14.3 docs list | STORY-N |

A git rename counts as one touched path in the story file counts. Not touched: `Makefile`
(`install-skill` already copies the routing skill and honors `PI_SKILLS_DIR`), `pyproject.toml`
(`skill/` force include covers `core.md`, `topics/`, `checks/`), `Dockerfile`.

Affected existing tests:

| Test | Verdict | Reason |
|---|---|---|
| `tests/test_skill_content.py` | **remove and replace** in STORY-A | it imports `build_skill_content`, asserts `## Description` and `workflow-create` markers of the legacy single block; both the function and the block disappear (FR-NEW-001/003). Its intent (assembly works, non trivial output) is covered by E2E-002, 003 on a temporary tree; the file is rewritten for the new module |
| `tests/test_arch_checks.py` | keep, extend (B), adapt (M) | `test_checklist_path_falls_back...`, `test_env_override...`, `test_missing_file...` still hold (`_repo_checks_dir` name kept); `test_read_checklist_returns_the_bundled_content` asserts `"2 passes"` and `"arch-col"` in the shipped file, STORY-M re-asserts them on the cut checklist (anchors kept) |
| `tests/test_settings.py`, `tests/test_config.py` | keep | `test_settings.py:16` clears every name in `_SIGNIFICANT_ENV_VARS`, so the two new variables are covered automatically |
| `tests/test_templates.py:78` | keep | only a comment mentions `skill/types/mail.md` (backlog, Section 5 of the report) |
| all others | keep | unaffected |

Documentation to update (STORY-N unless noted): `AGENTS.md` (command list: `skill`, `skill --type`,
`skill --all`, `skill-audit`; paths `skill/types/*.md`, `skill/workflow-*.md` replaced by
`skill/core.md`, `skill/topics/`; index entry for `docs/skill-archive/`; the "8 tools" statement),
`README.md:132-138,359,383,414` (default of `skill`, eight tools, routing skill text),
`.agent_docs/architecture.md:26` and its module row for `skill_content.py` (eight tools, new modules,
the tool list rule for later specs), `.agent_docs/testing.md` (rows for the new test files and the
anchors file), `dynamic-skills/README.md` (STORY-E). SPEC-0001 is not modified; the count of eight is
recorded in the architecture doc.

## 7. Compatibility and risks

| Risk | Effect | Mitigation |
|---|---|---|
| `mcp-htmleditor skill` changes meaning (core, not everything) | agents that read the old output get less | the routing skill is updated in STORY-E; `--all` reproduces the full text; documented in README |
| Interim states on `main` (stories A to M) | between E and N the shipped tree holds a core and only some topics, so `--type x` of an unmigrated topic answers "not installed" and a real `skill-audit` fails | DEC-016: no legacy fallback (it would be dead code after N and the spec forbids silent skips); the feature is released only after STORY-N; `make check` stays green because shipped content gates run only on files that exist |
| Users already seeded the old 11 856 byte checklist in `~/.config/mcp-htmleditor/arch-checks/` | their `arch-qa` output exceeds 8 000 bytes | accepted by the spec (user checklist printed unchanged, audit measures the shipped one, E2E-017); `make install` never overwrites it; stated in README |
| `registered_tool_names()` uses `asyncio.run` | raises inside a running loop | documented; audit CLI is sync; async tests precompute |
| Later specs add a tool without a core line | the audit and the gate test fail | by design (FR-NEW-008); rule written in 3 and in `.agent_docs/architecture.md` |
| Core grows past 7 000 bytes as tools are added | audit `OVER` | core shipped at most 6 000 bytes (about 1 000 bytes headroom, a line costs about 100 to 150 bytes) |
| Hand written index in `core.md` drifts from `TOPICS` | wrong command in the index | gate test compares every index line to `TOPICS` (E2E-001 plus gate) |
| Content cuts lose a rule | meaning change | priority rule recipe, anchors file, independent review of each content story against the archived source (Section 9) |
| Code comments and tool docstrings point to removed files (`skill/types/arch-diagram.md`, ...) | stale pointers | out of scope, listed as backlog findings |
| Concurrency | none | read only, single call |

## 9. Test strategy

Levels: E2E = CLI through `click.testing.CliRunner` (stdout and stderr separate, exit code), tool
through `fastmcp.Client(mcp)` in async tests; Unit = pure functions. Conventions: `pytest-asyncio`
auto mode, files under `tests/`, coverage stays at least 80 %.

Seams (names fixed here, from the 14.3 design inputs):

| Need | Seam |
|---|---|
| override the bundled skill directory (E2E-009, 010, 013, 016, 020, 023, 026, 028) | `HTMLEDITOR_SKILL_DIR` (`Settings.skill_dir_override`, `config.skill_dir()`); the `skill_tree` fixture in `tests/conftest.py` sets it with `monkeypatch.setenv` and resets the settings cache |
| `skill_tree` fixture | builds a valid temporary skill tree: `core.md` (index lines from `TOPICS`, `## Tools` from a `tools=` argument, default empty), 15 small topics, `checks/arch-diagram-checklist.md`, and `HTMLEDITOR_ARCH_CHECKS_DIR` pointed to an empty temporary directory; helpers `core_path`, `topic_path(name)`, `checklist_path`, `remove(name)`, `grow(path, to_bytes)` (appends ASCII), `write_core(text)` |
| routing skill location (E2E-021, 027) | `HTMLEDITOR_ROUTING_SKILL` (file path, replaces the installed location) plus `monkeypatch.setattr(skill_audit, "source_routing_skill_path", ...)` to simulate "outside a source checkout" |
| user checklist (E2E-017, 025) | existing `HTMLEDITOR_ARCH_CHECKS_DIR` |
| tool list | `registered_tool_names()` injected into `run_audit`; E2E-011 and 012 pass a modified core, not a modified server |
| install (E2E-022) | `subprocess.run(["make", "install-skill", f"PI_SKILLS_DIR={tmp}"], cwd=repo, timeout=60)` (variable is `?=`, `Makefile:37`) |

DEC-015: E2E whose Given reads "the shipped skill where X was changed" run on the `skill_tree`
(valid by construction) because the real content is migrated across stories F to M; the same
behaviors are then asserted on the real tree by the closing story (E2E-006) and by the gate cases
below. E2E-001 derives its expected tool set from `registered_tool_names()` (equality with the
`## Tools` names) and additionally asserts that the eight names at landing (`start_server`,
`stop_server`, `get_status`, `open_file`, `update_start`, `update_end`, `layout_arch_diagram`,
`get_skill`) are a subset, so the literal count of the spec is the set at landing time and later
specs that add tools do not break it (they must add their core line).

Gate cases (not spec E2E ids; they run in `make test`, parametrized over shipped files that exist,
in `tests/test_skill_shipped.py`): per topic `≤ 8 000 bytes` of `topic_output`, first line
`# Skill topic: <t>`, one final newline, no stale statement (`find_stale`), `Reference: <file>` last
line exactly for the six topics of FR-NEW-002 and absent elsewhere, every anchor of
`tests/data/skill_anchors.json` present; for the core `≤ 7 000` and `≤ 6 000` shipped bytes, tools
equal registered tools, index lines equal `TOPICS`. STORY-N flips them from "if the file exists" to
"all 15 files exist". Anchors (DEC-017) are verbatim substrings chosen from the archived source for
every "never", "always", "mandatory" rule and every attribute or class the agent must write; a
review sub-agent, read only and sceptical, compares each content story's topics with the archived
source against the priority rule and reports missing rules before the story is accepted.

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| E2E-002 | E2E | CliRunner `skill --type medical` on `skill_tree` | `tests/test_skill_content.py` | STORY-A |
| E2E-003 | E2E | CliRunner `skill --all` equals core plus topics joined | `tests/test_skill_content.py` | STORY-A |
| E2E-007 | E2E | CliRunner `--type foo`, stderr, exit 2, empty stdout | `tests/test_skill_content.py` | STORY-A |
| E2E-013 | E2E | `skill_tree.remove("gantt")`, `--all` fails, `--type medical` works | `tests/test_skill_content.py` | STORY-A |
| E2E-014 | E2E | `--type gantt --all`, `--type foo --all`, `--type "" --all` | `tests/test_skill_content.py` | STORY-A |
| E2E-015 | E2E | `--type ""` and `--type gantt` alone | `tests/test_skill_content.py` | STORY-A |
| E2E-004 | E2E | `Client(mcp).call_tool("get_skill")` equals CLI stdout | `tests/test_skill_tool.py` | STORY-B |
| E2E-005 | E2E | `get_skill(type="gantt")` equals CLI stdout | `tests/test_skill_tool.py` | STORY-B |
| E2E-008 | E2E | `get_skill(type="foo")` error message | `tests/test_skill_tool.py` | STORY-B |
| E2E-025 | E2E | empty user file, then directory in place of the file | `tests/test_skill_tool.py` | STORY-B |
| E2E-026 | E2E | `gantt` removed, tool error and CLI exit 1 | `tests/test_skill_tool.py` | STORY-B |
| E2E-009 | E2E | `grow(gantt, 8001)`, `skill-audit` | `tests/test_skill_audit.py` | STORY-C |
| E2E-010 | E2E | core grown to 7 001 | `tests/test_skill_audit.py` | STORY-C |
| E2E-016 | E2E | core of 7 000 bytes with 10 `é`, then 7 001; stdin closed | `tests/test_skill_audit.py` | STORY-C |
| E2E-017 | E2E | user checklist in CLI `--type`, `--all`, tool; removal; 9 000 byte file and audit `OK` | `tests/test_skill_audit.py` | STORY-C |
| E2E-020 | E2E | `skill-audit --json` with `mail` at 8 001 | `tests/test_skill_audit.py` | STORY-C |
| E2E-023 | E2E | `website` removed, audit | `tests/test_skill_audit.py` | STORY-C |
| E2E-028 | E2E | core removed: CLI, tool, audit | `tests/test_skill_audit.py` | STORY-C |
| E2E-011 | E2E | add `- frobnicate: ...` to `## Tools`, audit with `tool_names=registered_tool_names()` | `tests/test_skill_audit_checks.py` | STORY-D |
| E2E-012 | E2E | remove the `update_end` line | `tests/test_skill_audit_checks.py` | STORY-D |
| E2E-018 | E2E | `via grapesjs` in `tables` | `tests/test_skill_audit_checks.py` | STORY-D |
| E2E-019 | E2E | `Le serveur expose 8 outils` in core | `tests/test_skill_audit_checks.py` | STORY-D |
| E2E-024 | E2E | fenced `git commit` flagged, fenced `GrapesJS` not | `tests/test_skill_audit_checks.py` | STORY-D |
| E2E-027 | E2E | `HTMLEDITOR_ROUTING_SKILL` to a missing file, source path patched | `tests/test_skill_audit_checks.py` | STORY-D |
| E2E-001 | E2E | CliRunner `skill` on the real tree | `tests/test_skill_shipped.py` | STORY-E |
| E2E-021 | E2E | read `dynamic-skills/html-editor/SKILL.md`, `find_stale` empty | `tests/test_skill_shipped.py` | STORY-E |
| E2E-022 | E2E | `make install-skill PI_SKILLS_DIR=<tmp>`, compare file | `tests/test_skill_shipped.py` | STORY-E |
| E2E-006 | E2E | `skill-audit` on the real tree: 16 `OK` lines, `skill-audit: OK`, exit 0 | `tests/test_skill_shipped.py` | STORY-N |

All 28 spec E2E appear exactly once. Scenarios SC-001 to SC-006 are covered through them
(Section 10 of the spec). Unit level extras inside the same files: `strip_fenced_blocks`
(unclosed fence, `~~~`, longer closing fence), `find_stale` word boundary (`16 outils` does not match
`6 outils`, `15 types` versus `16 types`, apostrophe `’`), `listed_tools`.

## 10. Decisions log

- **DEC-001:** Layout is `skill/core.md`, `skill/topics/<topic>.md`, `skill/checks/arch-diagram-checklist.md`; topic files hold the body only. **Obliged by:** SPEC-0006/FR-NEW-001, FR-NEW-002. **Rationale:** the first line `# Skill topic: <t>` is produced by code so the name has one source; one file per topic maps one to one to the budgets and to the audit lines. **Alternatives considered:** front matter (Approach 2), markers in legacy files (Approach 3). **Source:** design. **Evidence:** `skill_content.py:28-42` (current concatenation list replaced).
- **DEC-002:** `TOPICS` registry (name and description, index order) lives in `skill_content.py`; the index in `core.md` is literal text checked against it by a gate test. **Obliged by:** SPEC-0006/FR-NEW-001, FR-NEW-004. **Rationale:** the valid topic list in the error message, the `--all` order and the audit order need a code constant; a literal core keeps E2E-010 and E2E-016 (grow the file to exact byte counts) simple. **Alternatives considered:** generate the index at render time. **Source:** design. **Evidence:** n/a
- **DEC-003:** `SkillLibrary` (frozen, slots) with injected `skill_dir` and `read_checklist`; `core_output`, `topic_output`, `all_output` return the exact stdout text including the final newline; `--all` is the outputs joined with `\n`. **Obliged by:** SPEC-0006/FR-NEW-003, FR-NEW-006, FR-NEW-007. **Rationale:** the audit measures the bytes the command prints and the tool returns the same bytes; injection lets the audit use the shipped checklist and tests use a temporary tree (project rule: dependencies injected, not created inside classes). **Alternatives considered:** module level functions reading globals. **Source:** design. **Evidence:** `skill_content.py:45-70` builds with hidden globals today.
- **DEC-004:** New setting `HTMLEDITOR_SKILL_DIR` (`skill_dir_override`, `config.skill_dir()` owns the bundled candidates moved from `skill_content.py`). **Obliged by:** SPEC-0006/FR-NEW-004, FR-NEW-007, FR-NEW-010 (missing, grown and removed files cannot be tested otherwise). **Rationale:** spec 14.3 asks for the override; project rule: settings only through `Settings`. **Alternatives considered:** function parameter only (CLI and tool tests could not reach it), monkeypatching a private function (breaks across CLI and tool). **Source:** spec constraint 14.3. **Evidence:** `skill_content.py:15-24`, `config.py:48,61`.
- **DEC-005:** `arch_checks._repo_checks_dir()` returns `config.skill_dir() / "checks"`; `read_checklist()` skips blank or unreadable candidates; new `read_shipped_checklist()`. **Obliged by:** SPEC-0006/FR-NEW-002, FR-NEW-007. **Rationale:** E2E-025 empty or unreadable user file falls back to shipped; the audit measures the shipped copy of the overridden tree. **Alternatives considered:** audit reading the bundled path directly (breaks the override seam). **Source:** spec constraint (FR-NEW-002 business rules). **Evidence:** `arch_checks.py:44-54,57-67`, `tests/test_arch_checks.py:44`.
- **DEC-006:** Errors are `SkillError` subclasses carrying message and exit code; the CLI writes the message with `click.echo(..., err=True)` and exits with `click.exceptions.Exit(code)`. **Obliged by:** SPEC-0006/FR-NEW-004, FR-NEW-005. **Rationale:** the spec demands exactly one line, no usage text, exit 2 for unknown and exit 1 for not installed; `ClickException` and `UsageError` add prefixes or usage. **Alternatives considered:** `click.BadParameter`. **Source:** spec constraint. **Evidence:** n/a
- **DEC-007:** The exclusive options check runs first, `--type ""` counts as given (`topic is not None`). **Obliged by:** SPEC-0006/FR-NEW-005. **Rationale:** the spec fixes precedence. **Alternatives considered:** click `cls=` mutual exclusion (cannot print the required text without usage). **Source:** spec constraint. **Evidence:** n/a
- **DEC-008:** `get_skill(type=None) -> str` returns the same string as the CLI stdout, final newline included; errors raise `ToolError(message)`. **Obliged by:** SPEC-0006/FR-NEW-006, FR-NEW-004. **Rationale:** "the returned text equals the output of the command" read literally means byte equality; one string for both makes the equality structural. **Alternatives considered:** strip the final newline (two readings possible; the literal one is taken). **Source:** design (reading settled here, spec 13 waiver). **Evidence:** `mcp_server.py:30-31` (decorator and docstring style), tool traced like `mcp_server.py:48`.
- **DEC-009:** `registered_tool_names()` in `mcp_server.py` wraps `asyncio.run(mcp.list_tools())`; the audit receives names as a parameter. **Obliged by:** SPEC-0006/FR-NEW-008. **Rationale:** the only public accessor of FastMCP 3.4.6 is async; compared at audit time so any number of tools works (cross-spec binding c). **Alternatives considered:** private `_tool_manager` (breaks on upgrade), a hand kept list (drifts). **Source:** spec constraint plus design. **Evidence:** `mcp_server.py:30-166` (decorator registration, no accessor), run check listing 7 names in order.
- **DEC-010:** Tool list parsing reads `- <name>:` line starts in the `## Tools` section of `core.md`; a story that registers a tool adds its line in that story; core shipped at most 6 000 bytes. **Obliged by:** SPEC-0006/FR-NEW-008, FR-NEW-001. **Rationale:** binding for SPEC-0007 to 0010; headroom keeps the 7 000 byte budget. **Alternatives considered:** generate the tool section from the registry (core no longer literal). **Source:** spec constraint plus cross-spec context. **Evidence:** n/a
- **DEC-011:** Stale scanner is a regex list with whole word guards, fence stripping (backtick and tilde fences, unclosed fence runs to the end), `git commit` scanned unstripped, per location dedupe. **Obliged by:** SPEC-0006/FR-NEW-009. **Rationale:** spec matching rules transcribed one to one. **Alternatives considered:** a Markdown parser (new dependency). **Source:** spec constraint. **Evidence:** n/a
- **DEC-012:** Routing skill lookup: `HTMLEDITOR_ROUTING_SKILL` (default `~/.pi/agent/dynamic-skills/html-editor/SKILL.md`), else `source_routing_skill_path()` (`<repo>/dynamic-skills/html-editor/SKILL.md` from `__file__`, independent of the cwd); not bundled in the wheel. **Obliged by:** SPEC-0006/FR-NEW-009. **Rationale:** the spec defines exactly these two locations and `routing skill not found` when neither exists; E2E-027 needs the first replaceable (setting) and the second replaceable (patch of the named function). **Alternatives considered:** force include in the wheel (would make "not found" unreachable outside a checkout, contradicting E2E-027's Given). **Source:** spec constraint. **Evidence:** `Makefile:37,190`, `pyproject.toml:48-52`.
- **DEC-013:** The audit renders items through the same `*_output()` with a library whose checklist reader is `read_shipped_checklist`; token estimate `ceil(bytes/4)`; boundary `size <= budget` passes. **Obliged by:** SPEC-0006/FR-NEW-007. **Rationale:** spec definition of size. **Alternatives considered:** measuring files. **Source:** spec constraint. **Evidence:** n/a
- **DEC-014:** `skill-audit` has no `make` target; the real tree audit runs inside `make test` (E2E-006). **Obliged by:** SPEC-0006/FR-NEW-007 (usable in a build gate through status codes). **Rationale:** `make check` already runs tests; a new target would be speculative. **Alternatives considered:** `make skill-audit`, adding it to `check`. **Source:** design. **Evidence:** `Makefile:139`.
- **DEC-015:** E2E whose Given is a modified shipped tree run on a generated `skill_tree`; real content is checked by gate cases and E2E-006/001. **Obliged by:** SPEC-0006/FR-NEW-007, FR-NEW-004 (tests must exist before the content does). **Rationale:** lets machinery stories land green while content stories land one by one. **Alternatives considered:** one giant content story first (violates 3 to 5 files). **Source:** design. **Evidence:** n/a
- **DEC-016:** Migration order: machinery (A to D), core (E), content stories (F to M), closing (N). Each content story `git mv`s its legacy source into `docs/skill-archive/` and ships its new topics; no legacy fallback, the audit stays strict (missing means problem); the work is released only after N. **Obliged by:** SPEC-0006/FR-NEW-002 (removed text kept in documentation), FR-NEW-010 (missing is a problem). **Rationale:** the spec allows no tolerance of unmigrated topics, so tolerance lives only in the content gate (runs on files that exist) and the real tree audit lands last. **Alternatives considered:** raise min_tier and bundle all content (about 40 files, far above 5), a "pending topics" list in the audit (contradicts FR-NEW-010). **Source:** design. **Evidence:** n/a
- **DEC-017:** `tests/data/skill_anchors.json` plus the review sub-agent make the priority rule checkable. **Obliged by:** SPEC-0006/FR-NEW-002. **Rationale:** budgets are machine checked, "keep every never rule" is not; anchors turn the listed rules into assertions. **Alternatives considered:** review only. **Source:** design. **Evidence:** n/a
- **DEC-018:** Content recipe for every topic story: (1) `git mv` the legacy source to the archive; (2) list rules with `rg -n "jamais|toujours|obligatoire|MUST|NEVER|ne pas"` on the archive; (3) write the topic: keep rules, then names (attributes, classes) from the kept example and one table of at most 1 500 bytes, then one complete example; drop rationale paragraphs first, then secondary examples; (4) remove stale statements (GrapesJS, `6 outils`, `15 types`, `localhost:7842` as a rule, forced `git commit`, the dated defect list stays only in the archive); (5) replace pointers to legacy files by `mcp-htmleditor skill --type <topic>`; (6) end with `Reference: <file>` for the six topics of FR-NEW-002; (7) add anchors; (8) run the gate. Slides: shared sections appear in both slides topics, class correspondence table in `slides-ei` only; medical sections 1 to 6 and 9 to 12 to `medical`, 7 and 8 to `medical-sources`. **Obliged by:** SPEC-0006/FR-NEW-002. **Rationale:** the spec's priority rule and source mapping, made operational. **Alternatives considered:** none. **Source:** spec constraint. **Evidence:** `skill/types/medical.md` (29 818 bytes), `skill/types/slides.md` (27 769) sizes.
- **DEC-019:** `arch-qa` topic is `workflow text (≤ 3 800) + "\n\n" + checklist (≤ 3 800)` under its first line; the cut checklist keeps `2 passes` and `arch-col` anchors. **Obliged by:** SPEC-0006/FR-NEW-002. **Rationale:** budget arithmetic from the spec (8 000 total). **Alternatives considered:** none. **Source:** spec constraint. **Evidence:** `tests/test_arch_checks.py:22-26`.

## 11. Stories

All stories are tier 2, vertical, leave `make check` green. "Tests" in content stories are gate cases
(Section 9) because the text itself is the deliverable; they run for the topic files the story ships.

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| STORY-A | Topic engine and `skill --type/--all` (library, errors, settings seam, fixture) | P1 | FR-NEW-002, 003, 004, 005 | main | 2 | no |
| STORY-B | `get_skill` tool and checklist fallback | P1 | FR-NEW-002, 004, 006 | STORY-A | 2 | no |
| STORY-C | `skill-audit` report: sizes, budgets, missing items, JSON | P1 | FR-NEW-002, 004, 007, 010 | STORY-B | 2 | no |
| STORY-D | Audit tool list check and stale statement check | P1 | FR-NEW-007, 008, 009 | STORY-C | 2 | no |
| STORY-E | Core text, routing skill, shipped content gates | P1 | FR-NEW-001, 009 | STORY-D | 2 | no |
| STORY-F | Topics `slides-carbon` and `slides-ei` | P1 | FR-NEW-002, 007, 009 | STORY-E | 2 | no |
| STORY-G | Topics `medical` and `medical-sources` | P1 | FR-NEW-002, 007, 009 | STORY-E | 2 | no |
| STORY-H | Topics `create` and `export` | P1 | FR-NEW-002, 007, 009 | STORY-E | 2 | no |
| STORY-I | Topics `document` and `mail` | P1 | FR-NEW-002, 007, 009 | STORY-E | 2 | no |
| STORY-J | Topics `website` and `tables` | P1 | FR-NEW-002, 007, 009 | STORY-E | 2 | no |
| STORY-K | Topics `gantt` and `annotated-image` | P1 | FR-NEW-002, 007, 009 | STORY-E | 2 | no |
| STORY-L | Topics `arch-diagram` and `templates` | P1 | FR-NEW-002, 007, 009 | STORY-E | 2 | no |
| STORY-M | Topic `arch-qa` and the cut shipped checklist | P1 | FR-NEW-002, 007, 009 | STORY-E | 2 | no |
| STORY-N | Clean real audit, all 15 topics enforced, documentation | P1 | FR-NEW-007, 008, 009 | STORY-F..M | 2 | yes |

Notes on slicing and deviations (stated, not hidden):

* Test counts: A 6, B 5, C 7, D 6 E2E; E 3 E2E plus about 4 core gate cases; F to M carry no spec E2E
  (their acceptance is 3 to 4 gate cases per topic, so 6 to 12 cases for two topics, inside 5 to 15);
  N carries E2E-006 plus the "all 15 files exist" and real `--all` gate cases (below 5 acceptance
  tests, because everything else closed earlier; it cannot be merged into a previous story without
  breaking the 5 file cap).
* Files per story: A 5, B 4, C 3, D 5, E 5, F 4, G 4, H 5, I 5, J 5, K 5, L 5, M 5, N 5.
* Cross-spec: SPEC-0007, 0008, 0009, 0010 each add their `- <name>: <description>` line to the
  `## Tools` section of `skill/core.md` in the story that registers the tool (Section 3); E2E-001
  and the gate derive the expected tools from the registered set, the literal eight of the spec is the
  set at landing time.
* Command evidence for counts: `rg -o 'FR-NEW-[0-9]{3}' spec.md | sort -u` gives 10,
  `rg -o 'E2E-[0-9]{3}' spec.md | sort -u` gives 28, `rg -o 'SC-[0-9]{3}' spec.md | sort -u` gives 6.
  Every FR-NEW is cited by at least one story (001 E; 002 A,B,C,F..M; 003 A; 004 A,B,C; 005 A; 006 B;
  007 C,D,F..N; 008 D,N; 009 D,E,F..N; 010 C). The last story, STORY-N, closes the spec once.
