# US-0018: Fix skill documents naming moved methods

> Spec: SPEC-0012 (sdlc/specs/SPEC-0012-charter-registry-and-splits/)
> Nature: DEBT
> Priority: P2
> Depends on: US-0012
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Updates the skill documents that name exporter methods by their old location in `to_pptx.py`, so they point to the modules created by US-0009 to US-0012.

This is a DEBT story: observable behavior is unchanged. The existing suite passes unmodified: `make test` (278 tests at the start of this work, `uv run pytest --collect-only -q`), tolerated exceptions: none.

## Requirements covered

- SPEC-0012/DR-004 (partial: documentation of the new locations): The exporter SHALL be organised in these modules, `_SlideBuilder` being composed of the mixin classes they define: `src/mcp_htmleditor/export/pptx_chrome.py` (EI, Carbon, medical and generic chrome), `pptx_flow.py` (flow and flex row logic), `pptx_blocks.py` (grid, panel, rule, hbar, table renderers), `pptx_gantt.py`, `pptx_arch.py`, `pptx_images.py` (annotated images, images and picture primitives), `pptx_text.py` (text and paragraph rendering and drawing primitives), and `pptx_model.py` (DR-009); every mixin SHALL inherit a common base class `_BuilderBase` defined in `pptx_model.py`, which declares the instance attributes (`ctx`, `res`, `theme`, `slide`, `article`, `index`, `handled`) as annotations and declares, for each method a mixin calls from another mixin, a stub `def name(self, ...) -> ...: raise NotImplementedError`, so that strict type checking passes without `type: ignore`; `to_pptx.py` keeps `ExportReport`, `to_pptx`, `_build_pptx`, `find_slides` and the composed `_SlideBuilder` with its `__init__`, in at most 600 lines, and every new module has at most 450 lines.

## Independent Test

`make test ARGS='tests/test_skill_content.py tests/test_arch_checks.py'` then `make check`.
- Expected: green. Non mock assertions: `rg -n "to_pptx\.py::|dans \`to_pptx.py\`" skill` finds nothing; for every `pptx_<x>.py::<method>` named in the edited lines, `rg -n "def <method>" src/mcp_htmleditor/export/pptx_<x>.py` finds exactly one definition (the documents must name real locations).

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
| `skill/types/arch-diagram.md` | l.73 `export/to_pptx.py::_render_arch` becomes `export/pptx_arch.py::_render_arch`; l.123 `export/to_pptx.py` (branch for the badge) becomes `export/pptx_arch.py` |
| `skill/types/gantt.md` | l.204 `_is_inline_gantt`/`_is_inline_gantt_row` dans `to_pptx.py` becomes `pptx_gantt.py` |
| `skill/types/medical.md` | l.511 `_chrome_medical()` (`export/to_pptx.py`) becomes `export/pptx_chrome.py` |
| `skill/checks/arch-diagram-checklist.md` | l.175 `to_pptx.py::_render_arch_children` becomes `pptx_arch.py::_render_arch_children`; l.178 `to_pptx.py::_render_arch_badge` becomes `pptx_arch.py::_render_arch_badge` |

### Paths

| Path | Action |
|---|---|
| `skill/types/arch-diagram.md` | edit |
| `skill/types/gantt.md` | edit |
| `skill/types/medical.md` | edit |
| `skill/checks/arch-diagram-checklist.md` | edit |

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
- [ ] Docs updated: `skill/types/arch-diagram.md`; `skill/types/gantt.md`; `skill/types/medical.md`; `skill/checks/arch-diagram-checklist.md`.
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0018: Fix skill documents naming moved methods`, body `Spec: SPEC-0012` and the requirement ids (DR-004).
