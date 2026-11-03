# US-0066: JSON output and the render tool

> Spec: SPEC-0008 (sdlc/specs/SPEC-0008-visual-render/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0065, US-0024, US-0025, US-0037, US-0047
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Add `--json` and the agent tool `render(file, slide, scale, report, report_only)`: one result object shared by both, identical checks and messages, and the line `- render: ...` in the `## Tools` section of the skill core.

## Requirements covered

- SPEC-0008/FR-NEW-005: WHEN an agent calls the tool `render` or a user passes `--json` THE Editor SHALL return a JSON object with the result.
- SPEC-0008/FR-NEW-006 (partial: the state of a running editor server (`get_status`) is unchanged by a render): The Editor SHALL NOT modify the presentation file or the state of a running editor server when rendering.
- SPEC-0008/FR-NEW-001 (partial: errors reach the tool as `ToolError` with the message of the command line without its prefix): WHEN a user runs `mcp-htmleditor render <file>` THE Editor SHALL write a PNG picture of one slide of the presentation and print one line giving its slide, path and size.

## Independent Test

`make test ARGS='-k render_tool'`: `fastmcp.Client` calls `render` with `slide` `slide-1` and `report` true and receives `{"ok":true,"path":"...DECK-EI-slide-1.png","width":480,"height":270,"problems":[]}`; `render DECK-EI --json` prints one such JSON object and nothing else; `skill-audit` is green with `render` listed in the core.

## Design excerpt

### Decisions

- DEC-017 (SPEC-0008): "The option conflict is detected in `check_options`, raised as `RenderUsageError`, and printed by the command as `Error: <message>` with exit status 2 by hand. `--scale` is a text option."
- DEC-018 (SPEC-0008): "The tool is `render(file, slide=None, scale=0.5, report=False, report_only=False)`; it passes `scale=None` to the service when it equals 0.5, so the conflict check sees "a scale other than the default"; errors become `ToolError(str(exc))` without the CLI prefixes."
- DEC-019 (SPEC-0008): "The result dict is built once by `result_to_dict` and used by `--json` and by the tool, compact with `ensure_ascii=False`."
- DEC-021 (SPEC-0008): "`render_deck` never reads or writes the editor state, the history store or the input file: it opens the file read only through `load_deck` and the browser reads it through `file://`."
- DEC-024 (SPEC-0008): "Spans: `render.session` (INFO; attributes `render.mode` picture, report or report_only, `render.slides` count, `render.scale` text), `render.cleanup` (DEBUG; `file.count`), `mcp.render`. No path, selector, text or image data in an attribute."

### Data model

```json
{"ok":true,"path":"/tmp/htmleditor-render/deck-slide-1.png","width":480,"height":270,"problems":[]}
{"ok":true,"path":null,"width":null,"height":null,"problems":[{"kind":"overflow","slide":"slide-4","message":"content is 1184px tall, the slide is 540px"}]}
```
Compact (`separators=(",",":")`, `ensure_ascii=False`), keys in this order; `problems` is empty unless `report` or `report_only`.

### Contracts

```python
# render/problems.py
def result_to_dict(result: RenderResult) -> dict[str, Any]
# mcp_server.py   (wrapped in trace_span("mcp.render"); ToolError(str(exc)))
@mcp.tool()
def render(file: str, slide: str | None = None, scale: float = 0.5,
           report: bool = False, report_only: bool = False) -> dict[str, Any]
```
The tool calls `render_deck(file, slide=slide, scale=None if scale == DEFAULT_SCALE else scale, report=report, report_only=report_only)` so that "a scale other than the default" is the conflict signal. It is a plain `def` (fastmcp runs it in a worker thread without an event loop, which the Playwright sync API needs).
Tool error messages are the command line messages without `error: ` and, for the option conflict, without `Error: `: `--report-only cannot be used with --slide, --scale or --report`, `File not found: ghost.html`, `Rendering needs Chromium. Install it with: make install-browser`.
Command `--json`: prints `json.dumps(result_to_dict(result), separators=(",", ":"), ensure_ascii=False)` alone on stdout (no `Rendered` line, no `report:` line); exit status follows the report (1 with at least one problem); on any error the error line is printed on stderr exactly as without `--json`, stdout stays empty, same status. `--json --report-only` prints the object with null `path`, `width`, `height`.
`skill/core.md`, section `## Tools`: add one line at the end of the section:
`- render: Picture of one slide plus a layout report (overflow, clipped, font, script, image); needs Chromium (make install-browser).`
`skill-audit` (SPEC-0006) must stay green; the section is the only place that lists tools.
Spec text for this story (verbatim):

#### FR-NEW-005 [EARS-E]: Tool surface and JSON
> WHEN an agent calls the tool `render` or a user passes `--json` THE Editor SHALL return a JSON object with the result.

- **Business rules:** tool `render(file, slide=None, scale=0.5, report=False, report_only=False)`. The object is `{"ok":true,"path":<path or null>,"width":<n or null>,"height":<n or null>,"problems":[{"kind","slide","message"}]}`; `path`, `width` and `height` are null for `report_only`; `problems` is empty unless `report` or `report_only` is set. With `--json` the command prints that object alone on the standard output and no other line; the exit status follows FR-NEW-003. Problems are collected only with `--report` or `--report-only` (the tool arguments `report`, `report_only`); otherwise the exit status is 0 after a successful picture. With `--json` the `Rendered ...` and `report: ...` lines are not printed; `--json --report-only` prints the object with null `path`, `width` and `height`. On any error, the command with `--json` prints the error line to the error output exactly as without `--json`, prints nothing on the standard output and keeps the same exit status. The tool applies the same checks in the same order, including the conflict of `report_only` with `slide`, a `scale` other than the default, or `report`, and returns errors with the message of the command line line without its `error: ` prefix.
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-006 [EARS-UB]: No side effect on the file or the editor
> The Editor SHALL NOT modify the presentation file or the state of a running editor server when rendering.

- **Business rules:** the file bytes and modification time, and the answer of `get_status`, are the same before and after.
- **Scenario:** SC-001, SC-002
- **Priority:** Must

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/mcp_server.py` | modify: tool `render` |
| `src/mcp_htmleditor/cli.py` | modify: option `--json` |
| `src/mcp_htmleditor/render/problems.py` | modify: `result_to_dict` |
| `skill/core.md` | modify: line `- render: ...` in `## Tools` |
| `tests/test_render_tool.py` | create |

### Existing patterns

- `src/mcp_htmleditor/mcp_server.py:31-32` (plain `def` tools with `@mcp.tool()`), `:93-108` (`get_status`), `trace_span("mcp.<tool>")` usage.
- `tests/deck_support.py` `call_tool` (US-0037, returns `(ok, value)`), `run_cli` (US-0035).
- `skill/core.md` `## Tools` format `- <name>: <description>` (SPEC-0006 design, US-0025).
- `tests/test_autosave_focus_e2e.py` (`start_http_server` harness) for the running server of E2E-025.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures of the spec (verbatim):

DECK-EI: an Euro-Information presentation of 8 slides `slide-0` to `slide-7` with no layout problem. DECK-MED: a
medical presentation of 6 slides whose `slide-2` has class `slide dark`. DOC-PERSO: a document. The machine running the tests has Segoe UI or Calibri installed, so DECK-EI and DECK-MED report no font problem. Where a test needs a defect, it states the defect.

Fixtures are generated by `tests/render_support.py` (US-0060) from the SPEC-0007 helpers in `tests/deck_support.py` (`build_deck`, `deck_med`, `doc_perso`, `run_cli`, `call_tool`), never committed and never read from `~/.config`. DECK-EI is `build_deck("ei", EI_TITLES)` with 8 titles and no big image. DECK-MED is `deck_med()` with the article of `slide-2` given `class="slide dark"`. DOC-PERSO is `doc_perso()`. The output directory is redirected with `monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))`. Browser tests carry `@needs_chromium`. On a machine without Segoe UI and Calibri the EI font stack still ends with Arial (`templates/bootstrap/slides-ei-empty.html:31`), which keeps DECK-EI free of a `font` problem.

### SPEC-0008/E2E-005: Tool call

- Level E2E; Driver tool over a stdio client (subprocess); Location `tests/test_render_tool.py`
- **Given** DECK-EI
- **When** the agent calls `render` with `file` DECK-EI, `slide` `slide-1`, `report` true
- **Then** it receives `{"ok":true,"path":"<path ending DECK-EI-slide-1.png>","width":480,"height":270,"problems":[]}`
- **Priority:** High

### SPEC-0008/E2E-006: JSON on the command line

- Level E2E; Driver CLI in a subprocess; Location `tests/test_render_tool.py`
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --json`
- **Then** the standard output is one JSON object equal to the one of E2E-005 with `slide-0` and nothing else
- **Priority:** Medium

### SPEC-0008/E2E-007: File not found

- Level E2E; Driver CLI + tool; Location `tests/test_render_tool.py`
- **Given** no file `ghost.html`
- **When** the user runs `render ghost.html`, and the agent calls `render` with `file` `ghost.html`
- **Then** the command prints `error: File not found: ghost.html` on the error output with exit status 1 and an empty standard output
- **And** the tool returns an error whose message is `File not found: ghost.html`
- **Priority:** High

### SPEC-0008/E2E-011: Browser missing

- Level E2E; Driver CLI + tool (browser path redirected); Location `tests/test_render_tool.py`
- **Given** DECK-EI (a valid presentation) and no browser installed for the product
- **When** the user runs `render DECK-EI`, and the agent calls `render`
- **Then** the command prints `error: Rendering needs Chromium. Install it with: make install-browser`, exit status 1, no picture
- **And** the tool returns an error with the same message without `error: `
- **Priority:** High

### SPEC-0008/E2E-025: Server state untouched

- Level E2E; Driver tool + running server; Location `tests/test_render_tool.py`
- **Given** the editor server running on DECK-EI
- **When** the agent calls `render` with `report_only` true
- **Then** the answer of `get_status` after is equal to the one before, field by field
- **Priority:** High

### SPEC-0008/E2E-026: Problems as JSON

- Level E2E; Driver CLI in process; Location `tests/test_render_tool.py`
- **Given** DECK-EI with the overflow defect of E2E-012
- **When** the user runs `render DECK-EI --report-only --json`
- **Then** the standard output is one JSON object with `ok` true, `path`, `width` and `height` null, and `problems` holding one element with `kind` `overflow`, `slide` `slide-4` and a `message` starting `content is `; nothing else is printed; the exit status is 1
- **Priority:** High

### SPEC-0008/E2E-028: JSON with an error

- Level E2E; Driver CLI + tool; Location `tests/test_render_tool.py`
- **Given** DECK-EI
- **When** the user runs `render DECK-EI --slide slide-9 --json`
- **Then** the error output is the `error: Unknown slide id "slide-9". Valid ids: ...` line of E2E-008, the standard output is empty and the exit status is 1
- **And** the tool `render` called with `report_only` true and `slide` `slide-1` returns an error whose message is `--report-only cannot be used with --slide, --scale or --report`
- **Priority:** Medium

### Additional integration and unit tests (`tests/test_render_tool.py`)

- The tool result and `render DECK-EI --json` for the same slide are equal objects (`path` aside from nothing: same path).
- `report_only` result through the tool has `path`, `width`, `height` null and `problems` as a list of `{kind, slide, message}`.
- Tool conflict messages: `report_only` with `slide`, with `scale` 0.7, with `report` each give the `--report-only cannot be used with --slide, --scale or --report` error; `scale` 0.5 with `report_only` is accepted.
- `--json` with an error keeps stderr and the status: a document gives `error: render needs a presentation: <file>`, stdout empty, status 1.
- Missing package variant: with `sys.modules["playwright.sync_api"] = None` the command and the tool give the install message.
- `skill-audit` on the real tree exits 0 and the core `## Tools` section contains a `render` line (listed tools equal registered tools).

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/export/*`, `src/mcp_htmleditor/state.py`, `src/mcp_htmleditor/http_server.py`.
- Dependencies not to add: none.
- Patterns to avoid: an `async def` tool (breaks the sync Playwright API); calling `get_state()` from `render`; printing in the tool; `type: ignore`; a second JSON builder.
- Scope boundary: no new report kind, no 40 slide budget test, no user documentation.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the command and output of the failing run).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: existing tests pass unmodified (`tests/test_skill_content.py`, `tests/test_templates.py`, the three existing browser E2E files); the existing commands and tools behave as before.
- [ ] Docs updated: `skill/core.md` `## Tools` updated in this story; user documentation in US-0067.
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0066: JSON output and the render tool` with body `Spec: SPEC-0008` and requirement ids FR-NEW-005, FR-NEW-006, FR-NEW-001.
