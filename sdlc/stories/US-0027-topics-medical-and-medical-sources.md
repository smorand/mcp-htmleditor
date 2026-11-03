# US-0027: Topics medical and medical-sources

> Spec: SPEC-0006 (sdlc/specs/SPEC-0006-progressive-skill/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0025
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Split the legacy `skill/types/medical.md` (29 818 bytes): sections 1 to 6 and 9 to 12 to `medical`, sections 7 and 8 to `medical-sources`, each at most 8 000 bytes, the 16 slide types stated once as 16, the dated defect list left in the archive.

## Requirements covered

- SPEC-0006/FR-NEW-002 (partial: topics `medical`, `medical-sources` only; the other topics are in their own stories): WHEN a user runs `mcp-htmleditor skill --type <topic>` with one of the 15 topics THE Skill SHALL print that topic only, at most 8 000 bytes. The topic output does not repeat the core. Its first line is `# Skill topic: <topic>`. Each topic keeps, in this priority order, (1) every absolute rule and every "never" rule of its source text, (2) every attribute and class name the agent must write, (3) one complete example; and drops, in this order, long rationale paragraphs, then secondary examples. Source text to topic: workflow-create to `create`; workflow-export to `export`; workflow-templates to `templates`; slides, Carbon part to `slides-carbon`; slides, Euro-Information part to `slides-ei`; medical sections 1 to 6 and 9 to 12 to `medical`; medical sections 7 and 8 to `medical-sources`; document to `document`; mail to `mail`; website to `website`; gantt to `gantt`; arch-diagram to `arch-diagram`; workflow-arch-qa plus the checklist to `arch-qa`; annotated-image to `annotated-image`; tables to `tables`. Sections of the `slides` source that serve both charters (file structure, insertable types, renumbering, height budget, adding a slide, PPTX conversion) appear in both `slides-carbon` and `slides-ei`, each shortened by the same priority rule; the class correspondence table appears in `slides-ei` only. Names kept under rule (2) are those appearing in the kept example and in one table of at most 1 500 bytes; the topics `slides-carbon`, `slides-ei`, `medical`, `document`, `mail` and `website` end with a line `Reference: <template file>` naming respectively `templates/reference/slides/ibm-carbon.html`, `templates/reference/slides/example-ei-complete.html`, `templates/reference/slides/medical.html`, `templates/reference/documents/report-standard.html`, `templates/reference/documents/mail-carbon-example.html` and `templates/reference/websites/ibm-carbon.html`; other topics have no such line.
- SPEC-0006/FR-NEW-007 (partial: the topic's item line of `skill-audit` is `OK`): Size is the number of bytes of the UTF 8 text the corresponding command prints; estimated tokens are the size divided by 4, rounded up. Budgets: each topic 8 000 bytes; a size equal to the budget passes, one byte more is `OVER`. Size counts every byte the command writes on the standard output, including its single final newline.
- SPEC-0006/FR-NEW-009 (partial: the topic text contains no stale statement): WHEN the audit runs THE Skill SHALL report as a problem each stale statement found in the core, in a topic or in the installed routing skill. The matching ignores letter case and matches whole words only; text inside fenced code blocks is ignored. The stale statements are: `GrapesJS`, `6 outils`, `15 types`, `localhost:7842`, `git commit`, `Défauts d'export mesurés`. `git commit` is detected inside and outside fenced code blocks; every other statement is ignored inside them. The words "never assume 7842" are not stale.

## Independent Test

`make test ARGS='tests/test_skill_shipped.py'`, then `uv run mcp-htmleditor skill --type medical`: the topic prints with first line `# Skill topic: medical`, its size is at most 8 000 bytes, and every anchor of the story is present. Observable: the gate cases below pass for `medical`, `medical-sources`, and `make check` is green.

## Design excerpt

### Decisions
- DEC-016 (SPEC-0006): "Migration order: machinery (A to D), core (E), content stories (F to M), closing (N). Each content story `git mv`s its legacy source into `docs/skill-archive/` and ships its new topics; no legacy fallback, the audit stays strict (missing means problem); the work is released only after N."
- DEC-017 (SPEC-0006): "`tests/data/skill_anchors.json` plus the review sub-agent make the priority rule checkable. Anchors are verbatim substrings chosen from the archived source for every "never", "always", "mandatory" rule and every attribute or class the agent must write."
- DEC-018 (SPEC-0006): the content recipe below, "Slides: shared sections appear in both slides topics, class correspondence table in `slides-ei` only; medical sections 1 to 6 and 9 to 12 to `medical`, 7 and 8 to `medical-sources`."
- DEC-001 (SPEC-0006): topic files hold the body only; the first line `# Skill topic: <t>` is produced by code.

### Data model
none (the anchors file is a JSON object `{topic: [verbatim substrings the topic must contain]}`).

### Contracts
Topic rendering (from `SkillLibrary.topic_output`): `# Skill topic: <t>\n\n` + topic file stripped + `\n`. Budget: whole output at most 8 000 bytes (the code adds about 30 bytes, so aim for a topic file of at most 7 900 bytes).

Source to topic mapping of this story:
- `medical` <- `skill/types/medical.md` sections 1 to 6 and 9 to 12 (Positionnement, Jetons et table des classes, Anatomie, Les 16 types, Surface claire et sombre, Largeurs w-*, Lisibilité, Budget de hauteur, Export PPTX de la charte without the dated defect list, Règles de construction); about 24 700 bytes to cut to 8 000
- `medical-sources` <- `skill/types/medical.md` sections 7 (Citer ses sources) and 8 (Anonymisation des images de patient)

Content recipe (DEC-018), applied to every topic of this story:
1. `git mv` each legacy source to `docs/skill-archive/` (same base name) so the removed text is kept.
2. List the rules with `rg -n "jamais|toujours|obligatoire|MUST|NEVER|ne pas"` on the archived source.
3. Write the topic body (no `# Skill topic:` line, the code adds it): keep the rules first; then the names (attributes, classes) that appear in the kept example, plus one table of at most 1 500 bytes; then one complete example. Drop long rationale paragraphs first, then secondary examples. Meaning of a rule is never changed (spec 3.2).
4. Remove stale statements: `GrapesJS` (say "the editor"), `6 outils`, `15 types`, `localhost:7842` as a rule (keep "read the `port` returned, never assume 7842"), a forced `git commit` step, the dated defect list `Défauts d'export mesurés`.
5. Replace pointers to legacy files (`skill/types/*.md`, `skill/workflow-*.md`) by `mcp-htmleditor skill --type <topic>`.
6. For the six reference topics end the file with the exact line `Reference: <file>`; other topics carry no `Reference:` line.
7. Add the anchors below to `tests/data/skill_anchors.json` under the topic name (JSON object `{topic: [substring, ...]}`), each a verbatim substring of both the archived source and the new topic.
8. Run the gate (`make check`); then an independent read only review compares the topic with the archived source against the priority rule and reports missing rules before the story is accepted.


### Paths
| Path | Action |
|---|---|
| `skill/topics/medical.md` | new |
| `skill/topics/medical-sources.md` | new |
| `skill/types/medical.md` | move to `docs/skill-archive/medical.md` (git rename, text kept) |
| `tests/data/skill_anchors.json` | modify (add keys `medical`, `medical-sources`) |

### Existing patterns
- Gate cases in `tests/test_skill_shipped.py` (created by US-0025), parametrized over `skill/topics/<t>.md` files that exist and over `tests/data/skill_anchors.json`; this story adds no test code.
- Legacy sources under `skill/` (listed in Paths) are the text to cut; `skill_audit.find_stale` defines the stale list; `skill_content.TOPICS` holds names and descriptions.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

This story carries no spec E2E test. Its acceptance is the per topic content gate defined in design DEC-017 and DEC-018, run by `tests/test_skill_shipped.py` through `make check`. Level: gate (Unit/E2E hybrid on the real shipped tree); Driver: pytest parametrized over the topic files; Location: `tests/test_skill_shipped.py` plus `tests/data/skill_anchors.json`.

#### Topic `medical` (Rules for medical slides: layouts, light and dark surfaces, widths, readability, height budget)
- Size: `topic_output("medical")` is at most 8 000 bytes (`len(text.encode("utf-8")) <= 8000`); the audit item line for `medical` ends with `OK`.
- Shape: first line is exactly `# Skill topic: medical`; the text ends with exactly one newline; the file `skill/topics/medical.md` does not itself contain the line `# Skill topic: medical`.
- Reference: Last line is exactly `Reference: templates/reference/slides/medical.html`; no other line starts with `Reference:`.
- Stale: `find_stale(text, include_counts=False)` returns `[]`.
- Anchors: every string below is a substring of `topic_output("medical")` (they are the `tests/data/skill_anchors.json["medical"]` entry this story adds):
```json
[
  "Jamais de mélange de chartes",
  "--med-teal",
  "--med-orange",
  ".med-band",
  "<i></i><b></b>",
  "class=\"slide dark\"",
  "w-25",
  "w-70",
  "data-slide-type",
  ".slide-foot-page",
  "Trebuchet MS",
  "make sync-medical-css",
  "jamais de sens porté par la seule couleur",
  "Ne jamais réduire la taille de police",
  "class=\"slide dense\"",
  "class=\"med-table compact\"",
  "16 layouts",
  "Chaque enfant direct d'une rangée porte une classe de largeur explicite"
]
```
- The dated section `### Défauts d'export mesurés au 2026-08-21 (à connaître, non corrigés)` is not in the topic (it stays in the archive; the gate's stale check covers it).

#### Topic `medical-sources` (Medical slides: citing sources and anonymising patient images)
- Size: `topic_output("medical-sources")` is at most 8 000 bytes (`len(text.encode("utf-8")) <= 8000`); the audit item line for `medical-sources` ends with `OK`.
- Shape: first line is exactly `# Skill topic: medical-sources`; the text ends with exactly one newline; the file `skill/topics/medical-sources.md` does not itself contain the line `# Skill topic: medical-sources`.
- Reference: No line starts with `Reference:`.
- Stale: `find_stale(text, include_counts=False)` returns `[]`.
- Anchors: every string below is a substring of `topic_output("medical-sources")` (they are the `tests/data/skill_anchors.json["medical-sources"]` entry this story adds):
```json
[
  ".med-source",
  "src-title",
  "Vancouver",
  "ICMJE",
  "DICOM",
  "PatientName",
  "AccessionNumber",
  "Toute slide portant des pixels de tiers a une ligne",
  "Citer n'est pas obtenir un droit",
  "J+14",
  "Figure N reproduite de",
  "Jamais",
  "Courtoisie de l'unité de pneumologie interventionnelle"
]
```

#### Source relocation (all topics of the story)
- `skill/types/medical.md` is no longer present under `skill/`, and `docs/skill-archive/medical.md` exists and is not empty.

## Constraints

- Files not to touch: Python sources, `Makefile`, `pyproject.toml`, `skill/core.md` (the index lines already exist), other topics, `tests/test_skill_shipped.py`.
- Dependencies not to add: none.
- Patterns to avoid: changing the meaning of a rule, dropping a "never" rule while keeping rationale, copying text from another charter's topic, em or en dashes in the topic text, keeping a legacy file under `skill/`, a legacy fallback.
- Scope boundary: rewording rules is out of scope (spec 3.2); the dated defect list stays only in the archive until SPEC-0011.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (here: the anchor entries and the size/shape gate fail for the missing topic files before they are written).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: all gate cases of the core and of topics shipped by earlier stories, `tests/test_skill_content.py` and `tests/test_skill_audit*.py` stay green.
- [ ] Docs updated: the removed text is kept in `docs/skill-archive/`; user docs are updated by US-0034.
- [ ] Self review: full at tier 2, including the read only comparison of each topic with its archived source.
- [ ] One commit `US-0027: Topics medical and medical-sources`, body `Spec: SPEC-0006` and `FR-NEW-002, FR-NEW-007, FR-NEW-009`.
