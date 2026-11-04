# US-0033: Topic arch-qa and the cut shipped checklist

> Spec: SPEC-0006 (sdlc/specs/SPEC-0006-progressive-skill/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0025
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Ship the `arch-qa` topic: the review workflow text (at most 3 800 bytes, from `skill/workflow-arch-qa.md`)
followed by the shipped checklist cut from 11 856 to at most 3 800 bytes, so that the `arch-qa` output
stays at most 8 000 bytes, while the original checklist is kept in the archive and a user checklist is
still printed unchanged.

## Requirements covered

- SPEC-0006/FR-NEW-002 (partial: topic `arch-qa` only; the other topics are in their own stories): WHEN a user runs `mcp-htmleditor skill --type <topic>` with one of the 15 topics THE Skill SHALL print that topic only, at most 8 000 bytes. The `arch-qa` topic contains the architecture checklist read from the user editable location at the time of the call, and the shipped checklist when the user has none; a user checklist larger than the shipped one is printed unchanged. Each topic keeps, in this priority order, (1) every absolute rule and every "never" rule of its source text, (2) every attribute and class name the agent must write, (3) one complete example; and drops, in this order, long rationale paragraphs, then secondary examples. Source text to topic: workflow-arch-qa plus the checklist to `arch-qa`. The shipped checklist is at most 3 800 bytes and the shipped arch-qa workflow text at most 3 800 bytes, so that the `arch-qa` output, with its first line and separators, is at most 8 000 bytes. Other topics have no `Reference:` line.
- SPEC-0006/FR-NEW-007 (partial: the `arch-qa` item line of `skill-audit` is `OK`): The size of `arch-qa` is measured on the shipped checklist and the shipped arch-qa workflow text, never on a user checklist. Size counts every byte the command writes on the standard output, including its single final newline. Budgets: each topic 8 000 bytes; a size equal to the budget passes, one byte more is `OVER`.
- SPEC-0006/FR-NEW-009 (partial: the `arch-qa` text contains no stale statement): WHEN the audit runs THE Skill SHALL report as a problem each stale statement found in the core, in a topic or in the installed routing skill. The stale statements are: `GrapesJS`, `6 outils`, `15 types`, `localhost:7842`, `git commit`, `Défauts d'export mesurés`.

## Independent Test

`make test ARGS='tests/test_skill_shipped.py tests/test_arch_checks.py'`, then
`uv run mcp-htmleditor skill --type arch-qa | wc -c` prints a number at most 8000 and the output contains
`2 passes` and `arch-col`.

## Design excerpt

### Decisions
- DEC-019 (SPEC-0006): "`arch-qa` topic is `workflow text (≤ 3 800) + "\n\n" + checklist (≤ 3 800)` under its first line; the cut checklist keeps `2 passes` and `arch-col` anchors."
- DEC-005 (SPEC-0006): `read_checklist()` returns the user file when usable, else the shipped file; `read_shipped_checklist()` is what the audit measures.
- DEC-016, DEC-017, DEC-018 (SPEC-0006): same migration order, anchors and content recipe as the other content stories.

### Data model
none

### Contracts
Rendering: `# Skill topic: arch-qa\n\n` + `skill/topics/arch-qa.md` stripped + `\n\n` + checklist stripped + `\n` (design 3: workflow text, an empty line, then the checklist). `skill/topics/arch-qa.md` holds only the workflow text, at most 3 800 bytes; `skill/checks/arch-diagram-checklist.md` is at most 3 800 bytes.

Content recipe: (1) `git mv skill/workflow-arch-qa.md docs/skill-archive/workflow-arch-qa.md`; (2) copy the original 11 856 byte checklist to `docs/skill-archive/arch-diagram-checklist.md` before cutting; (3) workflow text: keep the rule that the review runs systematically after every `mcp-htmleditor arch-layout` or `layout_arch_diagram`, the sub-agent protocol (capture, compare to the checklist loaded with `mcp-htmleditor arch-checklist`, fix the markup declaratively and re-run the layout, bounded to `2 passes maximum`, report fixes and unresolved defects as text), and the integration steps; drop the rationale section; replace pointers to legacy files by `mcp-htmleditor skill --type create` and `--type arch-diagram`; (4) checklist: keep the "how it is used" header with the 2 passes bound, then the generic rules and the `arch-col`, lane, multi flux and export rules as one line each (`- [ ] ...`), drop the long CORRIGÉ narratives and explanations; the cut file must still contain `2 passes` and `arch-col`; (5) no stale statement, no `Reference:` line.

### Paths
| Path | Action |
|---|---|
| `skill/topics/arch-qa.md` | new |
| `skill/workflow-arch-qa.md` | move to `docs/skill-archive/workflow-arch-qa.md` (git rename, text kept) |
| `skill/checks/arch-diagram-checklist.md` | modify (cut to at most 3 800 bytes) |
| `docs/skill-archive/arch-diagram-checklist.md` | new (copy of the 11 856 byte original) |
| `tests/test_arch_checks.py` | modify (re-assert the load bearing words on the cut checklist, size bounds) |

### Existing patterns
- `tests/test_arch_checks.py:19-26` (`test_read_checklist_returns_the_bundled_content` asserts `"2 passes"` and `"arch-col"` in `read_checklist()`; it must keep passing on the cut file).
- `src/mcp_htmleditor/arch_checks.py` (`read_checklist`, `read_shipped_checklist`, `_repo_checks_dir`), gate cases in `tests/test_skill_shipped.py` (US-0025).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

This story carries no spec E2E test (E2E-017 and E2E-025 were landed with the machinery on a generated tree). Acceptance is the per topic content gate of DEC-017 and DEC-018 on the real shipped tree. Level: gate; Driver: pytest; Location: `tests/test_skill_shipped.py` (parametrized, already written by US-0025) and `tests/test_arch_checks.py` (extended here).

#### Topic `arch-qa` (Visual quality review of architecture diagrams and its checklist)
- Size: `topic_output("arch-qa")` built with the shipped checklist (`read_shipped_checklist`) is at most 8 000 bytes; the file `skill/topics/arch-qa.md` is at most 3 800 bytes and `skill/checks/arch-diagram-checklist.md` is at most 3 800 bytes (new assertions in `tests/test_arch_checks.py`); the audit item line for `arch-qa` ends with `OK`.
- Shape: first line is exactly `# Skill topic: arch-qa`; the text ends with exactly one newline; the topic file has no `# Skill topic:` line.
- Reference: no line starts with `Reference:`.
- Stale: `find_stale(text, include_counts=False)` returns `[]` for the topic file and for the checklist.
- Anchors (asserted in `tests/test_arch_checks.py` on the cut checklist, because the topic body and the checklist are two files; `tests/data/skill_anchors.json` is not touched by this story): `2 passes`, `arch-col`, and in the topic file `mcp-htmleditor arch-layout`, `layout_arch_diagram`, `mcp-htmleditor arch-checklist`, `2 passes maximum`.
- Relocation: `skill/workflow-arch-qa.md` is no longer present under `skill/`; `docs/skill-archive/workflow-arch-qa.md` exists and is not empty; `docs/skill-archive/arch-diagram-checklist.md` exists and has 11 856 bytes.
- Behavior kept: a user checklist of 9 000 bytes is still printed unchanged by `skill --type arch-qa` (covered by the E2E-017 test of US-0023; must stay green).

### Carry-over from US-0022: SPEC-0006/E2E-025 at the command line

US-0022 could not assert, through `mcp-htmleditor skill --type arch-qa`, that the output holds the shipped checklist: `skill_content.py` was off limits there and the arch-qa rendering (workflow text, an empty line, the checklist) lands in this story. This story adds the missing assertions to `tests/test_arch_checks.py` or `tests/test_skill_content.py`:
- **Given** the user's checklist location holds an empty file, **When** the user runs `mcp-htmleditor skill --type arch-qa`, **Then** the output holds the shipped checklist and the exit status is 0; with the location being a directory the output and the exit status are the same.
- **Given** the user checklist is a non empty file larger than the shipped one, **Then** the output prints it unchanged.

## Constraints

- Files not to touch: Python sources, `skill/core.md`, other topics, `tests/test_skill_shipped.py`, `tests/data/skill_anchors.json`.
- Dependencies not to add: none.
- Patterns to avoid: changing the meaning of a rule, an em or en dash in the text, truncating mid sentence to hit the size, keeping `skill/workflow-arch-qa.md` under `skill/`.
- Scope boundary: users who already seeded the old 11 856 byte checklist keep it (`make install` never overwrites it); that is accepted by the spec.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the size assertions on the 11 856 byte checklist fail first).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_arch_checks.py` existing tests, `tests/test_arch_layout.py`, and the gate cases of earlier stories stay green.
- [ ] Docs updated: removed text kept in `docs/skill-archive/`; user docs are updated by US-0034.
- [ ] Self review: full at tier 2, including the read only comparison of the topic and checklist with the archived sources.
- [ ] One commit `US-0033: Topic arch-qa and the cut shipped checklist`, body `Spec: SPEC-0006` and `FR-NEW-002, FR-NEW-007, FR-NEW-009`.
