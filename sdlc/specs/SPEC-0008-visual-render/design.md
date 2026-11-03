# SPEC-0008: Visual render and layout report, design

> Spec: SPEC-0008 (`sdlc/specs/SPEC-0008-visual-render/spec.md`)
> Nature: FEAT
> Depth: L
> Security: n/a
> Designed on 2026-11-03
> Target tier: 2 (default)

## 1. Stack and skills

| Item | Value (source) |
|---|---|
| Language, tooling | Python >= 3.13, uv, hatchling; `make` is the only entry point; gate `make check` (ruff, ruff format, mypy strict, bandit, pytest with coverage >= 80%) (`pyproject.toml`, `Makefile:139`) |
| CLI | Click >= 8.0, already the CLI framework (`src/mcp_htmleditor/cli.py:26-30`): kept, no Typer migration; new commands use the `deck_command` wrapper that SPEC-0007 adds (US-0035) |
| Tool protocol | fastmcp (installed 3.4.6); a plain `def` tool runs in an AnyIO worker thread with no running event loop (measured, see DEC-001); errors raised as `ToolError` |
| Browser driver | Playwright for Python, sync API. Today only a dev dependency through `pytest-playwright` (`pyproject.toml:35`), locked at 1.62.0 (`uv.lock:1411-1412`); PyPI latest read on 2026-11-03: 1.64.1; context7 (`/websites/playwright_dev_python`, `/microsoft/playwright-python`) confirms `sync_playwright`, `chromium.launch`, `page.on("pageerror")`, `page.screenshot(clip=..., animations="disabled")`. It becomes an optional runtime extra `render` (DEC-002, NEEDS DECISION) |
| New dependency | `playwright>=1.62,<2` in `[project.optional-dependencies] render`. Nothing else. Pillow is already present through python-pptx and is used by tests only |
| Skill rules applied | make only (new target `install-browser`); no `os.environ` (no new setting: the output directory is the system temporary directory by spec, the viewport and timeouts are module constants); no stdout in the MCP process (services return values, only `cli.py` echoes; the picture is returned as bytes and written by `atomic_write`, never by the driver to a stream); `trace_span` on the browser session and the cleanup (`render.session`, `render.cleanup`, `mcp.render`); mypy strict without `type: ignore`; ruff line length 120; `%` formatting in logs; frozen dataclasses with `__slots__` for value objects; dependencies injected: the service takes plain arguments, `cli.py` and `mcp_server.py` build nothing |
| Documented deviations | sync API instead of asyncio: the project already runs synchronous (`.agent_docs/python.md`, deviations table), the CLI is synchronous and the tool is a plain `def` run in a worker thread; an async rewrite would add a loop for no gain |
| Library research | context7 for the API facts above; the behaviors that matter (thread safety, missing browser error, headless shell, scale rounding, font detection, `pageerror` payload) were measured on the installed Playwright 1.62.0 with Chromium 151, not taken from memory (Section 10 evidence) |

## 2. Approaches

### 2.1 How the browser is driven (the load bearing choice)

The report needs the page's DOM measures, uncaught script errors and a screenshot of one element, in one load.

**Approach A: Playwright sync API in the calling thread, one session per call (chosen).** The CLI calls it from the main thread; the tool is a plain `def`, so fastmcp already runs it in a worker thread that has no event loop, which the sync API requires. One browser, one context (fixed viewport and device scale), one page, loaded once with `goto(file://...)`; slides are shown one after the other by script; the browser is closed in a `finally`.
- Pros: one dependency; page events (`pageerror`) and `evaluate` give every measure of FR-NEW-003 directly; a 9 slide deck is analysed in 0.24 s after the launch (measured); two concurrent tool calls in one process work (measured with `asyncio.gather` over two `fastmcp.Client` calls); same function for the command and the tool (FR-NEW-005).
- Cons: if a caller runs it inside a running event loop (a future async tool), the sync API raises; guarded by the tool being a plain `def` and by a test that calls the tool through `fastmcp.Client`. A browser crash raises inside the process; wrapped into a `RenderError`.

**Approach B: the same Playwright code in a child process (`python -m mcp_htmleditor.render_worker`), JSON over pipes.**
- Pros: a crashing or hanging browser cannot take the MCP server down; a hard kill on timeout.
- Cons: a second protocol (request and result JSON, PNG as base64), 0.3 s more per call, process management, and no failure mode seen so far that needs it (the driver already runs as its own node process and the browser as another). Rejected; revisit if a hang is observed (Section 7).

**Approach C: Chrome headless command line (`--screenshot`, `--dump-dom`) with no Python dependency.**
- Pros: no extra, works with any installed Chrome.
- Cons: one process per slide (40 launches for E2E-023); no page error event, so FR-NEW-003 `script` is impossible; measures would have to be smuggled out through the DOM dump; the binary path differs per OS (`skill/types/slides.md` hardcodes the macOS one); no managed install, so `make install-browser` has nothing to install. Rejected.

### 2.2 How the measures are taken

**Approach A: script evaluated in the page (chosen).** The spec defines every measure in DOM terms (scroll height, computed `overflow-y`, bounding box tops, computed font family, `img` load state), so the definitions are transcribed one to one in two constants of `render/scripts.py` and the Python side only formats. Pure Python functions (`problems.py`) turn raw measures into lines, so ordering, plural and messages are unit tested with no browser.
**Approach B: Chrome DevTools Protocol calls** (`DOM.getBoxModel`, `CSS.getPlatformFontsForNode`). More round trips (one per element) and the font call reports the font used, not whether the family is installed. Rejected.

### 2.3 Where the logic lives

**Approach A: `render/` service package called by thin `cli.py` and `mcp_server.py` (chosen).** `cli.py` and `mcp_server.py` are excluded from coverage (`pyproject.toml:167-171`), so logic there would be untested by the gate. One implementation gives FR-NEW-005 by construction.
**Approach B: the tool calls the command, or the command calls the tool.** Imports the protocol layer into the CLI or the reverse. Rejected (same reasoning as SPEC-0007 DEC-009).

## 3. Architecture

```
 agent --stdio--> mcp_server.render(...) --+            user / agent shell
                  (ToolError(msg))         |                 |
                                           v                 v
                                     render.service.render_deck()  <---- cli.py render command
                                           |                          (echo, "error: msg", exit 1/2)
        check order (FR-NEW-001)           |
   conflict -> scale -> file -> presentation -> browser -> slide id
        options.py       deck.load_deck   service.py (session)
                                           |
              +----------------------------+------------------------------+
              v                            v                              v
   render/scripts.py            render/problems.py                render/files.py
   SHOW_SLIDE_JS                build_problems(raw) -> list       picture_path(), write_picture()
   MEASURE_SLIDE_JS             sort, lines, final line,          remove_stale()   (atomic_write
   IMAGES_JS                    result_to_dict                     from SPEC-0007 fileio)
              |
   Playwright (optional extra) -> Chromium headless
        one context 1280x900, device scale = scale, light scheme
        page.goto(file://...) once; page.on("pageerror")
        per slide: evaluate SHOW, evaluate MEASURE (report), page.screenshot(clip) (picture)
```

