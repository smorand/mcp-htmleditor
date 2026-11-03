# US-0008: pptx_model.py with types, constants, base class

> Spec: SPEC-0012 (sdlc/specs/SPEC-0012-charter-registry-and-splits/)
> Nature: DEBT
> Priority: P1
> Depends on: US-0007
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Creates `export/pptx_model.py` holding the shared types, all module constants of `to_pptx.py` and the `_BuilderBase` class, and makes `to_pptx.py` import and re-export them. Names stay importable from `to_pptx`, `to_pptx` stays defined in `to_pptx.py`. No behavior change.

This is a DEBT story: observable behavior is unchanged. The existing suite passes unmodified: `make test` (278 tests at the start of this work, `uv run pytest --collect-only -q`), tolerated exceptions: none.

## Requirements covered

- SPEC-0012/DR-009: A module `src/mcp_htmleditor/export/pptx_model.py` SHALL hold `_Context`, `_Block`, `_Column`, `_Region`, `_Para`, `_ColumnBasis`, `_column_basis`, `_column_widths` and all module constants of `to_pptx.py` (l.87-185: `SKIP_TAGS`, `SHELL_CLASSES`, `BLOCK_TAGS`, `GRID_CLASSES`, `TILE_CLASSES`, `FILL_KEYS`, `BAR_KEYS`, `_ALIGN`, `_SHAPES`, `_NOTIF_VARIANTS`, `_ANNOT_CLASS_COLORS`); no `pptx_*.py` module SHALL import from `to_pptx.py`; no mixin SHALL use a name starting with two underscores.
- SPEC-0012/DR-005: `mcp_htmleditor.export.to_pptx` SHALL still export `to_pptx`, `find_slides`, `ExportReport`, `_column_widths`, `SLIDE_W_IN` and `SLIDE_H_IN`.
- SPEC-0012/DR-010 (partial: `pptx_model.py` ignores, the other modules are US-0009 to US-0012): `pyproject.toml` SHALL give each of the eight new `export/pptx_*.py` modules the same per file lint ignores as `to_pptx.py` today (`PLR0911`, `PLR0912`, `ARG002`, `PLR2004`), with the explanatory comment kept; `charters.py` needs none.

## Independent Test

`make test ARGS='tests/test_pptx_names.py tests/test_export_pptx.py tests/test_http_export.py tests/test_medical_template.py tests/test_export_golden.py'`
- Expected: all passed; DT-001 hashes unchanged.
- Non mock assertions: `to_pptx.__module__ == "mcp_htmleditor.export.to_pptx"` (so `tests/test_http_export.py:38-39` patching still works) and `_column_widths.__module__ == "mcp_htmleditor.export.pptx_model"`.
- Structural: `wc -l src/mcp_htmleditor/export/pptx_model.py` at most 450; `rg -n "to_pptx" src/mcp_htmleditor/export/pptx_*.py` finds no `import` from `to_pptx`; `rg -n "def __[a-z]" ` and `rg -n "self\.__" src/mcp_htmleditor/export/pptx_model.py` find nothing (no double underscore name); `make check` green (strict mypy and ruff accept the new file).
- RED evidence: the added assertion on `_column_widths.__module__` fails before the move.

## Design excerpt

### Decisions

- DEC-002 (SPEC-0012): mixin classes, not a function library, for the exporter split. Alternatives considered: free functions taking the builder (changes every call site of `self`, 1800 lines of edits); a package with sub builders (state sharing through `_Context` is wide). Rationale: mixins keep `self.` call sites unchanged. Implemented by: DR-004.
- DEC-004 (SPEC-0012): each export story adds, in the same commit, the per file lint ignores of the modules it creates (`PLR0911`, `PLR0912`, `ARG002`, `PLR2004`, comment kept), instead of step 5 doing it at the end. Obliged by: DR-010 and the rule that every step leaves `make check` green: a new `pptx_*.py` without the ignores fails `make lint`. Alternatives: a glob entry `export/pptx_*.py` in the first story (rejected: would also cover the pre existing `pptx_style.py` and `pptx_components.py`, which have narrower ignores). Evidence: `pyproject.toml:104`.
- DEC-005 (SPEC-0012): `pptx_model.py` is created first (types, constants, `_BuilderBase` with stubs) and each mixin story appends the stubs it needs. Obliged by: DR-004, DR-009 (strict mypy without `type: ignore`). Mixins come before `_BuilderBase` in the `_SlideBuilder` bases so real methods win over stubs.

### Data model

