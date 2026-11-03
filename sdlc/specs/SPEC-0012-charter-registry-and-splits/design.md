# Charter registry and file splits: technical debt design

> Id: SPEC-0012
> Nature: DEBT
> Depth: M
> Depth evidence: 4 modules plus one script touched, about 70 non source occurrences, no public contract change
> Status: designed
> Generated on: 2026-11-03
> Behavior change: none
> From backlog: n/a
> Depends on: none (SPEC-0006 to SPEC-0011 add code in the same modules; this refactor runs on the code as it is when it starts)
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

## 1. Debt

### DBT-001: The charter is described in five places
- **Current structure:** the eight charters (`ei`, `carbon`, `medical`, `doc`, `doc-perso`, `doc-ei`, `mail`, `website`) are keyed or detected in `src/mcp_htmleditor/templates.py:39-73` (template file and description per key), `src/mcp_htmleditor/export/pptx_style.py:377-386` (`detect_theme`: `--med-teal` or `.med-rule`, then `--ei-blue` or `.slide-inner`, then `--ibm-blue`, `--cds-` or `.slide-header`), `src/mcp_htmleditor/export/reference_docx.py:299` (`charter_for`), `src/mcp_htmleditor/export/to_docx.py:230` (`_charter_of`, reads the `data-doc-template` mark) and `src/mcp_htmleditor/static/slide-layouts.js:12-18` (`detectTemplate`).
- **Cost paid today:** adding or renaming a charter needs five coordinated edits; the three detectors already use different signals for the same file (`pptx_style.py:377-386` against `slide-layouts.js:12-18`), and nothing tests that they agree.
- **Target structure:** one Python module `src/mcp_htmleditor/export/charters.py` holds the eight charters; `templates.py`, `detect_theme` and `charter_for` read it; the JavaScript detector stays (it cannot import Python) and a parity test compares it with the Python detector on the eight templates.
- **Observable behavior:** unchanged.

### DBT-002: `to_pptx.py` is one 2283 line file with one 1842 line class
- **Current structure:** `src/mcp_htmleditor/export/to_pptx.py` holds the entry point (`to_pptx` l.207, `find_slides` l.272), flow structures (l.302-440), and `_SlideBuilder` (l.441-2283) that mixes charter chrome (l.487-786), flow (l.787-1031), block renderers (l.1032-1402), Gantt (l.1403-1761), architecture diagrams (l.1762-1931), images (l.1932-1997), text (l.1998-2145) and drawing primitives (l.2146-2283).
- **Cost paid today:** every export change touches the same file; `pyproject.toml:104` disables four lint rules for the whole file.
- **Target structure:** modules by responsibility composed into `_SlideBuilder` (see DR-004).
- **Observable behavior:** unchanged, down to the XML of each exported slide.

### DBT-003: `editor.js` is one 1998 line script
- **Current structure:** `src/mcp_htmleditor/static/editor.js` holds state and bootstrap (l.15-184), frame and polling (l.188-332), undo and redo (l.333-538), edit mode and injected styles (l.539-694), format and insert bars (l.695-1015), context menus, tables and arch diagrams (l.1016-1390), saving (l.1391-1440), slides (l.1441-1638), document blocks (l.1639-1759), block drag (l.1760-1904) and node drag (l.1905-1998). `src/mcp_htmleditor/static/editor.html:81-83` loads three classic scripts.
- **Cost paid today:** any editor change touches one file with no boundaries.
- **Target structure:** nine classic scripts (eight new plus `editor.js`) loaded in a fixed order (DR-006).
- **Observable behavior:** unchanged.

## 2. Perimeter: the Current State

