# US-0025: Core text, routing skill, shipped content gates

> Spec: SPEC-0006 (sdlc/specs/SPEC-0006-progressive-skill/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0024
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Ship the real core (`skill/core.md`, at most 7 000 bytes, at most 6 000 bytes shipped to leave headroom
for later tools), keep the former index text in the archive, point the installed routing skill to the
core and `--type`, and add the shipped content gates that every later content story relies on.

## Requirements covered

- SPEC-0006/FR-NEW-001: WHEN a user runs `mcp-htmleditor skill` without option THE Skill SHALL print the core, at most 7 000 bytes, containing the absolute rules, the workflow, the list of tools, and an index of the 15 topics with, for each, one line of description and the exact command that loads it. Business rules: the core contains the 8 absolute rules of the former skill index (bracket every file change with `update_start` and `update_end`; never remove `data-type`, `data-id` or `data-title` on slides; put `data-editable="text"` on editable text; rewrite the complete HTML; images relative to the file or in base64; never start a second server when `get_status` reports one running; validate the rendering visually after each substantial change; treat a modification found in the file as deliberate), the 6 step workflow, and the command `mcp-htmleditor new <template> <file>` with the keys `ei, carbon, medical, doc, doc-perso, doc-ei, mail, website`. If the core is not installed, `mcp-htmleditor skill` and `get_skill` without argument print `Skill core is not installed` and exit with status 1. The 15 topics are `create`, `export`, `templates`, `slides-carbon`, `slides-ei`, `medical`, `medical-sources`, `document`, `mail`, `website`, `gantt`, `arch-diagram`, `arch-qa`, `annotated-image`, `tables`, in that order. The core does not state how many tools exist, it lists them. The installed routing skill tells the agent to read the core, then to load topics with `--type` according to the task, and no longer tells it to read everything. User visible text: the first line of the core is `# mcp-htmleditor skill (core)`. Tools are listed in one section headed `## Tools`, one line per tool of the shape `- <name>: <description>`, `get_skill` included. Index line shape: `<topic>: <description>. Load: mcp-htmleditor skill --type <topic>`.
- SPEC-0006/FR-NEW-009 (partial: the core and the routing skill are free of stale statements; the topics are covered by US-0026 to US-0033): WHEN the audit runs THE Skill SHALL report as a problem each stale statement found in the core, in a topic or in the installed routing skill. The stale statements are: `GrapesJS`, `6 outils`, `15 types`, `localhost:7842`, `git commit`, `Défauts d'export mesurés`; and, in the core and in the installed routing skill only, any number directly followed by the word `outils` or `tools`.

## Independent Test

`make test ARGS='tests/test_skill_shipped.py'`: `skill` on the real tree prints a core whose first line is
`# mcp-htmleditor skill (core)`, at most 6 000 bytes, with `## Tools` equal to the registered tool names
and 15 index lines equal to `TOPICS`; `dynamic-skills/html-editor/SKILL.md` contains
`mcp-htmleditor skill --type`, not `Lis entièrement`, and `find_stale(..., include_counts=True)` is empty.

## Design excerpt

### Decisions
- DEC-001, DEC-002 (SPEC-0006): core is the literal `skill/core.md`; the hand written index is checked against `TOPICS` by a gate test.
- DEC-010 (SPEC-0006): tool section `## Tools`, one `- <name>: <description>` line per tool; "the core is written at most 6 000 bytes in story E so later specs keep about 1 000 bytes of headroom under the 7 000 byte budget." SPEC-0007, 0009 and 0010 add their tool lines in their own stories.
- DEC-015 (SPEC-0006): E2E-001 derives the expected tool set from `registered_tool_names()` (equality with the `## Tools` names) and additionally asserts the eight names at landing (`start_server`, `stop_server`, `get_status`, `open_file`, `update_start`, `update_end`, `layout_arch_diagram`, `get_skill`) are a subset, so later specs that add tools and their core line do not break it.
- DEC-016 (SPEC-0006): no legacy fallback; the shipped tree is partial until US-0033; the gates below run only on files that exist.

### Data model
none

### Contracts
Core file `skill/core.md` (at most 6 000 bytes), content in this order:
1. First line `# mcp-htmleditor skill (core)`.
2. The 8 absolute rules (list above), each one line, wording taken from `skill/SKILL.md` "Règles absolues" (archived to `docs/skill-archive/index.md`); the English or French of the source is kept, meaning unchanged. Do not mention `localhost:7842` as a rule; keep "read the `port` returned, never assume 7842".
3. The 6 step workflow (`start_server`, `get_status`, `update_start`, edit the file on disk, `update_end`, optional export). No commit step.
4. `mcp-htmleditor new <template> <file>` with the keys `ei, carbon, medical, doc, doc-perso, doc-ei, mail, website` (and `--serve`).
5. Section `## Tools` (ends at the next `## ` heading): one line per tool: `start_server`, `stop_server`, `get_status`, `open_file`, `update_start`, `update_end`, `layout_arch_diagram`, `get_skill`, each `- <name>: <short description>`. The sentence must not state a number of tools.
6. Section `## Topics`: 15 lines in index order, shape `<topic>: <description>. Load: mcp-htmleditor skill --type <topic>`, descriptions exactly:

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

Routing skill (`dynamic-skills/html-editor/SKILL.md`): keep the front matter; replace the "Charge la skill complète" block by: run `mcp-htmleditor skill` and read the core; then load topics with `mcp-htmleditor skill --type <topic>` according to the task (name the 15 topics or point to the core index); remove "Lis entièrement la sortie"; replace "commit git" in the workflow line (no forced commit); no number followed by `outils` or `tools`; no `GrapesJS`, `localhost:7842`, `git commit`. `dynamic-skills/README.md` line 4 and neighbours: describe "run `mcp-htmleditor skill` (the core), then `--type <topic>`" instead of the full print.

Gate cases in `tests/test_skill_shipped.py` (parametrized over shipped files that exist; this story creates the file with the core and routing cases; US-0026 to US-0033 rely on the topic cases defined here and US-0034 extends them):
- core: `core_output()` bytes at most 7 000 and the file at most 6 000 bytes; first line `# mcp-htmleditor skill (core)`; ends with exactly one newline; `find_stale(core, include_counts=True)` is empty; `listed_tools(core)` equals `registered_tool_names()` as a set and the eight landing names are a subset; the 15 index lines equal `TOPICS` in order (`f"{t.name}: {t.description}. Load: mcp-htmleditor skill --type {t.name}"`); contains the strings `update_start`, `update_end`, `data-type`, `data-id`, `data-title`, `data-editable="text"`, `base64`, `get_status`, `mcp-htmleditor new`, and each of the 8 template keys.
- topic cases (run for every `skill/topics/<t>.md` that exists): `topic_output(t)` at most 8 000 bytes, first line `# Skill topic: <t>`, one final newline, `find_stale(text, include_counts=False)` empty, last line `Reference: <file>` exactly for `slides-carbon`, `slides-ei`, `medical`, `document`, `mail`, `website` (files `templates/reference/slides/ibm-carbon.html`, `templates/reference/slides/example-ei-complete.html`, `templates/reference/slides/medical.html`, `templates/reference/documents/report-standard.html`, `templates/reference/documents/mail-carbon-example.html`, `templates/reference/websites/ibm-carbon.html`) and no line starting with `Reference:` elsewhere, every substring of `tests/data/skill_anchors.json[t]` present (entry missing means no anchor yet).

### Paths
| Path | Action |
|---|---|
| `skill/core.md` | new |
| `skill/SKILL.md` | move to `docs/skill-archive/index.md` (git rename, text kept) |
| `dynamic-skills/html-editor/SKILL.md` | modify |
| `dynamic-skills/README.md` | modify |
| `tests/test_skill_shipped.py` | new |

### Existing patterns
- `skill/SKILL.md` (sections "Règles absolues" at line 109, "Workflow LLM type" at 122, "Commandes CLI" at 133, "MCP Tools" at 168) as the source of the rules and workflow.
- `Makefile:37,186-193` (`PI_SKILLS_DIR ?=`, `install-skill` copies the routing skill).
- `skill_audit.find_stale`, `listed_tools`; `mcp_server.registered_tool_names` (US-0024); `skill_content.TOPICS`.
- Repo root resolution in tests: `Path(__file__).resolve().parents[1]`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Level E2E; Location `tests/test_skill_shipped.py`; these run on the real shipped tree (no override).

### SPEC-0006/E2E-001: The core by default
- Level E2E; Driver `CliRunner` on `skill` with the real tree
- Given the tool is installed with the shipped skill
- When the user runs `mcp-htmleditor skill`
- Then the output is at most 7 000 bytes
- And it contains an index with exactly the 15 topics in the order `create, export, templates, slides-carbon, slides-ei, medical, medical-sources, document, mail, website, gantt, arch-diagram, arch-qa, annotated-image, tables`, each line of the shape `<topic>: <description>. Load: mcp-htmleditor skill --type <topic>`
- And its first line is `# mcp-htmleditor skill (core)`, it has a section headed `## Tools`, and that section holds one line `- <name>: <description>` for each of the 8 tools `start_server`, `stop_server`, `get_status`, `open_file`, `update_start`, `update_end`, `layout_arch_diagram`, `get_skill`
- And the index line of `medical` reads `medical: Rules for medical slides: layouts, light and dark surfaces, widths, readability, height budget. Load: mcp-htmleditor skill --type medical`

### SPEC-0006/E2E-021: Installed routing skill content
- Level E2E; Driver file read of `dynamic-skills/html-editor/SKILL.md` plus `find_stale`
- Given the routing skill file of the source tree
- When the maintainer reads it
- Then it contains `mcp-htmleditor skill --type`
- And it does not contain `Lis entièrement`
- And the audit reports no stale statement for it

### SPEC-0006/E2E-022: Installing the routing skill
- Level E2E; Driver `subprocess.run(["make", "install-skill", f"PI_SKILLS_DIR={tmp}"], cwd=repo, timeout=60)`
- Given an empty target directory for the routing skill
- When the maintainer runs `make install-skill`
- Then the target directory contains the routing skill file, identical to the one shipped

Gate cases (not spec ids, same file): the core cases and the topic cases defined under Contracts; with no topic file shipped yet they select zero topics and the topic parametrization must not fail when empty.

## Constraints

- Files not to touch: Python sources, `Makefile`, `pyproject.toml`, other `skill/` files (the legacy `skill/types/*.md` and `skill/workflow-*.md` stay until their content stories move them).
- Dependencies not to add: none.
- Patterns to avoid: stating a tool count, hard coding `localhost:7842` as a rule, a commit step in the workflow, copying the index from `TOPICS` at test time into the file, any legacy fallback.
- Scope boundary: topic files come in US-0026 to US-0033. Between this story and US-0033 a real `skill-audit` fails on missing topics (accepted, DEC-016); the release waits for US-0034.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_skill_content.py`, `tests/test_skill_audit.py`, `tests/test_skill_audit_checks.py`, `tests/test_skill_tool.py` unchanged and green; `make install-skill` still copies the routing skill.
- [ ] Docs updated: `dynamic-skills/README.md`.
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0025: Core text, routing skill, shipped content gates`, body `Spec: SPEC-0006` and `FR-NEW-001, FR-NEW-009`.
