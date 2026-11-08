# Documentation and stale pointers: technical debt design

> Id: SPEC-0018
> Nature: DEBT
> Depth: M
> Depth evidence: one theme (documentation), 33 files, 58 stale lines plus 4 over length agent docs, no program contract change
> Status: specified
> Generated on: 2026-11-08
> Behavior change: none in program behavior; documentation text only (DEC-002, DEC-003), declared in Section 7
> From backlog: BL-0012, BL-0021, BL-0025, BL-0026 (and the over length `.agent_docs` files, project rule)
> Depends on: none
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Debt

### DBT-001: Pointers to skill files that no longer exist
- **Current structure:** SPEC-0006 moved `skill/types/*.md` and `skill/workflow-*.md` to `docs/skill-archive/` and replaced them by `skill/topics/*.md` (`ls skill/topics`: 15 files). 48 lines in 23 files outside `docs/skill-archive/` and `sdlc/` still name the old paths (Section 2), two of them in `.agent_docs/`. `README.md:619` names `.pi/skills/mcp-htmleditor/`, while the routing skill source is `dynamic-skills/html-editor/SKILL.md` and `make install-skill` copies it to `~/.pi/agent/dynamic-skills/html-editor` (`Makefile:37`, `Makefile:201`).
- **Cost paid today:** agents and developers follow comments as instructions; every one of these pointers leads to a missing file, and the shipped templates copy the dead pointer into each new user file.
- **Target structure:** source and test comments name `skill/topics/<topic>.md`; shipped templates and README name the command `mcp-htmleditor skill --type <topic>`; a structural test keeps the old paths out (DT-010, DT-011).
- **Observable behavior:** program behavior unchanged; comment text of the shipped templates changes (DEC-003).

### DBT-002: Comments place moved editor code in `editor.js`
- **Current structure:** the SPEC-0012 split moved code out of `editor.js`; four comments still point there: `src/mcp_htmleditor/static/slide-layouts.js:192` (`voir editor.js resolveTemplateAssets`) and `src/mcp_htmleditor/http_server.py:920` (`see resolveTemplateAssets in static/editor.js`), the function being defined at `src/mcp_htmleditor/static/editor-slides.js:89`; `http_server.py:602` (`see editor.js's ``requestArchLayout```), while no function of that name exists and the `POST /arch-layout` is sent by `saveThenLayout` (`src/mcp_htmleditor/static/editor-menus.js:36-39`); `src/mcp_htmleditor/arch_layout.py:21` (`data-layout="manual"` set by ``editor.js``), while it is set at `src/mcp_htmleditor/static/editor-drag.js:216`. Three test docstrings do the same: `tests/test_autosave_focus_e2e.py:3` (``saveContent()`` in ``editor.js``; defined at `editor-save.js:9`), `tests/test_http_assets.py:4` (`resolveTemplateAssets()` (static/editor.js)), `tests/test_undo_redo_e2e.py:1` (`undo/redo ... in editor.js`; the undo code is `editor-undo.js`). Other `editor.js` mentions in `tests/` are true today (`test_tab_title_e2e.py:10` `onFrameLoad` at `editor.js:236`; `test_templates.py:86` `updateDocActionsVisibility` at `editor.js:306`; `test_fullscreen_e2e.py:209`, `:227` the fallback at `editor.js:202-209`; `pointer_support.py:243`, `width_support.py:65`; file name lists in `test_size_caps.py`, `test_static_scripts.py`, `test_requests_editor_e2e.py`, `test_http_caching.py`, `test_http_header_gate_e2e.py`). Other `editor.js` mentions in `src/` are true today (`editor.css:221`, `:224`: `requestFullscreen` at `editor.js:202-209`; `editor-requests.js:9`, `:230`: the status poll at `editor.js:349`; `http_server.py:662`: a list of files).
- **Cost paid today:** a reader looks for a function in the wrong file, or for one that does not exist.
- **Target structure:** each comment names the defining script and function; DT-012 checks the two pointer forms in use.
- **Python and script comments outside DT-012:** `arch_layout.py:21` names no function; it is fixed by hand (DR-002).
- **Observable behavior:** unchanged.