| File | Change | Occurrences |
|---|---|---|
| `src/mcp_htmleditor/export/charters.py` | new: the registry | 0 now |
| `src/mcp_htmleditor/templates.py` | `TEMPLATES` built from the registry | 4 lines mention `TEMPLATES` (definition l.39, uses l.91, 93, 104); `cli.py:51` and `cli.py:67` call functions of `templates.py` |
| `src/mcp_htmleditor/export/pptx_style.py` | `detect_theme` reads the registry tokens | 2 source lines (`detect_theme` l.377, call l.630) and 2 test lines (`tests/test_medical_template.py:23,218`) |
| `src/mcp_htmleditor/export/reference_docx.py` | `charter_for` reads the registry | 3 lines (l.299, 326, 343) and tests `tests/test_export_docx.py:207-213` |
| `src/mcp_htmleditor/export/to_docx.py` | none (reads the mark, calls `charter_for`) | 5 lines, no change |
| `src/mcp_htmleditor/export/to_pptx.py` | split; keeps entry point, `find_slides`, constants, re-exports | 2283 lines to under 600 |
| `src/mcp_htmleditor/export/pptx_*.py` | 8 new modules (DR-004, DR-009) | 0 now |
| `src/mcp_htmleditor/static/editor.js` | split; keeps bootstrap | 1998 lines to under 500 |
| `src/mcp_htmleditor/static/editor-*.js` | 8 new scripts (DR-006) | 0 now |
| `src/mcp_htmleditor/static/editor.html` | script tags l.81-83 | 3 tags to 11 |
| `src/mcp_htmleditor/static/slide-layouts.js` | none (detector kept) | 3 lines, no change |
| `pyproject.toml` | per file lint ignores follow the new modules (DR-010) | 6 lines (comment l.99-103, ignore list l.104) |
| `tests/` | new tests only; none edited | files importing `to_pptx`: `test_export_pptx.py` (32 lines), `test_http_export.py` (5), `test_medical_template.py` (3); files naming `editor.js`: 8 files, 11 lines |

**Non source occurrences:** `tools/check_ei_insert.py` (loads the editor scripts and names `resolveTemplateAssets` and `renumberSlides`, header l.5-12; it must load the 11 scripts in DR-006 order), `tools/gen_ei_bootstrap.py` (comment naming `editor.js`), `skill/types/website.md` and `skill/types/mail.md` (name `editor.js`), `README.md` (1 line `to_pptx`, 1 line `editor.js`; l.363 and l.372), `.agent_docs/architecture.md:49,67,131`, `.agent_docs/html-conventions.md:39,130,160`, `.agent_docs/observability.md:35` (span `export.pptx` names `export/to_pptx.to_pptx`), `AGENTS.md:83` (`node --check src/mcp_htmleditor/static/*.js`), skill documents naming `to_pptx` (`skill/checks/arch-diagram-checklist.md` 2, `skill/types/arch-diagram.md` 2, `skill/types/gantt.md` 1, `skill/types/medical.md` 1), no Makefile, no container file, no CI file mention them.
**Contracts touched:** `from mcp_htmleditor.export.to_pptx import to_pptx, find_slides, _column_widths, SLIDE_W_IN, SLIDE_H_IN, ExportReport` (internal: used by `cli.py:255`, `http_server.py:221` and the tests; `tests/test_export_pptx.py:32-38` imports `SLIDE_H_IN`, `SLIDE_W_IN`, `_column_widths`, `find_slides`, `to_pptx`; `tests/test_medical_template.py:24` imports `find_slides`, `to_pptx`; `tests/test_http_export.py:38-39` patches the dotted path `mcp_htmleditor.export.to_pptx.to_pptx`, so `to_pptx` must stay defined in `to_pptx.py`, not only re-exported; `tests/test_medical_template.py:202-204` slices `slide-layouts.js` between `function detectTemplate` and `function getLayouts`, which stay in place); `GET /static/editor.js` (public to the browser shell, cached `no-store` by `tests/test_http_caching.py:63`); the span name `export.pptx` (kept). No public contract is removed.
**Guardrail coverage:** 278 tests (`uv run pytest --collect-only -q`), of which 8 Playwright files exercise the editor, and `tests/test_export_pptx.py` (1135 lines) the exporter. **Test command:** `make test` (278 passed in 100 s at the start of this work).
**Total:** 4 Python modules edited, 1 new registry module, 8 new export modules, 1 script split into 9, 1 HTML shell edited, 1 config file edited, about 12 documentation lines.