Module responsibilities and rules:
- `render/__init__.py`: `RenderError(DeckError)`, `RenderUsageError(RenderError)`, frozen value objects `RenderProblem`, `RenderResult`, and the constants `DEFAULT_SCALE`, `CANVAS_WIDTH`, `CANVAS_HEIGHT` (STORY-B renders at the fixed default scale, so its size is `960 x 0.5` by `540 x 0.5` from these constants; STORY-C generalizes with `options.output_size`). It imports nothing heavy: importing `mcp_htmleditor.render` must not import `playwright`, `PIL` or `pptx` (test in STORY-B).
- `render/options.py`: `parse_scale`, `output_size`, `check_options` (pure, no I/O).
- `render/files.py`: output directory, file names, write, stale cleanup.
- `render/scripts.py`: the three JavaScript constants (a Python module because the wheel includes only `*.py` and `static/**`, `pyproject.toml:43-46`; the static directory is served by the editor, so a measure script does not belong there, and it is not checked by `node --check`: the E2E tests execute it).
- `render/problems.py`: raw measures to `RenderProblem`, ordering, report lines, final line, JSON dict. Pure.
- `render/service.py`: `render_deck` and the private browser session; the only module that imports Playwright, lazily inside the function (so `import mcp_htmleditor.render` works without the extra).
- Slide discovery and the presentation test reuse `deck.load_deck` (SPEC-0007); `file not found` and `not valid UTF-8` therefore have the same text as the editing commands.

## 4. Data model

All JSON compact (`separators=(",",":")`, `ensure_ascii=False`, SPEC-0007 DEC-015), keys in the order shown.

```json
// tool result and --json (picture)
{"ok":true,"path":"/tmp/htmleditor-render/deck-slide-1.png","width":480,"height":270,"problems":[]}
// report only
{"ok":true,"path":null,"width":null,"height":null,"problems":[{"kind":"overflow","slide":"slide-4","message":"content is 1184px tall, the slide is 540px"}]}
```
`ok` is always true in a returned object (errors never produce an object, FR-NEW-005); the exit status carries the verdict.

Raw measure returned by `MEASURE_SLIDE_JS(index)` (one slide), and raw load facts, before formatting:
```json
{"content":1184,"clipped":["div.probe"],"fonts":["NoSuchFont"]}
[{"slide_index":6,"src":"pics/missing.png"}]                 // IMAGES_JS, whole page, once
```
Python records (frozen, `slots=True`): `RenderProblem(kind, slide, message)` with `slide` equal to `"-"` for page wide problems; `RenderResult(path: Path | None, width: int | None, height: int | None, slide: str | None, problems: tuple[RenderProblem, ...])`; `SlideRef(index, slide_id)`; `RawSlide(slide, content, clipped, fonts)`; `ScriptError(slide, text)`.

Rules fixed by this design where the spec leaves room (all recorded in Section 10):
- Slides are `[data-type="slide"]` of the parsed file, in document order. Id of the slide at index `i` is `slide_id(tag)` of SPEC-0007 (`data-id`, else `id`) else `slide-<i>`, the same ids `outline` shows (DEC-006).
- File name of a picture: `<stem>-<safe id>.png` where `safe id` replaces `/`, `\` and NUL by `_` (a slide id must not leave the directory) (DEC-016).
- Script error lines are deduplicated per (slide, text); a data address is shortened only when longer than 40 characters.

## 5. Contracts and interfaces

### 5.1 Command (Click)

```
mcp-htmleditor render FILE [--slide ID] [--scale N] [--report] [--report-only] [--json]
```

| Parameter | Click declaration | Notes |
|---|---|---|
| `FILE` | `click.Path(dir_okay=False)` without `exists=True` | click's own existence check would give status 2 and another text (as SPEC-0007 5.1) |
| `--slide` | `str`, default `None` | |
| `--scale` | `str`, default `None` (meaning "not given", effective 0.5) | read as text so `abc`, `nan`, `inf` reach the spec message with status 1; a `float` option would give usage error 2 |
| `--report`, `--report-only`, `--json` | flags | |

`render_cmd` is wrapped by `deck_command` (catches `DeckError`, prints `error: <message>` on stderr, nothing on stdout, status 1). A `RenderUsageError` is caught inside the body first: prints `Error: <message>` (no usage block, which `click.UsageError` would add) and exits 2.

Check order, first failure alone is reported (FR-NEW-001), implemented as the order of calls in `render_deck`:

| # | Check | Message (stderr) | Status |
|---|---|---|---|
| 1 | `--report-only` with `--slide`, `--scale` or `--report` | `Error: --report-only cannot be used with --slide, --scale or --report` | 2 |
| 2 | scale not a finite decimal in [0.1, 1] | `error: Scale must be between 0.1 and 1` | 1 |
| 3 | file missing | `error: File not found: <file>` | 1 |
| 4 | not a presentation (document, mail, website, or no `data-type="slide"`) | `error: render needs a presentation: <file>` | 1 |
| 5 | Chromium or the `playwright` package missing | `error: Rendering needs Chromium. Install it with: make install-browser` | 1 |
| 6 | `--slide` not among the ids | `error: Unknown slide id "slide-9". Valid ids: slide-0, slide-1, ...` | 1 |

Because check 5 precedes check 6, the browser is launched before the slide id is validated (the spec fixes this order).

Output, standard output, in this order (no `Rendered`/`report` line with `--json`):
1. unless `--report-only`: `Rendered <slide> to <path> (<w>x<h>)`;
2. with `--report` or `--report-only`: one `<kind> <slide>: <message>` line per problem, then `report: OK`, `report: 1 problem` or `report: N problems`;
3. with `--json`: only `json.dumps(result_to_dict(result))`.
Exit status 1 when at least one problem was collected (only possible with `--report` or `--report-only`), else 0.

### 5.2 Tool (`mcp_server.py`, wrapped in `trace_span("mcp.render")`, errors as `ToolError(str(exc))`)

```python
@mcp.tool()
def render(file: str, slide: str | None = None, scale: float = 0.5,
           report: bool = False, report_only: bool = False) -> dict[str, Any]
```
It calls `render_deck(file, slide=slide, scale=None if scale == DEFAULT_SCALE else scale, ...)`: "a `scale` other than the default" is the conflict signal. A tool error message is the command line message without `error: ` (and without `Error: ` for the conflict, E2E-028). The story that registers the tool adds the line `- render: <description>` to the `## Tools` section of `skill/core.md` (SPEC-0006 contract), so `skill-audit` stays green. The tool count is whatever the core lists when this story lands; the audit compares names, not a number.

### 5.3 Function signatures

