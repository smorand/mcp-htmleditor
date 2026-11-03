# US-0063: Layout report for one slide

> Spec: SPEC-0008 (sdlc/specs/SPEC-0008-visual-render/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0062
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Add `--report` with the two geometric problem kinds: `overflow` (content height including content clipped by descendants) and `clipped` (elements outside the slide frame), the problem line format, the final line, the exit status 1, and the scope of the report to the rendered slide.

## Requirements covered

- SPEC-0008/FR-NEW-003 (partial: kinds `overflow` and `clipped`, ordering of lines, final line and exit status; the kinds `font`, `script` and `image` arrive in US-0065): WHEN a user passes `--report` THE Editor SHALL also print the layout problems of the rendered slide, then a final line, and exit with status 1 when at least one problem is found.
- SPEC-0008/FR-NEW-006 (partial: the presentation file is byte for byte and time unchanged after `--report`): The Editor SHALL NOT modify the presentation file or the state of a running editor server when rendering.

## Independent Test

`make test ARGS='-k render_report'`: `render DECK-EI --slide slide-2 --report` prints the `Rendered` line then `report: OK` with status 0; with the probe element of E2E-013 it prints `clipped slide-5: div.probe is outside the slide frame` and `report: 1 problem` with status 1.

## Design excerpt

### Decisions

- DEC-010 (SPEC-0008): "The layout measures are the spec definitions transcribed as page script (`SHOW_SLIDE_JS`, `MEASURE_SLIDE_JS`, `IMAGES_JS`), evaluated per slide; `problems.py` only formats and orders."
- DEC-014 (SPEC-0008): "One page load per run. `--report` shows and measures the target slide only; `--report-only` shows and measures each slide in order; images are collected once for the whole page and filtered by scope."
- DEC-015 (SPEC-0008): "Ordering is computed in `problems.py`: `-` first, then slide document order, then `KIND_ORDER`, then document order within a kind (a counter assigned at collection time)."
- DEC-021 (SPEC-0008): "`render_deck` never reads or writes the editor state, the history store or the input file: it opens the file read only through `load_deck` and the browser reads it through `file://`."
- DEC-022 (SPEC-0008): "The three scripts live in `render/scripts.py` as Python string constants."

### Data model

Raw measure of one slide: `{"content":1184,"clipped":["div.probe"],"fonts":[]}` (`fonts` is filled by US-0065). Python: `RawSlide(slide: str, index: int, content: int, clipped: tuple[str, ...], fonts: tuple[str, ...])`. `RenderProblem(kind, slide, message)`.

### Contracts

```python
# render/scripts.py   (the show script of US-0061 moves here unchanged)
SHOW_SLIDE_JS: Final[str]       # async (idx) => { ... }
MEASURE_SLIDE_JS: Final[str]    # async (idx) => ({content, clipped, fonts}) ; fonts [] until US-0065
# render/problems.py
KIND_ORDER: Final = ("script", "image", "font", "overflow", "clipped")
def build_problems(slides: Sequence[RawSlide], images=(), errors=()) -> list[RenderProblem]
def format_line(problem: RenderProblem) -> str                 # "<kind> <slide>: <message>"
def final_line(count: int) -> str                              # "report: OK" | "report: 1 problem" | "report: N problems"
# render/service.py
def render_deck(file, *, slide=None, scale=None, report=False) -> RenderResult
```
Messages: `overflow` is `content is {N}px tall, the slide is 540px`; `clipped` is `{selector} is outside the slide frame`.
Measure script (transcription of the spec): show the slide (SHOW script), then `content = Math.round(max(slide.scrollHeight, top(d) - top(slide) + d.scrollHeight))` over rendered descendants `d` (`getClientRects().length > 0`, computed display not `none`) whose computed `overflow-y` is `hidden`, `clip` or `auto`, tops from `getBoundingClientRect()` unrounded. `clipped`: iterate rendered descendants in document order, skip size 0 x 0, skip descendants of an already reported element, report when `left < frame.left - 1`, `right > frame.right + 1`, `top < frame.top - 1`, or (`content <= 540` and `bottom > frame.bottom + 1`); selector is the lower case tag name plus `.` plus each class of the `class` attribute in order (tag alone when none).
`--report` scope: problems of the rendered slide only (plus `script` problems whose slide is `-`, none yet), listed and counted; the other slides are not even measured. Order: by kind in `KIND_ORDER`, then document order. Output: `Rendered ...` line, one line per problem, final line; status 1 when at least one problem.
`render.session` span attribute `render.mode` is `report` for `--report`.
Spec text for this story (verbatim):

#### FR-NEW-003 [EARS-E]: Layout report
> WHEN a user passes `--report` THE Editor SHALL also print the layout problems of the rendered slide, then a final line, and exit with status 1 when at least one problem is found.

- **Business rules:** a problem line is `<kind> <slide>: <message>`. Kinds and messages:
  - `overflow`: the content height of the slide, rounded to the nearest pixel, is greater than 540: `content is 612px tall, the slide is 540px` (that rounded value). The content height is the largest of the scroll height of the slide element and, for every rendered descendant of the slide (not `display:none`) whose computed `overflow-y` is `hidden`, `clip` or `auto`, the unrounded distance from the top of the slide to the top of that descendant (difference of their bounding box tops) plus its scroll height; the value is rounded once, at the end; this makes content cut off by a slide body count, not only content cut off by the slide itself.
  - `clipped`: a rendered element (not `display:none`, not of zero size) inside the slide, which is not a descendant of an element already reported, has a box beyond the frame by more than 1 pixel on the left, right or top, or on the bottom when the slide does not already report `overflow`; at most one line per element: `<selector> is outside the slide frame`, the selector being the lower case tag name followed by `.` and each class in attribute order joined by `.` (the tag alone when there is no class), for example `span.slide-foot-page`.
  - `font`: for a font family list used by text of the slide, none of its non generic families is installed on this machine (`sans-serif`, `serif`, `monospace`, `system-ui` are ignored): `"NoSuchFont" is not available, fallback used`, naming the first non generic family; one line per name per slide.
  - `script`: an uncaught script error, written `<name>: <message>` (for example `Error: boom`); an error raised while the page loads is reported once per run with the slide `-`; an error raised while a slide is displayed is reported with that slide's id.
  - `image`: an image did not load: `<source> did not load`; a data address is shortened to its first 40 characters followed by `...`.
  - With `--report`, only problems of the rendered slide and `script` problems with the slide `-` are listed and counted; problems of other slides are not.
  - Order: problems with the slide `-` first, then by slide, then kind in the order `script`, `image`, `font`, `overflow`, `clipped`, then document order. Final line `report: OK` or `report: 3 problems` (`1 problem` singular).
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-006 [EARS-UB]: No side effect on the file or the editor
> The Editor SHALL NOT modify the presentation file or the state of a running editor server when rendering.

- **Business rules:** the file bytes and modification time, and the answer of `get_status`, are the same before and after.
- **Scenario:** SC-001, SC-002
- **Priority:** Must

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/render/scripts.py` | create: `SHOW_SLIDE_JS` moved from `service.py`, `MEASURE_SLIDE_JS` |
| `src/mcp_htmleditor/render/problems.py` | create |
| `src/mcp_htmleditor/render/service.py` | modify: `--report`, move the show script |
| `src/mcp_htmleditor/cli.py` | modify: option `--report`, output and exit status |
| `tests/test_render_report.py` | create |

### Existing patterns

- `src/mcp_htmleditor/render/service.py` (US-0061/62).
- The amended definition in `sdlc/specs/SPEC-0008-visual-render/design-issues.md` ISSUE-001 (resolved) and the measurements of design DEC-010.
- `templates/bootstrap/slides-ei-empty.html:79-88,158` (`.slide`, `.slide-body {overflow:hidden}`), `templates/bootstrap/slides-medical-empty.html:94-100`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures of the spec (verbatim):

DECK-EI: an Euro-Information presentation of 8 slides `slide-0` to `slide-7` with no layout problem. DECK-MED: a
medical presentation of 6 slides whose `slide-2` has class `slide dark`. DOC-PERSO: a document. The machine running the tests has Segoe UI or Calibri installed, so DECK-EI and DECK-MED report no font problem. Where a test needs a defect, it states the defect.

Fixtures are generated by `tests/render_support.py` (US-0060) from the SPEC-0007 helpers in `tests/deck_support.py` (`build_deck`, `deck_med`, `doc_perso`, `run_cli`, `call_tool`), never committed and never read from `~/.config`. DECK-EI is `build_deck("ei", EI_TITLES)` with 8 titles and no big image. DECK-MED is `deck_med()` with the article of `slide-2` given `class="slide dark"`. DOC-PERSO is `doc_perso()`. The output directory is redirected with `monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))`. Browser tests carry `@needs_chromium`. On a machine without Segoe UI and Calibri the EI font stack still ends with Arial (`templates/bootstrap/slides-ei-empty.html:31`), which keeps DECK-EI free of a `font` problem.

### SPEC-0008/E2E-003: Clean report

- Level E2E; Driver CLI; Location `tests/test_render_report.py`
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --slide slide-2 --report`
- **Then** the output is two lines: `Rendered slide-2 to <path> (480x270)` and `report: OK`, exit status 0
- **Priority:** Critical