## 3. Class sweep

Not applicable (`--security` not set).

## 4. Requirements (EARS)

### 4.1 Structural

#### DR-001 [EARS-U]: One charter registry
> The Editor SHALL describe each of the eight charters once, in `src/mcp_htmleditor/export/charters.py`, as a record with the fields `key`, `kind` (`presentation`, `document`, `mail` or `website`), `template` (path under a templates directory), `description`, `css_tokens` (substrings searched in the style text), `css_classes` (class names searched in the markup), `layout_set` (`carbon`, `ei`, `medical` or none) and `docx_key` (key of a `reference_docx` charter, or none). Presentation values: medical (`--med-teal`; `med-rule`), ei (`--ei-blue`; `slide-inner`), carbon (`--ibm-blue`, `--cds-`; `slide-header`). Document, mail and website charters carry empty `css_tokens` and `css_classes`. `docx_key` is `perso` for `doc-perso`, `ei` for `doc-ei`, and none for all other charters, including `mail` and `website`. The record class is `CharterSpec` and the tuple is `REGISTRY` (not `Charter` or `CHARTERS`, which `reference_docx.py:196,291` already defines). `charters.py` imports nothing from `templates.py`.
- **Old form:** the literal dict `TEMPLATES` (`templates.py:39-73`) and the marker tests in `detect_theme` (`pptx_style.py:377-386`) and `charter_for` (`reference_docx.py:299`).
- **New form:** `REGISTRY: tuple[CharterSpec, ...]` in the order `ei, carbon, medical, doc, doc-perso, doc-ei, mail, website`.
- **Applies to:** the occurrences listed for those three files in Section 2.
- **Casing convention:** snake case, as the codebase.

#### DR-002 [EARS-U]: `TEMPLATES` from the registry
> `templates.TEMPLATES` SHALL remain a `dict[str, tuple[str, str]]` equal, key by key, in the same order, to the dict it is today, built as `{c.key: (c.template, c.description) for c in REGISTRY}`.
- **Old form:** literal dict. **New form:** comprehension over `REGISTRY`. **Applies to:** `templates.py` and the functions of it called by `cli.py:51` and `cli.py:67`.

#### DR-003 [EARS-U]: Detectors read the registry
> `detect_theme(soup)` SHALL keep returning `Theme` objects, reading only the presentation charters' `css_tokens` and `css_classes` from `REGISTRY`, evaluated in the order medical, ei, carbon, then generic, and SHALL return, for every input, what it returns today; `charter_for(key)` SHALL return the same result for every input (it resolves `perso` and `ei`, strips and lowercases the key, and returns none otherwise) using the `docx_key` fields: it returns the existing `reference_docx.PERSO` and `reference_docx.EI` objects (identity kept), `reference_docx.CHARTERS` stays a mapping of `Charter` and `charter_keys()` stays `("perso", "ei")`; `reference_docx.py` imports `charters.py` and `charters.py` imports nothing from `reference_docx.py`.
- **Old form:** inline marker tests. **New form:** loops over registry fields in the same priority.

