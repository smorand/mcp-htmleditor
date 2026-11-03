# US-0034: Clean real audit, all 15 topics enforced, documentation

> Spec: SPEC-0006 (sdlc/specs/SPEC-0006-progressive-skill/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0026, US-0027, US-0028, US-0029, US-0030, US-0031, US-0032, US-0033
> min_tier: 2
> Files touched: 5
> Closes spec: yes

## Objective

Prove that the shipped skill is clean end to end: `skill-audit` on the real tree prints 16 `OK` lines and
`skill-audit: OK`, all 15 topic files must now exist (the content gates stop tolerating a missing file),
and the user and agent documentation describes the new commands, the eight tools and the rule for later
specs that add tools. Closes SPEC-0006.

## Requirements covered

- SPEC-0006/FR-NEW-007 (partial: the real tree passes the whole report): WHEN a maintainer runs `mcp-htmleditor skill-audit` THE Skill SHALL print one line per item (the core, then each topic in index order) with its size in bytes, its estimated tokens, its budget and its verdict, then one line per problem found, then a final verdict, and exit with status 0 when no problem is found and 1 otherwise. Final line `skill-audit: OK` or `skill-audit: FAIL (3 problems)`.
- SPEC-0006/FR-NEW-008 (partial: the real core lists exactly the registered tools): WHEN the audit runs THE Skill SHALL report as a problem every tool that the core lists and that the product does not provide, and every tool that the product provides and that the core does not list. Only the names at the start of the lines of the core section `## Tools` are read.
- SPEC-0006/FR-NEW-009 (partial: the real core, 15 topics and routing skill have no stale statement): WHEN the audit runs THE Skill SHALL report as a problem each stale statement found in the core, in a topic or in the installed routing skill. The routing skill checked is, in order, the installed file `~/.pi/agent/dynamic-skills/html-editor/SKILL.md` and, only when that file is absent, the routing skill file of the source tree the running tool was started from, whatever the current directory; when the installed file exists only it is checked.

## Independent Test

`make test ARGS='tests/test_skill_shipped.py'`: `skill-audit` on the real tree exits 0, prints 16 item lines
(`core` then the 15 topics in index order) each ending with `OK`, last line `skill-audit: OK`, and no line
starting with `PROBLEM`; `uv run mcp-htmleditor skill-audit` run by hand gives the same.

## Design excerpt

### Decisions
- DEC-014 (SPEC-0006): "`skill-audit` has no `make` target; the real tree audit runs inside `make test` (E2E-006)."
- DEC-016 (SPEC-0006): "the work is released only after N"; tolerance of absent files lived only in the content gates of US-0025; this story flips them to "all 15 files exist".
- DEC-010 (SPEC-0006): a story that registers a tool adds one `- <name>: <description>` line to the `## Tools` section of `skill/core.md` in the same story; this rule is written in `.agent_docs/architecture.md` for SPEC-0007, 0008, 0009, 0010.

### Data model
none

### Contracts
Test changes in `tests/test_skill_shipped.py`:
- add E2E-006 (below);
- the topic gate cases are parametrized over `TOPIC_NAMES` and no longer skip a missing file: a case `test_every_topic_file_exists` asserts the 15 files `skill/topics/<t>.md` exist; the `Reference:` last line cases cover the six reference topics and assert absence for the others; the anchors file must have a non empty entry for every topic except `arch-qa` (its anchors live in `tests/test_arch_checks.py`);
- `skill --all` on the real tree equals `core_output()` followed by the 15 `topic_output(t)` joined by one empty line, size equal to the sum of the parts plus the separators (E2E-003 on the real tree, gate case);
- the legacy files are gone: no `skill/SKILL.md`, `skill/types/`, `skill/workflow-*.md` remain; `docs/skill-archive/` holds `index.md`, `slides.md`, `medical.md`, `workflow-create.md`, `workflow-export.md`, `workflow-templates.md`, `workflow-arch-qa.md`, `document.md`, `mail.md`, `website.md`, `tables.md`, `gantt.md`, `annotated-image.md`, `arch-diagram.md`, `arch-diagram-checklist.md`.

Documentation edits:
- `AGENTS.md`: command list gains `mcp-htmleditor skill` (core), `skill --type <topic>`, `skill --all`, `skill-audit [--json]`; paths `skill/types/*.md` and `skill/workflow-*.md` replaced by `skill/core.md`, `skill/topics/`, `skill/checks/`; index entry for `docs/skill-archive/`; statement of eight tools; the rule that a story registering a tool adds its line to the `## Tools` section of `skill/core.md`.
- `README.md` (about lines 132-138, 359, 383, 414): `skill` prints the core, `--type`, `--all`, `skill-audit`; eight tools including `get_skill`; routing skill text; a note that a user checklist seeded earlier keeps its size.
- `.agent_docs/architecture.md` (about line 26 and the module row for `skill_content.py`): eight tools, new modules `skill_audit.py`, the `HTMLEDITOR_SKILL_DIR` and `HTMLEDITOR_ROUTING_SKILL` seams, the tool line rule; record that SPEC-0001 FR-009 (seven operations) is superseded by eight.
- `.agent_docs/testing.md`: rows for `test_skill_content.py` (rewritten), `test_skill_tool.py`, `test_skill_audit.py`, `test_skill_audit_checks.py`, `test_skill_shipped.py`, the `skill_tree` fixture and `tests/data/skill_anchors.json`.

### Paths
| Path | Action |
|---|---|
| `tests/test_skill_shipped.py` | modify (E2E-006, all 15 files enforced, `--all` and relocation cases) |
| `AGENTS.md` | modify |
| `README.md` | modify |
| `.agent_docs/architecture.md` | modify |
| `.agent_docs/testing.md` | modify |

### Existing patterns
- `tests/test_skill_shipped.py` gate cases from US-0025; `CliRunner` audit assertions from `tests/test_skill_audit.py`.
- Documentation layout rule in `AGENTS.md` (compact index plus `.agent_docs/` topic files, timestamped entries).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0006/E2E-006: A clean audit
- Level E2E; Driver `CliRunner` on `skill-audit` with the real tree and the source tree routing skill (no installed file, `HTMLEDITOR_ROUTING_SKILL` set to the source `dynamic-skills/html-editor/SKILL.md`); Location `tests/test_skill_shipped.py`
- Given the shipped skill
- When the maintainer runs `mcp-htmleditor skill-audit`
- Then the output has 16 item lines, `core` first then the 15 topics in index order, each ending with `OK`
- And the last line is `skill-audit: OK` and the exit status is 0
- And no line starts with `PROBLEM`

Gate cases (not spec ids, same file): all 15 topic files exist; `--all` equals core plus topics; legacy files absent and archive files present; every anchors entry present for the 14 topics that use the anchors file; `Reference:` lines exactly for the six reference topics; `make check` passes as a whole.

## Constraints

- Files not to touch: Python sources, `skill/` content, `Makefile`, specs (never edit a spec).
- Dependencies not to add: none.
- Patterns to avoid: detailed explanations in `AGENTS.md` (index only, detail goes to `.agent_docs/`), a tool count in the skill text, em or en dashes in documentation, editing SPEC-0001.
- Scope boundary: code comments and tool docstrings that still point to removed files (for example `skill/types/arch-diagram.md`) are reported as backlog findings, not fixed here.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (E2E-006 and the "all 15 files exist" case fail on a tree where a topic is missing).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: every gate case and test of US-0021 to US-0033 stays green; `mcp-htmleditor skill` still works from an installed wheel (the `skill/` tree is force included).
- [ ] Docs updated: `AGENTS.md`, `README.md`, `.agent_docs/architecture.md`, `.agent_docs/testing.md`.
- [ ] Self review: full at tier 2.
- [ ] The spec's full acceptance set green (every E2E-001 to E2E-028 across US-0021 to US-0034), and every requirement of SPEC-0006 (FR-NEW-001 to FR-NEW-010) cited by at least one story with status done or landed.
- [ ] One commit `US-0034: Clean real audit, all 15 topics enforced, documentation`, body `Spec: SPEC-0006` and `FR-NEW-007, FR-NEW-008, FR-NEW-009`.
