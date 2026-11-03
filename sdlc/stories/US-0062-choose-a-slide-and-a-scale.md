# US-0062: Choose a slide and a scale

> Spec: SPEC-0008 (sdlc/specs/SPEC-0008-visual-render/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0061
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Add `--slide <id>` and `--scale <number>`: the slide and scale of the picture, the scale validation, the size rounding, and the unknown slide error, in the spec check order.

## Requirements covered

- SPEC-0008/FR-NEW-002: WHEN a user passes `--slide <id>` or `--scale <number>` THE Editor SHALL render that slide at that scale.
- SPEC-0008/FR-NEW-001 (partial: the order of the checks scale, file, presentation, browser, unknown slide id; the size rounded half up): WHEN a user runs `mcp-htmleditor render <file>` THE Editor SHALL write a PNG picture of one slide of the presentation and print one line giving its slide, path and size.

## Independent Test

`make test ARGS='-k render_options'`: `render DECK-EI --slide slide-3 --scale 1` ends with `(960x540)`, `--scale 0.1` with `(96x54)`, `--scale 1.5` prints `error: Scale must be between 0.1 and 1` with status 1 and writes nothing, `--slide slide-9` lists the eight valid ids.

## Design excerpt

### Decisions

- DEC-005 (SPEC-0008): "`render_deck` performs the checks in the spec order, which launches the browser before validating `--slide`."
- DEC-009 (SPEC-0008): "The expected size is computed with `Decimal` and `ROUND_HALF_UP` from the text of the scale, and the PNG header read after capture must equal it, otherwise `Rendering failed: picture is <w>x<h>, expected <w>x<h>`."
- DEC-017 (SPEC-0008): "The option conflict is detected in `check_options`, raised as `RenderUsageError`, and printed by the command as `Error: <message>` with exit status 2 by hand. `--scale` is a text option."

### Data model

No new data. `RenderResult.width` and `height` now come from `output_size`; the PNG header check compares with it.

### Contracts

```python
# render/options.py
def parse_scale(raw: str | float | None) -> Decimal      # None -> Decimal("0.5"); RenderError("Scale must be between 0.1 and 1")
def output_size(scale: Decimal) -> tuple[int, int]       # ROUND_HALF_UP of CANVAS_WIDTH*scale and CANVAS_HEIGHT*scale
# render/service.py
def render_deck(file: str, *, slide: str | None = None, scale: str | float | None = None) -> RenderResult
```
`parse_scale`: strip, `Decimal(text)` (a float input uses `Decimal(repr(value))`), reject `InvalidOperation`, non finite (`nan`, `inf`, `-inf`) and values outside [0.1, 1] (compared as `Decimal`), all with `Scale must be between 0.1 and 1`. Accepted forms include `.5`, `1e-1`, ` 0.5 `. `device_scale_factor = float(scale)`.
Command: `--slide` is `str` (default `None`), `--scale` is a `str` option (default `None` = not given, effective 0.5) so `abc` reaches the scale message with status 1 (a float option would exit 2).
Check order after this story: scale, file not found, not a presentation, browser missing, unknown slide id. The browser is launched before the id is validated. Unknown slide: `Unknown slide id "slide-9". Valid ids: slide-0, slide-1, ...` (all ids, in order). Default slide: the first.
Spec text for this story (verbatim):

#### FR-NEW-002 [EARS-E]: Slide and scale
> WHEN a user passes `--slide <id>` or `--scale <number>` THE Editor SHALL render that slide at that scale.

- **Business rules:** the scale is a finite decimal number from 0.1 to 1 inclusive; 0.1 gives 96 x 54; anything else (including `nan`, `inf`) is refused with the message below.
- **User visible text:** `error: Unknown slide id "slide-9". Valid ids: slide-0, slide-1, ...` (all ids, in order, exit status 1); `error: Scale must be between 0.1 and 1` (exit status 1; also for a value that is not a number).
- **Scenario:** SC-001
- **Priority:** Must

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/render/options.py` | create |
| `src/mcp_htmleditor/render/service.py` | modify: scale, slide choice, check order |
| `src/mcp_htmleditor/cli.py` | modify: options `--slide`, `--scale` |
| `tests/test_render_options.py` | create |
| `.agent_docs/render.md` | create: picture rules, output directory and cleanup, scale and size rounding, check order, fixtures and install |

### Existing patterns

- `src/mcp_htmleditor/render/service.py` and `files.py` (US-0061).
- `src/mcp_htmleditor/cli.py` option declarations (`:126-134`), `deck_command` (US-0035).
- `.agent_docs/*.md` structure (one topic per file, timestamped entries, under 200 lines).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures of the spec (verbatim):

DECK-EI: an Euro-Information presentation of 8 slides `slide-0` to `slide-7` with no layout problem. DECK-MED: a
medical presentation of 6 slides whose `slide-2` has class `slide dark`. DOC-PERSO: a document. The machine running the tests has Segoe UI or Calibri installed, so DECK-EI and DECK-MED report no font problem. Where a test needs a defect, it states the defect.

Fixtures are generated by `tests/render_support.py` (US-0060) from the SPEC-0007 helpers in `tests/deck_support.py` (`build_deck`, `deck_med`, `doc_perso`, `run_cli`, `call_tool`), never committed and never read from `~/.config`. DECK-EI is `build_deck("ei", EI_TITLES)` with 8 titles and no big image. DECK-MED is `deck_med()` with the article of `slide-2` given `class="slide dark"`. DOC-PERSO is `doc_perso()`. The output directory is redirected with `monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))`. Browser tests carry `@needs_chromium`. On a machine without Segoe UI and Calibri the EI font stack still ends with Arial (`templates/bootstrap/slides-ei-empty.html:31`), which keeps DECK-EI free of a `font` problem.

### SPEC-0008/E2E-002: Slide and scale

- Level E2E; Driver CLI; Location `tests/test_render_options.py`
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --slide slide-3 --scale 1`, checks the picture, then runs it with `--scale 0.1`
- **Then** the outputs end with `(960x540)` and `(96x54)` and the pictures, checked after each run, have those sizes; the path ends with `DECK-EI-slide-3.png`
- **Priority:** High

### SPEC-0008/E2E-008: Unknown slide

- Level E2E; Driver CLI; Location `tests/test_render_options.py`
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --slide slide-9`
- **Then** the error output is `error: Unknown slide id "slide-9". Valid ids: slide-0, slide-1, slide-2, slide-3, slide-4, slide-5, slide-6, slide-7`, exit status 1
- **Priority:** High

### SPEC-0008/E2E-009: Scale out of range

- Level E2E; Driver CLI; Location `tests/test_render_options.py`
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --scale 1.5`, `--scale 0`, `--scale abc`
- **Then** each prints `error: Scale must be between 0.1 and 1` and exits with status 1, and no picture is written
- **Priority:** High

### SPEC-0008/E2E-020: Dark surface

- Level E2E; Driver CLI + pixel read; Location `tests/test_render_options.py`
- **Given** DECK-MED
- **When** the user runs `render DECK-MED --slide slide-2 --scale 1`
- **Then** the pixel at x 2, y 300 of the picture is the colour `#0B0E11`
- **Priority:** Medium

### SPEC-0008/E2E-021: Only the last render stays

- Level E2E; Driver CLI; Location `tests/test_render_options.py`
- **Given** DECK-EI
- **When** the user renders `slide-1`, then `slide-2`
- **Then** the directory `htmleditor-render` holds `DECK-EI-slide-2.png` and no `DECK-EI-slide-1.png`
- **And** a picture of another file in that directory is untouched
- **Priority:** Medium

### Additional integration and unit tests (`tests/test_render_options.py`)

- `parse_scale` table: accepted `0.1`, `1`, `.5`, `1e-1`, ` 0.5 `, `0.50`; refused with `Scale must be between 0.1 and 1`: `0.09`, `1.01`, `0`, `-1`, ``, `abc`, `nan`, `inf`, `-inf`, `1,5`.
- `output_size` table: 0.1 gives (96, 54); 0.5 gives (480, 270); 1 gives (960, 540); 0.125 gives (120, 68) (67.5 rounds up); 0.123 gives (118, 66); 0.995 gives (955, 537).
- Check order: `--scale abc` on a missing file reports the scale message; a missing file with a document name reports `File not found`; a document with `--slide slide-9` reports `render needs a presentation`; with `PLAYWRIGHT_BROWSERS_PATH` pointing at an empty directory and `--slide slide-9` on DECK-EI the browser message comes first.
- A slide with neither `data-id` nor `id` is rendered with `--slide slide-1` when it is the second slide (`slide-<index>` fallback), and the unknown slide message lists the fallback ids.
- `--scale 0.5` gives the same size as no option; the two pictures are the same path.

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/export/*`, `src/mcp_htmleditor/mcp_server.py`.
- Dependencies not to add: none.
- Patterns to avoid: a Click `float` option for `--scale`; `round()` on floats for the size (use `Decimal` and `ROUND_HALF_UP`); `print`; `type: ignore`.
- Scope boundary: no report, no JSON, no tool.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the command and output of the failing run).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: existing tests pass unmodified (`tests/test_skill_content.py`, `tests/test_templates.py`, the three existing browser E2E files); the existing commands and tools behave as before.
- [ ] Docs updated: `.agent_docs/render.md` created (topic file) in this story.
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0062: Choose a slide and a scale` with body `Spec: SPEC-0008` and requirement ids FR-NEW-002, FR-NEW-001.
