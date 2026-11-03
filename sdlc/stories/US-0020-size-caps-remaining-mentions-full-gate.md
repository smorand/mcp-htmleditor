# US-0020: Size caps, remaining mentions, full gate

> Spec: SPEC-0012 (sdlc/specs/SPEC-0012-charter-registry-and-splits/)
> Nature: DEBT
> Priority: P1
> Depends on: US-0019
> min_tier: 2
> Files touched: 4
> Closes spec: yes

## Objective

Closes SPEC-0012: adds the size cap test, fixes the last mentions of `editor.js` in skill documents and tools, and runs the full gate. After it every requirement and every acceptance test of the spec is green.

This is a DEBT story: observable behavior is unchanged. The existing suite passes unmodified: `make test` (278 tests at the start of this work, `uv run pytest --collect-only -q`), tolerated exceptions: none.

## Requirements covered

- SPEC-0012/DR-004 (partial: size caps of `to_pptx.py` and the eight new modules): The exporter SHALL be organised in these modules, `_SlideBuilder` being composed of the mixin classes they define: `src/mcp_htmleditor/export/pptx_chrome.py` (EI, Carbon, medical and generic chrome), `pptx_flow.py` (flow and flex row logic), `pptx_blocks.py` (grid, panel, rule, hbar, table renderers), `pptx_gantt.py`, `pptx_arch.py`, `pptx_images.py` (annotated images, images and picture primitives), `pptx_text.py` (text and paragraph rendering and drawing primitives), and `pptx_model.py` (DR-009); every mixin SHALL inherit a common base class `_BuilderBase` defined in `pptx_model.py`, which declares the instance attributes (`ctx`, `res`, `theme`, `slide`, `article`, `index`, `handled`) as annotations and declares, for each method a mixin calls from another mixin, a stub `def name(self, ...) -> ...: raise NotImplementedError`, so that strict type checking passes without `type: ignore`; `to_pptx.py` keeps `ExportReport`, `to_pptx`, `_build_pptx`, `find_slides` and the composed `_SlideBuilder` with its `__init__`, in at most 600 lines, and every new module has at most 450 lines.
- SPEC-0012/DR-006 (partial: size caps of the editor scripts): The editor page SHALL load, in this order, the classic scripts `slide-layouts.js`, `doc-blocks.js`, `editor-undo.js`, `editor-edit.js`, `editor-format.js`, `editor-menus.js`, `editor-save.js`, `editor-slides.js`, `editor-blocks.js`, `editor-drag.js`, `editor.js`; each has at most 500 lines; `editor.js` holds the state declarations (l.15-68), the start up block (l.69-184) and the polling and is loaded last; no global function or variable changes name. The top level `let` and `const` declarations of `editor.js` SHALL NOT be read or written at script evaluation time by any other script, only inside functions; the start up block and the `setInterval` of the polling SHALL stay in `editor.js`; each script SHALL evaluate without throwing when loaded alone after `slide-layouts.js` and `doc-blocks.js`.
- SPEC-0012/DR-007 (partial: closing: slide XML hashes (DT-001), unmodified suite): The Editor SHALL produce, for every input covered by the existing test suite, byte identical observable output before and after this change, and the XML of every exported slide of the ten templates and reference decks (DT-001) SHALL be byte identical.
- SPEC-0012/DR-008 (partial: closing: `/static` scripts served with `no-store` (DT-004)): `GET /static/editor.js` SHALL keep answering with `Cache-Control: no-store`, and the new scripts SHALL be served the same way under `/static/`.

## Independent Test

`make check` (DT-013), which runs `tests/test_size_caps.py` (DT-011) with the whole suite.
- Expected: lint, format, types, security scan green; tests pass with at least 80 percent coverage; 278 original tests unmodified plus the tests added by US-0006 to US-0017 and this story.
- Non mock assertions: `wc -l` of the real files; `git diff --stat <commit before US-0006>..HEAD -- tests` shows only added files (no existing test edited).
- RED evidence: run `tests/test_size_caps.py` from a `git worktree` of the commit that closed US-0005, where `to_pptx.py` has 2283 lines and `editor.js` 1998; it fails there.

