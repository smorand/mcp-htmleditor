# US-0010: Extract images and arch mixins

> Spec: SPEC-0012 (sdlc/specs/SPEC-0012-charter-registry-and-splits/)
> Nature: DEBT
> Priority: P1
> Depends on: US-0009
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Moves architecture diagram rendering into `export/pptx_arch.py` (`ArchMixin`) and annotated image, image and picture primitives into `export/pptx_images.py` (`ImagesMixin`). No behavior change.

This is a DEBT story: observable behavior is unchanged. The existing suite passes unmodified: `make test` (278 tests at the start of this work, `uv run pytest --collect-only -q`), tolerated exceptions: none.

## Requirements covered

- SPEC-0012/DR-004 (partial: modules `pptx_arch.py` and `pptx_images.py`): The exporter SHALL be organised in these modules, `_SlideBuilder` being composed of the mixin classes they define: `src/mcp_htmleditor/export/pptx_chrome.py` (EI, Carbon, medical and generic chrome), `pptx_flow.py` (flow and flex row logic), `pptx_blocks.py` (grid, panel, rule, hbar, table renderers), `pptx_gantt.py`, `pptx_arch.py`, `pptx_images.py` (annotated images, images and picture primitives), `pptx_text.py` (text and paragraph rendering and drawing primitives), and `pptx_model.py` (DR-009); every mixin SHALL inherit a common base class `_BuilderBase` defined in `pptx_model.py`, which declares the instance attributes (`ctx`, `res`, `theme`, `slide`, `article`, `index`, `handled`) as annotations and declares, for each method a mixin calls from another mixin, a stub `def name(self, ...) -> ...: raise NotImplementedError`, so that strict type checking passes without `type: ignore`; `to_pptx.py` keeps `ExportReport`, `to_pptx`, `_build_pptx`, `find_slides` and the composed `_SlideBuilder` with its `__init__`, in at most 600 lines, and every new module has at most 450 lines.
- SPEC-0012/DR-010 (partial: ignores for both modules): `pyproject.toml` SHALL give each of the eight new `export/pptx_*.py` modules the same per file lint ignores as `to_pptx.py` today (`PLR0911`, `PLR0912`, `ARG002`, `PLR2004`), with the explanatory comment kept; `charters.py` needs none.

## Independent Test

`make test ARGS='tests/test_export_golden.py tests/test_export_pptx.py tests/test_http_export.py tests/test_medical_template.py'`, then `make check`.
- Expected: all passed. DT-001 (slide XML hashes of ten decks, US-0006) is the non mock assertion: the real exporter output is byte identical to the hashes recorded before SPEC-0012.
- Moved methods: _render_arch, _render_arch_children, _node_box, _render_arch_node, _render_arch_line, _render_arch_tip, _render_arch_badge, _render_arch_label, _edge_color, _render_annotated_image, _render_annotation, _annotation_colors, _render_image, _image_source, _image_aspect, _add_picture.

## Design excerpt

### Decisions

- DEC-002 (SPEC-0012): mixin classes, not a function library, for the exporter split. Alternatives considered: free functions taking the builder (changes every call site of `self`, 1800 lines of edits); a package with sub builders (state sharing through `_Context` is wide). Rationale: mixins keep `self.` call sites unchanged. Implemented by: DR-004.
- DEC-004 (SPEC-0012): each export story adds, in the same commit, the per file lint ignores of the modules it creates (`PLR0911`, `PLR0912`, `ARG002`, `PLR2004`, comment kept), instead of step 5 doing it at the end. Obliged by: DR-010 and the rule that every step leaves `make check` green: a new `pptx_*.py` without the ignores fails `make lint`. Alternatives: a glob entry `export/pptx_*.py` in the first story (rejected: would also cover the pre existing `pptx_style.py` and `pptx_components.py`, which have narrower ignores). Evidence: `pyproject.toml:104`.
- DEC-005 (SPEC-0012): `pptx_model.py` is created first (types, constants, `_BuilderBase` with stubs) and each mixin story appends the stubs it needs. Obliged by: DR-004, DR-009 (strict mypy without `type: ignore`). Mixins come before `_BuilderBase` in the `_SlideBuilder` bases so real methods win over stubs.

### Data model

none

### Contracts

- Each new module defines one mixin class that inherits `_BuilderBase` (from `pptx_model`); the class names are fixed here: `TextMixin` (`pptx_text`), `ImagesMixin` (`pptx_images`), `ArchMixin` (`pptx_arch`), `GanttMixin` (`pptx_gantt`), `BlocksMixin` (`pptx_blocks`), `FlowMixin` (`pptx_flow`), `ChromeMixin` (`pptx_chrome`).
- `_SlideBuilder` lists the mixins first and `_BuilderBase` last in its bases, so real methods win over stubs (DEC-005). Method names, signatures and bodies are moved unchanged; `self.` call sites are unchanged (DEC-002).
- For each method a moved method calls on another mixin, `_BuilderBase` (in `pptx_model.py`) gets a one line stub `def name(self, ...) -> ...: raise NotImplementedError` with the exact signature; no `type: ignore`.
- No module imports from `to_pptx.py`; no mixin uses a name starting with two underscores; `ExportReport`, `to_pptx`, `_build_pptx`, `find_slides` stay in `to_pptx.py`.

