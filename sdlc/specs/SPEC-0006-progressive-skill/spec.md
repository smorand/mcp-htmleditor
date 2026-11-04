# Progressive skill loading and skill budget audit: functional specification

> Id: SPEC-0006
> Nature: FEAT
> Depth: L
> Depth evidence: 4 areas touched (skill text, command line, agent tool surface, installed routing skill), a new audit command, more than 10 anticipated requirements
> Status: implemented
> Generated on: 2026-11-03
> Project: existing
> From backlog: n/a
> Depends on: none
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Summary

Today an agent that needs one small edit receives the whole skill, about 198 000 bytes, roughly
50 000 tokens, including rules for charters it will never touch. This increment gives the agent a
short core (at most 7 000 bytes) and 15 on demand topics (at most 8 000 bytes each), the same text
through the command line and through the agent tool surface, and an audit command that keeps the
size and the accuracy of that text under control.

## 2. Current State

### 2.1 What users can do today

- `mcp-htmleditor skill` prints one block: the index, 13 sub documents and the architecture
  checklist, about 198 000 bytes in total. There is no option to print less.
- The block is reachable only through the command line. An agent connected through the tool
  protocol alone cannot read the skill.
- The installed routing skill tells the agent to run `mcp-htmleditor skill` and to read the whole
  output.
- The text contradicts the product in several places: it says the tool protocol exposes 6 tools
  (it exposes 7), says the medical charter has 15 slide types in one line and 16 elsewhere, says
  the browser editor is GrapesJS, hard codes `http://localhost:7842` in a rule while telling the
  agent elsewhere never to assume that port, orders a git commit after each edit, and carries a
  dated list of known export defects.
- Nothing measures the skill size or checks the skill text against the product.

### 2.2 Specs governing this area

- SPEC-0001 FR-025: the skill prints in full. This increment replaces that default; the full print
  stays available with `--all`. SPEC-0001 is not modified.
- SPEC-0001 FR-009 ("exactly seven operations") is contradicted by this increment, which adds the
  tool `get_skill` and makes eight. SPEC-0001 is not modified; the count of eight is recorded here.
  The tool list check below compares the skill with whatever tools exist at the time.

### 2.3 What is verified today

One test checks that the assembled skill contains its index title and a sub document marker and is
longer than 2 000 characters. Nothing checks size, topics, contradictions or the tool list.

## 3. Scope

### 3.1 In scope

- A short core plus 15 topics, selectable on the command line and through the agent tool surface.
- A full print option that reproduces the former behavior.
- An audit command, with a machine readable output, that checks size budgets, the tool list and a
  list of stale statements.
- Rewriting the skill text so that every part fits its budget, with the contradictions of Section 2.1
  removed. Text that does not fit is cut by the priority rule of FR-NEW-002 and the removed text is
  kept in the project documentation, not deleted.
- Updating the installed routing skill.

### 3.2 Out of scope, and why

- Tools that read or patch slides: SPEC-0007.
- Rendering and visual checks: SPEC-0008.
- Making the medical export defects disappear: SPEC-0011. The dated defect list leaves the skill
  and is kept in project documentation until then.
- A user override directory for the skill text: not asked; the architecture checklist keeps its
  existing user editable location.
- Rewording the rules themselves: rules are split, shortened by the priority rule, never changed in meaning.

### 3.3 Constraints imposed by the context

- Nothing is ever written on the standard output of the tool protocol process other than protocol
  messages (project rule), so the audit and the skill print are command line features and the
  agent tool returns text.
- Specs already written are not edited (project rule).

## 4. Actors

| Actor | Description |
|---|---|
| Agent | A language model driving the editor through the command line or the tool protocol |
| Maintainer | The person who edits the skill text and releases the tool |

## 4.5 Bounded contexts

| Context | What it owns | Key concepts |
|---|---|---|
| Skill | the text an agent reads, how it is split, how its size is controlled | core, topic, budget, stale statement |
| Agent tools | the operations an agent can call | tool, tool list |

## 5. Usage scenarios

### SC-001: An agent starts a task
**Actor:** Agent
**Preconditions:** the tool is installed; the agent has not read the skill yet.
**Flow:**
1. The agent runs `mcp-htmleditor skill` → the core is printed: absolute rules, the workflow, the list of tools, and an index of 15 topics, each with one line of description and the command to load it.
2. The agent picks the topics its task needs → it knows exactly which commands to run.
**Postconditions:** the agent has read at most 7 000 bytes.
**Exceptions:**
- EXC-001a: the agent only has the tool protocol → see SC-004.
**Interactions:** SC-002.

### SC-002: An agent loads one topic
**Actor:** Agent
**Preconditions:** the agent has read the core.
**Flow:**
1. The agent runs `mcp-htmleditor skill --type medical` → only the medical topic is printed, at most 8 000 bytes.
2. For the sources and anonymisation rules the agent runs `mcp-htmleditor skill --type medical-sources`.
**Postconditions:** the agent holds only the rules it needs.
**Exceptions:**
- EXC-002a: the topic name is wrong → error message listing valid topics.
- EXC-002b: the topic file is missing from the installation → error message.
- EXC-002c: the agent passes both a topic and the full print option → usage error.
**Interactions:** SC-001.

### SC-003: An agent or a maintainer wants everything
**Actor:** Agent or Maintainer
**Preconditions:** none.
**Flow:**
1. The actor runs `mcp-htmleditor skill --all` → the core followed by every topic in index order is printed.
**Postconditions:** the output holds every rule of the product.
**Exceptions:**
- EXC-003a: a topic is missing from the installation → the same error as in SC-002.

