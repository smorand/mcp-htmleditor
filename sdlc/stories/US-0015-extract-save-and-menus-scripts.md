# US-0015: Extract save and menus scripts

> Spec: SPEC-0012 (sdlc/specs/SPEC-0012-charter-registry-and-splits/)
> Nature: DEBT
> Priority: P1
> Depends on: US-0014
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Moves saving and the context menus (tables, arch diagram mouse editing) out of `editor.js` into `static/editor-save.js` and `static/editor-menus.js`, loaded before `editor-slides.js`. No global name changes.

This is a DEBT story: observable behavior is unchanged. The existing suite passes unmodified: `make test` (278 tests at the start of this work, `uv run pytest --collect-only -q`), tolerated exceptions: none.

## Requirements covered

- SPEC-0012/DR-006 (partial: scripts `editor-save.js` and `editor-menus.js`): The editor page SHALL load, in this order, the classic scripts `slide-layouts.js`, `doc-blocks.js`, `editor-undo.js`, `editor-edit.js`, `editor-format.js`, `editor-menus.js`, `editor-save.js`, `editor-slides.js`, `editor-blocks.js`, `editor-drag.js`, `editor.js`; each has at most 500 lines; `editor.js` holds the state declarations (l.15-68), the start up block (l.69-184) and the polling and is loaded last; no global function or variable changes name. The top level `let` and `const` declarations of `editor.js` SHALL NOT be read or written at script evaluation time by any other script, only inside functions; the start up block and the `setInterval` of the polling SHALL stay in `editor.js`; each script SHALL evaluate without throwing when loaded alone after `slide-layouts.js` and `doc-blocks.js`.

## Independent Test

`make test ARGS='tests/test_autosave_focus_e2e.py tests/test_fullscreen_e2e.py tests/test_http_origin_e2e.py tests/test_tab_title_e2e.py tests/test_undo_redo_e2e.py tests/test_website_template_e2e.py tests/test_http_caching.py tests/test_http_assets.py'`, then `make check`.
- Expected: all passed. Non mock assertions: real Chromium runs the real editor scripts served by the real HTTP server (the Playwright suites) and `node --check` on every `static/*.js` exits 0.

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
| `editor-save.js` | l.1391-1440: section 'Save': `onEditableInput` l.1394, `onEditableBlur` l.1395, `scheduleSave` l.1396, `saveContent` l.1398-1439. 50 lines. The top level `saveTimer` and `hasPendingChanges` stay declared in `editor.js` (l.22-23) and are only used inside functions. |
| `editor-menus.js` | l.1016-1390: sections 'Context menus' and 'Declarative arch-diagram mouse editing': `isDeclarativeArchDiagram` l.1031 through `removeLastTableCol` l.1384-1389, including `ensureNodeId`, `saveThenLayout`, `addArchNodeDeclarative`, `removeArchNode`, `startArchConnect`, `cancelArchConnect`, `finishArchConnect`, `injectContextMenus`, `getContextMenuItems`, `tableContextMenu`, `showContextMenu`, `addTableRow`, `removeLastTableRow`, `addTableCol`. 375 lines. |

Script tags of `editor.html` after this story, in order: `slide-layouts.js`, `doc-blocks.js`, `editor-menus.js`, `editor-save.js`, `editor-slides.js`, `editor-blocks.js`, `editor-drag.js`, `editor.js`. Each tag has the form `<script src="/static/<name>"></script>`; the final eleven tag order is in DR-006.

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-save.js` | create |
| `src/mcp_htmleditor/static/editor-menus.js` | create |
| `src/mcp_htmleditor/static/editor.js` | edit: remove the moved ranges |
| `src/mcp_htmleditor/static/editor.html` | edit: add the script tags before `editor.js` |

### Existing patterns

- `src/mcp_htmleditor/static/doc-blocks.js` and `slide-layouts.js` (existing classic scripts: globals, no `import`/`export`).
- `src/mcp_htmleditor/static/editor.html:81-83` (current script tags).
- Playwright suites: `tests/test_undo_redo_e2e.py`, `tests/test_autosave_focus_e2e.py`, `tests/test_website_template_e2e.py`, `tests/test_fullscreen_e2e.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

The success criterion of this story is the non regression command below (`make test`, which runs the 8 Playwright files exercising the editor and `tests/test_http_caching.py`). No new test is added by this story, so RED evidence does not apply. Structural checks of this migration step, all run before the commit:
1. `node --check src/mcp_htmleditor/static/*.js` passes.
2. Function inventory unchanged: `rg -o --no-filename "^(async )?function ([A-Za-z0-9_]+)" src/mcp_htmleditor/static/*.js | sort > /tmp/after.txt` equals the same command run on the baseline `git show HEAD:src/mcp_htmleditor/static/editor.js` (the tree before the story) plus the unchanged other scripts; no name appears twice.
3. Line counts: the new scripts equal the moved ranges (give the numbers in the report) and each is at most 500; `editor.js` shrinks by exactly the moved lines (a leftover blank line pair at most).
4. Each new script evaluates without throwing alone: `node -e "const vm=require('vm'),fs=require('fs');for(const f of process.argv.slice(1)){vm.runInNewContext(fs.readFileSync(f,'utf8'),{document:{addEventListener(){},getElementById(){return null}},window:{}});}" <new scripts>` exits 0 (no top level read of a `let` or `const` of `editor.js`, DR-006).
5. `editor.html` tags: the new `script` tags sit before `editor.js`, in their final relative order (DEC-007), `editor.js` last.

## Constraints

- Files not to touch: existing tests, `slide-layouts.js`, `doc-blocks.js`, `editor.css`, any Python source.
- No ES modules, no renamed global, no new global, no behavior edit while moving.
- Every new script at most 500 lines.
- Dependencies not to add: none (no bundler: the repo has no JavaScript build step).
- Scope boundary: only the ranges listed; the order and serving tests are US-0017.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the existing suite passes unmodified via `make test` (278 tests at the start of this work); tolerated exceptions: none.
- [ ] DEBT: the existing suite passes unmodified, exceptions: none.
- [ ] Docs updated: none in this story (design assigns the documentation to US-0018, US-0019, US-0020).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0015: Extract save and menus scripts`, body `Spec: SPEC-0012` and the requirement ids (DR-006).