Code to move (line numbers of `src/mcp_htmleditor/export/to_pptx.py` at the start of the spec, 2283 lines; re-read the real method boundaries before cutting, line numbers shift as earlier stories land):

| New module | Class | Moved from `to_pptx.py` |
|---|---|---|
| `pptx_arch.py` | `ArchMixin` | l.1762-1931: `_render_arch` (l.1762), `_render_arch_children` (l.1771), `_node_box` (l.1807), `_render_arch_node` (l.1821), `_render_arch_line` (l.1845), `_render_arch_tip` (l.1863), `_render_arch_badge` (l.1879), `_render_arch_label` (l.1904), `_edge_color` (l.1923). `_arch_block` (l.1124, measurement) stays for `pptx_blocks.py`. |
| `pptx_images.py` | `ImagesMixin` | l.1932-1997: `_render_annotated_image` (l.1932), `_render_annotation` (l.1957), `_annotation_colors` (l.1980), `_render_image` (l.1992); plus the picture primitives l.2193-2282: `_image_source` (l.2193), `_image_aspect` (l.2222), `_add_picture` (l.2236). DR-004 assigns picture primitives to `pptx_images.py`, although the design's section 1 line ranges list them under drawing primitives. |

Stubs for cross-mixin calls (for example `_rect`, `_textbox`, `_write`, `_element_color` now in `TextMixin`, and `_render_image`/`_add_picture` calls from arch or blocks).

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/export/pptx_arch.py` | create |
| `src/mcp_htmleditor/export/pptx_images.py` | create |
| `src/mcp_htmleditor/export/to_pptx.py` | edit: remove the moved methods, add the mixin to the bases of `_SlideBuilder` |
| `src/mcp_htmleditor/export/pptx_model.py` | edit: append the stubs this story needs to `_BuilderBase` (DEC-005) |
| `pyproject.toml` | edit: per file ignores for `pptx_arch.py`, `pptx_images.py` (DEC-004) |

### Existing patterns

- `src/mcp_htmleditor/export/pptx_style.py` and `pptx_components.py` (existing sibling modules: private helpers, `from __future__ import annotations`, module docstring).
- `pyproject.toml:99-107` (per file ignores and the comment to keep).
- `tests/test_export_golden.py` (DT-001, US-0006): the guard that must stay green after each moved mixin.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

The success criterion of this story is the non regression command below (`make test`, which includes the DT-001 slide XML hashes of US-0006). No new test is added by this story, so RED evidence does not apply; the guard is DT-001 recorded by US-0006. Structural checks of this migration step, all run before the commit:
1. `uv run python -c "from mcp_htmleditor.export.to_pptx import _SlideBuilder as B; print(sorted(n for n in dir(B) if not n.startswith('__')))" > /tmp/after.txt`, compared with the same command run on the tree before the story (`/tmp/before.txt`): identical (no method lost, none added).
2. `uv run python -c "import inspect; from mcp_htmleditor.export.to_pptx import _SlideBuilder as B; bad=[n for n in dir(B) if callable(getattr(B,n)) and 'raise NotImplementedError' in inspect.getsource(getattr(B,n)) ]; assert not bad, bad"`: no stub wins over a real method.
3. `wc -l` of every module created by this story at most 450, and of `to_pptx.py` strictly below its value before the story (the final cap, 600, is asserted by US-0020).
4. `rg -n "def (_render_arch|_render_arch_children|_node_box|_render_arch_node|_render_arch_line|_render_arch_tip|_render_arch_badge|_render_arch_label|_edge_color|_render_annotated_image|_render_annotation|_annotation_colors|_render_image|_image_source|_image_aspect|_add_picture)" src/mcp_htmleditor/export/to_pptx.py` finds nothing; `rg -n "from .to_pptx|export.to_pptx" src/mcp_htmleditor/export/pptx_*.py` finds nothing.
5. `pyproject.toml` has one ignore line per created module with `PLR0911`, `PLR0912`, `ARG002`, `PLR2004` (DEC-004) and `make check` is green (strict mypy without `type: ignore`).

## Constraints

- Files not to touch: existing tests, `pptx_style.py`, `pptx_components.py`; no behavior change: methods move unchanged, byte for byte, comments included.
- No `type: ignore`; stubs are one line `raise NotImplementedError` with the exact signature; no name starting with two underscores; no import from `to_pptx.py` in any `pptx_*.py`.
- Every new module at most 450 lines; DT-001 and `make test` run after each moved class and stay green.
- Dependencies not to add: none.
- Scope boundary: only the modules listed in Paths; the size cap tests are US-0020.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the existing suite passes unmodified via `make test` (278 tests at the start of this work); tolerated exceptions: none.
- [ ] DEBT: the existing suite passes unmodified, exceptions: none.
- [ ] Docs updated: none in this story (design assigns the documentation to US-0018, US-0019, US-0020).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0010: Extract images and arch mixins`, body `Spec: SPEC-0012` and the requirement ids (DR-004, DR-010).