#### DR-004 [EARS-U]: `to_pptx.py` split by responsibility
> The exporter SHALL be organised in these modules, `_SlideBuilder` being composed of the mixin classes they define: `src/mcp_htmleditor/export/pptx_chrome.py` (EI, Carbon, medical and generic chrome), `pptx_flow.py` (flow and flex row logic), `pptx_blocks.py` (grid, panel, rule, hbar, table renderers), `pptx_gantt.py`, `pptx_arch.py`, `pptx_images.py` (annotated images, images and picture primitives), `pptx_text.py` (text and paragraph rendering and drawing primitives), and `pptx_model.py` (DR-009); every mixin SHALL inherit a common base class `_BuilderBase` defined in `pptx_model.py`, which declares the instance attributes (`ctx`, `res`, `theme`, `slide`, `article`, `index`, `handled`) as annotations and declares, for each method a mixin calls from another mixin, a stub `def name(self, ...) -> ...: raise NotImplementedError`, so that strict type checking passes without `type: ignore`; `to_pptx.py` keeps `ExportReport`, `to_pptx`, `_build_pptx`, `find_slides` and the composed `_SlideBuilder` with its `__init__`, in at most 600 lines, and every new module has at most 450 lines.
- **Old form:** one file of 2283 lines. **New form:** eight files. **Applies to:** the `export/` package, `pyproject.toml` ignores.

#### DR-009 [EARS-U]: Shared types and constants in a model module
> A module `src/mcp_htmleditor/export/pptx_model.py` SHALL hold `_Context`, `_Block`, `_Column`, `_Region`, `_Para`, `_ColumnBasis`, `_column_basis`, `_column_widths` and all module constants of `to_pptx.py` (l.87-185: `SKIP_TAGS`, `SHELL_CLASSES`, `BLOCK_TAGS`, `GRID_CLASSES`, `TILE_CLASSES`, `FILL_KEYS`, `BAR_KEYS`, `_ALIGN`, `_SHAPES`, `_NOTIF_VARIANTS`, `_ANNOT_CLASS_COLORS`); no `pptx_*.py` module SHALL import from `to_pptx.py`; no mixin SHALL use a name starting with two underscores.
- **Old form:** defined in `to_pptx.py` (l.87-185, l.302-373, l.376-440). **New form:** defined in `pptx_model.py`.

#### DR-010 [EARS-U]: Lint configuration follows the modules
> `pyproject.toml` SHALL give each of the eight new `export/pptx_*.py` modules the same per file lint ignores as `to_pptx.py` today (`PLR0911`, `PLR0912`, `ARG002`, `PLR2004`), with the explanatory comment kept; `charters.py` needs none.

#### DR-005 [EARS-U]: Names kept importable
> `mcp_htmleditor.export.to_pptx` SHALL still export `to_pptx`, `find_slides`, `ExportReport`, `_column_widths`, `SLIDE_W_IN` and `SLIDE_H_IN`.
- **Old form:** `to_pptx`, `find_slides`, `ExportReport` defined in the file, `_column_widths` defined in the file, `SLIDE_W_IN` and `SLIDE_H_IN` imported from `pptx_style` (l.63-78). **New form:** defined in the new modules and re-exported by name; `to_pptx` itself stays defined in `to_pptx.py`.

#### DR-006 [EARS-U]: `editor.js` split into ordered scripts
> The editor page SHALL load, in this order, the classic scripts `slide-layouts.js`, `doc-blocks.js`, `editor-undo.js`, `editor-edit.js`, `editor-format.js`, `editor-menus.js`, `editor-save.js`, `editor-slides.js`, `editor-blocks.js`, `editor-drag.js`, `editor.js`; each has at most 500 lines; `editor.js` holds the state declarations (l.15-68), the start up block (l.69-184) and the polling and is loaded last; no global function or variable changes name. The top level `let` and `const` declarations of `editor.js` SHALL NOT be read or written at script evaluation time by any other script, only inside functions; the start up block and the `setInterval` of the polling SHALL stay in `editor.js`; each script SHALL evaluate without throwing when loaded alone after `slide-layouts.js` and `doc-blocks.js`.
- **Old form:** three `script` tags (`editor.html:81-83`). **New form:** eleven tags (nine `editor` scripts counted with `editor.js`). **Applies to:** `editor.js`, `editor.html`.

### 4.2 Invariance

#### DR-007 [EARS-U]: Behavior invariance
> The Editor SHALL produce, for every input covered by the existing test suite, byte identical observable output before and after this change, and the XML of every exported slide of the ten templates and reference decks (DT-001) SHALL be byte identical.