### SC-004: An agent that only has the tool protocol
**Actor:** Agent
**Preconditions:** the agent is connected through the tool protocol only.
**Flow:**
1. The agent calls the tool `get_skill` without argument → it receives the core.
2. The agent calls `get_skill` with the argument `type` set to `gantt` → it receives the gantt topic.
**Postconditions:** the agent got the same text as a command line user.
**Exceptions:**
- EXC-004a: unknown topic → error result with the message of SC-002.
- EXC-004b: missing topic → error result with the message of SC-002.

### SC-005: A maintainer audits the skill
**Actor:** Maintainer
**Preconditions:** the skill text was edited.
**Flow:**
1. The maintainer runs `mcp-htmleditor skill-audit` → one line per item (core, then topics) with size, estimated tokens, budget and verdict, then problems found, then a final verdict.
2. The maintainer fixes the problems and runs the command again.
**Postconditions:** exit status 0 when every check passes.
**Exceptions:**
- EXC-005a: a topic or the core is over its budget → the item is marked `OVER`, the final verdict is a failure, exit status 1.
- EXC-005b: a tool is listed in the core but does not exist, or exists and is not listed → problem lines, failure.
- EXC-005c: a stale statement is found → problem line naming the statement and where, failure.
- EXC-005d: a topic file is missing → problem line, failure.
**Interactions:** SC-001, SC-002.

### SC-006: A user customised the architecture checklist
**Actor:** Agent
**Preconditions:** the user edited the checklist at its user editable location.
**Flow:**
1. The agent loads the `arch-qa` topic, alone or through the full print → the user's checklist content is part of the output on that very call, with no reinstall.
**Postconditions:** edits are visible immediately.

## 6. Functional requirements

### 6.1 New

#### FR-NEW-001 [EARS-E]: Core by default
> WHEN a user runs `mcp-htmleditor skill` without option THE Skill SHALL print the core, at most 7 000 bytes, containing the absolute rules, the workflow, the list of tools, and an index of the 15 topics with, for each, one line of description and the exact command that loads it.

- **Business rules:** the core contains the 8 absolute rules of the former skill index (bracket every file change with `update_start` and `update_end`; never remove `data-type`, `data-id` or `data-title` on slides; put `data-editable="text"` on editable text; rewrite the complete HTML; images relative to the file or in base64; never start a second server when `get_status` reports one running; validate the rendering visually after each substantial change; treat a modification found in the file as deliberate), the 6 step workflow, and the command `mcp-htmleditor new <template> <file>` with the keys `ei, carbon, medical, doc, doc-perso, doc-ei, mail, website`. If the core is not installed, `mcp-htmleditor skill` and `get_skill` without argument print `Skill core is not installed` and exit with status 1. The 15 topics are `create`, `export`, `templates`, `slides-carbon`, `slides-ei`, `medical`, `medical-sources`, `document`, `mail`, `website`, `gantt`, `arch-diagram`, `arch-qa`, `annotated-image`, `tables`, in that order. The core does not state how many tools exist, it lists them. The installed routing skill tells the agent to read the core, then to load topics with `--type` according to the task, and no longer tells it to read everything.
- **User visible text:** the first line of the core is `# mcp-htmleditor skill (core)`. Tools are listed in one section headed `## Tools`, one line per tool of the shape `- <name>: <description>`, `get_skill` included. Index line shape: `<topic>: <description>. Load: mcp-htmleditor skill --type <topic>` with these descriptions:

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

- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-002 [EARS-E]: One topic
> WHEN a user runs `mcp-htmleditor skill --type <topic>` with one of the 15 topics THE Skill SHALL print that topic only, at most 8 000 bytes.

- **Business rules:** the topic output does not repeat the core. Its first line is `# Skill topic: <topic>`. The `arch-qa` topic contains the architecture checklist read from the user editable location at the time of the call, and the shipped checklist when the user has none; a user checklist larger than the shipped one is printed unchanged. Each topic keeps, in this priority order, (1) every absolute rule and every "never" rule of its source text, (2) every attribute and class name the agent must write, (3) one complete example; and drops, in this order, long rationale paragraphs, then secondary examples. Source text to topic: workflow-create to `create`; workflow-export to `export`; workflow-templates to `templates`; slides, Carbon part to `slides-carbon`; slides, Euro-Information part to `slides-ei`; medical sections 1 to 6 and 9 to 12 to `medical`; medical sections 7 and 8 to `medical-sources`; document to `document`; mail to `mail`; website to `website`; gantt to `gantt`; arch-diagram to `arch-diagram`; workflow-arch-qa plus the checklist to `arch-qa`; annotated-image to `annotated-image`; tables to `tables`. Sections of the `slides` source that serve both charters (file structure, insertable types, renumbering, height budget, adding a slide, PPTX conversion) appear in both `slides-carbon` and `slides-ei`, each shortened by the same priority rule; the class correspondence table appears in `slides-ei` only. Names kept under rule (2) are those appearing in the kept example and in one table of at most 1 500 bytes; the topics `slides-carbon`, `slides-ei`, `medical`, `document`, `mail` and `website` end with a line `Reference: <template file>` naming respectively `templates/reference/slides/ibm-carbon.html`, `templates/reference/slides/example-ei-complete.html`, `templates/reference/slides/medical.html`, `templates/reference/documents/report-standard.html`, `templates/reference/documents/mail-carbon-example.html` and `templates/reference/websites/ibm-carbon.html`; other topics have no such line. The shipped checklist is at most 3 800 bytes and the shipped arch-qa workflow text at most 3 800 bytes, so that the `arch-qa` output, with its first line and separators, is at most 8 000 bytes. IF the user checklist file is empty or unreadable THEN the shipped checklist is used.
- **Scenario:** SC-002, SC-006
- **Priority:** Must