### DBT-003: Statements that contradict the code
- **Current structure:** `AGENTS.md:135-137` says specifications live in `specs/*.md` and the backlog in `specs/BACKLOG.md`; they live in `sdlc/specs/` and `sdlc/backlog/` (`ls sdlc`). `skill/topics/arch-diagram.md:53` says the step badge is not exported to PPTX; it is, `tests/test_export_pptx.py:656` (`test_arch_edge_badge_exports_as_a_numbered_circle`) asserts a circle holding the number.
- **Cost paid today:** an agent writes specs in the wrong folder, or avoids a badge that exports correctly.
- **Target structure:** both statements match the code (DR-003, DR-004).
- **Observable behavior:** program unchanged; the `arch-diagram` skill topic output changes by one sentence (DEC-002).

### DBT-004: Four agent docs exceed the 200 line rule
- **Current structure:** `wc -l .agent_docs/*.md`: `html-conventions.md` 300 lines (21 420 bytes), `testing.md` 254 (24 774), `architecture.md` 220 (21 056), `agent-editing.md` 201 (17 738). The global rule says above about 200 lines, consolidate (dedup, merge, keep current actionable content). Known duplication: the fullscreen mode is described in `html-conventions.md:53` and `architecture.md:128`, the pointer in `html-conventions.md:107` and `architecture.md:141`; `testing.md` keeps dated closing run logs (`testing.md:223`, `:230`) whose numbers are history, not instructions.
- **Cost paid today:** agents load more context than needed and read duplicated facts that drift.
- **Target structure:** each of the four files at most 200 lines and not larger in bytes than today; no current actionable fact lost (DR-005, DR-006); a size test keeps the rule (DT-013).
- **Observable behavior:** unchanged.

## 2. Perimeter: the Current State

Stale skill paths, recounted with `rg --hidden -n "skill/types/|skill/workflow-" --glob '!docs/skill-archive/**' --glob '!sdlc/**' --glob '!.git/**' .` (48 lines in 23 files; the 2 lines of `tests/test_arch_checks.py:199-200` are assertions that the old paths are absent and stay).

