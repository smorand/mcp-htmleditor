# US-0064: Report only across the deck

> Spec: SPEC-0008 (sdlc/specs/SPEC-0008-visual-render/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0063
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Add `--report-only`: analyse every slide, write no picture, print the problem lines and the final line, exit 1 on a problem, and refuse its combination with `--slide`, `--scale` or `--report` as a usage error with status 2.

## Requirements covered

- SPEC-0008/FR-NEW-004: WHEN a user passes `--report-only` THE Editor SHALL analyse every slide of the presentation, write no picture, print the problem lines and the final line, and exit with status 1 when at least one problem is found.
- SPEC-0008/FR-NEW-003 (partial: problems of several slides are listed in slide order; the presentation check also applies to `--report-only`): WHEN a user passes `--report` THE Editor SHALL also print the layout problems of the rendered slide, then a final line, and exit with status 1 when at least one problem is found.

## Independent Test

`make test ARGS='-k render_report_only'`: `render DECK-EI --report-only` prints the single line `report: OK` and creates no picture; with a `height:700px` block on `slide-4` it prints `overflow slide-4: content is <N>px tall, the slide is 540px` and `report: 1 problem` with status 1; `render DECK-EI --report-only --slide slide-1` prints `Error: --report-only cannot be used with --slide, --scale or --report` with status 2.

## Design excerpt

### Decisions

- DEC-014 (SPEC-0008): "One page load per run. `--report` shows and measures the target slide only; `--report-only` shows and measures each slide in order; images are collected once for the whole page and filtered by scope."
- DEC-015 (SPEC-0008): "Ordering is computed in `problems.py`: `-` first, then slide document order, then `KIND_ORDER`, then document order within a kind (a counter assigned at collection time)."
- DEC-017 (SPEC-0008): "The option conflict is detected in `check_options`, raised as `RenderUsageError`, and printed by the command as `Error: <message>` with exit status 2 by hand. `--scale` is a text option."

### Data model

No new data. A report only run returns `RenderResult(path=None, width=None, height=None, slide=None, problems=...)`.

### Contracts

```python
# render/options.py
def check_options(*, slide: str | None, scale: str | float | None, report: bool, report_only: bool) -> None   # RenderUsageError
# render/service.py
def render_deck(file, *, slide=None, scale=None, report=False, report_only=False) -> RenderResult
```
`check_options` is the first call of `render_deck`: `--report-only` with `slide` set, `scale` not `None` or `report` true raises `RenderUsageError("--report-only cannot be used with --slide, --scale or --report")`. The command catches `RenderUsageError` inside its body, prints `Error: <message>` (no usage block) on stderr, nothing on stdout, and exits with status 2. All other errors keep `error: ` and status 1.
Check order after this story: conflict (status 2), scale, file not found, not a presentation, browser missing, unknown slide id.
Report only run: one page load, show and measure each slide in document order, no screenshot, no output directory access (no mkdir, no cleanup); output: the problem lines then the final line, no `Rendered` line; status 1 when at least one problem. Problems are ordered by slide in document order, then `KIND_ORDER`, then document order.
`render.session` span attribute `render.mode` is `report_only`.
Spec text for this story (verbatim):

#### FR-NEW-004 [EARS-E]: Report only
> WHEN a user passes `--report-only` THE Editor SHALL analyse every slide of the presentation, write no picture, print the problem lines and the final line, and exit with status 1 when at least one problem is found.

- **Business rules:** `--report-only` together with `--slide`, `--scale` or `--report` is a usage error: `Error: --report-only cannot be used with --slide, --scale or --report` (exit status 2, no other output). The analysis of a slide uses the same measures as FR-NEW-003.
- **Scenario:** SC-002
- **Priority:** Must

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/render/options.py` | modify: `check_options` |
| `src/mcp_htmleditor/render/service.py` | modify: `--report-only` run |
| `src/mcp_htmleditor/cli.py` | modify: option `--report-only`, usage error path |
| `tests/test_render_report_only.py` | create |
| `.agent_docs/testing.md` | modify: test file map rows for the render tests, `needs_chromium` and fixtures |

### Existing patterns

- `src/mcp_htmleditor/render/service.py` (US-0061 to US-0063).
- `.agent_docs/testing.md` Files table (one row per test file).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures of the spec (verbatim):

DECK-EI: an Euro-Information presentation of 8 slides `slide-0` to `slide-7` with no layout problem. DECK-MED: a
medical presentation of 6 slides whose `slide-2` has class `slide dark`. DOC-PERSO: a document. The machine running the tests has Segoe UI or Calibri installed, so DECK-EI and DECK-MED report no font problem. Where a test needs a defect, it states the defect.

Fixtures are generated by `tests/render_support.py` (US-0060) from the SPEC-0007 helpers in `tests/deck_support.py` (`build_deck`, `deck_med`, `doc_perso`, `run_cli`, `call_tool`), never committed and never read from `~/.config`. DECK-EI is `build_deck("ei", EI_TITLES)` with 8 titles and no big image. DECK-MED is `deck_med()` with the article of `slide-2` given `class="slide dark"`. DOC-PERSO is `doc_perso()`. The output directory is redirected with `monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))`. Browser tests carry `@needs_chromium`. On a machine without Segoe UI and Calibri the EI font stack still ends with Arial (`templates/bootstrap/slides-ei-empty.html:31`), which keeps DECK-EI free of a `font` problem.

### SPEC-0008/E2E-004: Clean report only

- Level E2E; Driver CLI; Location `tests/test_render_report_only.py`
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --report-only`
- **Then** the output is the single line `report: OK`, exit status 0, and no picture file is created for DECK-EI
- **Priority:** Critical