### 4.3 Compatibility

#### DR-008 [EARS-U]: URL kept
> `GET /static/editor.js` SHALL keep answering with `Cache-Control: no-store`, and the new scripts SHALL be served the same way under `/static/`.

## 5. Compatibility plan

| Contract | Kind | Public | Plan | Deprecation window | Removal condition |
|---|---|---|---|---|---|
| `mcp_htmleditor.export.to_pptx` names | internal | no | re-export (DR-005) | none | none |
| `/static/editor.js` | browser shell | no (same package) | kept (DR-008) | none | none |
| `/static/editor-*.js` | browser shell | no | additive | none | none |
| span `export.pptx` | trace | yes (operators) | kept | none | none |

**Dual maintenance semantics:** none; no name is renamed, only moved.

## 6. Decisions

- **DEC-001:** classic scripts, not ES modules, for the editor split. **Alternatives considered:** ES modules (need `type="module"` and explicit exports; the iframe and `onclick` attributes call globals, so every function would be re attached to `window`; rejected as a behavior risk with no user gain). **Rationale:** zero change of global names. **Implemented by:** DR-006. **Evidence:** `static/editor.html:81-83` shows classic tags; no `import` or `export` in the three scripts.
- **DEC-002:** mixin classes, not a function library, for the exporter split. **Alternatives considered:** free functions taking the builder (changes every call site of `self`, 1800 lines of edits); a package with sub builders (state sharing through `_Context` is wide). **Rationale:** mixins keep `self.` call sites unchanged. **Implemented by:** DR-004.
- **DEC-003:** keep the JavaScript detector and test parity, instead of generating it from the registry. **Alternatives considered:** generating `slide-layouts.js` fragments at build time (adds a generated file and a build step). **Rationale:** no build step exists. **Implemented by:** DR-001, DT-002.
- **Assumption:** the line numbers of Section 1 are those of the working tree at the date above; the implementer re-reads the real method boundaries before cutting.

## 7. Declared breaks

None.

## 8. Tests

### 8.1 Non regression: the success criterion
The existing test suite passes **unmodified**:

    make test

### 8.2 Compatibility tests

#### DT-001: Exported slide XML is identical
- **Validates:** DR-007 on the exporter
- **Given** golden hashes, committed under `tests/testdata/`, of the raw bytes of the slide XML parts, read from the zip (not of the zip file), recorded from the code before the change and confirmed identical on a second run of the unchanged code (an attribute that differs between runs is listed in Section 7 as a declared exception), of the slide XML parts (`ppt/slides/slide*.xml`) of the PPTX exported from `templates/bootstrap/slides-ei-empty.html`, `slides-empty.html`, `slides-medical-empty.html` and `templates/reference/slides/euro-information.html`, `ibm-carbon.html`, `medical.html`, `example-ei-complete.html`, `example-medical-complete.html`, `presentation-standard.html`, `roadmap-one-pager.html`
- **When** the test exports each file
- **Then** every part hash equals its golden hash

#### DT-002: Detectors keep their results, and Python and JavaScript are compared
- **Validates:** DR-001, DR-003
- **Given** the eight bootstrap templates, and a table of expected results recorded from the code before the change (step 1) for `detect_theme` (a `Theme` key) and for `detectTemplate` run in the browser (a template key)
- **When** both detectors are applied to each template after the change
- **Then** every result equals the recorded table
- **And** the table contains the facts known today: `detectTemplate` returns `ei` for `ei` and `doc-ei`, `medical` for `medical`, `carbon` for the five others; `detect_theme` returns the EI, Carbon and medical themes for the three presentations, the generic theme for `doc`, `doc-perso` and `mail`, the EI theme for `doc-ei` (its style holds `--ei-blue`) and the Carbon theme for `website`

#### DT-003: Names re-exported
- **Validates:** DR-005
- **Then** the six names import from `mcp_htmleditor.export.to_pptx`