#### FR-NEW-003 [EARS-E]: Full print
> WHEN a user runs `mcp-htmleditor skill --all` THE Skill SHALL print the core followed by every topic in the index order.

- **Business rules:** the output of `--all` is the core output followed by each topic output in index order, each separated from the next by one empty line, and ending with one newline. The user's checklist is part of it.
- **Scenario:** SC-003, SC-006
- **Priority:** Must

#### FR-NEW-004 [EARS-O]: Topic selection errors
> IF the requested topic is unknown, empty, or not installed (or the core is not installed) THEN THE Skill SHALL print an error message naming the problem and SHALL NOT print any skill text.

- **Business rules:** exit status 2 for an unknown or empty topic, 1 for a topic that is not installed. The same two messages are returned as an error by the agent tool.
- **Business rules:** the error output is exactly one line, the message below, followed by a newline (for the usage error of FR-NEW-005 with its `Error: ` prefix), with no usage text, and the standard output is empty. `--type <topic>` and `get_skill(type)` do not read the core and succeed when the core is missing; `--all` with the core missing fails with `Skill core is not installed` (exit 1) before any topic; with several missing parts the first in index order (core first) is reported.
- **User visible text:** `Unknown skill topic "foo". Valid topics: create, export, templates, slides-carbon, slides-ei, medical, medical-sources, document, mail, website, gantt, arch-diagram, arch-qa, annotated-image, tables` and `Skill topic "gantt" is not installed`. An empty topic is reported as `Unknown skill topic "". Valid topics: ...`.
- **Scenario:** SC-002, SC-004
- **Priority:** Must

#### FR-NEW-005 [EARS-UB]: Exclusive options
> The Skill command SHALL NOT accept `--type` and `--all` in the same call.

- **Business rules:** the call fails with a usage error (exit status 2) and prints no skill text. This check runs before the topic validation: `--type foo --all` prints this message, not the unknown topic message.
- **Business rules (continued):** `--type` counts as given even with an empty value: `--type "" --all` prints the message below and exits with status 2.
- **User visible text:** `Error: --type and --all cannot be used together`
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-006 [EARS-E]: Skill through the agent tool surface
> WHEN an agent calls the tool `get_skill` THE Skill SHALL return the same text as `mcp-htmleditor skill`, and the same text as `mcp-htmleditor skill --type <topic>` when the argument `type` is given.

- **Business rules:** no argument returns the core. An unknown, empty or not installed topic returns the messages of FR-NEW-004 as an error.
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-007 [EARS-E]: Audit report
> WHEN a maintainer runs `mcp-htmleditor skill-audit` THE Skill SHALL print one line per item (the core, then each topic in index order) with its size in bytes, its estimated tokens, its budget and its verdict, then one line per problem found, then a final verdict, and exit with status 0 when no problem is found and 1 otherwise.

- **Business rules:** the size of `arch-qa` is measured on the shipped checklist and the shipped arch-qa workflow text, never on a user checklist. When the core is not installed, the tool list check and the stale statement check of the core are skipped, so the only problem raised for the core is `core is not installed`. Size counts every byte the command writes on the standard output, including its single final newline. Problems are printed in this order: for each item in index order (core first) its missing or over budget problem; then the tool list problems (listed but not provided, in the order of the `## Tools` lines, then provided but not listed, in registration order); then stale statements by location (core, topics in index order, routing skill), each location in the order of the stale statement list; then `routing skill not found`. A topic that is not installed prints the item line `<topic>: MISSING` and counts as one problem. If the core is not installed the audit prints the item line `core: MISSING`, the line `PROBLEM core is not installed`, and still audits the topics. Size is the number of bytes of the UTF 8 text the corresponding command prints; estimated tokens are the size divided by 4, rounded up. Budgets: core 7 000 bytes, each topic 8 000 bytes; a size equal to the budget passes, one byte more is `OVER`. With `--json` the same facts are printed as one JSON object holding, for the core and each topic, the name, the bytes, the tokens, the budget and the status, plus the list of problems and the final verdict; the exit status is the same.
- **User visible text:** an item over its budget also prints `PROBLEM <item> is over its budget (<bytes> > <budget>)` where `<item>` is `core` or `topic <name>`, and counts as one problem. The `--json` object is `{"items":[{"name","bytes","tokens","budget","status"}],"problems":[strings],"verdict":"OK"|"FAIL"}`; `status` is `OK`, `OVER` or `MISSING`; a missing item has `bytes` and `tokens` null and its budget value; each string of `problems` is the matching `PROBLEM` line without the `PROBLEM ` prefix. Item line `core: 6120 bytes, ~1530 tokens (budget 7000) OK` or `... OVER`; final line `skill-audit: OK` or `skill-audit: FAIL (3 problems)` (`1 problem` in the singular).
- **Scenario:** SC-005
- **Priority:** Must

#### FR-NEW-008 [EARS-E]: Tool list check
> WHEN the audit runs THE Skill SHALL report as a problem every tool that the core lists and that the product does not provide, and every tool that the product provides and that the core does not list.

- **Business rules:** only the names at the start of the lines of the core section `## Tools` are read. The tools the product provides are compared at audit time, so the list is correct whatever the number of tools.
- **User visible text:** `PROBLEM tool "foo" is listed in the core but does not exist` and `PROBLEM tool "bar" exists but is not listed in the core`.
- **Scenario:** SC-005
- **Priority:** Must