### SPEC-0008/E2E-013: Clipped element

- Level E2E; Driver CLI; Location `tests/test_render_report.py`
- **Given** DECK-EI where the slide element of `slide-5` is made `position:relative` and its body holds `<div class="probe" style="position:absolute; left:940px; top:10px; width:100px; height:20px">x</div>`
- **When** the user runs `render DECK-EI --slide slide-5 --report`
- **Then** the output holds `clipped slide-5: div.probe is outside the slide frame` and ends with `report: 1 problem`, exit status 1
- **Priority:** High

### SPEC-0008/E2E-014: Page number outside the frame

- Level E2E; Driver CLI; Location `tests/test_render_report.py`
- **Given** DECK-EI where the page number element `<span class="slide-foot-page">` of `slide-3` gets the style `position:relative; left:920px`
- **When** the user runs `render DECK-EI --slide slide-3 --report`
- **Then** the output holds `clipped slide-3: span.slide-foot-page is outside the slide frame`, no `overflow` line, and ends with `report: 1 problem`, exit status 1
- **Priority:** High

### SPEC-0008/E2E-024: File untouched

- Level E2E; Driver CLI; Location `tests/test_render_report.py`
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --report`
- **Then** the file bytes and modification time are the same as before
- **Priority:** High

### Additional integration and unit tests (`tests/test_render_report.py`)

- `format_line` and `final_line` tables: 0 gives `report: OK`, 1 gives `report: 1 problem`, 2 gives `report: 2 problems`, 12 gives `report: 12 problems`.
- `build_problems` unit: content 540 gives no `overflow`; content 541 gives `content is 541px tall, the slide is 540px`; the clipped lines come after the overflow line of the same slide.
- Selector format in a real page: a `<p style="position:absolute; left:950px">` gives `p is outside the slide frame`; `<div class="a b">` gives `div.a.b is outside the slide frame`; a child inside a reported element is not reported on its own line.
- A body block of `height:700px` on `slide-4` produces no `clipped` line (bottom edge ignored when the slide reports `overflow`).
- `render DECK-EI --slide slide-2 --report` with a `height:700px` block on `slide-4` prints `report: OK` (other slides are not listed or counted).
- Exit status is 1 with a problem and 0 without; the `Rendered` line is printed before the problem lines.

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/export/*`, `src/mcp_htmleditor/mcp_server.py`.
- Dependencies not to add: none.
- Patterns to avoid: weakening a measure to make a fixture pass (fix the fixture); `print`; evaluating the measure before the animations are finished.
- Scope boundary: no `--report-only`, no `font`, `script`, `image` kinds, no JSON, no tool.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the command and output of the failing run).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: existing tests pass unmodified (`tests/test_skill_content.py`, `tests/test_templates.py`, the three existing browser E2E files); the existing commands and tools behave as before.
- [ ] Docs updated: none required by this story (`.agent_docs/render.md` gets the measure definitions in US-0065).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0063: Layout report for one slide` with body `Spec: SPEC-0008` and requirement ids FR-NEW-003, FR-NEW-006.