#### DT-004: `editor.js` URL and new scripts served
- **Validates:** DR-006, DR-008
- **Then** `GET /static/editor.js` and each `GET /static/editor-*.js` return 200 with `Cache-Control: no-store`

### 8.3 Structural tests

#### DT-010: Registry is the only source
- **Asserts:** the three strings `--med-teal`, `--ei-blue`, `--ibm-blue` do not appear in the body of `detect_theme`; `TEMPLATES` is built by a comprehension, not a dict literal
- **Method:** source inspection of the two functions

#### DT-011: Size caps
- **Asserts:** `to_pptx.py` has at most 600 lines, each `export/pptx_*.py` at most 450, each `static/editor*.js` at most 500
- **Method:** line count assertion

#### DT-012: Script order and syntax
- **Asserts:** `editor.html` lists the eleven scripts in the order of DR-006; `node --check` passes on every `static/*.js` including `slide-layouts.js` and `doc-blocks.js`; a Playwright smoke test loads the editor page and sees no page error; no top level function name is defined in two static scripts
- **Method:** HTML parse, process call, regular expression over `function <name>(` definitions

#### DT-013: Quality gate
- **Asserts:** `make check` passes (lint, format, types, security scan, tests with 80 percent coverage)

### 8.4 Existing tests to modify

| Test file | Test | Change | Justification |
|---|---|---|---|
| none | | | |

## 9. Implementation order

1. Record the golden slide XML hashes (DT-001) and the detector table (DT-002) on the unchanged code, run twice, and commit them with their tests. Green.
2. Add `charters.py` and DT-002, DT-010 pending; switch `templates.py`, then `detect_theme`, then `charter_for` to it, one commit each. Suite green after each.
3. Create `pptx_model.py` with the types and constants first (suite green), then split `to_pptx.py` one mixin at a time, in the order text and primitives, images, arch, gantt, blocks, flow, chrome, running `make test` and DT-001 after each. Add DT-003 and the Python half of DT-011 (the `to_pptx.py` and `pptx_*.py` caps).
4. Split `editor.js` from the leaf (node drag) toward the core, updating `editor.html` each time, running the Playwright tests after each. Add DT-004, DT-012 and the JavaScript half of DT-011 (the `static/editor*.js` caps).
5. Update `pyproject.toml` ignores (DR-010), `tools/check_ei_insert.py`, documents of Section 2, then run `make check`.

## 10. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 9 | 7 | NOT-IMPLEMENTABLE |
| 2 | 3 | 3 | NOT-IMPLEMENTABLE (amended after; cap of two rounds reached) |

**Amendments applied:** all F findings of rounds 1 and 2. Concern (user waiver, 2026-11-03): the two round cap was reached with F findings amended but not re audited.

## Design additions (2026-11-03)

**Validation result:** designed, no spec issue. Checked: DEC-001..003 each name their DR (and DEC-003 DT-002); DR-001..010 are all implemented by a DEC or are mechanical (DR-002, 003, 005, 007, 008, 009, 010); the success criterion (`make test`, 278 tests unmodified) is in 8.1. Code claims re-read: `templates.py:39` (`TEMPLATES`), `pptx_style.py:377-386` (`detect_theme`), `reference_docx.py:299` (`charter_for`), `slide-layouts.js:12-18` (`detectTemplate`), `editor.html:81-83` (3 tags), `pyproject.toml:104` (ignores on `to_pptx.py`), `to_pptx.py` 2283 lines, `editor.js` 1998 lines. One ordering defect in Section 9 step 5 is resolved by DEC-004 (not a blocker).

### Decisions