| File | Change | Occurrences |
|---|---|---|
| `src/mcp_htmleditor/mcp_server.py` | `:187` arch-diagram → `skill/topics/arch-diagram.md` | 1 |
| `src/mcp_htmleditor/cli.py` | `:279` arch-diagram | 1 |
| `src/mcp_htmleditor/config.py` | `:187` `skill/workflow-arch-qa.md` → `skill/topics/arch-qa.md` (`:186` `skill/checks/...` exists, kept) | 1 |
| `src/mcp_htmleditor/arch_layout.py` | `:12`, `:102`, `:391` arch-diagram; `:21` ``editor.js`` → ``editor-drag.js`` (DBT-002) | 3 + 1 |
| `src/mcp_htmleditor/http_server.py` | `:920` → `static/editor-slides.js`; `:602` → `editor-menus.js's ``saveThenLayout``` (DBT-002) | 2 |
| `src/mcp_htmleditor/export/to_pptx.py` | `:21` `skill/workflow-export.md` → `skill/topics/export.md` | 1 |
| `src/mcp_htmleditor/static/slide-layouts.js` | `:159`, `:306` arch-diagram, inside layout markup copied into user decks (command form, DEC-001); `:339` medical (script comment, path form); `:192` DBT-002 | 3 + 1 |
| `src/mcp_htmleditor/static/editor-menus.js` | `:8`, `:268` arch-diagram | 2 |
| `src/mcp_htmleditor/static/editor.js` | `:310` website | 1 |
| `tests/test_undo_redo_e2e.py` | `:83` docstring, arch-diagram; `:1` module docstring `in editor.js` → `in editor-undo.js` (DBT-002) | 1 + 1 |
| `tests/test_autosave_focus_e2e.py` | `:3` module docstring ``editor.js`` → ``editor-save.js`` (DBT-002) | 1 |
| `tests/test_http_assets.py` | `:4` module docstring `static/editor.js` → `static/editor-slides.js` (DBT-002) | 1 |
| `tests/test_templates.py` | `:78` comment, mail | 1 |
| `templates/bootstrap/slides-empty.html` | `:7`, `:86`, `:105`, `:223` slides → `slides-carbon`; `:207` arch-diagram | 5 |
| `templates/bootstrap/slides-ei-empty.html` | `:207` arch-diagram, generated from `euro-information.html` by `make bootstrap-ei` | 1 |
| `templates/bootstrap/slides-medical-empty.html` | `:10` banner, `:103`, `:142`, `:186` medical; `:356` `§ Citer ses sources` → `medical-sources` (the four `<style>` lines are the source of `make sync-medical-css`) | 5 |
| `templates/bootstrap/website-empty.html` | `:9`, `:175` website | 2 |
| `templates/bootstrap/mail-empty.html` | `:4`, `:19` mail | 2 |
| `templates/reference/slides/ibm-carbon.html` | `:289` slides → `slides-carbon` | 1 |
| `templates/reference/slides/euro-information.html` | `:202` arch-diagram (source of the EI bootstrap line) | 1 |
| `templates/reference/slides/medical.html` | `:19` slides → `medical`; `:115`, `:154`, `:198`, `:368` copied by `make sync-medical-css` | 5 |
| `templates/reference/slides/example-medical-complete.html` | `:24` slides → `medical`; `:115`, `:154`, `:198`, `:368` copied | 5 |
| `templates/reference/websites/ibm-carbon.html` | `:5`, `:345` website | 2 |
| `templates/reference/documents/mail-carbon-example.html` | `:6`, `:16` mail | 2 |
| `README.md` | `:619` `.pi/skills/mcp-htmleditor/` (DBT-001) | 1 |
| `AGENTS.md` | `:135`, `:137` (DBT-003); documentation index rows for the four agent docs if their sections move | 2 |
| `skill/topics/arch-diagram.md` | `:53` badge sentence (DBT-003) | 1 |
| `.agent_docs/html-conventions.md` | `:44` `skill/types/medical.md` → `skill/topics/medical.md` (story A); consolidation (DBT-004, story B) | 1 + 300 lines |
| `.agent_docs/architecture.md` | `:206-207` the sentence `code comments naming \`skill/types/*\` or \`skill/workflow-*\` are stale (backlog).` removed, leaving `The old skill is frozen in \`docs/skill-archive/\`.` (story A); consolidation (story B) | 1 + 220 lines |
| `.agent_docs/testing.md`, `.agent_docs/agent-editing.md` | consolidation (DBT-004, story B) | 254 + 201 lines |
| `tests/test_stale_pointers.py` | new: DT-010, DT-011, DT-012 | 0 now |
| `tests/test_agent_docs_size.py` | new: DT-013 | 0 now |

**Already resolved, not in the perimeter:** `.agent_docs/architecture.md:27` now lists `/export/pptx`, `/export/docx` and `POST /arch-layout` (BL-0012 item 2); `tests/test_tab_title_e2e.py` no longer names a skill file (BL-0021); `tests/test_arch_layout.py:524`, `:708`, `:771` and `config.py:186` name `skill/checks/arch-diagram-checklist.md`, which exists. `skill/topics/medical.md:75` asks to reread the `dark`, `section`, `thanks` backgrounds in the PPTX: a caution, not a false claim, so BL-0012 item 4 is closed without edit (no test asserts the fill colour of those slides; the caution stays true).
**Backlog entries closed without edit in this commit:** BL-0028 (stories cite a 3 800 byte cap for `skill/topics/create.md`) is deleted as stale: the stories it names are `landed` (`sdlc/stories/_queue.md:58`, `:62`, `:63`), landed stories and the SPEC-0010 design are history that is not rewritten, the real gate is `skill-audit` (`create: 7987 bytes ... (budget 8000)`), and the two tests that met the figure already say so (`tests/test_requests_cli.py:28`, `tests/test_request_loop_acceptance.py:34`).
**Non source occurrences:** Makefile, Dockerfile, `docker-compose*.yml`, `pyproject.toml`, `dynamic-skills/html-editor/SKILL.md` and `skill/` hold no old path (same `rg`, 0 lines). `sdlc/` (history) and `docs/skill-archive/` (the archive itself) are out of scope on purpose.
**Contracts touched:** none public. The shipped templates are copied by `new` (`src/mcp_htmleditor/templates.py`); their HTML and CSS comments are not parsed by any consumer (DEC-003). The skill topic `arch-diagram` is served by `skill --type arch-diagram` and `get_skill`; one sentence changes (DEC-002).
**Guardrail coverage:** 1843 tests collected, 8 deselected (`make test ARGS='--collect-only -q'`). Generated file freshness: `tests/test_generated_freshness.py`, `tests/test_ei_bootstrap_generation.py`; template guards: `tests/test_presentation_templates_fullscreen.py`; skill sizes and anchors: `tests/test_skill_shipped.py`, `tests/data/skill_anchors.json`; PPTX goldens: `tests/test_export_golden.py`. **Test command:** `make check`.
**Total:** 33 files (31 edited, of which 2 are regenerated by make targets, and 2 new), 58 stale lines (48 skill paths, 7 `editor.js` pointers, `README.md:619`, `AGENTS.md:135` and `:137`), 1 skill sentence, 4 docs. Counted with `rg --hidden` (the first count missed `.agent_docs/`, a hidden folder: audit round 1).