#### FR-NEW-009 [EARS-E]: Stale statement check
> WHEN the audit runs THE Skill SHALL report as a problem each stale statement found in the core, in a topic or in the installed routing skill.

- **Business rules:** the matching ignores letter case and matches whole words only (`16 types` and `16 outils` do not match `6 outils` or `15 types`); text inside fenced code blocks is ignored. The stale statements are: `GrapesJS`, `6 outils`, `15 types`, `localhost:7842`, `git commit`, `Défauts d'export mesurés`; and, in the core and in the installed routing skill only, any number directly followed by the word `outils` or `tools`. The words "never assume 7842" are not stale. `git commit` is detected inside and outside fenced code blocks; every other statement is ignored inside them. A whole word match means the statement is not directly preceded or followed by a letter, a digit or an underscore; whitespace inside a statement matches one or more whitespace characters; the apostrophe of `Défauts d'export mesurés` matches `'` and `’`. The location is `in core`, `in topic <name>` or `in routing skill`; the quoted statement is the matched text in lower case; one problem line is printed per distinct statement per location, however many times it occurs there. The routing skill checked is, in order, the installed file `~/.pi/agent/dynamic-skills/html-editor/SKILL.md` and, only when that file is absent, the routing skill file of the source tree the running tool was started from, whatever the current directory; when the installed file exists only it is checked; if neither exists the audit prints `PROBLEM routing skill not found` and counts one problem.
- **User visible text:** `PROBLEM stale statement "grapesjs" in topic gantt`
- **Scenario:** SC-005
- **Priority:** Must

#### FR-NEW-010 [EARS-O]: Missing topic during the audit
> IF a topic of the index is not installed THEN THE Skill audit SHALL report it as a problem and SHALL still audit the other items.

- **User visible text:** `PROBLEM topic "gantt" is not installed`
- **Scenario:** SC-005
- **Priority:** Must

## 7. Non functional requirements (user observable)

No non functional requirement is added: no performance, access, privacy or accessibility rule is
touched, and the audit is usable in a build gate through the status codes of FR-NEW-007 (no prompt
is ever shown).

## 8. Edge cases

| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Boundary values | core of exactly 7 000 bytes, then 7 001 | passes, then `OVER` | E2E-016 |
| Boundary values | accented text | size counted in bytes, not characters | E2E-016 |
| Boundary values | user checklist larger than the shipped one | printed unchanged, audit unaffected | E2E-017 |
| Empty states | `--type ""` | unknown topic message | E2E-015 |
| Data variations | stale statement in lower case | detected | E2E-018 |
| Access states | user checklist present, then absent | user text, then shipped text | E2E-017 |
| Partial operations | one topic missing during `--all` | not installed error, no partial text | E2E-013 |
| Partial operations | core missing | `Skill core is not installed`, audit still checks topics | E2E-028 |
| Data variations | user checklist empty or unreadable | shipped checklist used | E2E-025 |
| Access states | routing skill file absent | `PROBLEM routing skill not found` | E2E-027 |
| Ordering | topics in `--all` and in the audit | index order | E2E-003, E2E-006 |
| Concurrent actions, connectivity, navigation, exhaustion, timing | not applicable: single call, read only | none | none |

## 9. Acceptance tests (the contract)

### 9.1 Summary

| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | journey | SC-001 | FR-NEW-001 | Critical |
| E2E-002 | New | journey | SC-002 | FR-NEW-002, FR-NEW-005 | Critical |
| E2E-003 | New | journey | SC-003 | FR-NEW-003, FR-NEW-005 | High |
| E2E-004 | New | journey | SC-004 | FR-NEW-006 | High |
| E2E-005 | New | journey | SC-004 | FR-NEW-006 | High |
| E2E-006 | New | journey | SC-005 | FR-NEW-007, FR-NEW-008, FR-NEW-009 | Critical |
| E2E-007 | New | failure | SC-002 | FR-NEW-004 | Critical |
| E2E-008 | New | failure | SC-004 | FR-NEW-004, FR-NEW-006 | High |
| E2E-009 | New | failure | SC-005 | FR-NEW-007 | Critical |
| E2E-010 | New | failure | SC-005 | FR-NEW-001, FR-NEW-007 | Critical |
| E2E-011 | New | failure | SC-005 | FR-NEW-008 | High |
| E2E-012 | New | failure | SC-005 | FR-NEW-008 | High |
| E2E-013 | New | failure | SC-003 | FR-NEW-003, FR-NEW-004, FR-NEW-010 | High |
| E2E-014 | New | failure | SC-002 | FR-NEW-004, FR-NEW-005 | Medium |
| E2E-015 | New | edge | SC-002 | FR-NEW-002, FR-NEW-004, FR-NEW-005 | Medium |
| E2E-016 | New | edge | SC-005 | FR-NEW-001, FR-NEW-007 | High |
| E2E-017 | New | edge | SC-006 | FR-NEW-002, FR-NEW-003, FR-NEW-006, FR-NEW-007 | High |
| E2E-018 | New | edge | SC-005 | FR-NEW-009 | High |
| E2E-019 | New | failure | SC-005 | FR-NEW-001, FR-NEW-009 | Medium |
| E2E-020 | New | edge | SC-005 | FR-NEW-007 | Medium |
| E2E-021 | New | side effect | SC-001 | FR-NEW-001, FR-NEW-009 | Medium |
| E2E-022 | New | side effect | SC-001 | FR-NEW-001 | Low |
| E2E-023 | New | failure | SC-005 | FR-NEW-010 | High |
| E2E-024 | New | failure | SC-005 | FR-NEW-009 | High |
| E2E-025 | New | failure | SC-006 | FR-NEW-002 | High |
| E2E-026 | New | failure | SC-004 | FR-NEW-004, FR-NEW-006, FR-NEW-010 | High |
| E2E-027 | New | failure | SC-005 | FR-NEW-009 | Medium |
| E2E-028 | New | failure | SC-005 | FR-NEW-001, FR-NEW-004, FR-NEW-007 | High |

