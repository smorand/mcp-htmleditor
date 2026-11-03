# US-0065: Font, script and image problems

> Spec: SPEC-0008 (sdlc/specs/SPEC-0008-visual-render/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0064
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Complete the layout report with the three signals that come from the page and not from geometry: missing fonts, uncaught script errors and images that do not load, with their attribution to slides and the full problem ordering.

## Requirements covered

- SPEC-0008/FR-NEW-003 (partial: kinds `font`, `script`, `image` and the complete ordering rule): WHEN a user passes `--report` THE Editor SHALL also print the layout problems of the rendered slide, then a final line, and exit with status 1 when at least one problem is found.
- SPEC-0008/FR-NEW-004 (partial: the same measures in `--report-only`): WHEN a user passes `--report-only` THE Editor SHALL analyse every slide of the presentation, write no picture, print the problem lines and the final line, and exit with status 1 when at least one problem is found.

## Independent Test

`make test ARGS='-k render_signals'`: with `NoSuchFont, sans-serif` text on `slide-1`, a missing `pics/missing.png` on `slide-6` and a `throw new Error("boom")` script, `render DECK-EI --report-only` lists `script -: Error: boom`, `font slide-1: "NoSuchFont" is not available, fallback used` and `image slide-6: pics/missing.png did not load`.

## Design excerpt

### Decisions

- DEC-011 (SPEC-0008): "A font family list is reported when none of its non generic names is installed; "installed" means the width of a probe text drawn with `<name>, <base>` differs from the width with `<base>` alone for at least one of `monospace`, `serif`, `sans-serif`, after `document.fonts.load` for that name. The first non generic name is the one printed."
- DEC-012 (SPEC-0008): "Script errors come from `page.on("pageerror")`, written `<name>: <message>`, attributed to the slide being displayed at that moment and to `-` before the first slide is shown (page load), identical (slide, text) pairs kept once."
- DEC-013 (SPEC-0008): "An image failed when, after the `load` event, an `img` inside a slide has `complete` true and `naturalWidth` 0; the reported source is the `src` attribute as written; a data address longer than 40 characters is shortened to its first 40 characters plus `...`, a shorter one is printed as is."
- DEC-015 (SPEC-0008): "Ordering is computed in `problems.py`: `-` first, then slide document order, then `KIND_ORDER`, then document order within a kind (a counter assigned at collection time)."

### Data model

Raw load facts: images `[{"slide_index":6,"src":"pics/missing.png"}]` (once per page, from `IMAGES_JS`); script errors `ScriptError(slide: str, text: str)` where `slide` is `-` before the first slide is shown. `RawSlide.fonts` carries the names to report.

### Contracts

```python
# render/scripts.py
IMAGES_JS: Final[str]           # () => [{slide_index, src}] for img in a slide with complete && naturalWidth === 0
MEASURE_SLIDE_JS                # now fills "fonts"
# render/problems.py
def shorten_source(src: str) -> str            # data address longer than 40 characters: first 40 + "..." ; shorter kept
def build_problems(slides, images, errors) -> list[RenderProblem]    # full ordering
```
Messages: `font`: `"{name}" is not available, fallback used`; `script`: `{name}: {message}` (Playwright `Error.name`, `Error.message`, e.g. `Error: boom`); `image`: `{source} did not load` (the `src` attribute as written).
Font rule (page script): for each element of the slide with a direct non blank text node, collect its computed `font-family`; split into names (quotes removed); ignore `sans-serif`, `serif`, `monospace`, `system-ui`; a list is reported when none of its remaining names is installed, naming the first remaining name; one line per name per slide. A name is installed when, after `await document.fonts.load('72px ' + raw)`, the canvas text width of `raw + ',' + base` differs from the width of `base` for at least one of `monospace`, `serif`, `sans-serif`.
Script errors: `page.on("pageerror", ...)` registered before `goto`; the service sets a `current` marker to `-` and to the slide id around each show; identical (slide, text) pairs are kept once. In `--report` only errors with slide `-` and errors of the rendered slide are kept.
Images: collected once after the load event; in `--report` only the images of the rendered slide count.
Full order: slide `-` first, then slide document order, then `KIND_ORDER` (`script`, `image`, `font`, `overflow`, `clipped`), then document order inside a kind.
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

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/render/scripts.py` | modify: `IMAGES_JS`, fonts in `MEASURE_SLIDE_JS` |
| `src/mcp_htmleditor/render/problems.py` | modify: kinds, `shorten_source`, ordering |
| `src/mcp_htmleditor/render/service.py` | modify: `pageerror` listener, images, fonts |
| `tests/test_render_signals.py` | create |
| `.agent_docs/render.md` | modify: measure definitions and their measured behavior |

### Existing patterns

- `src/mcp_htmleditor/render/scripts.py`, `problems.py`, `service.py` (US-0063, US-0064).
- Design DEC-011 to DEC-013 for the measured behavior (`document.fonts.check` is useless, `pageerror` carries name and message, `naturalWidth` of a viewBox only SVG is non zero).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures of the spec (verbatim):

DECK-EI: an Euro-Information presentation of 8 slides `slide-0` to `slide-7` with no layout problem. DECK-MED: a
medical presentation of 6 slides whose `slide-2` has class `slide dark`. DOC-PERSO: a document. The machine running the tests has Segoe UI or Calibri installed, so DECK-EI and DECK-MED report no font problem. Where a test needs a defect, it states the defect.

Fixtures are generated by `tests/render_support.py` (US-0060) from the SPEC-0007 helpers in `tests/deck_support.py` (`build_deck`, `deck_med`, `doc_perso`, `run_cli`, `call_tool`), never committed and never read from `~/.config`. DECK-EI is `build_deck("ei", EI_TITLES)` with 8 titles and no big image. DECK-MED is `deck_med()` with the article of `slide-2` given `class="slide dark"`. DOC-PERSO is `doc_perso()`. The output directory is redirected with `monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))`. Browser tests carry `@needs_chromium`. On a machine without Segoe UI and Calibri the EI font stack still ends with Arial (`templates/bootstrap/slides-ei-empty.html:31`), which keeps DECK-EI free of a `font` problem.

### SPEC-0008/E2E-015: Missing font

- Level E2E; Driver CLI; Location `tests/test_render_signals.py`
- **Given** DECK-EI where `slide-1` holds two text blocks using the font family `NoSuchFont, sans-serif`
- **When** the user runs `render DECK-EI --report-only`
- **Then** the output holds exactly one line `font slide-1: "NoSuchFont" is not available, fallback used`
- **Priority:** Medium

### SPEC-0008/E2E-016: Script error

- Level E2E; Driver CLI; Location `tests/test_render_signals.py`
- **Given** DECK-EI where a script of `slide-2` runs `throw new Error("boom")` when the page loads
- **When** the user runs `render DECK-EI --slide slide-2 --report`
- **Then** the output holds `script -: Error: boom` and ends with `report: 1 problem`, exit status 1
- **Priority:** High

### SPEC-0008/E2E-017: Image that does not load

- Level E2E; Driver CLI; Location `tests/test_render_signals.py`
- **Given** DECK-EI where `slide-6` holds `<img src="pics/missing.png">` and the file `pics/missing.png` does not exist
- **When** the user runs `render DECK-EI --report-only`
- **Then** the output holds `image slide-6: pics/missing.png did not load`, exit status 1
- **Priority:** High

### SPEC-0008/E2E-019: Several problems counted

- Level E2E; Driver CLI; Location `tests/test_render_signals.py`
- **Given** DECK-EI with the defects of E2E-012, E2E-015 and E2E-017
- **When** the user runs `render DECK-EI --report-only`
- **Then** the lines appear in this order: `font slide-1: "NoSuchFont" is not available, fallback used`, `overflow slide-4: ...`, `image slide-6: pics/missing.png did not load`, then the last line `report: 3 problems`; exit status 1
- **Priority:** High

### Additional integration and unit tests (`tests/test_render_signals.py`)

- Fonts in a real page: a list `"Other Fnt", Arial` is not reported; `'Other Fnt', NoSuchFont` is reported once naming `Other Fnt`; `sans-serif` alone is not reported; two blocks with the same family give one line; a quoted name with a space is read as one name.
- Script attribution: an error thrown at load is reported on `-`; an error thrown by a `MutationObserver` on the class of `slide-3` (run when the slide is shown) is reported as `script slide-3: Error: late`; an identical error repeated is listed once.
- `shorten_source`: a 60 character data address becomes its first 40 characters plus `...`; a 30 character data address and a relative path are unchanged.
- A valid data PNG and a data SVG with only a `viewBox` are not reported as images.
- `--report` on `slide-2` ignores the missing image of `slide-6` but lists a load time `script -` error.
- Ordering unit with the five kinds on two slides plus a `-` problem: `-` first, then slide order, then `script`, `image`, `font`, `overflow`, `clipped`.

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/export/*`, `src/mcp_htmleditor/mcp_server.py`, `src/mcp_htmleditor/cli.py`.
- Dependencies not to add: none.
- Patterns to avoid: `document.fonts.check` as the availability test; matching `requestfailed` URLs for images; `print`; `type: ignore`.
- Scope boundary: no JSON, no tool.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the command and output of the failing run).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: existing tests pass unmodified (`tests/test_skill_content.py`, `tests/test_templates.py`, the three existing browser E2E files); the existing commands and tools behave as before.
- [ ] Docs updated: `.agent_docs/render.md` updated in this story.
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0065: Font, script and image problems` with body `Spec: SPEC-0008` and requirement ids FR-NEW-003, FR-NEW-004.