## Design excerpt

### Decisions

- DEC-006 (SPEC-0012): size cap test DT-011 and the final doc fixes live in the closing story, because the caps (`to_pptx.py` at most 600 lines, `editor.js` at most 500) only hold once every split story has landed. Obliged by: DR-004, DR-006 and "main green after each step".

### Data model

none

### Contracts

- No code contract changes. `tests/test_size_caps.py` reads line counts of real files under `src/mcp_htmleditor/export/` and `src/mcp_htmleditor/static/` (paths from `Path(__file__).resolve().parents[1]`).

### Paths

| Path | Action |
|---|---|
| `tests/test_size_caps.py` | create (DT-011) |
| `skill/types/website.md` | edit: l.42 `editor.js` (`isWebsite`) names the script that defines it after the split (read the real location with `rg -n isWebsite src/mcp_htmleditor/static`) |
| `skill/types/mail.md` | edit: l.173 `code cote editor.js` names the real script (`rg -n "docx" src/mcp_htmleditor/static`) |
| `tools/gen_ei_bootstrap.py` | edit: comment l.12 naming `static/editor.js` names the script that holds `resolveTemplateAssets` (`editor-slides.js`) |

### Existing patterns

- `tests/test_medical_template.py:15-24` (REPO_ROOT based path constants).
- `Makefile` target `check` (lint, format-check, typecheck, security, test-cov).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0012/DT-011: Size caps

- Level: unit; Driver: pytest line count; Location: `tests/test_size_caps.py`
- **Asserts:** `to_pptx.py` has at most 600 lines, each `export/pptx_*.py` at most 450, each `static/editor*.js` at most 500
- **Method:** line count assertion

Scope of the Python assertion: `to_pptx.py` (at most 600) and the eight new modules `pptx_model.py`, `pptx_text.py`, `pptx_images.py`, `pptx_arch.py`, `pptx_gantt.py`, `pptx_blocks.py`, `pptx_flow.py`, `pptx_chrome.py` (at most 450 each). The pre existing `pptx_style.py` (719 lines) and `pptx_components.py` (348) are NOT covered although the design text says `each export/pptx_*.py`; DR-004 limits the cap to new modules. Scope of the JavaScript assertion: `editor.js` and the eight new `editor-*.js` (at most 500 each); `slide-layouts.js` (884) and `doc-blocks.js` are not covered.

### SPEC-0012/DT-013: Quality gate

- Level: gate; Driver: `make check`; Location: `n/a`
- **Asserts:** `make check` passes (lint, format, types, security scan, tests with 80 percent coverage)

Run `make check` as the last act of the story and attach its output; it is not a pytest file. The `Location` is the Makefile target.

## Constraints

- Files not to touch: source code under `src/`, existing tests.
- Edit only the three lines named in Paths for the remaining mentions; no dash characters of the em or en kind.
- Dependencies not to add: none.
- Scope boundary: if `make check` fails on code outside SPEC-0012, report it (do not fix it) and finish as DONE_WITH_CONCERNS or BLOCKED.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the existing suite passes unmodified via `make test` (278 tests at the start of this work); tolerated exceptions: none.
- [ ] DEBT: the existing suite passes unmodified, exceptions: none.
- [ ] Docs updated: `skill/types/website.md`, `skill/types/mail.md`, `tools/gen_ei_bootstrap.py` (remaining `editor.js` mentions).
- [ ] Self review: full at tier 2.
- [ ] Closing story: the spec's full acceptance set green (DT-001, DT-002, DT-003, DT-004, DT-010, DT-011, DT-012, DT-013), the non regression command green (`make test`, 278 original tests unmodified), every DR requirement (DR-001 to DR-010) cited by at least one story (US-0006 to US-0020).
- [ ] One commit `US-0020: Size caps, remaining mentions, full gate`, body `Spec: SPEC-0012` and the requirement ids (DR-004, DR-006, DR-007, DR-008).
