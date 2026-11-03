# US-0019: Update README, AGENTS and agent docs

> Spec: SPEC-0012 (sdlc/specs/SPEC-0012-charter-registry-and-splits/)
> Nature: DEBT
> Priority: P2
> Depends on: US-0017, US-0018
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Updates the project documentation to the new module and script layout, and documents the charter registry.

This is a DEBT story: observable behavior is unchanged. The existing suite passes unmodified: `make test` (278 tests at the start of this work, `uv run pytest --collect-only -q`), tolerated exceptions: none.

## Requirements covered

- SPEC-0012/DR-004 (partial: documentation of the exporter modules): The exporter SHALL be organised in these modules, `_SlideBuilder` being composed of the mixin classes they define: `src/mcp_htmleditor/export/pptx_chrome.py` (EI, Carbon, medical and generic chrome), `pptx_flow.py` (flow and flex row logic), `pptx_blocks.py` (grid, panel, rule, hbar, table renderers), `pptx_gantt.py`, `pptx_arch.py`, `pptx_images.py` (annotated images, images and picture primitives), `pptx_text.py` (text and paragraph rendering and drawing primitives), and `pptx_model.py` (DR-009); every mixin SHALL inherit a common base class `_BuilderBase` defined in `pptx_model.py`, which declares the instance attributes (`ctx`, `res`, `theme`, `slide`, `article`, `index`, `handled`) as annotations and declares, for each method a mixin calls from another mixin, a stub `def name(self, ...) -> ...: raise NotImplementedError`, so that strict type checking passes without `type: ignore`; `to_pptx.py` keeps `ExportReport`, `to_pptx`, `_build_pptx`, `find_slides` and the composed `_SlideBuilder` with its `__init__`, in at most 600 lines, and every new module has at most 450 lines.
- SPEC-0012/DR-006 (partial: documentation of the nine editor scripts): The editor page SHALL load, in this order, the classic scripts `slide-layouts.js`, `doc-blocks.js`, `editor-undo.js`, `editor-edit.js`, `editor-format.js`, `editor-menus.js`, `editor-save.js`, `editor-slides.js`, `editor-blocks.js`, `editor-drag.js`, `editor.js`; each has at most 500 lines; `editor.js` holds the state declarations (l.15-68), the start up block (l.69-184) and the polling and is loaded last; no global function or variable changes name. The top level `let` and `const` declarations of `editor.js` SHALL NOT be read or written at script evaluation time by any other script, only inside functions; the start up block and the `setInterval` of the polling SHALL stay in `editor.js`; each script SHALL evaluate without throwing when loaded alone after `slide-layouts.js` and `doc-blocks.js`.

## Independent Test

`make check`, then the structural greps below.
- Expected: green. Non mock assertions: every path named in the edited docs exists (`for p in $(rg -o "(export|static)/[a-z_-]+\.(py|js)" README.md AGENTS.md .agent_docs | cut -d: -f3 | sort -u); do test -e src/mcp_htmleditor/$p || echo MISSING $p; done` prints nothing); `rg -n "editor\.js" README.md .agent_docs` shows no line that attributes moved functions to `editor.js`.

## Design excerpt

### Decisions

- none governs this story; it applies the file structure impact table of the design additions (documentation rows).

### Data model

none

### Contracts

- No code contract changes. Documentation only; the paths named in the documents must exist and the method names must be real.

Edits:

| File | Edit |
|---|---|
| `README.md` | l.363 `to_pptx.py` line plus new lines for `charters.py`, `pptx_model.py`, `pptx_text.py`, `pptx_images.py`, `pptx_arch.py`, `pptx_gantt.py`, `pptx_blocks.py`, `pptx_flow.py`, `pptx_chrome.py`; l.372 `editor.js` line plus the eight `editor-*.js` scripts in load order |
| `AGENTS.md` | l.83 keep `node --check src/mcp_htmleditor/static/*.js` (the glob already covers the new files) and add one line: the editor is eleven classic scripts loaded in the order of `editor.html`; the exporter is composed of mixins; point to `.agent_docs/architecture.md` |
| `.agent_docs/architecture.md` | l.49 `export/to_pptx.py` row split into one row per module and a `export/charters.py` row (registry: `REGISTRY`, `CharterSpec`, consumers `templates.py`, `detect_theme`, `charter_for`; the JavaScript detector stays, parity tested by DT-002); l.62 `static/editor.js` row split into the nine scripts; l.131 `to_pptx.py` mention kept valid; a dated entry (2026-11-03) on the mixin composition and the classic script order (DEC-001, DEC-002) |
| `.agent_docs/html-conventions.md` | l.39 `to_pptx.py` (row splitting) to `pptx_flow.py`; l.130 `export/to_pptx.py::_render_arch` to `export/pptx_arch.py::_render_arch`; l.145 and l.201 `editor.js` to `editor-drag.js` (`makeArchNodeDraggable`) and `editor-undo.js`; l.160 `export/to_pptx.py` to `export/pptx_arch.py`; l.26 `renumberSlides()` in `editor.js` to `editor-slides.js`; l.196 `saveContent` in `editor.js` to `editor-save.js` |
| `.agent_docs/observability.md` | l.35 span `export.pptx` still names `export/to_pptx.to_pptx`: verify and leave unchanged (the function stays defined in `to_pptx.py`) |

### Paths

| Path | Action |
|---|---|
| `README.md` | edit |
| `AGENTS.md` | edit |
| `.agent_docs/architecture.md` | edit |
| `.agent_docs/html-conventions.md` | edit |
| `.agent_docs/observability.md` | edit |

### Existing patterns

- `.agent_docs/architecture.md` and `README.md` style: tables, short dated entries, no dashes.
- `tests/test_skill_content.py` (skill document assembly).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

The success criterion of this story is the non regression command below (`make check`, which includes `make test`). Structural checks of this documentation step: see the Independent Test above; every edited line is re-read in the file and the greps are run before the commit.

## Constraints

- Files not to touch: source code and tests.
- No dash characters of the em or en kind in the edited documents; edit only the lines listed, keep the surrounding text.
- Scope boundary: other documents are not edited.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the existing suite passes unmodified via `make test` (278 tests at the start of this work); tolerated exceptions: none.
- [ ] DEBT: the existing suite passes unmodified, exceptions: none.
- [ ] Docs updated: `README.md`; `AGENTS.md`; `.agent_docs/architecture.md`; `.agent_docs/html-conventions.md`; `.agent_docs/observability.md`.
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0019: Update README, AGENTS and agent docs`, body `Spec: SPEC-0012` and the requirement ids (DR-004, DR-006).