## 3. Class sweep

Not a security lot.

## 4. Requirements (EARS)

### 4.1 Structural

#### DR-001 [EARS-UB]: No pointer to a removed skill file
> The repository SHALL NOT contain `skill/types/`, `skill/workflow-` or `.pi/skills/` in any file under `src/`, `tests/`, `templates/`, `tools/`, `skill/`, `dynamic-skills/`, `.agent_docs/`, `docs/` (except `docs/skill-archive/`), nor in `README.md`, `AGENTS.md`, `Makefile`, `Dockerfile`, except in `tests/test_arch_checks.py` and `tests/test_stale_pointers.py`.
- **Old form:** `skill/types/<name>.md`, `skill/workflow-<name>.md`, `.pi/skills/mcp-htmleditor/`
- **New form:** in `src/`, `tests/` and `.agent_docs/`: `skill/topics/<topic>.md`; in `templates/`, in the layout markup strings `slide-layouts.js:159` and `:306` (copied into user decks) and in `README.md`: `mcp-htmleditor skill --type <topic>`; only the path token is replaced, the rest of each line stays; README routing skill: `dynamic-skills/html-editor/SKILL.md`, installed by `make install-skill` into `~/.pi/agent/dynamic-skills/html-editor/`
- **Topic mapping (old → topic):** `types/arch-diagram` → `arch-diagram`; `types/medical` → `medical`, except the line naming `§ Citer ses sources` → `medical-sources`; `types/slides` → `slides-carbon` in `slides-empty.html` and `ibm-carbon.html`, → `medical` in `medical.html:19` and `example-medical-complete.html:24`; `types/website` → `website`; `types/mail` → `mail`; `workflow-export` → `export`; `workflow-arch-qa` → `arch-qa`.
- **Section anchors, exhaustive:** anchors that stay as written, with only the path token replaced: `§ Largeurs` (medical, 3 lines), `§ Citer ses sources` (medical-sources, 3 lines), `section hauteur utile` (`slides-empty.html:105`, `ibm-carbon.html:289`), `section "Hauteur utile d'une slide"` (`slides-empty.html:86-87`, read as `mcp-htmleditor skill --type slides-carbon,` / `section "Hauteur utile d'une slide"`), and `§ Hauteur utile` (`slides-empty.html:223-224`, read as `(mcp-htmleditor skill --type slides-carbon` / `§ Hauteur utile)`); their target is `## Hauteur utile (contrainte silencieuse)` (`skill/topics/slides-carbon.md:90`). Anchors that change: `§ Interactivite` (2 lines) becomes `§ Interactivité`; `§ Hauteur utile d'une slide` (`medical.html:19`, `example-medical-complete.html:24`) becomes `§ Hauteur`, so those two lines read `(mcp-htmleditor skill --type medical § Hauteur).`
- **Applies to:** every row of Section 2 but the four agent docs.
- **Casing convention:** topic ids are lowercase kebab case, exactly the stems of `skill/topics/*.md`.

