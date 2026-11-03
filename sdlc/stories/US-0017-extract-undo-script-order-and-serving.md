# US-0017: Extract undo script, order and serving tests

> Spec: SPEC-0012 (sdlc/specs/SPEC-0012-charter-registry-and-splits/)
> Nature: DEBT
> Priority: P1
> Depends on: US-0016
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Moves undo and redo out of `editor.js` into `static/editor-undo.js`, completes the eleven script order in `editor.html`, makes `tools/check_ei_insert.py` load the eleven scripts, and adds the tests that prove the scripts are served without cache, in order, syntactically valid and free of duplicate global functions.

This is a DEBT story: observable behavior is unchanged. The existing suite passes unmodified: `make test` (278 tests at the start of this work, `uv run pytest --collect-only -q`), tolerated exceptions: none.

## Requirements covered

- SPEC-0012/DR-006: The editor page SHALL load, in this order, the classic scripts `slide-layouts.js`, `doc-blocks.js`, `editor-undo.js`, `editor-edit.js`, `editor-format.js`, `editor-menus.js`, `editor-save.js`, `editor-slides.js`, `editor-blocks.js`, `editor-drag.js`, `editor.js`; each has at most 500 lines; `editor.js` holds the state declarations (l.15-68), the start up block (l.69-184) and the polling and is loaded last; no global function or variable changes name. The top level `let` and `const` declarations of `editor.js` SHALL NOT be read or written at script evaluation time by any other script, only inside functions; the start up block and the `setInterval` of the polling SHALL stay in `editor.js`; each script SHALL evaluate without throwing when loaded alone after `slide-layouts.js` and `doc-blocks.js`.
- SPEC-0012/DR-008: `GET /static/editor.js` SHALL keep answering with `Cache-Control: no-store`, and the new scripts SHALL be served the same way under `/static/`.

## Independent Test

`make test ARGS='tests/test_static_scripts.py tests/test_http_caching.py tests/test_undo_redo_e2e.py tests/test_autosave_focus_e2e.py'`
- Expected: all passed. Non mock assertions: a real HTTP server answers 200 and `Cache-Control` containing `no-store` for `/static/editor.js` and each `/static/editor-*.js` (eight files); a real Chromium loads `/` and records no `pageerror`; `node --check` runs on the real files.
- RED evidence: before the change `GET /static/editor-undo.js` answers 404 and `editor.html` lists three tags, so DT-004 and DT-012 fail.

## Design excerpt

### Decisions

- DEC-001 (SPEC-0012): classic scripts, not ES modules, for the editor split. Alternatives considered: ES modules (need `type="module"` and explicit exports; the iframe and `onclick` attributes call globals, so every function would be re attached to `window`; rejected as a behavior risk with no user gain). Rationale: zero change of global names. Implemented by: DR-006. Evidence: `static/editor.html:81-83` shows classic tags; no `import` or `export` in the three scripts.
- DEC-007 (SPEC-0012): during the editor split the code not yet moved stays in `editor.js` (loaded last), each story inserts its new script tag before `editor.js` in the final relative order; DT-012 (full order) is only asserted in the last JS story. Obliged by: DR-006.

### Data model

none

### Contracts

- Classic scripts only (DEC-001): no `import`, no `export`, no `type="module"`; every global function and variable keeps its name (`onclick` attributes and the iframe call globals).
- Moved ranges are cut and pasted verbatim, comments included; the section header comments move with their code.
- The top level `let` and `const` declarations left in `editor.js` (state l.15-68) are never read or written at script evaluation time by the new scripts, only inside functions; the start up block and `setInterval(pollStatus, pollInterval)` stay in `editor.js`, which is loaded last (DR-006).
- Each script is served by the existing static route under `/static/` with `Cache-Control: no-store` (DR-008); no server change.

Code to move (line numbers of `src/mcp_htmleditor/static/editor.js` at the start of the spec, 1998 lines; re-read before cutting):

| New script | Moved from `editor.js` |
|---|---|
| `editor-undo.js` | l.333-538 of `editor.js`: section 'Undo / redo (structural mutations only)': `UNDO_MAX_DEPTH` l.357, `undoStack`, `redoStack`, `restoringFromUndo` (l.358-366), `captureDomSnapshot` l.370, `snapshotForUndo` l.404, `restoreDomSnapshot` l.425, `handleUndoRedoKeydown` l.451, `performUndo` l.489, `performRedo` l.500, `updateUndoRedoButtons` l.511, `updateUndoRedoVisibility` l.519, `resetUndoStacks` l.533-537. 206 lines. After it `editor.js` holds l.1-332 only (state declarations l.15-68, start up block l.69-183, iframe load and polling l.184-331). |

