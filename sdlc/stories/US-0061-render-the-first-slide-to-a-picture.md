# US-0061: Render the first slide to a picture

> Spec: SPEC-0008 (sdlc/specs/SPEC-0008-visual-render/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0060, US-0035, US-0038
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Give an agent or a maintainer `mcp-htmleditor render <file>`: a PNG of the first slide at scale 0.5 written under `<system temporary directory>/htmleditor-render/`, one printed line, the check order up to the browser, and the cleanup of stale pictures of the same presentation.

## Requirements covered

- SPEC-0008/FR-NEW-001 (partial: default slide and scale 0.5, picture path, size and cleanup, checks file not found, not a presentation and browser missing; `--slide` and `--scale` arrive in US-0062, the layout report in US-0063 to US-0065, `--json` in US-0066): WHEN a user runs `mcp-htmleditor render <file>` THE Editor SHALL write a PNG picture of one slide of the presentation and print one line giving its slide, path and size.
- SPEC-0008/FR-NEW-006 (partial: the presentation file is not modified by a render; the editor server state is checked with the tool in US-0066): The Editor SHALL NOT modify the presentation file or the state of a running editor server when rendering.

## Independent Test

`make test ARGS='-k render_picture'`: `mcp-htmleditor render DECK-EI` prints `Rendered slide-0 to <tmp>/htmleditor-render/DECK-EI-slide-0.png (480x270)`, the file is a 480 x 270 PNG, `render ghost.html` prints `error: File not found: ghost.html` on stderr with an empty stdout.

## Design excerpt

### Decisions

- DEC-001 (SPEC-0008): "Playwright sync API, one session per call, in the calling thread; the tool is a plain `def`."
- DEC-003 (SPEC-0008): "A missing browser and a missing `playwright` package give the same message `Rendering needs Chromium. Install it with: make install-browser`. Missing browser is detected by catching the launch error whose text contains `Executable doesn't exist`, missing package by `ImportError`."
- DEC-004 (SPEC-0008): "The browser-missing test needs no production seam: it redirects `PLAYWRIGHT_BROWSERS_PATH` to an empty directory."
- DEC-006 (SPEC-0008): "Slides are the `[data-type="slide"]` elements of the BeautifulSoup tree that `deck.load_deck` already parsed; the file is a presentation when `doc_type == "presentation"` and there is at least one such element; the id of slide `i` is `slide_id(tag)` (SPEC-0007: `data-id`, else `id`) else `slide-<i>`."
- DEC-007 (SPEC-0008): "Showing one slide alone is done in the live page: toggle `active` on every `[data-type="slide"]`, hide the others with an inline `display:none !important`, fall back to `display:block` on the target when it is still hidden, finish all animations. The file is never written."
- DEC-008 (SPEC-0008): "One context with viewport 1280 x 900, `device_scale_factor` equal to the scale, light colour scheme; the picture is `page.screenshot(clip={x: round(box.x), y: round(box.y), width: 960, height: 540}, animations="disabled")`."
- DEC-009 (SPEC-0008): "The expected size is computed with `Decimal` and `ROUND_HALF_UP` from the text of the scale, and the PNG header read after capture must equal it, otherwise `Rendering failed: picture is <w>x<h>, expected <w>x<h>`."
- DEC-016 (SPEC-0008): "Pictures go to `<tempfile.gettempdir()>/htmleditor-render/<stem>-<id>.png`; `<id>` has `/`, `\` and NUL replaced by `_`; the file is written with `fileio.atomic_write` after `mkdir(parents=True, exist_ok=True)`; stale pictures are removed by enumerating the presentation's own slide ids (`<stem>-<id>.png` for each id) and unlinking each one that exists and is not the new picture, only after a successful render; an unlink failure is logged at warning level and ignored."
- DEC-020 (SPEC-0008): "Failures the spec does not name get one `RenderError` each: `Chromium could not start: <reason>`, `Rendering failed: <reason>` (load timeout, driver error), `Rendering failed: picture is <w>x<h>, expected <w>x<h>`."
- DEC-021 (SPEC-0008): "`render_deck` never reads or writes the editor state, the history store or the input file: it opens the file read only through `load_deck` and the browser reads it through `file://`."
- DEC-024 (SPEC-0008): "Spans: `render.session` (INFO; attributes `render.mode` picture, report or report_only, `render.slides` count, `render.scale` text), `render.cleanup` (DEBUG; `file.count`), `mcp.render`. No path, selector, text or image data in an attribute."

### Data model

Value objects in `render/__init__.py` (frozen, `slots=True`): `RenderProblem(kind, slide, message)`, `RenderResult(path, width, height, slide, problems)`; constants `DEFAULT_SCALE = 0.5`, `CANVAS_WIDTH = 960`, `CANVAS_HEIGHT = 540`.
`SlideRef(index, slide_id)` private to `service.py`. This story renders at the fixed default scale: the size is `CANVAS_WIDTH * DEFAULT_SCALE` by `CANVAS_HEIGHT * DEFAULT_SCALE` (480 x 270). The script that shows one slide is a private constant of `service.py` here and moves unchanged to `render/scripts.py` in US-0063.

### Contracts

Command: `mcp-htmleditor render FILE` (`FILE` is `click.Path(dir_okay=False)` without `exists=True`), wrapped by `deck_command` (SPEC-0007: `DeckError` becomes `error: <message>` on stderr, empty stdout, status 1).
```python
# render/__init__.py
class RenderError(DeckError): ...
class RenderUsageError(RenderError): ...        # raised from US-0064 on, defined here
# render/files.py
def render_dir() -> Path                                  # Path(tempfile.gettempdir()) / "htmleditor-render"
def picture_path(file: str, slide_id: str) -> Path        # <stem>-<id>.png, "/", "\\" and NUL in the id replaced by "_"
def write_picture(path: Path, data: bytes) -> None        # mkdir(parents=True, exist_ok=True); fileio.atomic_write
def remove_stale(file: str, slide_ids: Sequence[str], keep: Path) -> int   # trace_span("render.cleanup", {"file.count": n})
# render/service.py
def render_deck(file: str, *, slide: str | None = None, scale: str | float | None = None,
                report: bool = False, report_only: bool = False) -> RenderResult
```
In this story the signature is `render_deck(file: str) -> RenderResult`; the keyword parameters shown above are added by the stories that need them (US-0062 and later).
Order of checks in this story: file not found (`File not found: <file>`), not a presentation (`render needs a presentation: <file>`), browser (`Rendering needs Chromium. Install it with: make install-browser`). Presentation test: `deck.doc_type == "presentation"` and at least one `[data-type="slide"]` in `deck.soup`. Slide id of index `i`: `slide_id(tag)` else `slide-<i>`.
Browser: lazy `from playwright.sync_api import sync_playwright, Error`; `ImportError` or an `Error` whose text contains `Executable doesn't exist` gives the install message; any other launch `Error` gives `Chromium could not start: <first line, max 200 characters>`; page load or driver errors give `Rendering failed: <reason>`; a PNG whose header size differs from the expected gives `Rendering failed: picture is <w>x<h>, expected <w>x<h>`.
Session: `browser = chromium.launch()`, `context = browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=0.5, color_scheme="light")`, `page.goto(Path(file).resolve().as_uri(), wait_until="load", timeout=15_000)`, always `browser.close()` in `finally`; the whole session inside `trace_span("render.session", {"render.mode": "picture", "render.slides": n, "render.scale": "0.5"})`.
Show script (target index `idx`): toggle `active` on every `[data-type="slide"]`, inline `display:none !important` on the others, `display:block` on the target when its computed display is still `none`, finish `document.getAnimations()`, await two animation frames.
Picture: `box = page.locator('[data-type="slide"]').nth(idx).bounding_box()`; `page.screenshot(clip={"x": round(box["x"]), "y": round(box["y"]), "width": 960, "height": 540}, animations="disabled")` returns bytes; check IHDR size; `write_picture`; then `remove_stale`.
Cleanup: for each slide id of the presentation, the file `render_dir()/<stem>-<safe id>.png` is unlinked when it exists and is not the new picture; only after a successful render; an unlink `OSError` is logged with `logger.warning("render: could not remove %s", path)` and ignored; errors delete nothing.
Output (stdout): `Rendered <slide> to <path> (<w>x<h>)`.
Spec text for this story (verbatim):


#### FR-NEW-001 [EARS-E]: Render a slide
> WHEN a user runs `mcp-htmleditor render <file>` THE Editor SHALL write a PNG picture of one slide of the presentation and print one line giving its slide, path and size.

- **Business rules:** the picture is exactly the 960 x 540 slide element at device scale equal to the scale, with no border or shadow, captured after the slide's entrance animation has finished; nothing else of the page appears (no top bar, toolbar, side arrows, status bar or neighbouring slide); the slide's own markup and styles are not altered, except that only the target slide is displayed. Slides are the elements `data-type="slide"` in document order, identified by `data-id`; a presentation with no slide is refused as not a presentation. Checks are made in this order and the first failure alone is reported: option conflict (exit status 2), scale, file not found, not a presentation, browser missing, unknown slide id (exit status 1 each). Sizes are rounded half up. The default slide is the first. The default scale is 0.5, so the picture is `round(960 x scale)` by `round(540 x scale)` pixels. The picture is written to `<system temporary directory>/htmleditor-render/<file name without extension>-<slide id>.png`, and, only after a successful render, every file in that directory other than the picture just written, named `<file name without extension>-<id>.png` where `<id>` is a slide id of the presentation, is deleted (errors and `--report-only` delete nothing); the name keeps the file's own characters. The file given is a presentation; a document, mail or website is refused. Without the browser installed the command prints the error below. The command never prompts.
- **User visible text:** `Rendered slide-3 to /tmp/htmleditor-render/deck-slide-3.png (480x270)`; `error: File not found: <file>`; `error: render needs a presentation: <file>`; `error: Rendering needs Chromium. Install it with: make install-browser` (exit status 1 for all three).
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
| `src/mcp_htmleditor/render/__init__.py` | create |
| `src/mcp_htmleditor/render/service.py` | create |
| `src/mcp_htmleditor/render/files.py` | create |
| `src/mcp_htmleditor/cli.py` | modify: command `render` |
| `tests/test_render_picture.py` | create |

### Existing patterns

- `src/mcp_htmleditor/cli.py:26-30` (Click group), `:113-121` (lazy import inside the command body), `deck_command` from US-0035 (error wrapper).
- `src/mcp_htmleditor/deck/__init__.py` (US-0035): `load_deck`, `slide_id`, `DeckError`; `src/mcp_htmleditor/fileio.py` (US-0038): `atomic_write(path, data)`.
- `src/mcp_htmleditor/tracing.py:132` `trace_span`; `.agent_docs/observability.md` attribute rules.
- `tests/test_tab_title_e2e.py:29-40` (Chromium skip), `tests/render_support.py` (US-0060), `tests/deck_support.py` `run_cli` (US-0035).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures of the spec (verbatim):

DECK-EI: an Euro-Information presentation of 8 slides `slide-0` to `slide-7` with no layout problem. DECK-MED: a
medical presentation of 6 slides whose `slide-2` has class `slide dark`. DOC-PERSO: a document. The machine running the tests has Segoe UI or Calibri installed, so DECK-EI and DECK-MED report no font problem. Where a test needs a defect, it states the defect.

Fixtures are generated by `tests/render_support.py` (US-0060) from the SPEC-0007 helpers in `tests/deck_support.py` (`build_deck`, `deck_med`, `doc_perso`, `run_cli`, `call_tool`), never committed and never read from `~/.config`. DECK-EI is `build_deck("ei", EI_TITLES)` with 8 titles and no big image. DECK-MED is `deck_med()` with the article of `slide-2` given `class="slide dark"`. DOC-PERSO is `doc_perso()`. The output directory is redirected with `monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))`. Browser tests carry `@needs_chromium`. On a machine without Segoe UI and Calibri the EI font stack still ends with Arial (`templates/bootstrap/slides-ei-empty.html:31`), which keeps DECK-EI free of a `font` problem.

### SPEC-0008/E2E-001: Default render

- Level E2E; Driver CLI; Location `tests/test_render_picture.py`
- **Given** DECK-EI and the browser installed
- **When** the user runs `mcp-htmleditor render DECK-EI`
- **Then** the output is `Rendered slide-0 to <path> (480x270)` where `<path>` ends with `htmleditor-render/DECK-EI-slide-0.png`, the exit status is 0
- **And** the file at `<path>` is a PNG picture of 480 x 270 pixels
- **Priority:** Critical

### SPEC-0008/E2E-022: Path with spaces and accents

- Level E2E; Driver CLI; Location `tests/test_render_picture.py`
- **Given** the file `Présentation été.html` (a copy of DECK-EI)
- **When** the user runs `render "Présentation été.html"`
- **Then** the output is `Rendered slide-0 to <path> (480x270)` where `<path>` ends with `Présentation été-slide-0.png`, and the picture exists
- **Priority:** Medium

### Additional integration and unit tests (`tests/test_render_picture.py`)

- `render ghost.html`: stderr exactly `error: File not found: ghost.html\n`, stdout empty, status 1 (no browser needed).
- `render DOC-PERSO`: stderr `error: render needs a presentation: DOC-PERSO\n`, status 1; the same for the mail bootstrap, the website bootstrap, and for a file with `data-doc-type="presentation"` whose slides are `<article class="slide">` without `data-type="slide"`.
- A default render leaves the file bytes and modification time unchanged (compare `Path.read_bytes()` and `st_mtime_ns`, after forcing the time with `os.utime`).
- `picture_path("deck.html", "a/b\\c")` ends with `deck-a_b_c.png` and has the directory `htmleditor-render` as parent; the stem keeps `[`, `*` and accents.
- `remove_stale` removes `deck-slide-1.png` and `deck-slide-2.png` when `keep` is `deck-slide-3.png`, leaves `other-slide-1.png` and `deck-extra.png` (not an id of the deck), and returns 2.
- A failed render deletes nothing: with `PLAYWRIGHT_BROWSERS_PATH` pointing at an empty directory (browser missing) a stale `DECK-EI-slide-5.png` placed in the output directory is still there after the command fails.
- The picture is written through `atomic_write`: with `mcp_htmleditor.render.files.atomic_write` replaced by a recording stub the call receives the target path and PNG bytes.
- Import purity: a subprocess that imports `mcp_htmleditor.render` and prints whether `playwright` and `pptx` are in `sys.modules` prints `False False`.

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/export/*`, `src/mcp_htmleditor/mcp_server.py`, `src/mcp_htmleditor/state.py`, `src/mcp_htmleditor/config.py` (no new setting).
- Dependencies not to add: none (Playwright is the optional extra from US-0060).
- Patterns to avoid: `print` or any stdout use in `render/` (only `cli.py` echoes); module level `import playwright`; `type: ignore`; `os.environ`; writing the picture with the driver's `path=` argument.
- Scope boundary: no `--slide`, `--scale`, `--report`, `--report-only`, `--json`, no tool.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the command and output of the failing run).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: existing tests pass unmodified (`tests/test_skill_content.py`, `tests/test_templates.py`, the three existing browser E2E files); the existing commands and tools behave as before.
- [ ] Docs updated: none required by this story (`.agent_docs/render.md` is created in US-0062, the user documentation in US-0067).
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0061: Render the first slide to a picture` with body `Spec: SPEC-0008` and requirement ids FR-NEW-001, FR-NEW-006.
