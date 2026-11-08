# US-0111: Stale skill and script pointers

> Spec: SPEC-0018 (sdlc/specs/SPEC-0018-documentation-and-stale-pointers/)
> Nature: DEBT
> Priority: P1
> Depends on: main
> min_tier: 1
> Files touched: 30
> Closes spec: no

## Objective

48 lines in 23 files still point to skill files removed by SPEC-0006, seven comments place editor functions in the wrong script, `AGENTS.md` names a `specs/` folder that does not exist and the `arch-diagram` topic denies a badge export that works. This story replaces every stale pointer by one that resolves, corrects the two false statements, and adds the structural tests that keep them out. One decision applied 30 times (DEC-007): wide but mechanical, with three silent pitfalls listed under Constraints.

## Requirements covered

- SPEC-0018/DR-001: The repository SHALL NOT contain `skill/types/`, `skill/workflow-` or `.pi/skills/` in any file under `src/`, `tests/`, `templates/`, `tools/`, `skill/`, `dynamic-skills/`, `.agent_docs/`, `docs/` (except `docs/skill-archive/`), nor in `README.md`, `AGENTS.md`, `Makefile`, `Dockerfile`, except in `tests/test_arch_checks.py` and `tests/test_stale_pointers.py`.
- SPEC-0018/DR-002: The sources under `src/mcp_htmleditor/` and `tests/` SHALL name, in every comment pointer of the form `(voir|see) <script>.js[ 's] <name>`, `(voir|see) <name> in [static/]<script>.js` or `<name>() in <script>.js` / `<name>() ([static/]<script>.js)`, the script of `src/mcp_htmleditor/static/` that defines `function <name>(` or `async function <name>(`.
- SPEC-0018/DR-003: `AGENTS.md` SHALL state that specifications live in `sdlc/specs/` and deferred ideas in `sdlc/backlog/`.
- SPEC-0018/DR-004: `skill/topics/arch-diagram.md` SHALL replace the sentence `Le badge n'est pas converti à l'export PPTX.` by `Le badge est exporté en PPTX (cercle numéroté).`
- SPEC-0018/DR-007 (partial: this story's edits): The system SHALL produce, for every input covered by the existing test suite, byte identical observable output before and after this change, except the documentation text named in DEC-002 and DEC-003.

## Independent Test

`make test ARGS='-k stale_pointers'`: before the edits DT-010 reports 51 hits, DT-012 fails on `slide-layouts.js:192`, DT-014 fails on the old sentence, DT-011 passes; after the edits all four pass. `make check-generated` passes (generated families regenerated, not hand edited). `make run ARGS='skill-audit'` reports `arch-diagram` at about 7867 bytes, OK. `make check` green.

## Design excerpt

### Decisions

- DEC-001 (SPEC-0018): Pointer form by audience: `skill/topics/<topic>.md` in source, tests and agent docs; `mcp-htmleditor skill --type <topic>` in text that reaches users (shipped templates, the two layout markup strings of `slide-layouts.js` inserted into decks, README).
- DEC-002 (SPEC-0018): Correcting a false sentence in a skill topic is documentation, not a behavior change (`tests/test_export_pptx.py:656` proves the badge exports).
- DEC-003 (SPEC-0018): Comment text inside the shipped templates is not a contract; generated families are regenerated through their own targets so `check-generated` stays green.
- DEC-007 (SPEC-0018): one story for all pointers, `min_tier: 1`, decision density rule.
- DEC-008 (SPEC-0018): this story does not touch `.agent_docs/testing.md` (US-0112 adds the row for `test_stale_pointers.py`).

### Token tables (verbatim from DR-001 and DR-002)

- **New form:** in `src/`, `tests/` and `.agent_docs/`: `skill/topics/<topic>.md`; in `templates/`, in the layout markup strings `slide-layouts.js:159` and `:306` (copied into user decks) and in `README.md`: `mcp-htmleditor skill --type <topic>`; only the path token is replaced, the rest of each line stays; README routing skill: `dynamic-skills/html-editor/SKILL.md`, installed by `make install-skill` into `~/.pi/agent/dynamic-skills/html-editor/`.
- **Topic mapping (old → topic):** `types/arch-diagram` → `arch-diagram`; `types/medical` → `medical`, except the line naming `§ Citer ses sources` → `medical-sources`; `types/slides` → `slides-carbon` in `slides-empty.html` and `ibm-carbon.html`, → `medical` in `medical.html:19` and `example-medical-complete.html:24`; `types/website` → `website`; `types/mail` → `mail`; `workflow-export` → `export`; `workflow-arch-qa` → `arch-qa`.
- **Anchors that stay**, only the path token replaced: `§ Largeurs` (medical, 3 lines), `§ Citer ses sources` (medical-sources, 3 lines), `section hauteur utile` (`slides-empty.html:105`, `ibm-carbon.html:289`), `section "Hauteur utile d'une slide"` (`slides-empty.html:86-87`, read as `mcp-htmleditor skill --type slides-carbon,` / `section "Hauteur utile d'une slide"`), `§ Hauteur utile` (`slides-empty.html:223-224`, read as `(mcp-htmleditor skill --type slides-carbon` / `§ Hauteur utile)`).
- **Anchors that change:** `§ Interactivite` (2 lines) becomes `§ Interactivité`; `§ Hauteur utile d'une slide` (`medical.html:19`, `example-medical-complete.html:24`) becomes `§ Hauteur`, so those two lines read `(mcp-htmleditor skill --type medical § Hauteur).`
- **Script pointers, old to new:** `tests/test_autosave_focus_e2e.py:3` ``saveContent()`` in ``editor.js`` → ``saveContent()`` in ``editor-save.js``; `tests/test_http_assets.py:4` `` `resolveTemplateAssets()` (static/editor.js) `` → `` `resolveTemplateAssets()` (static/editor-slides.js) ``; `tests/test_undo_redo_e2e.py:1` `in editor.js.` → `in editor-undo.js.`; `slide-layouts.js:192` `voir editor.js resolveTemplateAssets` → `voir editor-slides.js resolveTemplateAssets`; `http_server.py:920` `see resolveTemplateAssets in static/editor.js` → `see resolveTemplateAssets in static/editor-slides.js`; `http_server.py:602` `see editor.js's ``requestArchLayout``` → `see editor-menus.js's ``saveThenLayout```; `arch_layout.py:21` `(set by ``editor.js`` on the first` → `(set by ``editor-drag.js`` on the first`.
- **AGENTS.md:135-137 new form:** `Specifications live in \`sdlc/specs/SPEC-NNNN-<slug>/\` (never modify an existing one, only reference and flag inconsistencies). Deferred ideas are tracked one per file in \`sdlc/backlog/BL-NNNN-<slug>.md\`.`
- **`.agent_docs/architecture.md:206-207`:** remove `; code comments naming \`skill/types/*\` or \`skill/workflow-*\` are stale (backlog).`, leaving `The old skill is frozen in \`docs/skill-archive/\`.`

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/mcp_server.py:187`, `cli.py:279`, `config.py:187`, `arch_layout.py:12,21,102,391`, `http_server.py:602,920`, `export/to_pptx.py:21` | edit comment |
| `src/mcp_htmleditor/static/slide-layouts.js:159,306` (command form), `:339` (path form), `:192` | edit |
| `src/mcp_htmleditor/static/editor-menus.js:8,268`, `editor.js:310` | edit comment |
| `tests/test_undo_redo_e2e.py:1,83`, `tests/test_autosave_focus_e2e.py:3`, `tests/test_http_assets.py:4`, `tests/test_templates.py:78` | edit comment or docstring |
| `templates/bootstrap/slides-empty.html:7,86,105,207,223` | edit |
| `templates/bootstrap/slides-medical-empty.html:10,103,142,186,356` | edit (`<style>` lines are the source of `make sync-medical-css`) |
| `templates/bootstrap/website-empty.html:9,175`, `mail-empty.html:4,19` | edit |
| `templates/reference/slides/ibm-carbon.html:289`, `euro-information.html:202`, `medical.html:19`, `example-medical-complete.html:24` | edit |
| `templates/reference/websites/ibm-carbon.html:5,345`, `templates/reference/documents/mail-carbon-example.html:6,16` | edit |
| `templates/bootstrap/slides-ei-empty.html`, `<style>` of `medical.html` and `example-medical-complete.html` (`:115,154,198,368`) | regenerate: `make bootstrap-ei`, `make sync-medical-css` |
| `README.md:619`, `AGENTS.md:135-137`, `skill/topics/arch-diagram.md:53` | edit |
| `.agent_docs/html-conventions.md:44`, `.agent_docs/architecture.md:206-207` | edit |
| `tests/test_stale_pointers.py` | create |

### Existing patterns

- In process CLI with the real skill tree: `tests/test_skill_shipped.py:91-99` (`real_tree` fixture) and `:341` (`CliRunner().invoke(main, ...)`).
- Assertions that old paths are absent: `tests/test_arch_checks.py:199-200`.
- Generated families: `Makefile:251-256`, `tests/test_generated_freshness.py`, `tests/test_ei_bootstrap_generation.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0018/DT-010: No removed skill path survives
- Level / Driver / Location: structural / `Path.rglob` walk / `tests/test_stale_pointers.py`
- Given the files with suffix `.py`, `.js`, `.html`, `.css`, `.md`, `.json`, `.toml`, `.yml`, `.yaml`, plus `Makefile` and `Dockerfile`, under the roots of DR-001 (hidden folders included, skipping `docs/skill-archive/`, `__pycache__`, `tests/test_arch_checks.py` and `tests/test_stale_pointers.py`)
- When the walk reads them
- Then no line contains `skill/types/`, `skill/workflow-` or `.pi/skills/`, and `AGENTS.md`, `README.md`, `.agent_docs/*.md` contain no match of `(?<![\w/])specs/(\*\.md|BACKLOG\.md)`; the failure message lists `path:line` of each hit
- Red before the fix because: the walk reports 51 hits (48 skill path lines, `README.md:619`, `AGENTS.md:135`, `AGENTS.md:137`).

### SPEC-0018/DT-011: Every skill pointer resolves
- Level / Driver / Location: structural / same walk / `tests/test_stale_pointers.py`
- Then every match of `skill/topics/([a-z][a-z-]*)\.md` names an existing `skill/topics/<name>.md`, and every match of `skill --type ([a-z][a-z-]*)` names a stem of `skill/topics/*.md`; failure lists `path:line: <name>`
- Green before and after (49 current mentions); it guards the replacements.

### SPEC-0018/DT-012: Script comment pointers resolve
- Level / Driver / Location: structural / regex scan / `tests/test_stale_pointers.py`
- Given `src/mcp_htmleditor/**/*.py`, `src/mcp_htmleditor/static/*.js`, `src/mcp_htmleditor/static/*.css`, `tests/*.py` (this file excluded)
- Then for every match of form A `(?:voir|see|Voir|See) ([\w-]+\.js)(?:'s)? `{0,2}(\w+)` (script, name), form B `(?:voir|see|Voir|See) `{0,2}(\w+)`{0,2} in (?:static/)?([\w-]+\.js)` (name, script) and form C ``{0,2}(\w+)\(\)`{0,2} (?:in `{0,2}|\()(?:static/)?([\w-]+\.js)` (name, script), `src/mcp_htmleditor/static/<script>` exists and contains `function <name>(`; at least one match exists
- Red before the fix because: `slide-layouts.js:192` names `editor.js`, which holds no `function resolveTemplateAssets(`. After the fix the same 5 lines match and resolve.

### SPEC-0018/DT-014: The arch-diagram topic states the exported badge
- Level / Driver / Location: functional, in process / `CliRunner` / `tests/test_stale_pointers.py`
- Given `HTMLEDITOR_SKILL_DIR` set by `monkeypatch.setenv` to the repository `skill/` folder, `config_module.reset_settings_cache()` called after it, `configure_tracing` patched as in `tests/test_skill_shipped.py:91-99`
- When `CliRunner().invoke(main, ["skill", "--type", "arch-diagram"])` (`main` from `mcp_htmleditor.cli`)
- Then exit code 0, stdout contains `Le badge est exporté en PPTX (cercle numéroté).` and does not contain `n'est pas converti`
- Red before the fix because: `skill/topics/arch-diagram.md:53` holds `Le badge n'est pas converti à l'export PPTX.`

## Constraints

- Files not to touch: `docs/skill-archive/**`, `sdlc/**`, `tests/test_arch_checks.py`, `.agent_docs/testing.md` (DEC-008), any other existing test line than the five of SPEC-0018 Section 8.4.
- Never edit `templates/bootstrap/slides-ei-empty.html` or the `<style>` of `medical.html` / `example-medical-complete.html` by hand: edit the sources, run `make bootstrap-ei` and `make sync-medical-css`, then `make check-generated`.
- `slide-layouts.js:159` and `:306` are layout markup copied into user decks: command form; `:339` is a script comment: path form.
- Only the path token changes on each line, except the two anchor rewrites listed; the `skill-audit` budget of `arch-diagram` stays at most 8000 bytes.
- Dependencies not to add: any. Scope boundary: the agent docs consolidation and DT-013 belong to US-0112.

## Definition of done

- [ ] RED evidence recorded for DT-010, DT-012, DT-014 before the edits (DT-011 green before, by design).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: generated freshness, template guards, skill shipped and PPTX golden tests unchanged and green.
- [ ] DEBT: the existing suite passes unmodified, exceptions: 5 comment and docstring lines (`tests/test_undo_redo_e2e.py:1`, `:83`, `tests/test_autosave_focus_e2e.py:3`, `tests/test_http_assets.py:4`, `tests/test_templates.py:78`).
- [ ] Docs updated: `README.md:619`, `AGENTS.md:135-137`, `skill/topics/arch-diagram.md:53`, `.agent_docs/html-conventions.md:44`, `.agent_docs/architecture.md:206-207`; no other doc.
- [ ] Self review: full.
- [ ] One commit `US-0111: Stale skill and script pointers`, body `Spec: SPEC-0018` and `DR-001, DR-002, DR-003, DR-004, DR-007`.