### SPEC-0008/E2E-010: Not a presentation

- Level E2E; Driver CLI; Location `tests/test_render_report_only.py`
- **Given** DOC-PERSO
- **When** the user runs `render DOC-PERSO` and `render DOC-PERSO --report-only`
- **Then** each prints `error: render needs a presentation: DOC-PERSO`, exit status 1
- **Priority:** High

### SPEC-0008/E2E-012: Overflow

- Level E2E; Driver CLI; Location `tests/test_render_report_only.py`
- **Given** DECK-EI where the body of `slide-4` holds a block with the style `height:700px`
- **When** the user runs `render DECK-EI --report-only`
- **Then** the output holds one line `overflow slide-4: content is <N>px tall, the slide is 540px` where `<N>` is an integer of at least 700, then `report: 1 problem`; no `clipped` line appears; the exit status is 1
- **And** the block of `height:700px` placed instead as a direct child of the slide element, after the inner frame, not absolutely positioned, gives the same line with `<N>` at least 700
- **And** `slide-4` whose body content is replaced by `<div style="height:300px"></div>` gives no `overflow` line
- **And** the file DECK-EI is byte for byte unchanged
- **Priority:** Critical

### SPEC-0008/E2E-018: Incompatible options

- Level E2E; Driver CLI; Location `tests/test_render_report_only.py`
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --report-only --slide slide-1`
- **Then** the error output is exactly `Error: --report-only cannot be used with --slide, --scale or --report`, exit status 2, nothing on the standard output
- **Priority:** Medium

### Additional integration and unit tests (`tests/test_render_report_only.py`)

- After `--report-only` the output directory holds exactly what it held before (a pre existing `DECK-EI-slide-5.png` is untouched; no directory is created when it did not exist).
- Two slides with overflow (`slide-1` and `slide-4`) give two `overflow` lines in slide order and `report: 2 problems`.
- Conflict table: `--report-only` with `--slide slide-1`, with `--scale 0.7`, with `--report` each give status 2, the exact `Error:` line, an empty stdout; `--scale 0.5` given explicitly is also a conflict.
- `--report-only` on DOC-PERSO is refused as not a presentation before any browser is started (works with `PLAYWRIGHT_BROWSERS_PATH` pointing at an empty directory).
- `check_options` unit: no error for `report_only` alone; no error for the other options without `report_only`.

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/export/*`, `src/mcp_htmleditor/mcp_server.py`.
- Dependencies not to add: none.
- Patterns to avoid: `click.UsageError` (adds a usage block); `print`; writing any file in a report only run.
- Scope boundary: no `font`, `script`, `image` kinds, no JSON, no tool.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the command and output of the failing run).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: existing tests pass unmodified (`tests/test_skill_content.py`, `tests/test_templates.py`, the three existing browser E2E files); the existing commands and tools behave as before.
- [ ] Docs updated: `.agent_docs/testing.md` updated in this story.
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0064: Report only across the deck` with body `Spec: SPEC-0008` and requirement ids FR-NEW-004, FR-NEW-003.