```python
# render/__init__.py
class RenderError(DeckError): ...
class RenderUsageError(RenderError): ...
@dataclass(frozen=True, slots=True) class RenderProblem: kind: str; slide: str; message: str
@dataclass(frozen=True, slots=True) class RenderResult: ...      # Section 4
DEFAULT_SCALE: Final = 0.5
CANVAS_WIDTH: Final = 960
CANVAS_HEIGHT: Final = 540

# render/options.py
def check_options(*, slide: str | None, scale: str | float | None, report: bool, report_only: bool) -> None   # RenderUsageError
def parse_scale(raw: str | float | None) -> Decimal                  # RenderError("Scale must be between 0.1 and 1")
def output_size(scale: Decimal) -> tuple[int, int]                   # ROUND_HALF_UP of 960*s and 540*s

# render/files.py
def render_dir() -> Path                                  # <tempfile.gettempdir()>/htmleditor-render
def picture_path(file: str, slide_id: str) -> Path
def write_picture(path: Path, data: bytes) -> None        # mkdir, fileio.atomic_write
def remove_stale(file: str, slide_ids: Sequence[str], keep: Path) -> int   # span render.cleanup

# render/problems.py
KIND_ORDER: Final = ("script", "image", "font", "overflow", "clipped")
def build_problems(slides: Sequence[RawSlide], images: Sequence[ImageFailure], errors: Sequence[ScriptError]) -> list[RenderProblem]
def format_line(problem: RenderProblem) -> str                 # "<kind> <slide>: <message>"
def final_line(count: int) -> str                              # "report: OK" | "report: 1 problem" | "report: N problems"
def result_to_dict(result: RenderResult) -> dict[str, Any]
def shorten_source(src: str) -> str                            # data address: first 40 characters + "..."

# render/service.py
def render_deck(file: str, *, slide: str | None = None, scale: str | float | None = None,
                report: bool = False, report_only: bool = False) -> RenderResult
```
`render_deck` pseudo flow: `check_options` -> `parse_scale` -> `load_deck(file)` -> `list_slides(deck)` (refuses a non presentation) -> `with trace_span("render.session", ...)` open Chromium (lazy import, `RenderError` message 5) -> choose the slide (message 6) -> `goto` once -> for picture: show slide, `page.screenshot(clip={x: round(box.x), y: round(box.y), width: 960, height: 540}, animations="disabled")`, check PNG size equals `output_size`, `write_picture`, `remove_stale` -> for report: images once, then show and measure the slides in scope (the target slide, or all) -> `build_problems` filtered to the scope.

Scope with `--report`: problems of the rendered slide, plus `script` problems whose slide is `-`; other slides' problems are neither listed nor counted. With `--report-only`: everything.

### 5.4 Exact messages

All strings of the spec Sections 6 and 9 verbatim. Additions where the spec is silent (DEC-020): `Chromium could not start: <reason>`; `Rendering failed: <reason>` (page load timeout or driver error while working); `Rendering failed: picture is <w>x<h>, expected <w>x<h>`. `<reason>` is the first line of the driver message, at most 200 characters. These three use the `RenderError` path (`error: ...`, status 1; tool: `ToolError`).

Browser measures (definitions transcribed from FR-NEW-003, `render/scripts.py`):
- show: `s.classList.toggle('active', i === idx)` for every `[data-type="slide"]`; non target slides get `style.setProperty('display','none','important')`; if the target is still `display:none` computed, `style.display = 'block'`; `document.getAnimations()` finished; two animation frames awaited. Nothing is written to the file; the page is discarded.
- content height: `max(slide.scrollHeight, top(d) - top(slide) + d.scrollHeight)` over rendered descendants `d` with computed `overflow-y` in `hidden`, `clip`, `auto`; rounded once with `Math.round`.
- clipped: rendered element (`getClientRects().length > 0`, not `display:none`), size not 0 x 0, not inside an already reported element, with `left < frame.left - 1`, `right > frame.right + 1`, `top < frame.top - 1`, or (`content <= 540` and `bottom > frame.bottom + 1`); selector = lower case tag plus `.` plus classes in attribute order.
- fonts: for each distinct computed `font-family` of elements with a direct text node, the non generic names (`sans-serif`, `serif`, `monospace`, `system-ui` ignored); reported when none is installed, naming the first.

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `pyproject.toml` | edit: extra `render`, ruff per file ignore `PLC0415` for `render/service.py` | FR-NEW-001 | STORY-A |
| `uv.lock` | regenerate (`uv lock`, generated) | FR-NEW-001 | STORY-A |
| `Makefile` | edit: target `install-browser`, `install` uses `.[render]`, `.PHONY`, `help` | FR-NEW-001 | STORY-A |
| `tests/render_support.py` | create: `needs_chromium`, deck builders, defect injectors, `big_deck`, PNG helpers | all E2E | STORY-A |
| `tests/test_render_install.py` | create | FR-NEW-001 | STORY-A |
| `src/mcp_htmleditor/render/__init__.py` | create | FR-NEW-001 | STORY-B |
| `src/mcp_htmleditor/render/service.py` | create / edit | FR-NEW-001..004, 007 | STORY-B, C, D, E, F |
| `src/mcp_htmleditor/render/files.py` | create | FR-NEW-001 | STORY-B |
| `src/mcp_htmleditor/render/options.py` | create / edit | FR-NEW-002, 004 | STORY-C, E |
| `src/mcp_htmleditor/render/scripts.py` | create / edit | FR-NEW-003 | STORY-D, F |
| `src/mcp_htmleditor/render/problems.py` | create / edit | FR-NEW-003, 005 | STORY-D, F, G |
| `src/mcp_htmleditor/cli.py` | edit: `render` command | FR-NEW-001..005 | B, C, D, E, G |
| `src/mcp_htmleditor/mcp_server.py` | edit: tool `render` | FR-NEW-005 | STORY-G |
| `skill/core.md` (SPEC-0006 core, section `## Tools`) | edit | SPEC-0006 FR-NEW-008 | STORY-G |
| `tests/test_render_picture.py` | create | FR-NEW-001, 006 | STORY-B |
| `tests/test_render_options.py` | create | FR-NEW-002 | STORY-C |
| `tests/test_render_report.py` | create | FR-NEW-003, 006 | STORY-D |
| `tests/test_render_report_only.py` | create | FR-NEW-003, 004 | STORY-E |
| `tests/test_render_signals.py` | create | FR-NEW-003, 004 | STORY-F |
| `tests/test_render_tool.py` | create | FR-NEW-001, 005, 006 | STORY-G |
| `tests/test_render_scale.py` | create | FR-NEW-003, 004, 007 | STORY-H |
| `.agent_docs/render.md` | create / edit (picture rules, measure definitions, fixtures, install) | FR-NEW-001, 003 | STORY-C, F |
| `.agent_docs/testing.md` | edit: test file map rows | all | STORY-E |
| `.agent_docs/observability.md` | edit: spans `render.session`, `render.cleanup`, `mcp.render` | FR-NEW-001 | STORY-H |
| `.agent_docs/makefile.md` | edit: `install-browser` row | FR-NEW-001 | STORY-H |
| `README.md` | edit: usage of `render`, install of the extra and Chromium | all | STORY-H |
| `AGENTS.md` | edit: commands, index row for `.agent_docs/render.md` | all | STORY-H |

Affected existing tests: none edited. `tests/test_skill_content.py` and the SPEC-0006 audit tests keep passing: the story that registers `render` adds its line to `## Tools` in the same change. `tests/test_templates.py` unaffected. The three existing browser test files (`test_fullscreen_e2e.py`, `test_tab_title_e2e.py`, `test_autosave_focus_e2e.py`) each define their own `needs_chromium`; they are left alone (not in scope), `tests/render_support.py` carries a fourth copy of the pattern and the duplication is reported as a backlog finding.

Documentation: `README.md` (usage, optional extra, `make install-browser`, report kinds), `AGENTS.md` (commands, index), `.agent_docs/render.md` (new topic file), `.agent_docs/testing.md`, `.agent_docs/observability.md`, `.agent_docs/makefile.md`. Not touched: `skill/` topics (SPEC-0006 owns the skill text; no topic yet tells the agent to run `render` for the mandatory visual check, reported as backlog), `Dockerfile` (the image ships no browser; `render` answers the install message there, documented in `README.md`), `.env.example` and `config/config.yaml` (no setting added).