Coverage: happy 6, failure 15, side effect 2, edge 5 (28 tests). Happy to failure ratio 1:2.5 (beats 1:1).

### 9.2 New tests

#### E2E-001: The core by default
- **Category:** journey
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001
- **Given** the tool is installed with the shipped skill
- **When** the user runs `mcp-htmleditor skill`
- **Then** the output is at most 7 000 bytes
- **And** it contains an index with exactly the 15 topics in the order `create, export, templates, slides-carbon, slides-ei, medical, medical-sources, document, mail, website, gantt, arch-diagram, arch-qa, annotated-image, tables`, each line of the shape `<topic>: <description>. Load: mcp-htmleditor skill --type <topic>`
- **And** its first line is `# mcp-htmleditor skill (core)`, it has a section headed `## Tools`, and that section holds one line `- <name>: <description>` for each of the 8 tools `start_server`, `stop_server`, `get_status`, `open_file`, `update_start`, `update_end`, `layout_arch_diagram`, `get_skill`
- **And** the index line of `medical` reads `medical: Rules for medical slides: layouts, light and dark surfaces, widths, readability, height budget. Load: mcp-htmleditor skill --type medical`
- **Priority:** Critical

#### E2E-002: One topic only
- **Category:** journey
- **Scenario:** SC-002
- **Requirements:** FR-NEW-002, FR-NEW-005
- **Given** the shipped skill
- **When** the user runs `mcp-htmleditor skill --type medical`
- **Then** the output is at most 8 000 bytes
- **And** `mcp-htmleditor skill --type medical` alone is accepted (exit status 0)
- **And** its first line is `# Skill topic: medical`, and it contains neither `# mcp-htmleditor skill (core)` nor `# Skill topic: gantt`
- **Priority:** Critical

#### E2E-003: Full print
- **Category:** journey
- **Scenario:** SC-003
- **Requirements:** FR-NEW-003, FR-NEW-005
- **Given** the shipped skill
- **When** the user runs `mcp-htmleditor skill --all`
- **Then** `--all` alone is accepted (exit status 0) and the output equals the core output followed by the output of `--type` for each of the 15 topics in index order, each separated from the next by one empty line, and ends with one newline
- **Priority:** High

#### E2E-004: Core through the tool surface
- **Category:** journey
- **Scenario:** SC-004
- **Requirements:** FR-NEW-006
- **Given** an agent connected through the tool protocol
- **When** it calls `get_skill` with no argument
- **Then** the returned text equals the output of `mcp-htmleditor skill`
- **Priority:** High

#### E2E-005: Topic through the tool surface
- **Category:** journey
- **Scenario:** SC-004
- **Requirements:** FR-NEW-006
- **Given** an agent connected through the tool protocol
- **When** it calls `get_skill` with `type` set to `gantt`
- **Then** the returned text equals the output of `mcp-htmleditor skill --type gantt`
- **Priority:** High

#### E2E-006: A clean audit
- **Category:** journey
- **Scenario:** SC-005
- **Requirements:** FR-NEW-007, FR-NEW-008, FR-NEW-009
- **Given** the shipped skill
- **When** the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the output has 16 item lines, `core` first then the 15 topics in index order, each ending with `OK`
- **And** the last line is `skill-audit: OK` and the exit status is 0
- **And** no line starts with `PROBLEM`
- **Priority:** Critical

#### E2E-007: Unknown topic on the command line
- **Category:** failure
- **Scenario:** SC-002
- **Requirements:** FR-NEW-004
- **Given** the shipped skill
- **When** the user runs `mcp-htmleditor skill --type foo`
- **Then** the error output is `Unknown skill topic "foo". Valid topics: create, export, templates, slides-carbon, slides-ei, medical, medical-sources, document, mail, website, gantt, arch-diagram, arch-qa, annotated-image, tables` and the exit status is 2
- **And** nothing is printed on the standard output
- **Priority:** Critical

#### E2E-008: Unknown topic through the tool surface
- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-004, FR-NEW-006
- **Given** an agent connected through the tool protocol
- **When** it calls `get_skill` with `type` set to `foo`
- **Then** it receives an error whose message is the one of E2E-007
- **Priority:** High

#### E2E-009: A topic over its budget
- **Category:** failure
- **Scenario:** SC-005
- **Requirements:** FR-NEW-007
- **Given** the shipped skill where the `gantt` topic has been grown to 8 001 bytes
- **When** the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the line of `gantt` reads `gantt: 8001 bytes, ~2001 tokens (budget 8000) OVER`
- **And** the output contains `PROBLEM topic gantt is over its budget (8001 > 8000)`
- **And** the last line is `skill-audit: FAIL (1 problem)` and the exit status is 1
- **And** every other item line still ends with `OK`
- **Priority:** Critical