#### DR-002 [EARS-U]: Script pointers name the defining script
> The sources under `src/mcp_htmleditor/` and `tests/` SHALL name, in every comment pointer of the form `(voir|see) <script>.js[ 's] <name>`, `(voir|see) <name> in [static/]<script>.js` or `<name>() in <script>.js` / `<name>() ([static/]<script>.js)`, the script of `src/mcp_htmleditor/static/` that defines `function <name>(` or `async function <name>(`.
- **Old to new, exhaustive:** `tests/test_autosave_focus_e2e.py:3` ``saveContent()`` in ``editor.js`` → ``saveContent()`` in ``editor-save.js``; `tests/test_http_assets.py:4` `` `resolveTemplateAssets()` (static/editor.js) `` → `` `resolveTemplateAssets()` (static/editor-slides.js) ``; `tests/test_undo_redo_e2e.py:1` `in editor.js.` → `in editor-undo.js.`; `slide-layouts.js:192` `voir editor.js resolveTemplateAssets` → `voir editor-slides.js resolveTemplateAssets`; `http_server.py:920` `see resolveTemplateAssets in static/editor.js` → `see resolveTemplateAssets in static/editor-slides.js`; `http_server.py:602` `see editor.js's ``requestArchLayout``` → `see editor-menus.js's ``saveThenLayout```; `arch_layout.py:21` `(set by ``editor.js`` on the first` → `(set by ``editor-drag.js`` on the first`.

#### DR-003 [EARS-U]: AGENTS.md names the sdlc layout
> `AGENTS.md` SHALL state that specifications live in `sdlc/specs/` and deferred ideas in `sdlc/backlog/`.
- **Old form:** `Specifications live in \`specs/*.md\` ... tracked in \`specs/BACKLOG.md\`.`
- **New form:** `Specifications live in \`sdlc/specs/SPEC-NNNN-<slug>/\` (never modify an existing one, only reference and flag inconsistencies). Deferred ideas are tracked one per file in \`sdlc/backlog/BL-NNNN-<slug>.md\`.`

#### DR-004 [EARS-U]: The arch-diagram topic states that the badge exports
> `skill/topics/arch-diagram.md` SHALL replace the sentence `Le badge n'est pas converti à l'export PPTX.` by `Le badge est exporté en PPTX (cercle numéroté).`
- The topic stays within its byte budget (`skill-audit` measures the topic output, header included: `arch-diagram: 7862 bytes` of 8000 today, while `wc -c skill/topics/arch-diagram.md` gives 7833; the new sentence is 5 bytes longer, 7867).

#### DR-005 [EARS-U]: Agent docs within the line rule
> Each of `.agent_docs/html-conventions.md`, `testing.md`, `architecture.md`, `agent-editing.md` SHALL hold at most 200 lines and at most its byte count of Section 1 DBT-004.
- DT-013 enforces 220 lines afterwards as a trigger (DEC-004); the 200 line and byte limits are checked by story B with `wc -l -c` and pasted in its report.

#### DR-006 [EARS-UB]: Consolidation loses no current fact
> The consolidation SHALL NOT drop a backticked token (text between single backquotes) present in the four files before the change unless the token is present after it in `.agent_docs/*.md` or `AGENTS.md`, or the story report lists it as removed with the `file:LINE` proving it false today.
- **Method (run once by the story, output pasted in its report):**
  `git show HEAD:.agent_docs/<f>.md | rg -o '\x60[^\x60]+\x60' | sort -u > /tmp/before-<f>` for each of the four files, then for each token check `rg -F -q -- "<token>" .agent_docs AGENTS.md`; the list of missing tokens must be empty or each one justified.
- Moves allowed: dedup across files (one home per fact, the other file points to it by `§` heading), dated history (closing run numbers, superseded measurements) reduced to the current rule it supports, merged headings. Every `AGENTS.md` index row stays true.

### 4.2 Invariance (MANDATORY)

#### DR-007 [EARS-U]: Behavior invariance
> The system SHALL produce, for every input covered by the existing test suite, byte identical observable output before and after this change, except the documentation text named in DEC-002 and DEC-003.

### 4.3 Compatibility

None: no public contract changes (Section 5).

## 5. Compatibility plan