`make install-browser` target (added by STORY-A):
```
install-browser:   # needs the render extra
	TOOL_PY="$(uv tool dir)/mcp-htmleditor/bin/python"
	if [ -x "$TOOL_PY" ]; then "$TOOL_PY" -m playwright install chromium
	else uv run --extra render python -m playwright install chromium; fi
```
The first branch installs the Chromium revision of the Playwright that the installed `mcp-htmleditor` actually imports (revisions are tied to the Playwright version, and `uv tool install .` does not read `uv.lock`); the second serves a working tree. `make install` runs `uv tool install ".[render]"`. pyproject extra: `render = ["playwright>=1.62,<2"]`.

## 7. Compatibility and risks

| Risk | Detection | Handling |
|---|---|---|
| `playwright` package absent (the extra is not installed) | E2E-011 variant: `sys.modules["playwright.sync_api"] = None` makes the import raise `ImportError` | same message as a missing browser (DEC-003); `make install-browser` run from the repo installs the extra in the project environment, and `make install` includes it |
| Chromium missing | E2E-011: `PLAYWRIGHT_BROWSERS_PATH` pointed at an empty directory makes `launch()` raise `Executable doesn't exist` (measured) | message of FR-NEW-001; any other launch error becomes `Chromium could not start: ...` |
| `executable_path` points at the full Chromium, while headless launches the headless shell | measured: with an empty cache `executable_path` is `chromium-1234/...` and `launch()` complains about `chromium_headless_shell-1234` | detection by catching the launch error, never by testing a path |
| Picture size off by one pixel at fractional scales | `locator.screenshot` gave 481 x 270 at scale 0.5 when the element sat on a fractional offset (measured); `page.screenshot(clip=...)` with an integer origin gave the exact size on 12 scales including the half cases 0.125 and 0.625 | clip with `round(box.x)`, `round(box.y)`, 960 x 540; the PNG header is checked against `output_size`, mismatch is a `RenderError` (DEC-009) |
| Deck whose slide is not 960 x 540 (legacy Carbon files measure 900 wide, `example-carbon-complete.html`) or whose slides use another show mechanism | measured on the reference decks | the clip is 960 x 540 from the slide origin as the spec says; the show step falls back to `display:block`; documented in `.agent_docs/render.md` |
| Font rule false report for lists made only of system aliases (`-apple-system, sans-serif`) | measured: `-apple-system` is not an installed family for the canvas test | spec literal (only four names are ignored); the Carbon bootstrap reports `"IBM Plex Sans" is not available` on a machine without it, which is true and useful |
| Test machine fonts | the spec assumes Segoe UI or Calibri; the EI font stack ends with Arial (`templates/bootstrap/slides-ei-empty.html:31`) and the medical stack with Arial, so a machine with Arial passes; a bare container may not | `needs_chromium` tests assert the font facts on a deck whose family is Arial; E2E-015 uses a family that cannot exist |
| Generated fixture `build_deck` (SPEC-0007) is not layout clean under the real measure | E2E-004 (clean report only) fails | the slide templates of `deck_support.py` are adjusted by the implementer of STORY-E; the measure is not weakened |
| A hung page (remote image on a blackholed network) | `LOAD_TIMEOUT_MS` (15 s) raises `Rendering failed: ...` | the file is local in normal use; remote images are not blocked so that an unreachable image is reported as `image` |
| Two renders of the same file at once write the same picture | `atomic_write` replaces atomically | last writer wins, the file is never torn |
| Playwright inside a running event loop | the tool is a plain `def`; E2E-005 and the in process tool tests call it through a `fastmcp.Client` | none needed |
| Coverage with no Chromium installed | `make test-cov` | pure modules (`options`, `problems`, `files`) are tested without a browser; `make sync` installs Chromium for the project |

Public contracts: one added command, one added tool, one added make target, one optional extra. No removal, no change to an existing command.

## 8. Security

Not applicable (`Security: n/a`). The only boundary rule is functional: a slide id never leaves the output directory (DEC-016).

## 9. Test strategy

Levels: **E2E** drives the Click command with `run_cli` (SPEC-0007 `tests/deck_support.py`, separate stdout and stderr) or the tool through `call_tool` (in process `fastmcp.Client`); two tests use a real subprocess (stdout purity: E2E-005 over a stdio MCP client, E2E-006 over `python -m mcp_htmleditor`); **Integration** calls `render_deck` on files in `tmp_path`; **Unit** tests a pure function. Playwright tests are skipped with the project pattern (`needs_chromium = pytest.mark.skipif(not any(cache_dir.glob("chromium-*")), ...)`, `tests/test_tab_title_e2e.py:29-40`) defined once in `tests/render_support.py`. No `sleep`; elapsed time asserted with `time.monotonic()` for the speed tests only.