Moved verbatim from `to_pptx.py` (as it is at the start of the story; re-read the boundaries before cutting):
- constants l.87-185: `SKIP_TAGS`, `SHELL_CLASSES`, `BLOCK_TAGS`, `GRID_CLASSES`, `TILE_CLASSES`, `INLINE_BLOCK_CLASSES`, `INLINE_BLOCK_TAGS`, `FILL_KEYS`, `BAR_KEYS`, `_PX_FLEX_BASIS_RE`, `_FLEX_SHORTHAND_RE`, `_ALIGN`, `_SHAPES`, `_NOTIF_VARIANTS`, `_ANNOT_CLASS_COLORS` (DR-009 says "all module constants"; its explicit list omits the four names `INLINE_BLOCK_CLASSES`, `INLINE_BLOCK_TAGS`, `_PX_FLEX_BASIS_RE`, `_FLEX_SHORTHAND_RE`, which are included here).
- types and helpers l.302-435: `_Context` (l.302), `_Block` (l.312), `_Column` (l.326), `_Region` (l.340), `_Para` (l.349), `_ColumnBasis` (l.358), `_column_basis` (l.376), `_column_widths` (l.406).
- New `class _BuilderBase`: declares as annotations `ctx: _Context`, `res: StyleResolver`, `theme: Theme`, `slide: Any`, `article: Tag`, `index: int`, `handled: set[int]` (read the real types from `_SlideBuilder.__init__`, l.444-454, and use exactly those); no stubs yet (each mixin story appends the stubs it needs, DEC-005). `_SlideBuilder` now inherits `_BuilderBase`.
Stays in `to_pptx.py`: `ExportReport`, `to_pptx`, `_build_pptx`, `find_slides`, `_has_slide_ancestor`, `logger`, `_SlideBuilder`.

### Contracts

- `from mcp_htmleditor.export.to_pptx import to_pptx, find_slides, ExportReport, _column_widths, SLIDE_W_IN, SLIDE_H_IN` keeps working (the last three re-exported by import; `SLIDE_W_IN`, `SLIDE_H_IN` are already imported from `pptx_style`).
- `to_pptx` is DEFINED in `to_pptx.py` (patched by dotted path `mcp_htmleditor.export.to_pptx.to_pptx` in `tests/test_http_export.py:38-39`); span name `export.pptx` kept.
- New module `mcp_htmleditor.export.pptx_model` exports the names above plus `_BuilderBase`; it imports nothing from `to_pptx.py`.
- `to_pptx.py` re-exports the moved names it still uses by importing them from `pptx_model`; `__all__` stays `["ExportReport", "find_slides", "to_pptx"]` (l.2283) unless ruff requires adding re-exported private names with `# noqa: F401`.

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/export/pptx_model.py` | create |
| `src/mcp_htmleditor/export/to_pptx.py` | edit: remove l.87-185 and l.296-435, import from `pptx_model`, `_SlideBuilder(_BuilderBase)` |
| `pyproject.toml` | edit: add `pptx_model.py` to the per file ignores (DEC-004), keep the comment (l.99-103) |
| `tests/test_pptx_names.py` | create (DT-003) |

### Existing patterns

- `pyproject.toml:99-107` (per file ignores and the explanatory comment to keep).
- `tests/test_http_export.py:38-39` (dotted path patch of `to_pptx`).
- `tests/test_export_pptx.py:32-38` (names imported from `to_pptx`).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0012/DT-003: Names re-exported

- Level: unit; Driver: pytest import; Location: `tests/test_pptx_names.py`
- **Validates:** SPEC-0012/DR-005
- **Then** the six names import from `mcp_htmleditor.export.to_pptx`

The six names are `to_pptx`, `find_slides`, `ExportReport`, `_column_widths`, `SLIDE_W_IN`, `SLIDE_H_IN`. Additional assertions of this story (they are what is RED before the move): `to_pptx.__module__ == 'mcp_htmleditor.export.to_pptx'`; `_column_widths.__module__ == 'mcp_htmleditor.export.pptx_model'`; `SLIDE_W_IN == 13.333...` equals `pptx_style.SLIDE_W_IN`; `pptx_model` source contains no line starting `from .to_pptx` or `from mcp_htmleditor.export.to_pptx`.

## Constraints

- Files not to touch: existing tests, `pptx_style.py`, `pptx_components.py`.
- No `type: ignore`; no name starting with two underscores in `pptx_model.py` (name mangling would break mixins).
- `pptx_model.py` at most 450 lines; if constants, types and the base class exceed it, STOP and report BLOCKED (later stubs also land here).
- `pyproject.toml` ignores for `pptx_model.py`: `PLR0911`, `PLR0912`, `ARG002`, `PLR2004` (DR-010, DEC-004).
- Scope boundary: no `_SlideBuilder` method moves in this story.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the existing suite passes unmodified via `make test` (278 tests at the start of this work); tolerated exceptions: none.
- [ ] DEBT: the existing suite passes unmodified, exceptions: none.
- [ ] Docs updated: none in this story.
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0008: pptx_model.py with types, constants, base class`, body `Spec: SPEC-0012` and the requirement ids (DR-009, DR-005, DR-010).