| Contract | Kind | Public | Plan | Deprecation window | Removal condition |
|---|---|---|---|---|---|
| `skill --type arch-diagram` output | skill text | yes (agents) | one sentence corrected, no dual form (DEC-002) | n/a | n/a |
| files written by `new <key>` | template copy | yes (users) | HTML and CSS comments only change (DEC-003) | n/a | n/a |

**Dual maintenance semantics:** none; a false documentation sentence is not kept beside the true one.

## 6. Decisions

- **DEC-001:** Pointer form by audience: `skill/topics/<topic>.md` in source, tests and agent docs (read in the repository), `mcp-htmleditor skill --type <topic>` in text that reaches users (shipped templates, the two layout markup strings of `slide-layouts.js` inserted into decks, README). **Alternatives considered:** the command form everywhere (a developer reading `arch_layout.py` wants the file, and DT-011 can check a path exists); the path form everywhere (an installed template user has no `skill/topics/`). **Rationale:** each reader gets a pointer that resolves where they are. **Implemented by:** DR-001. **Evidence:** `README.md:617-619`, `skill/topics/` (15 files).
- **DEC-002:** Correcting a false sentence in a skill topic is documentation, not a behavior change. **Alternatives considered:** declare a break (nothing consumes the sentence mechanically; no test asserts it, `rg "pas converti" tests` returns nothing); leave it (agents avoid a working feature). **Rationale:** the program exports badges today (`tests/test_export_pptx.py:656`); the text follows the code. **Implemented by:** DR-004. **Evidence:** `skill/topics/arch-diagram.md:53`.
- **DEC-003:** Comment text inside the shipped templates is not a contract. **Alternatives considered:** leave the templates (the dead pointer is copied into every new user file); strip the pointers (loses guidance). **Rationale:** no consumer parses template comments; the generated families are regenerated through their own targets so `check-generated` stays green. **Implemented by:** DR-001. **Evidence:** `Makefile:251-256`, `tests/test_generated_freshness.py`.
- **DEC-004:** Add a docs size test (DT-013) at 220 lines, not 200. **Alternatives considered:** no test (the rule already drifted to 300 lines); 200 (a story adding one dated entry to a full file would fail the gate mid story). **Rationale:** cheap (reads 10 small files), and 20 lines of slack make it a trigger for consolidation, not a blocker for every edit. **Implemented by:** DT-013.
- **DEC-005:** BL-0012 items 2 and 4 and the BL-0021, BL-0026 lines listed as resolved in Section 2 are closed without edit. **Rationale:** verified true or harmless today (citations in Section 2).
- **DEC-006:** One story for the pointers (DR-001 to DR-004, DT-010 to DT-012, DT-014) and one for the consolidation (DR-005, DR-006, DT-013). **Alternatives considered:** one story (two unrelated review surfaces); one per file (DT-013 would be red for three stories). **Rationale:** each story closes its own tests.
- **Assumption:** the test plan is approved without a review round (batch run, user instruction); no question was asked.

## 7. Declared breaks

No program behavior changes. Two documentation text changes are declared for transparency (not a break of any program contract):

- **BRK-001: `arch-diagram` topic text.** Who: agents and users running `mcp-htmleditor skill --type arch-diagram` or calling `get_skill` with that topic. Change: the sentence of DR-004 (+5 bytes). Migration: none. Authorized by DEC-002.
- **BRK-002: comments in files created by `new` and in inserted layouts.** Who: users whose new files or inserted slides carry the template comments. Change: the pointers of DR-001 in HTML and CSS comments. Migration: none; existing user files keep their old comments. Authorized by DEC-003.

## 8. Tests

### 8.1 Non regression: the success criterion
The existing test suite passes **unmodified** (except the five comment and docstring lines of Section 8.4):

    make check

Test step at or below 330 s (the hard cap of `.agent_docs/testing.md` § Test step budget); a run above 330 s at load average above 30 is re run once before any trim.

### 8.2 Compatibility tests

None (no dual maintained contract).

### 8.3 Structural tests