Script tags of `editor.html` after this story, in order: `slide-layouts.js`, `doc-blocks.js`, `editor-undo.js`, `editor-edit.js`, `editor-format.js`, `editor-menus.js`, `editor-save.js`, `editor-slides.js`, `editor-blocks.js`, `editor-drag.js`, `editor.js`. Each tag has the form `<script src="/static/<name>"></script>`; the final eleven tag order is in DR-006.

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-undo.js` | create |
| `src/mcp_htmleditor/static/editor.js` | edit: remove l.333-538 (about 332 lines remain) |
| `src/mcp_htmleditor/static/editor.html` | edit: script tags l.81-83 become the eleven tags of DR-006 |
| `tests/test_static_scripts.py` | create (DT-004, DT-012) |
| `tools/check_ei_insert.py` | edit: load the eleven scripts in DR-006 order; header comment l.5-12 |

### Existing patterns

- `src/mcp_htmleditor/static/doc-blocks.js` and `slide-layouts.js` (existing classic scripts: globals, no `import`/`export`).
- `src/mcp_htmleditor/static/editor.html:81-83` (current script tags).
- Playwright suites: `tests/test_undo_redo_e2e.py`, `tests/test_autosave_focus_e2e.py`, `tests/test_website_template_e2e.py`, `tests/test_fullscreen_e2e.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0012/DT-004: `editor.js` URL and new scripts served

- Level: integration; Driver: pytest, real HTTP server (fixture pattern of `tests/test_http_caching.py`); Location: `tests/test_static_scripts.py`
- **Validates:** SPEC-0012/DR-006, SPEC-0012/DR-008
- **Then** `GET /static/editor.js` and each `GET /static/editor-*.js` return 200 with `Cache-Control: no-store`

Files: `editor.js`, `editor-undo.js`, `editor-edit.js`, `editor-format.js`, `editor-menus.js`, `editor-save.js`, `editor-slides.js`, `editor-blocks.js`, `editor-drag.js` (nine files; `editor-*.js` means the eight new ones).

### SPEC-0012/DT-012: Script order and syntax

- Level: integration + E2E; Driver: pytest, `node --check`, Playwright, regular expression; Location: `tests/test_static_scripts.py`
- **Asserts:** `editor.html` lists the eleven scripts in the order of SPEC-0012/DR-006; `node --check` passes on every `static/*.js` including `slide-layouts.js` and `doc-blocks.js`; a Playwright smoke test loads the editor page and sees no page error; no top level function name is defined in two static scripts
- **Method:** HTML parse, process call, regular expression over `function <name>(` definitions

Expected order (DR-006): `slide-layouts.js`, `doc-blocks.js`, `editor-undo.js`, `editor-edit.js`, `editor-format.js`, `editor-menus.js`, `editor-save.js`, `editor-slides.js`, `editor-blocks.js`, `editor-drag.js`, `editor.js`. The duplicate check scans `^(async )?function ([A-Za-z0-9_$]+)\(` over every `static/*.js` and asserts each name occurs once in total. The smoke test opens the served editor page with `page.on('pageerror')` collecting errors and asserts the list is empty after load.

## Constraints

- Files not to touch: existing tests, `slide-layouts.js`, `doc-blocks.js`, any Python source under `src/`.
- Edit `tools/check_ei_insert.py` only to load the eleven scripts in DR-006 order and fix its header comment; do not run it as part of `make check` (it needs a manual visual review).
- No ES modules, no renamed or new global, `editor-undo.js` at most 500 lines, `editor.js` at most 500 lines.
- Dependencies not to add: none.
- Scope boundary: size cap tests and remaining documentation are US-0018 to US-0020.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the existing suite passes unmodified via `make test` (278 tests at the start of this work); tolerated exceptions: none.
- [ ] DEBT: the existing suite passes unmodified, exceptions: none.
- [ ] Docs updated: none in this story (design assigns the documentation to US-0018, US-0019, US-0020).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0017: Extract undo script, order and serving tests`, body `Spec: SPEC-0012` and the requirement ids (DR-006, DR-008).