- **DEC-004:** each export story adds, in the same commit, the per file lint ignores of the modules it creates (`PLR0911`, `PLR0912`, `ARG002`, `PLR2004`, comment kept), instead of step 5 doing it at the end. **Obliged by:** DR-010 and the rule that every step leaves `make check` green: a new `pptx_*.py` without the ignores fails `make lint`. **Alternatives:** a glob entry `export/pptx_*.py` in the first story (rejected: would also cover the pre existing `pptx_style.py` and `pptx_components.py`, which have narrower ignores). **Evidence:** `pyproject.toml:104`.
- **DEC-005:** `pptx_model.py` is created first (types, constants, `_BuilderBase` with stubs) and each mixin story appends the stubs it needs. **Obliged by:** DR-004, DR-009 (strict mypy without `type: ignore`). Mixins come before `_BuilderBase` in the `_SlideBuilder` bases so real methods win over stubs.
- **DEC-006:** size cap test DT-011 and the final doc fixes live in the closing story, because the caps (`to_pptx.py` at most 600 lines, `editor.js` at most 500) only hold once every split story has landed. **Obliged by:** DR-004, DR-006 and "main green after each step".
- **DEC-007:** during the editor split the code not yet moved stays in `editor.js` (loaded last), each story inserts its new script tag before `editor.js` in the final relative order; DT-012 (full order) is only asserted in the last JS story. **Obliged by:** DR-006.

### File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `tests/test_export_golden.py` | create | DR-007 | STORY-A |
| `tests/testdata/pptx_slide_hashes.json` | create | DR-007 | STORY-A |
| `tests/test_charter_detection.py` | create | DR-001, DR-003 | STORY-A |
| `tests/testdata/detector_table.json` | create | DR-001, DR-003 | STORY-A |
| `src/mcp_htmleditor/export/charters.py` | create | DR-001 | STORY-B |
| `src/mcp_htmleditor/templates.py` | edit | DR-002 | STORY-B |
| `src/mcp_htmleditor/export/pptx_style.py` | edit | DR-003 | STORY-B |
| `src/mcp_htmleditor/export/reference_docx.py` | edit | DR-003 | STORY-B |
| `tests/test_charters.py` | create (DT-010) | DR-001, DR-002 | STORY-B |
| `src/mcp_htmleditor/export/pptx_model.py` | create, then append stubs | DR-009, DR-004 | STORY-C..G |
| `src/mcp_htmleditor/export/to_pptx.py` | edit (shrinks each story) | DR-004, DR-005 | STORY-C..G |
| `pyproject.toml` | edit (ignores per new module) | DR-010 | STORY-C..G |
| `tests/test_pptx_names.py` | create (DT-003) | DR-005 | STORY-C |
| `src/mcp_htmleditor/export/pptx_text.py` | create | DR-004 | STORY-D |
| `src/mcp_htmleditor/export/pptx_images.py`, `pptx_arch.py` | create | DR-004 | STORY-E |
| `src/mcp_htmleditor/export/pptx_gantt.py`, `pptx_blocks.py` | create | DR-004 | STORY-F |
| `src/mcp_htmleditor/export/pptx_flow.py`, `pptx_chrome.py` | create | DR-004 | STORY-G |
| `src/mcp_htmleditor/static/editor-drag.js` | create | DR-006 | STORY-H |
| `src/mcp_htmleditor/static/editor-blocks.js`, `editor-slides.js` | create | DR-006 | STORY-I |
| `src/mcp_htmleditor/static/editor-save.js`, `editor-menus.js` | create | DR-006 | STORY-J |
| `src/mcp_htmleditor/static/editor-format.js`, `editor-edit.js` | create | DR-006 | STORY-K |
| `src/mcp_htmleditor/static/editor-undo.js` | create | DR-006 | STORY-L |
| `src/mcp_htmleditor/static/editor.js` | edit (shrinks each story) | DR-006 | STORY-H..L |
| `src/mcp_htmleditor/static/editor.html` | edit (script tags) | DR-006 | STORY-H..L |
| `tests/test_static_scripts.py` | create (DT-004, DT-012) | DR-006, DR-008 | STORY-L |
| `tools/check_ei_insert.py` | edit (load 11 scripts) | DR-006 | STORY-L |
| `skill/types/arch-diagram.md`, `gantt.md`, `medical.md`, `skill/checks/arch-diagram-checklist.md` | edit (paths of moved methods) | DR-004 | STORY-M |
| `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`, `html-conventions.md`, `observability.md` | edit | DR-004, DR-006 | STORY-N |
| `tests/test_size_caps.py` | create (DT-011) | DR-004, DR-006 | STORY-O |
| `skill/types/website.md`, `mail.md`, `tools/gen_ei_bootstrap.py` | edit (comment or name) | DR-006 | STORY-O |