#### DT-010: No removed skill path survives
- **Asserts:** DR-001. Reading every file with suffix `.py`, `.js`, `.html`, `.css`, `.md`, `.json`, `.toml`, `.yml`, `.yaml`, plus `Makefile` and `Dockerfile`, under the roots of DR-001 (skipping `docs/skill-archive/`, `__pycache__`, and the two allowed test files), no line contains `skill/types/`, `skill/workflow-` or `.pi/skills/`; and `AGENTS.md`, `README.md`, `.agent_docs/*.md` contain no match of `(?<![\w/])specs/(\*\.md|BACKLOG\.md)`. The failure message lists `path:line` of each hit.
- **Method:** Python file walk with `Path.rglob` (no subprocess); reads about 10 MB of templates once, under 1 s.
- **Red before the fix because:** the walk reports 51 hits: the 48 skill path lines of Section 2, `README.md:619`, `AGENTS.md:135` and `AGENTS.md:137`. The walk includes hidden folders (`.agent_docs/`), unlike a default `rg`.

#### DT-011: Every skill pointer resolves
- **Asserts:** in the same files, every match of `skill/topics/([a-z][a-z-]*)\.md` names an existing `skill/topics/<name>.md`, and every match of `skill --type ([a-z][a-z-]*)` names a stem of `skill/topics/*.md`; placeholders such as `skill/topics/<topic>.md` do not match by construction; failure lists `path:line: <name>`.
- **Method:** same walk, two regular expressions.
- **Note:** green before and after (49 current mentions, 37 `skill --type` and 12 `skill/topics/`, all valid, recounted with `rg -o`); it guards the replacements of DR-001.