#### E2E-010: A core over its budget
- **Category:** failure
- **Scenario:** SC-005
- **Requirements:** FR-NEW-001, FR-NEW-007
- **Given** the shipped skill where the core has been grown to 7 001 bytes
- **When** the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the line of `core` reads `core: 7001 bytes, ~1751 tokens (budget 7000) OVER`
- **And** the output contains `PROBLEM core is over its budget (7001 > 7000)`
- **And** the last line is `skill-audit: FAIL (1 problem)` and the exit status is 1
- **Priority:** Critical

#### E2E-011: A listed tool that does not exist
- **Category:** failure
- **Scenario:** SC-005
- **Requirements:** FR-NEW-008
- **Given** the shipped skill where the section `## Tools` of the core also holds the line `- frobnicate: does nothing`
- **When** the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the output contains `PROBLEM tool "frobnicate" is listed in the core but does not exist`
- **And** the exit status is 1
- **Priority:** High

#### E2E-012: A tool missing from the core
- **Category:** failure
- **Scenario:** SC-005
- **Requirements:** FR-NEW-008
- **Given** the shipped skill where the line `- update_end: ...` is removed from the section `## Tools` of the core
- **When** the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the output contains `PROBLEM tool "update_end" exists but is not listed in the core`
- **And** the exit status is 1
- **Priority:** High

#### E2E-013: A missing topic with the full print
- **Category:** failure
- **Scenario:** SC-003
- **Requirements:** FR-NEW-003, FR-NEW-004, FR-NEW-010
- **Given** the shipped skill where the `gantt` topic file has been removed
- **When** the user runs `mcp-htmleditor skill --all`
- **Then** the error output is `Skill topic "gantt" is not installed` and the exit status is 1
- **And** nothing is printed on the standard output
- **And** `mcp-htmleditor skill --type medical` still prints the medical topic
- **Priority:** High

#### E2E-014: Both options at once
- **Category:** failure
- **Scenario:** SC-002
- **Requirements:** FR-NEW-004, FR-NEW-005
- **Given** the shipped skill
- **When** the user runs `mcp-htmleditor skill --type gantt --all`
- **Then** the error output is exactly `Error: --type and --all cannot be used together` and the exit status is 2
- **And** nothing is printed on the standard output
- **And** `mcp-htmleditor skill --type foo --all` and `mcp-htmleditor skill --type "" --all` print the same message and exit with status 2
- **And** the error output of each of these calls is exactly that one line, with no usage text
- **Priority:** Medium

#### E2E-015: Empty topic name
- **Category:** edge
- **Scenario:** SC-002
- **Requirements:** FR-NEW-002, FR-NEW-004, FR-NEW-005
- **Given** the shipped skill
- **When** the user runs `mcp-htmleditor skill --type ""`
- **Then** the error output starts with `Unknown skill topic "". Valid topics: create, export,` and the exit status is 2
- **And** `mcp-htmleditor skill --type gantt` alone still succeeds with exit status 0
- **Priority:** Medium

#### E2E-016: Budget boundaries and accented text
- **Category:** edge
- **Scenario:** SC-005
- **Requirements:** FR-NEW-001, FR-NEW-007
- **Given** the shipped skill where the core has been set to exactly 7 000 bytes of which 20 bytes come from 10 accented letters `é` (2 bytes each)
- **When** the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the `core` line reads `core: 7000 bytes, ~1750 tokens (budget 7000) OK`
- **And** after adding one more ASCII character the line reads `core: 7001 bytes, ~1751 tokens (budget 7000) OVER`
- **And** the audit ran without any prompt, with its standard input closed
- **Priority:** High

#### E2E-017: A customised checklist
- **Category:** edge
- **Scenario:** SC-006
- **Requirements:** FR-NEW-002, FR-NEW-003, FR-NEW-006, FR-NEW-007
- **Given** the user's checklist location holds a file whose first line is `- [ ] Check the logo is visible`
- **When** the user runs `mcp-htmleditor skill --type arch-qa`, then `mcp-htmleditor skill --all`, and an agent calls `get_skill` with `type` set to `arch-qa`
- **Then** all three outputs contain `- [ ] Check the logo is visible`
- **And** after the user removes the file, the next call prints the shipped checklist instead
- **And** with a user checklist of 9 000 bytes, `mcp-htmleditor skill --type arch-qa` prints it unchanged and `mcp-htmleditor skill-audit` still reports the `arch-qa` line `OK`
- **Priority:** High

#### E2E-018: Stale statement in lower case
- **Category:** edge
- **Scenario:** SC-005
- **Requirements:** FR-NEW-009
- **Given** the shipped skill where the `tables` topic contains the text `via grapesjs`
- **When** the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the output contains `PROBLEM stale statement "grapesjs" in topic tables`
- **And** the exit status is 1
- **Priority:** High

#### E2E-019: A tool count in the core
- **Category:** failure
- **Scenario:** SC-005
- **Requirements:** FR-NEW-001, FR-NEW-009
- **Given** the shipped skill where the core contains the sentence `Le serveur expose 8 outils`
- **When** the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the output contains `PROBLEM stale statement "8 outils" in core`
- **And** the exit status is 1
- **Priority:** Medium

#### E2E-020: Machine readable audit
- **Category:** edge
- **Scenario:** SC-005
- **Requirements:** FR-NEW-007
- **Given** the shipped skill where the `mail` topic is 8 001 bytes
- **When** the maintainer runs `mcp-htmleditor skill-audit --json`
- **Then** the output is one JSON object with 16 entries (core and 15 topics), each holding name, bytes, tokens, budget and status
- **And** the entry for `mail` has bytes 8001, tokens 2001, budget 8000, status `OVER`
- **And** `problems` is `["topic mail is over its budget (8001 > 8000)"]` and `verdict` is `FAIL`
- **And** the exit status is 1
- **Priority:** Medium