Seams and generators (all in `tests/render_support.py`, built from the SPEC-0007 `build_deck`, `deck_med`, `doc_perso`, never from `~/.config`, never committed):
- Browser missing seam (E2E-011): no production seam. The test sets `PLAYWRIGHT_BROWSERS_PATH` to an empty `tmp_path` with `monkeypatch.setenv`; the Playwright driver inherits it and `launch()` fails exactly as on a machine without the browser. This test does not need `needs_chromium`. Extra unit: `sys.modules["playwright.sync_api"] = None` for the missing package.
- Output directory: `monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))` so `htmleditor-render` lands in `tmp_path`.
- DECK-EI: `build_deck("ei", EI_TITLES)` with 8 titles and no big image (the 1 500 character image of `deck_ei()` is not a valid PNG, which would be a legitimate `image` problem). DECK-MED: `deck_med()` with the article of `slide-2` changed to `class="slide dark"`. DOC-PERSO: `doc_perso()`.
- Defect injectors, pure string functions: `inject_in_body(html, slide_id, snippet)` (first child of `.slide-body`), `append_to_slide(html, slide_id, snippet)` (after the inner frame, before `</article>`), `set_slide_class(html, slide_id, cls)`, `add_script(html, js)`, `add_inline_style(html, selector_marker, style)`.
- 40-slide generator (E2E-023, 027, 029): `big_deck(tmp_path, count=40, with_images=False)` calls `build_deck("ei", [f"Slide {i}" for i in range(count)])`; with images each slide gets `<img src="data:image/png;base64,...">` of a valid 1 x 1 PNG built with `zlib` and `struct`, plus a file based `<img src="pics/ok.png">` for half of them so both load paths run.
- PNG helpers: `png_size(path)` reads the IHDR (no Pillow), `png_pixel(path, x, y)` uses Pillow (already installed through python-pptx).
- Dark pixel test (E2E-020): DECK-MED slide-2 at `--scale 1`, `png_pixel(path, 2, 300) == (0x0B, 0x0E, 0x11)`. Measured on `templates/reference/slides/medical.html` slide 5: `#0B0E11`.
- Determinism: viewport 1280 x 900, device scale equal to the scale, light colour scheme, animations finished before any measure and with `animations="disabled"` at capture; tests read files only through the product.

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| SPEC-0008/E2E-001 | E2E | CLI | `tests/test_render_picture.py` | STORY-B |
| SPEC-0008/E2E-002 | E2E | CLI | `tests/test_render_options.py` | STORY-C |
| SPEC-0008/E2E-003 | E2E | CLI | `tests/test_render_report.py` | STORY-D |
| SPEC-0008/E2E-004 | E2E | CLI | `tests/test_render_report_only.py` | STORY-E |
| SPEC-0008/E2E-005 | E2E | tool over a stdio client (subprocess) | `tests/test_render_tool.py` | STORY-G |
| SPEC-0008/E2E-006 | E2E | CLI in a subprocess | `tests/test_render_tool.py` | STORY-G |
| SPEC-0008/E2E-007 | E2E | CLI + tool | `tests/test_render_tool.py` | STORY-G |
| SPEC-0008/E2E-008 | E2E | CLI | `tests/test_render_options.py` | STORY-C |
| SPEC-0008/E2E-009 | E2E | CLI | `tests/test_render_options.py` | STORY-C |
| SPEC-0008/E2E-010 | E2E | CLI | `tests/test_render_report_only.py` | STORY-E |
| SPEC-0008/E2E-011 | E2E | CLI + tool (browser path redirected) | `tests/test_render_tool.py` | STORY-G |
| SPEC-0008/E2E-012 | E2E | CLI | `tests/test_render_report_only.py` | STORY-E |
| SPEC-0008/E2E-013 | E2E | CLI | `tests/test_render_report.py` | STORY-D |
| SPEC-0008/E2E-014 | E2E | CLI | `tests/test_render_report.py` | STORY-D |
| SPEC-0008/E2E-015 | E2E | CLI | `tests/test_render_signals.py` | STORY-F |
| SPEC-0008/E2E-016 | E2E | CLI | `tests/test_render_signals.py` | STORY-F |
| SPEC-0008/E2E-017 | E2E | CLI | `tests/test_render_signals.py` | STORY-F |
| SPEC-0008/E2E-018 | E2E | CLI | `tests/test_render_report_only.py` | STORY-E |
| SPEC-0008/E2E-019 | E2E | CLI | `tests/test_render_signals.py` | STORY-F |
| SPEC-0008/E2E-020 | E2E | CLI + pixel read | `tests/test_render_options.py` | STORY-C |
| SPEC-0008/E2E-021 | E2E | CLI | `tests/test_render_options.py` | STORY-C |
| SPEC-0008/E2E-022 | E2E | CLI | `tests/test_render_picture.py` | STORY-B |
| SPEC-0008/E2E-023 | E2E | CLI, 40 slides | `tests/test_render_scale.py` | STORY-H |
| SPEC-0008/E2E-024 | E2E | CLI | `tests/test_render_report.py` | STORY-D |
| SPEC-0008/E2E-025 | E2E | tool + running server | `tests/test_render_tool.py` | STORY-G |
| SPEC-0008/E2E-026 | E2E | CLI in process | `tests/test_render_tool.py` | STORY-G |
| SPEC-0008/E2E-027 | E2E | CLI, 40 slides | `tests/test_render_scale.py` | STORY-H |
| SPEC-0008/E2E-028 | E2E | CLI + tool | `tests/test_render_tool.py` | STORY-G |
| SPEC-0008/E2E-029 | E2E | CLI, 40 slides with images | `tests/test_render_scale.py` | STORY-H |

29 E2E tests, each exactly once. Placement notes: E2E-021 renders two different slides, so it needs `--slide` and sits with STORY-C (the cleanup code itself is STORY-B and is unit tested there); E2E-007 and E2E-011 hold a command part and a tool part, so they sit with the tool; E2E-010 and E2E-012 use `--report-only`, so they sit with it; E2E-019 needs the font and image kinds on top of overflow, so it closes STORY-F; E2E-025 needs a running editor server (`start_http_server`, as `tests/test_autosave_focus_e2e.py`) and the SPEC-0009 `get_status` (`update_expires_in` added there is compared field by field).

Non E2E tests (integration and unit, listed per story in Section 11): `parse_scale` table (`0.1`, `1`, `.5`, `1e-1`, ` 0.5 `, `0.09`, `1.01`, `0`, `-1`, ``, `abc`, `nan`, `inf`, `-inf`), `output_size` half up table (0.125 gives 120 x 68, 0.5 gives 480 x 270, 0.1 gives 96 x 54), file name sanitizing, stale cleanup (own pictures only, a name that merely starts alike untouched, errors delete nothing), problem ordering and plural table, shortened data address, import purity (`playwright` not in `sys.modules` after importing `mcp_htmleditor.render`), the check order table (conflict beats bad scale beats missing file beats document beats missing browser beats unknown slide), `make -n` checks of the install targets, the extra declared in `pyproject.toml` and `uv.lock`.

## 10. Decisions log