#### DT-012: Script comment pointers resolve
- **Asserts:** DR-002: in `src/mcp_htmleditor/**/*.py`, `src/mcp_htmleditor/static/*.js`, `src/mcp_htmleditor/static/*.css` and `tests/*.py` (the DT file itself excluded), for every match of form A `(?:voir|see|Voir|See) ([\w-]+\.js)(?:'s)? `{0,2}(\w+)` (groups: script, name), form B `(?:voir|see|Voir|See) `{0,2}(\w+)`{0,2} in (?:static/)?([\w-]+\.js)` (groups: name, script) and form C ``{0,2}(\w+)\(\)`{0,2} (?:in `{0,2}|\()(?:static/)?([\w-]+\.js)` (groups: name, script), the file `src/mcp_htmleditor/static/<script>` exists and contains `function <name>(`. At least one match must exist (guards against a regex that matches nothing).
- **Matches today (recounted with a Python scan of those files):** 5, all stale: A at `http_server.py:602` and `slide-layouts.js:192`, B at `http_server.py:920`, C at `tests/test_autosave_focus_e2e.py:3` and `tests/test_http_assets.py:4`; after the fix the same 5 lines match and resolve. `test_undo_redo_e2e.py:1` and `arch_layout.py:21` name no function and are fixed by hand.
- **Red before the fix because:** `slide-layouts.js:192` names `editor.js`, which holds no `function resolveTemplateAssets(`.

#### DT-013: Agent docs stay within the size rule
- **Asserts:** every `.agent_docs/*.md` has at most 220 lines (DEC-004); failure names each file and its count.
- **Red before the fix because:** `html-conventions.md` has 300 and `testing.md` 254.

#### DT-014: The arch-diagram topic states the exported badge
- **Asserts:** DR-004: with the environment of the `real_tree` fixture (`tests/test_skill_shipped.py:91-99`) replicated in the new file (`HTMLEDITOR_SKILL_DIR` set by `monkeypatch.setenv` to the repository `skill/` folder, `config_module.reset_settings_cache()` called after it, and `configure_tracing` patched as there), `CliRunner().invoke(main, ["skill", "--type", "arch-diagram"])` (`main` from `mcp_htmleditor.cli`, as `tests/test_skill_shipped.py:341` does) exits 0 and its stdout contains `Le badge est exporté en PPTX (cercle numéroté).` and does not contain `n'est pas converti`.
- **Method:** in `tests/test_stale_pointers.py`, in process, no subprocess.
- **Red before the fix because:** the topic holds `Le badge n'est pas converti à l'export PPTX.` (`skill/topics/arch-diagram.md:53`).

**Coverage of DR-005 and DR-006:** DR-005 is checked by the story with `wc -l -c` on the four files (at most 200 lines, bytes at most those of DBT-004), DT-013 keeps the 220 line floor afterwards; DR-006 by the method of DR-006, output in the story report. **DR-003** is covered by DT-010 (the `specs/` pattern). **DR-007** by Section 8.1.

### 8.4 Existing tests to modify
| Test file | Test | Change | Justification |
|---|---|---|---|
| `tests/test_undo_redo_e2e.py` | docstring at `:83` | `skill/types/arch-diagram.md` → `skill/topics/arch-diagram.md` | comment only, no assertion or behavior; required by DR-001 |
| `tests/test_templates.py` | comment at `:78` | `skill/types/mail.md` → `skill/topics/mail.md` | comment only; required by DR-001 |
| `tests/test_undo_redo_e2e.py` | module docstring `:1` | `editor.js` → `editor-undo.js` | docstring only; required by DR-002 |
| `tests/test_autosave_focus_e2e.py` | module docstring `:3` | `editor.js` → `editor-save.js` | docstring only; required by DR-002 |
| `tests/test_http_assets.py` | module docstring `:4` | `static/editor.js` → `static/editor-slides.js` | docstring only; required by DR-002 |

## 9. Implementation order

1. Story A, step 1: add DT-010, DT-011, DT-012, DT-014 (DT-010, DT-012, DT-014 red, DT-011 green).
2. Source and test comments (`src/`, the five test lines of Section 8.4): `make test ARGS='-k "stale_pointers or arch or templates"'` green except the template and doc hits of DT-010; DT-012 green.
3. Templates: edit sources only (`slides-empty.html`, `slides-medical-empty.html` banner and `<style>`, `euro-information.html`, banners of `medical.html` and `example-medical-complete.html`, websites, mail), then `make bootstrap-ei` and `make sync-medical-css`, then `make check-generated`. Never edit `slides-ei-empty.html` or the medical reference `<style>` by hand.
4. `README.md:619`, `AGENTS.md:135-137`, `skill/topics/arch-diagram.md:53`, `.agent_docs/html-conventions.md:44`, `.agent_docs/architecture.md:206-207` (the `src/` pointers, `http_server.py:602`, `:920` and `arch_layout.py:21` included, are done in step 2); `uv run mcp-htmleditor skill-audit` through `make run ARGS='skill-audit'` reports OK. DT-010 to DT-012 and DT-014 green; `make check` green.
5. Story B: add DT-013 (red), consolidate the four docs (DR-005, DR-006, method output in the report), fix `AGENTS.md` index rows if a section moved; DT-013 green; `make check` green.

Between steps the existing suite stays green: comments do not reach any assertion, and the generated families are regenerated in the same step that edits their source.

## 10. Implementability gate
| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 2 | 3 | NOT-IMPLEMENTABLE |
| 2 | 2 | 0 | NOT-IMPLEMENTABLE |
| 3 | 1 | 2 | NOT-IMPLEMENTABLE (cap reached, escalated) |

**Amendments applied:** round 1: F-1 (two more stale `editor.js` pointers, `http_server.py:920` and `:602`, plus `arch_layout.py:21` found while verifying it; DR-002 and DT-012 widened), F-2 (anchor rewrites listed exhaustively), A-1 (`.agent_docs` stale lines added, counts redone with `rg --hidden`), A-2 (DR-005 states how 200 is checked), A-3 (`skill-audit` figure explained). Round 2: F-1 (three stale `editor.js` docstrings in `tests/`; DT-012 form C and `tests/*.py` scope added; 8.4 rows added), F-2 (file count 22 corrected to 23). Round 3: F-1 (anchors of `slides-empty.html:86-87` and `:223-224` listed, `§ Largeurs` and `§ Citer ses sources` counts corrected to 3), A-1 (DT-011 regexes spelled), A-2 (DT-014 replicates the `real_tree` environment); applied verbatim from the auditor and checked by the author against `rg -n -A1 "skill/types/slides" templates`; no fourth audit round was run (three round cap), so this document stays `draft` until the user accepts the round 3 amendments.

## 11. Open questions

- The test plan (Section 8) is treated as approved per the batch instruction; no interview round was held. Does not change observable behavior.