#### E2E-021: Installed routing skill content
- **Category:** side effect
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-009
- **Given** the routing skill file of the source tree
- **When** the maintainer reads it
- **Then** it contains `mcp-htmleditor skill --type`
- **And** it does not contain `Lis entièrement`
- **And** the audit reports no stale statement for it
- **Priority:** Medium

#### E2E-022: Installing the routing skill
- **Category:** side effect
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001
- **Given** an empty target directory for the routing skill
- **When** the maintainer runs `make install-skill`
- **Then** the target directory contains the routing skill file, identical to the one shipped
- **Priority:** Low

#### E2E-023: A missing topic during the audit
- **Category:** failure
- **Scenario:** SC-005
- **Requirements:** FR-NEW-010
- **Given** the shipped skill where the `website` topic file has been removed
- **When** the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the output contains `PROBLEM topic "website" is not installed` and the item line `website: MISSING`
- **And** the other 14 topics and the core still have their item lines
- **And** the last line is `skill-audit: FAIL (1 problem)` and the exit status is 1
- **Priority:** High

#### E2E-024: The forced commit inside a code block
- **Category:** failure
- **Scenario:** SC-005
- **Requirements:** FR-NEW-009
- **Given** the shipped skill where the `create` topic contains a fenced code block holding the line `git commit -m "x"`
- **When** the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the output contains `PROBLEM stale statement "git commit" in topic create` and the exit status is 1
- **And** a fenced block holding the text `GrapesJS` in the same topic raises no problem
- **Priority:** High

#### E2E-025: Empty or unreadable user checklist
- **Category:** failure
- **Scenario:** SC-006
- **Requirements:** FR-NEW-002
- **Given** the user's checklist location holds an empty file
- **When** the user runs `mcp-htmleditor skill --type arch-qa`
- **Then** the output holds the shipped checklist and the exit status is 0
- **And** with the checklist location being a directory instead of a file, the output and the exit status are the same
- **Priority:** High

#### E2E-026: Missing topic through both surfaces
- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-004, FR-NEW-006, FR-NEW-010
- **Given** the shipped skill where the `gantt` topic file has been removed
- **When** an agent calls `get_skill` with `type` set to `gantt`, and the user runs `mcp-htmleditor skill --type gantt`
- **Then** the agent receives an error whose message is `Skill topic "gantt" is not installed`
- **And** the command exits with status 1, that message is on the error output and nothing is on the standard output
- **Priority:** High

#### E2E-027: Routing skill not found
- **Category:** failure
- **Scenario:** SC-005
- **Requirements:** FR-NEW-009
- **Given** the shipped skill, no installed routing skill file, and the audit run outside a source checkout
- **When** the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the output contains `PROBLEM routing skill not found`, the last line is `skill-audit: FAIL (1 problem)` and the exit status is 1
- **Priority:** Medium

#### E2E-028: Core not installed
- **Category:** failure
- **Scenario:** SC-005
- **Requirements:** FR-NEW-001, FR-NEW-004, FR-NEW-007
- **Given** the shipped skill where the core file has been removed
- **When** the user runs `mcp-htmleditor skill`, an agent calls `get_skill` without argument, and the maintainer runs `mcp-htmleditor skill-audit`
- **Then** the command prints `Skill core is not installed` on the error output and exits with status 1, and the agent receives an error with that message
- **And** the audit prints `core: MISSING` and `PROBLEM core is not installed`, still prints the 15 topic lines, and ends with `skill-audit: FAIL (1 problem)` and status 1
- **Priority:** High

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001 | E2E-001 | E2E-019, 028 | E2E-021, 022 |
| SC-002 | FR-NEW-002, 004, 005 | E2E-002 | E2E-007, 014 | E2E-015 |
| SC-003 | FR-NEW-003, 004, 010 | E2E-003 | E2E-013 | E2E-017 |
| SC-004 | FR-NEW-006, 004, 010 | E2E-004, 005 | E2E-008, 026 | E2E-017 |
| SC-005 | FR-NEW-007 to 010 | E2E-006 | E2E-009 to 012, 023, 024, 027, 028 | E2E-016, 018, 020 |
| SC-006 | FR-NEW-002, 003 | E2E-002, 003 | E2E-025 | E2E-017 |

Requirements to tests: FR-NEW-001 (E2E-001, 010, 016, 019, 021, 022, 028); 002 (002, 015, 017, 025); 003 (003, 013, 017); 004 (007, 008, 013, 014, 015, 026, 028); 005 (002, 003, 014, 015); 006 (004, 005, 008, 017, 026); 007 (006, 009, 010, 016, 017, 020, 028); 008 (006, 011, 012); 009 (006, 018, 019, 021, 024, 027); 010 (013, 023, 026).

## 11. Open questions

None.

## 12. Glossary

| Term | Definition | Context |
|---|---|---|
| Core | The short text printed by `mcp-htmleditor skill`: rules, workflow, tool list, topic index | Skill |
| Topic | One of the 15 on demand parts of the skill, loaded with `--type` | Skill |
| Budget | Maximum size in bytes: 7 000 for the core, 8 000 per topic | Skill |
| Stale statement | A sentence the audit forbids because it contradicts the product | Skill |
| Tool | An operation an agent can call through the tool protocol | Agent tools |
| Routing skill | The small file installed in the agent's skills directory that tells it to run `mcp-htmleditor skill` | Skill |