- **DEC-001:** Playwright sync API, one session per call, in the calling thread; the tool is a plain `def`. **Obliged by:** SPEC-0008/FR-NEW-001, 003, 005. **Rationale:** the page events and DOM measures of FR-NEW-003 come from one page load; the same function serves the command and the tool; fastmcp runs a plain `def` tool in a worker thread without an event loop, which the sync API needs. **Alternatives considered:** child process worker (extra protocol, no failure seen that needs it), headless Chrome command line (no page errors, 40 launches for 40 slides), async API (the project is synchronous). **Source:** design. **Evidence:** measured on fastmcp 3.4.6 + Playwright 1.62.0: a `def` tool reports no running loop on thread `AnyIO worker thread`, and two concurrent in process tool calls both returned (`asyncio.gather`); `src/mcp_htmleditor/mcp_server.py:31-32` (plain `def` tools); `.agent_docs/python.md` deviations table.
- **DEC-002 (NEEDS DECISION, default applied: optional extra named `render`):** Playwright is declared as `[project.optional-dependencies] render = ["playwright>=1.62,<2"]`; the lock keeps 1.62.0 through the dev group. **Obliged by:** SPEC-0008/FR-NEW-001 and Section 3.3 (the product must keep working without a browser). **Rationale:** a heavy dependency stays opt in; the floor is the version measured here (PyPI latest 1.64.1 on 2026-11-03, the API used is unchanged since 1.x: `sync_playwright`, `page.on("pageerror")`, `page.screenshot(clip, animations)`). **Alternatives considered:** a core dependency (installs a 100 MB class driver for everyone), a dev only dependency (the status quo, the product cannot render once installed). **Source:** spec 14.3 design input. **Evidence:** `pyproject.toml:35` (dev group), `uv.lock:1411-1412`, context7 `/websites/playwright_dev_python`.
- **DEC-003:** A missing browser and a missing `playwright` package give the same message `Rendering needs Chromium. Install it with: make install-browser`. Missing browser is detected by catching the launch error whose text contains `Executable doesn't exist`, missing package by `ImportError`. **Obliged by:** SPEC-0008/FR-NEW-001. **Rationale:** both are fixed by `make install-browser` run from the repo (it installs the extra then the browser); no path test is reliable. **Alternatives considered:** testing `chromium.executable_path` (it points at the full Chromium while headless launches the headless shell, so it misreports a shell only install). **Source:** design. **Evidence:** measured with `PLAYWRIGHT_BROWSERS_PATH=/tmp/pp/empty`: `executable_path` is `.../chromium-1234/...` and `launch()` raises `playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist at .../chromium_headless_shell-1234/...`; `sys.modules[...] = None` raises `ImportError`.
- **DEC-004:** The browser-missing test needs no production seam: it redirects `PLAYWRIGHT_BROWSERS_PATH` to an empty directory. **Obliged by:** SPEC-0008/FR-NEW-001 (E2E-011). **Rationale:** reproduces the real failure; a patched flag would pass while the real detection is wrong. **Alternatives considered:** a `Settings` field forcing "no browser" (a test only branch in product code). **Source:** design. **Evidence:** same measurement as DEC-003.
- **DEC-005:** `render_deck` performs the checks in the spec order, which launches the browser before validating `--slide`. **Obliged by:** SPEC-0008/FR-NEW-001. **Rationale:** the spec lists "browser missing" before "unknown slide id" (first failure alone is reported). **Alternatives considered:** validate the id from the parsed file first (cheaper, but wrong when both fail). **Source:** spec constraint. **Evidence:** spec FR-NEW-001 business rules.
- **DEC-006:** Slides are the `[data-type="slide"]` elements of the BeautifulSoup tree that `deck.load_deck` already parsed; the file is a presentation when `doc_type == "presentation"` and there is at least one such element; the id of slide `i` is `slide_id(tag)` (SPEC-0007: `data-id`, else `id`) else `slide-<i>`. **Obliged by:** SPEC-0008/FR-NEW-001, 002. **Rationale:** `outline` shows the same ids, so an agent can pass them to `--slide`; the same parse also gives `File not found` and the UTF 8 check. **Alternatives considered:** `find_slides` of the exporter (accepts `article.slide` without `data-type`, which the spec refuses as "no slide"), a regex scan (comments, scripts). **Source:** spec constraint plus SPEC-0007. **Evidence:** `src/mcp_htmleditor/export/to_pptx.py:272-282` (fallback to `article.slide`), `sdlc/stories/US-0035-outline-on-the-command-line.md` (`slide_id`, `load_deck`).
- **DEC-007:** Showing one slide alone is done in the live page: toggle `active` on every `[data-type="slide"]`, hide the others with an inline `display:none !important`, fall back to `display:block` on the target when it is still hidden, finish all animations. The file is never written. **Obliged by:** SPEC-0008/FR-NEW-001 ("the slide's own markup and styles are not altered, except that only the target slide is displayed"). **Rationale:** the shipped templates show a slide through `.slide.active` (`display:block` or `flex`), third party decks differ; the fallback covers them; finishing animations removes the entrance translate so tops are stable. **Alternatives considered:** call the deck's own `goToSlide` (not generic), rewrite the HTML (changes the page). **Source:** spec 14.3. **Evidence:** `templates/bootstrap/slides-ei-empty.html:79-88` (`.slide {display:none; ... animation:fadein 200ms}`, `.slide.active {display:block}`), `templates/bootstrap/slides-medical-empty.html:94-100` (`display:flex`); measured tops drift (207.6 to 208) while the entrance animation runs.
- **DEC-008:** One context with viewport 1280 x 900, `device_scale_factor` equal to the scale, light colour scheme; the picture is `page.screenshot(clip={x: round(box.x), y: round(box.y), width: 960, height: 540}, animations="disabled")`. **Obliged by:** SPEC-0008/FR-NEW-001, 002 (exact size) and 14.3 (deterministic measures). **Rationale:** `.slide` is `width:100%; max-width:960px` inside a padded frame, so the viewport must give it 960 x 540 (measured at 1280 wide: box 960 x 540 at x 160); an integer clip gives the exact size. **Alternatives considered:** `locator.screenshot` (off by one when the element has a fractional offset), full page screenshot then crop (Pillow dependency in the product). **Source:** design. **Evidence:** measured on 12 scales (0.1 to 1, half cases 0.125, 0.375, 0.625, 0.875): `locator.screenshot` gave 481 x 270 at 0.5 and 600 vs 601 at 0.625 for an element at a 3.3 px offset; the integer clip gave the exact size every time; `templates/bootstrap/slides-ei-empty.html:76` (frame padding 28 px).
- **DEC-009:** The expected size is computed with `Decimal` and `ROUND_HALF_UP` from the text of the scale, and the PNG header read after capture must equal it, otherwise `Rendering failed: picture is <w>x<h>, expected <w>x<h>`. **Obliged by:** SPEC-0008/FR-NEW-001, 002 ("sizes are rounded half up"). **Rationale:** a float `round` is banker's rounding (68 for 67.5 happens to match, 2.5 would not) and the printed size must be the real size of the file. **Alternatives considered:** trust the browser. **Source:** spec constraint. **Evidence:** measured agreement on 12 scales; Python `round(0.5)` is 0.
- **DEC-010:** The layout measures are the spec definitions transcribed as page script (`SHOW_SLIDE_JS`, `MEASURE_SLIDE_JS`, `IMAGES_JS`), evaluated per slide; `problems.py` only formats and orders. **Obliged by:** SPEC-0008/FR-NEW-003. **Rationale:** the definitions are DOM facts; formatting is pure and unit testable. **Alternatives considered:** DevTools protocol per element. **Source:** spec constraint. **Evidence:** measured on the amended definition: EI reference slide with a `height:700px` block as first child of `.slide-body` gives content 1184 (at least 700, no `clipped`), the same block as direct child of the slide gives 700, a probe `position:absolute; left:940px` gives `div.probe`, `position:relative; left:920px` on the page number gives `span.slide-foot-page`; all 9 slides of `example-ei-complete.html`, `euro-information.html`, `medical.html`, `example-medical-complete.html` and the three bootstraps of EI and medical give no problem, so the measure has no false positive on shipped charters.
- **DEC-011:** A font family list is reported when none of its non generic names is installed; "installed" means the width of a probe text drawn with `<name>, <base>` differs from the width with `<base>` alone for at least one of `monospace`, `serif`, `sans-serif`, after `document.fonts.load` for that name. The first non generic name is the one printed. **Obliged by:** SPEC-0008/FR-NEW-003. **Rationale:** `document.fonts.check` answers true for a family that does not exist, so it cannot be used; testing against three bases avoids a false "missing" for a font whose metrics equal the default of one base. **Alternatives considered:** `fonts.check` (measured useless), `CSS.getPlatformFontsForNode` (gives the font used, not availability). **Source:** design. **Evidence:** measured: `document.fonts.check('12px NoSuchFont')` returned `true`; the canvas test gave not installed for `NoSuchFont`, installed for `Georgia`, `Helvetica`, `Times New Roman` and for the full EI stack (through Arial), not installed for `'Segoe UI', Calibri` on this macOS.
- **DEC-012:** Script errors come from `page.on("pageerror")`, written `<name>: <message>`, attributed to the slide being displayed at that moment and to `-` before the first slide is shown (page load), identical (slide, text) pairs kept once. **Obliged by:** SPEC-0008/FR-NEW-003. **Rationale:** the event carries `name` and `message`; the marker is a variable set by the service around each show. **Alternatives considered:** parse `console` messages (not uncaught errors). **Source:** spec constraint. **Evidence:** measured: a `<script>throw new Error("boom")</script>` produced `('Error', 'boom')` before any slide was shown.
- **DEC-013:** An image failed when, after the `load` event, an `img` inside a slide has `complete` true and `naturalWidth` 0; the reported source is the `src` attribute as written; a data address longer than 40 characters is shortened to its first 40 characters plus `...`, a shorter one is printed as is. **Obliged by:** SPEC-0008/FR-NEW-003. **Rationale:** the check needs no network event and works for data addresses; `loading="lazy"` images of hidden slides are not started by the browser and are not flagged (they are not failures). **Alternatives considered:** `requestfailed` events (not fired for data addresses, URL absolute instead of as written). **Source:** spec constraint. **Evidence:** measured: `pics/missing.png` flagged, a data SVG with only a `viewBox` not flagged (`naturalWidth` non zero), `requestfailed` reported the absolute `file:///` URL.
- **DEC-014:** One page load per run. `--report` shows and measures the target slide only; `--report-only` shows and measures each slide in order; images are collected once for the whole page and filtered by scope. **Obliged by:** SPEC-0008/FR-NEW-003, 004, 007. **Rationale:** a 9 slide deck takes 0.24 s after launch, so 40 slides stay far below 30 s; one load keeps `-` script errors once per run. **Alternatives considered:** one page per slide (40 loads, repeated load errors). **Source:** spec constraint. **Evidence:** measured 0.24 s for load plus 9 slide analyses.
- **DEC-015:** Ordering is computed in `problems.py`: `-` first, then slide document order, then `KIND_ORDER`, then document order within a kind (a counter assigned at collection time). **Obliged by:** SPEC-0008/FR-NEW-003 (E2E-019). **Rationale:** deterministic and testable without a browser. **Alternatives considered:** order of discovery. **Source:** spec constraint.
- **DEC-016:** Pictures go to `<tempfile.gettempdir()>/htmleditor-render/<stem>-<id>.png`; `<id>` has `/`, `\` and NUL replaced by `_`; the file is written with `fileio.atomic_write` after `mkdir(parents=True, exist_ok=True)`; stale pictures are removed by enumerating the presentation's own slide ids (`<stem>-<id>.png` for each id) and unlinking each one that exists and is not the new picture, only after a successful render; an unlink failure is logged at warning level and ignored. **Obliged by:** SPEC-0008/FR-NEW-001. **Rationale:** enumeration instead of a glob keeps the file's own characters (`[`, `*`) harmless; the rename of an id character keeps a hostile `data-id` inside the directory; `atomic_write` leaves no half picture for a concurrent reader. **Alternatives considered:** glob `<stem>-*.png` (matches pictures of a file named `<stem>-slide-1.html`), `Path.write_bytes` (not atomic). **Source:** spec constraint plus design. **Evidence:** `sdlc/specs/SPEC-0007-agent-editing-tools/design.md` DEC-010 and `sdlc/specs/SPEC-0009-reliable-saves/design.md:133-134` (`atomic_write(path, data, *, reason=None)`, `reason=None` keeps the plain behaviour).
- **DEC-017:** The option conflict is detected in `check_options`, raised as `RenderUsageError`, and printed by the command as `Error: <message>` with exit status 2 by hand. `--scale` is a text option. **Obliged by:** SPEC-0008/FR-NEW-004, FR-NEW-002. **Rationale:** `click.UsageError` prints a usage block before `Error:`, and the spec wants the line alone; a `float` option would turn `abc` into status 2 instead of the scale message with status 1. **Alternatives considered:** `UsageError` (extra lines), `click.FloatRange` (wrong text and status). **Source:** spec constraint. **Evidence:** `src/mcp_htmleditor/cli.py:125,216,238` use `click.Path(exists=True)` (status 2, other text), which SPEC-0007 DEC-009 also avoids.
- **DEC-018:** The tool is `render(file, slide=None, scale=0.5, report=False, report_only=False)`; it passes `scale=None` to the service when it equals 0.5, so the conflict check sees "a scale other than the default"; errors become `ToolError(str(exc))` without the CLI prefixes. **Obliged by:** SPEC-0008/FR-NEW-005. **Rationale:** same checks, same order, same messages (E2E-028). **Alternatives considered:** `scale: str` in the tool (the spec signature has the default 0.5). **Source:** spec constraint.
- **DEC-019:** The result dict is built once by `result_to_dict` and used by `--json` and by the tool, compact with `ensure_ascii=False`. **Obliged by:** SPEC-0008/FR-NEW-005. **Rationale:** E2E-006 compares the command output with the tool object. **Alternatives considered:** two builders. **Source:** SPEC-0007 DEC-015.
- **DEC-020:** Failures the spec does not name get one `RenderError` each: `Chromium could not start: <reason>`, `Rendering failed: <reason>` (load timeout, driver error), `Rendering failed: picture is <w>x<h>, expected <w>x<h>`. **Obliged by:** SPEC-0008/FR-NEW-001. **Rationale:** every failure path ends in one `error:` line, never a traceback (same stance as SPEC-0007 DEC-016). **Alternatives considered:** let the Playwright exception escape. **Source:** design.
- **DEC-021:** `render_deck` never reads or writes the editor state, the history store or the input file: it opens the file read only through `load_deck` and the browser reads it through `file://`. **Obliged by:** SPEC-0008/FR-NEW-006. **Rationale:** `get_status` comes from the process state singleton, which render does not touch. **Alternatives considered:** none. **Source:** spec constraint. **Evidence:** `src/mcp_htmleditor/mcp_server.py:93-108` (`get_status` reads `get_state()`); E2E-024, E2E-025 check bytes, mtime and status.
- **DEC-022:** The three scripts live in `render/scripts.py` as Python string constants. **Obliged by:** SPEC-0008/FR-NEW-003. **Rationale:** the wheel includes `src/mcp_htmleditor/**/*.py` and `static/**` only, so a `.js` next to the package would be missing from an installed copy; `static/` is served to the editor. **Alternatives considered:** `static/render-measure.js` (served to the editor for nothing, and SPEC-0012 changes the order and serving tests of that directory), widening the wheel include. **Source:** design. **Evidence:** `pyproject.toml:43-46`.
- **DEC-023:** `make install` installs the tool with `.[render]` and `make install-browser` installs Chromium with the Python of the installed tool when it exists, else with `uv run --extra render`. **Obliged by:** SPEC-0008/FR-NEW-001 (the message names `make install-browser`). **Rationale:** the Chromium revision is tied to the Playwright version; `uv tool install .` ignores `uv.lock`, so a browser installed by the project environment may not match the tool. **Alternatives considered:** `uv run playwright install chromium` only (as `sync` does for tests, `Makefile:51`), a `mcp-htmleditor install-browser` subcommand (a second public command for a maintainer task). **Source:** design. **Evidence:** `Makefile:155-175` (`uv tool install . --reinstall --force`); `~/Library/Caches/ms-playwright` holds five chromium revisions (1223 to 1248) side by side, so revisions do diverge.
- **DEC-024:** Spans: `render.session` (INFO; attributes `render.mode` picture, report or report_only, `render.slides` count, `render.scale` text), `render.cleanup` (DEBUG; `file.count`), `mcp.render`. No path, selector, text or image data in an attribute. **Obliged by:** SPEC-0008/FR-NEW-001 (project tracing rule for external calls). **Rationale:** the browser is an external tool call; the picture write is already traced by `file.write` inside `atomic_write`. **Alternatives considered:** one span per slide (noise for 40 slides). **Source:** `.agent_docs/observability.md` rules.
- **DEC-025:** Pure modules are tested with no browser; browser tests are skipped without Chromium; `cli.py` and `mcp_server.py` stay in the coverage omit list. **Obliged by:** SPEC-0008/FR-NEW-007 and the 80 % gate. **Rationale:** the gate must not depend on a downloaded browser. **Alternatives considered:** omitting `render/service.py` from coverage (hides the one module with real behavior). **Source:** `.agent_docs/testing.md`. **Evidence:** `pyproject.toml:167-171`.
- **DEC-026:** Test decks come from `build_deck`/`deck_med`/`doc_perso` (SPEC-0007) plus string injectors; the 1 500 character image of `deck_ei()` is avoided; PNG data is generated with `zlib` and `struct`. **Obliged by:** SPEC-0008/E2E-001 to E2E-029 (fixtures DECK-EI, DECK-MED, DOC-PERSO, 40 slide decks). **Rationale:** no committed megabyte fixture, charters stay in step with the templates SPEC-0011 and SPEC-0012 regenerate, and a valid image is needed for a deck "without layout problem". **Alternatives considered:** committed golden decks, `example-ei-complete.html` as is (the SPEC-0007 design records out of palette colours there, irrelevant here, but it has 9 slides not 8). **Source:** design.

## 11. Stories

Slicing check: every story is a vertical increment that leaves `make check` green and is observable (a command, an option, a report kind, the tool, the 40 slide budget), keeps to 4 or 5 files (documentation files included), 1 to 3 requirements, 5 to 15 tests, and every E2E appears once. STORY-A has one requirement (partial) because the install step is the only part of FR-NEW-001 that exists before the command; STORY-B has two. STORY-H closes the spec.

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| STORY-A | Optional render extra, install-browser and fixtures | P1 | FR-NEW-001 | SPEC-0010 closing story | 2 | no |
| STORY-B | Render the first slide to a picture | P1 | FR-NEW-001, 006 | STORY-A, SPEC-0007 | 2 | no |
| STORY-C | Choose a slide and a scale | P1 | FR-NEW-002, 001 | STORY-B | 2 | no |
| STORY-D | Layout report for one slide | P1 | FR-NEW-003, 006 | STORY-C | 2 | no |
| STORY-E | Report only across the deck | P1 | FR-NEW-004, 003 | STORY-D | 2 | no |
| STORY-F | Font, script and image problems | P1 | FR-NEW-003, 004 | STORY-E | 2 | no |
| STORY-G | JSON output and the render tool | P1 | FR-NEW-005, 006, 001 | STORY-F, SPEC-0006, SPEC-0009 | 2 | no |
| STORY-H | Large decks and documentation | P2 | FR-NEW-007, 003, 004 | STORY-G | 2 | yes |

Files, tests and observable check per story:

- **STORY-A:** `pyproject.toml`, `uv.lock`, `Makefile`, `tests/render_support.py`, `tests/test_render_install.py`. Tests (no E2E): extra `render` declared with `playwright>=1.62,<2` (tomllib); `uv.lock` lists the extra; `make -n install-browser` shows both branches; `make -n install` shows `.[render]`; `make help` lists the target; the fixture builders (8 slide ids `slide-0`..`slide-7`, `inject_in_body` changes only the target slide, `big_deck(40)` has 40 slides, `set_slide_class` marks `dark`, generated PNG is valid with `png_size`). Check: `make install-browser` installs Chromium.
- **STORY-B:** `src/mcp_htmleditor/render/__init__.py`, `src/mcp_htmleditor/render/service.py`, `src/mcp_htmleditor/render/files.py`, `src/mcp_htmleditor/cli.py`, `tests/test_render_picture.py`. Tests: E2E-001, 022; integration for file not found, document refused, presentation with no `data-type="slide"` refused, mail and website refused, file bytes and mtime unchanged by a render, file name sanitizing, stale cleanup (errors delete nothing), import purity of `mcp_htmleditor.render`, writer is `atomic_write`. Check: `render DECK-EI` prints `Rendered slide-0 to ... (480x270)`.
- **STORY-C:** `src/mcp_htmleditor/render/options.py`, `src/mcp_htmleditor/render/service.py`, `src/mcp_htmleditor/cli.py`, `tests/test_render_options.py`, `.agent_docs/render.md`. Tests: E2E-002, 008, 009, 020, 021; `parse_scale` and `output_size` tables; check order (bad scale before missing file, missing browser before unknown slide); id fallback `slide-<i>`; unknown slide message lists all ids in order. Check: `render DECK-EI --slide slide-3 --scale 1` prints `(960x540)`.
- **STORY-D:** `src/mcp_htmleditor/render/scripts.py`, `src/mcp_htmleditor/render/problems.py`, `src/mcp_htmleditor/render/service.py`, `src/mcp_htmleditor/cli.py`, `tests/test_render_report.py`. Tests: E2E-003, 013, 014, 024; `format_line`, `final_line` plural table, overflow rounding unit, selector format (`div.probe`, `span.slide-foot-page`, tag alone, svg), `clipped` skipped under a reported ancestor, bottom edge ignored when `overflow` is reported, `--report` scope (problems of other slides not listed). Check: `render DECK-EI --slide slide-5 --report` ends with `report: OK`.
- **STORY-E:** `src/mcp_htmleditor/render/options.py`, `src/mcp_htmleditor/render/service.py`, `src/mcp_htmleditor/cli.py`, `tests/test_render_report_only.py`, `.agent_docs/testing.md`. Tests: E2E-004, 010, 012, 018; no picture file for the deck after `--report-only` and the directory left as it was; two slides with overflow listed in slide order; conflict with each of `--slide`, `--scale`, `--report` (status 2, empty stdout); `--report-only` on a document refused before any browser start. Check: `render DECK-EI --report-only` prints `report: OK`.
- **STORY-F:** `src/mcp_htmleditor/render/scripts.py`, `src/mcp_htmleditor/render/problems.py`, `src/mcp_htmleditor/render/service.py`, `tests/test_render_signals.py`, `.agent_docs/render.md`. Tests: E2E-015, 016, 017, 019; font table in a real page (`"NoSuchFont"`, a list where one name exists, generic only, quoted names); script error dedupe and attribution (load time `-`, error thrown when a slide is shown has that id); image: data address shortened, short data address kept, valid SVG data address not flagged, `--report` of a slide ignores the images of other slides; ordering across the five kinds. Check: `render DECK-EI --report-only` lists `font`, `image` and `script` lines.
- **STORY-G:** `src/mcp_htmleditor/mcp_server.py`, `src/mcp_htmleditor/cli.py`, `skill/core.md`, `src/mcp_htmleditor/render/problems.py`, `tests/test_render_tool.py`. Tests: E2E-005, 006, 007, 011, 025, 026, 028; tool and `--json` give equal objects; `report_only` dict has null `path`, `width`, `height`; JSON mode errors keep stderr and status; the `## Tools` section of the core lists `render` and `skill-audit` is green; tool error text equals the command text without prefix; missing package variant (`sys.modules` set to `None`). Check: a `fastmcp.Client` lists `render` and calls it.
- **STORY-H:** `tests/test_render_scale.py`, `README.md`, `AGENTS.md`, `.agent_docs/observability.md`, `.agent_docs/makefile.md`. Tests: E2E-023, 027, 029; documentation gates: `README.md` names `render` and `make install-browser`, `AGENTS.md` lists the command and the `.agent_docs/render.md` row, `.agent_docs/observability.md` lists the three spans, `skill/core.md` `## Tools` contains `render`. Check: `make check` with the whole acceptance set.

Stories as machine readable JSON are returned in the final message of the design run.