### Test strategy

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| DT-001 slide XML hashes | integration | pytest, `to_pptx` on 10 files | `tests/test_export_golden.py` | STORY-A |
| DT-002 detector table (Python + browser) | integration + E2E | pytest, Playwright for `detectTemplate` | `tests/test_charter_detection.py` | STORY-A |
| DT-010 registry sole source | unit (source inspection) | pytest, `inspect.getsource` | `tests/test_charters.py` | STORY-B |
| DT-003 names re-exported | unit | pytest import | `tests/test_pptx_names.py` | STORY-C |
| DT-004, DT-012 scripts served, order, syntax, smoke | integration + E2E | pytest, real HTTP server, `node --check`, Playwright | `tests/test_static_scripts.py` | STORY-L |
| DT-011 size caps | unit | pytest line count | `tests/test_size_caps.py` | STORY-O |
| DT-013 quality gate | gate | `make check` | n/a | STORY-O |
| Non regression (8.1) | suite | `make test` | whole `tests/` | every story; criterion closed in STORY-O |

DT-001 is re run (it is part of `make test`) by every export story D..G.

## Stories

Every story restates: the existing suite passes unmodified (`make test`), and `make check` is green on main after it lands.

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| STORY-A | Record golden slide XML hashes and detector table | P1 | DR-007 | main | 2 | no |
| STORY-B | Charter registry, templates and detectors read it | P1 | DR-001, DR-002, DR-003 | STORY-A | 2 | no |
| STORY-C | `pptx_model.py` with types, constants, base class | P1 | DR-005, DR-009, DR-010 | STORY-B | 2 | no |
| STORY-D | Extract text and primitives mixin | P1 | DR-004, DR-010 | STORY-C | 2 | no |
| STORY-E | Extract images and arch mixins | P1 | DR-004, DR-010 | STORY-D | 2 | no |
| STORY-F | Extract Gantt and blocks mixins | P1 | DR-004, DR-010 | STORY-E | 2 | no |
| STORY-G | Extract flow and chrome mixins | P1 | DR-004, DR-010 | STORY-F | 2 | no |
| STORY-H | Extract node and block drag script | P1 | DR-006 | STORY-G | 2 | no |
| STORY-I | Extract blocks and slides scripts | P1 | DR-006 | STORY-H | 2 | no |
| STORY-J | Extract save and menus scripts | P1 | DR-006 | STORY-I | 2 | no |
| STORY-K | Extract format and edit scripts | P1 | DR-006 | STORY-J | 2 | no |
| STORY-L | Extract undo script, order and serving tests | P1 | DR-006, DR-008 | STORY-K | 2 | no |
| STORY-M | Fix skill documents naming moved exporter methods | P2 | DR-004 | STORY-G | 2 | no |
| STORY-N | Update README, AGENTS and agent docs | P2 | DR-004, DR-006 | STORY-L, STORY-M | 2 | no |
| STORY-O | Size caps, remaining mentions, full gate | P1 | DR-004, DR-006, DR-007, DR-008 | STORY-N | 2 | yes |

Counts: `rg -o 'DR-[0-9]{3}' design.md | sort -u` gives DR-001..DR-010 (10), every one cited above; `rg -o 'DT-[0-9]{3}' design.md | sort -u` gives DT-001..004, DT-010..013 (8), each in exactly one story.