## 13. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 11 | 1 | NOT-IMPLEMENTABLE |
| 2 | 11 | 1 | NOT-IMPLEMENTABLE |
| 3 | 4 | 2 | NOT-IMPLEMENTABLE |
| 4 | 6 | 5 | NOT-IMPLEMENTABLE (amended after; no round 5 run) |

**Amendments applied:** all F findings of rounds 1 to 4 (budgets and source mapping, tool list format, stale statement matching, output formats, precedence, missing core, routing skill location, json schema). **Concern (user waiver, 2026-11-03):** round 5 was not run; output level details may still surface at design or implementation, to be settled there.
**No implementation detail outside Section 14:** PASS (source tree path of the routing skill kept to Section 14.3)

## 14. Evidence appendix

### 14.1 Current State evidence

| Claim (Section 2) | Evidence |
|---|---|
| `skill` prints index, sub documents, checklist, no option | `src/mcp_htmleditor/cli.py:39-48`, `src/mcp_htmleditor/skill_content.py:28-70` |
| about 198 000 bytes | `wc -c skill/*.md skill/types/*.md skill/checks/*.md` gives 197 582 for the files; the printed text adds separators |
| 7 tools exist | `src/mcp_htmleditor/mcp_server.py:31,81,93,112,133,150,166` |
| skill says 6 tools | `skill/SKILL.md:8`, `skill/SKILL.md:168` |
| medical 15 versus 16 | `skill/SKILL.md:226` (15) against `skill/SKILL.md:83,100` and `skill/types/medical.md` section 4 (16) |
| GrapesJS | `skill/SKILL.md:7`, `skill/SKILL.md:213`, `skill/types/tables.md:99`, `skill/workflow-templates.md:116` |
| port 7842 hard coded | `skill/SKILL.md:117` against `skill/SKILL.md:186` (legitimate rule text "never assume 7842" at `skill/workflow-create.md:334-336`, not stale) |
| forced commits | `skill/workflow-create.md:226,240,256` |
| dated defect list | `skill/types/medical.md:542` |
| routing skill reads everything | `dynamic-skills/html-editor/SKILL.md` (lines "Lis entièrement la sortie") |
| install command | `Makefile:186-193` |
| single existing test | `tests/test_skill_content.py:1-16` |
| checklist user location | `src/mcp_htmleditor/arch_checks.py:39,57` |

Test command: `make test` (`Makefile:83-89`); gate: `make check` (`Makefile:139`).

### 14.3 Design inputs
- Tests that remove or grow files (E2E-009, 010, 013, 016, 020, 023, 026, 028) need an override of the bundled skill directory: `src/mcp_htmleditor/skill_content.py:15-24` uses two fixed candidates. Detection signal: those tests cannot be written.
- E2E-027 needs a location override for the installed routing skill: the location is only the `PI_SKILLS_DIR` Makefile variable (`Makefile:37`), no code reads it. The routing skill file of the source tree is `dynamic-skills/html-editor/SKILL.md`.
- No fenced block aware, whole word text scanner, no parser of the core `## Tools` section, and no `--type`, `--all`, `skill-audit`, `--json` exist yet. Detection signal: E2E-006, 018, 024.
- Checklist fallback: today the first existing user file wins even when empty (`src/mcp_htmleditor/arch_checks.py:39-57`); the shipped copy must be used when the user file is empty or unreadable. Detection signal: E2E-025.
- Documents to update with the count of eight tools and the new default of `skill`: `.agent_docs/architecture.md:26` (and its tree line), `README.md:132`, `README.md:136`, `README.md:359`.
- `dynamic-skills/html-editor/SKILL.md` is not in the wheel force include (`pyproject.toml:48-52`), and the audit must read it: it has to be bundled or found in the source checkout. Detection signal: E2E-021 and E2E-027.
- The 15 topic names and the stale statement list are product contracts; the source files `skill/*.md` are split accordingly, `medical.md` sections 1 to 6 and 9 to 12 weigh about 24 700 bytes and must be cut to 8 000 by the priority rule.

- The tool list check needs the registered tool names at audit time; `src/mcp_htmleditor/mcp_server.py` registers them with a decorator, no registry accessor exists (lines 31-166).
- The skill is bundled through the wheel force include (`pyproject.toml`, agent report); the new topic files must be picked up by it.
- `skill_content.py:58-61` skips missing sub documents silently; the new behavior reports them. Detection signal: E2E-013, E2E-023.
- Over budget today and to be cut: `SKILL.md` (16 324 against 7 000 for the core), `slides.md` (27 769), `medical.md` (29 818), `arch-diagram.md` (23 121), `workflow-create.md` (15 269), `document.md` (14 418), `workflow-export.md` (13 706), `gantt.md` (11 732), `mail.md` (9 553) and the shipped checklist (11 856, to be cut to 3 800). The audit is the signal. Cuts follow the priority rule of FR-NEW-002; the removed text goes to project documentation.
- The routing skill still says "Lis entièrement la sortie" at `dynamic-skills/html-editor/SKILL.md:17`; E2E-021 is the signal.
- Adding `get_skill` makes 8 tools and contradicts SPEC-0001 FR-009 and the wording `.agent_docs/architecture.md:26`.
- `get_skill` returns text through the tool protocol, so no standard output is involved; the audit stays a command line command.
- Docs to update on implementation: `AGENTS.md`, `README.md:359`, `.agent_docs/architecture.md:26`, `.agent_docs/testing.md`, `dynamic-skills/README.md`.
