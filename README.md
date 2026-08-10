# mcp-htmleditor

WYSIWYG HTML editor for LLM-assisted document creation. A browser editor renders
the HTML file as-is in an iframe (all styles/JS intact), with lightweight in-place
editing; a FastMCP server lets AI agents create, modify, and export HTML
presentations and documents.

## Stack

- Python 3.13+, uv, FastMCP, python-pptx, BeautifulSoup4, Click
- pydantic-settings for configuration, rich for logging, OpenTelemetry for tracing
- No Node.js, no build step (iframe renderer + vanilla JS)
- pandoc for DOCX export
- stdlib `http.server` for the HTTP server

## Installation

Everything goes through `make` (uv under the hood, never `pip`).

### System install (XDG compliant)

```bash
make install
```

`make install` performs:
1. Installs the CLI as a **uv tool** in its own isolated environment and links
   `mcp-htmleditor` into `~/.local/bin/` (ensure it is on your PATH). A legacy
   `pip install --user` copy is removed when found, because its console script
   used to shadow both the tool and the sources.
2. Copies templates into `~/.config/mcp-htmleditor/templates/`
3. Creates the log dir `~/.cache/mcp-htmleditor/logs/`
4. Installs the dynamic Pi skill into `~/.pi/agent/dynamic-skills/html-editor/`
   (then add the routing rule to `~/.pi/agent/dynamic_prompt.yaml`, see
   `dynamic-skills/README.md`, zero overlap with the `pptx`/`docx` skills via the
   word "html")

The tool environment is a snapshot: run `make install` again after changing the
sources. All install targets are overridable via env vars (see below).
`make uninstall` reverses everything.

### Development

```bash
make sync     # uv sync: .venv from the committed uv.lock, dev group included
make check    # lint + format-check + typecheck + security + tests with coverage
make run ARGS='export pptx pres.html /tmp/out.pptx'
make run-dev ARGS='-v serve doc.html'
```

### Docker

```bash
make docker-build            # image mcp-htmleditor:latest, version from the git tag
make run-up                  # docker compose up -d, editor on http://localhost:7842/
make run-down
```

The image is multi stage (`python:3.13-slim`), installs from `uv.lock`, ships pandoc,
runs as a non root user and exposes `GET /health`. Documents live in the `./data`
volume mounted on `/data`. Details in `.agent_docs/docker.md`.

### Version

```bash
mcp-htmleditor --version      # or: curl localhost:7842/health
```

`src/mcp_htmleditor/version.py` holds `dev` in the working tree; `make build` and
`make docker-build` overwrite it from `git describe --tags --always --dirty`.

## Usage

### Create from a template (recommended)

```bash
mcp-htmleditor templates                          # list templates: ei, carbon, doc, doc-perso, doc-ei
mcp-htmleditor new ei ma-presentation.html --serve # create + open editor
```

### Visual editor

```bash
mcp-htmleditor serve path/to/file.html            # open existing file
mcp-htmleditor serve file.html --port 7842 --poll 500
mcp-htmleditor -v serve file.html                 # DEBUG logs (-q for errors only)
mcp-htmleditor serve file.html --host 0.0.0.0 --no-browser   # remote or container
```

Without `--port`, a free port is auto-picked (7842 first, then 7840-7849), so several
presentations can be served at once (one process per file) without colliding on the
default port — see [Multiple presentations at once](#multiple-presentations-at-once).
An explicit `--port` is used as-is and fails with a clear error if it is already taken.

Global options come before the subcommand: `-v` / `--verbose` raises the log level,
`-q` / `--quiet` keeps errors only, `-V` / `--version` prints the version.

Edit mode toggle (top-right "Édition"): in-place rich-text editing, format toolbar
on selection (bold/italic/underline/strike, superscript/subscript, align, size,
color), insert image (local file picker or drag-drop, embedded as base64), insert
table, slide insert/delete (presentation mode) with a template-aware picker, and
document block insert before/after (document mode) via "＋ Bloc avant / Bloc après"
pickers (title, subtitle, h1-h5, paragraph, table, list). Drag-and-drop editing:
reorder top-level document blocks with a left-side grip handle (DOM order = visual
order, no attribute added), and move arch-diagram nodes with the mouse (position
written as readable `data-x`/`data-y` percentages plus inline `left`/`top` in %).

### MCP server (stdio)

```bash
mcp-htmleditor mcp
```

Connect your LLM agent via stdin/stdout (e.g. Claude Desktop, Cursor, pi).

### Skill content

```bash
mcp-htmleditor skill      # prints the full skill (index + all sub-docs)
```

The dynamic Pi skill triggers on "html powerpoint", "html edition", "html doc" and
simply instructs the agent to run `mcp-htmleditor skill`, keeping the skill content
in sync with the installed tool. Routing is disjoint from the native `pptx`/`docx`
skills (the word "html" is the exclusive discriminant). See `dynamic-skills/README.md`.

### Export

```bash
mcp-htmleditor export pptx input.html output.pptx
mcp-htmleditor export docx input.html output.docx
```

The PPTX export writes one 16:9 slide (13.333 x 7.5 in) per element carrying
`data-type="slide"`, with a fallback on `article.slide` for older templates. The
navigation shell, `<script>` and `<style>` are never exported. It detects the
charter of the document (Euro-Information, IBM Carbon, generic), draws the slide
chrome (frames, footers, logo ring, header rule), then flows the content: text at
the typographic scale of the template, tile grids, callouts, native tables with
`colspan` / `rowspan` merges, real Gantt bars, diagram nodes as autoshapes with
their connectors, annotated images with the annotations placed in the image frame.
Base64 images are embedded and relative paths resolve against the HTML file. The
command prints the slide count, lists every skipped item and exits non zero when
no slide could be written. Full breakdown of what is faithful, approximated or
lost: `skill/workflow-export.md`.

The DOCX export carries the document charter into Word. The charter is read from
`data-doc-template` on the document `<article>` (`perso`, `ei`), a matching
`reference.docx` is generated from pandoc's own default (fonts, heading sizes and
colours, underlines, table header fill) and cached in
`~/.cache/mcp-htmleditor/reference/`. A document without that attribute keeps the
default pandoc styles. The title is emitted once (Word `Title`, then `Subtitle`),
not duplicated as a `Heading1`. SVG figures and pandoc warnings are reported:
figures must be PNG, never SVG.

## MCP Tools

| Tool | Description |
|------|-------------|
| `start_server(file, port=None)` | Start HTTP server + open browser. Idempotent. Without `port`, a free one is auto-picked (7842 first, then 7840-7849) — always read the `port` field of the response, never assume 7842. |
| `stop_server()` | Stop the HTTP server. |
| `get_status()` | Current state: file, port, pid, mtime, running. |
| `open_file(file)` | Switch to a different HTML file. |
| `update_start()` | Signal modification start (shows overlay in browser). |
| `update_end()` | Signal modification complete (browser reloads). |

### Multiple presentations at once

Each `mcp-htmleditor serve <file>` (CLI) or `mcp-htmleditor mcp` (one per agent session) is
an independent process. Without an explicit port, it tries 7842 then scans 7840-7849 for a
free one, so up to 10 presentations can coexist (one file each) without any manual port
juggling. Within a *single* agent session (one `mcp-htmleditor mcp` process), only one
server runs at a time: calling `start_server` on a second file switches the served file
(use `open_file` for that) rather than opening a second server — run a separate agent
session per presentation if you need several displayed simultaneously.

## Templates

Templates are resolved in priority order:
1. `HTMLEDITOR_TEMPLATES_DIR` (env override)
2. `~/.config/mcp-htmleditor/templates/` (installed by `make install`)
3. `<repo>/templates/` (development / bundled fallback)

```
templates/
├── bootstrap/                     starters copied by `new`
│   ├── slides-ei-empty.html       key: ei        (Euro-Information)
│   ├── slides-empty.html          key: carbon    (IBM Carbon)
│   ├── document-empty.html        key: doc       (Word-like document)
│   ├── document-perso-empty.html  key: doc-perso (Perso charter, Arial)
│   └── document-ei-empty.html     key: doc-ei    (Euro-Information, Segoe UI)
└── reference/                     rich examples to clone (read-only via server)
    ├── slides/
    │   ├── euro-information.html   EI: title + agenda + content, embedded logos (CSS source of the `ei` bootstrap)
    │   ├── example-ei-complete.html EI: 9 slides, gantt, arch diagram, table, annotated image
    │   ├── ibm-carbon.html         IBM Carbon: 9 slides, all components
    │   ├── presentation-standard.html
    │   └── roadmap-one-pager.html
    └── documents/
        ├── report-standard.html    generic standard report
        ├── perso.html              Perso charter: title/subtitle + h1-h5 + table + list
        └── euro-information.html    EI document: blue header + logo, blue headings
```

Add your own templates by dropping files into `~/.config/mcp-htmleditor/templates/`
or by committing to `templates/` in this repo.

`bootstrap/slides-ei-empty.html` is **generated**, not hand written: it is derived from
`reference/slides/euro-information.html` by `tools/gen_ei_bootstrap.py` (`make bootstrap-ei`),
which keeps the reference as the single source of the EI charter CSS, trims the deck down to
the title slide, and copies the EI chevrons data URI onto `<html data-asset-chevrons>` so a
slide inserted into a brand new file still gets its footer logo. Edit the reference, then
run `make bootstrap-ei`; never patch the bootstrap directly.

## HTML data-types

| `data-type` | Description |
|-------------|-------------|
| `slide` | Presentation slide section |
| `gantt` | Gantt chart container |
| `gantt-task` | Single Gantt task bar |
| `arch-diagram` | Architecture diagram container |
| `arch-node` | Architecture diagram node |
| `annotation` | Image annotation callout |
| `annotated-image` | Image + annotations container |
| `table` | HTML table |
| `document` | Word-like document article |

## Environment variables

Every variable is read through the `Settings` class (pydantic-settings,
`src/mcp_htmleditor/config.py`). A local `.env` file is loaded automatically; see
`.env.example`.

| Variable | Default | Description |
|----------|---------|-------------|
| `HTMLEDITOR_HOST` | `localhost` | HTTP bind address (`0.0.0.0` in a container) |
| `HTMLEDITOR_PORT` | `7842` | Preferred HTTP port, tried first before auto-picking a free one in 7840-7849 |
| `HTMLEDITOR_POLL_INTERVAL` | `1000` | Browser polling interval in ms |
| `HTMLEDITOR_TEMPLATES_DIR` | `~/.config/mcp-htmleditor/templates` | Templates directory |
| `HTMLEDITOR_CACHE_DIR` | `~/.cache/mcp-htmleditor` | Cache base (logs, generated `reference.docx`) |
| `HTMLEDITOR_LOG_DIR` | `<cache>/logs` | Log directory (`HTMLEDITOR_LOGS` is an accepted alias) |
| `HTMLEDITOR_BIN_DIR` | `~/.local/bin` | CLI install target |
| `HTMLEDITOR_OTEL_DESTINATION` | unset | OTLP/HTTP endpoint for spans; unset means local JSONL |
| `HTMLEDITOR_OTEL_API_KEY` | unset | Sent as `Authorization: Bearer <key>` on OTLP exports |
| `XDG_CONFIG_HOME` | `~/.config` | Base for config |
| `XDG_CACHE_HOME` | `~/.cache` | Base for cache |

A malformed `HTMLEDITOR_PORT` or `HTMLEDITOR_POLL_INTERVAL` falls back to its default
instead of aborting; a blank path variable means "unset", not the current directory.

## Logs and tracing

| File | Content |
|------|---------|
| `<log dir>/mcp-htmleditor.log` | Application log, rotating (2 MB, 3 backups) |
| `<log dir>/mcp-htmleditor-otel.log` | One JSON object per finished span (JSONL) |

Console logs go to stderr (stdout carries the MCP protocol and the CLI output) and every
line carries its own timestamp. Spans are named `category.operation`: `mcp.*` for tool
calls, `export.pptx` / `export.docx` with slide count, charter and duration,
`tool.pandoc` for pandoc runs, `file.write` for file mutations. Document content,
prompts and credentials are never traced. Details in `.agent_docs/observability.md`.

## Project structure

```
src/mcp_htmleditor/
├── cli.py           CLI: templates, new, serve, skill, mcp, export (-v/-q, --version)
├── config.py        Settings (pydantic-settings): XDG paths, ports, OTel
├── logging_config.py setup_logging(): rich console on stderr + rotating file
├── tracing.py       configure_tracing(), trace_span(), JSONL span exporter
├── version.py       __version__, written at build time from the git tag
├── templates.py     template registry + search-path resolution
├── skill_content.py assembles `mcp-htmleditor skill` output
├── mcp_server.py    FastMCP server with 6 tools
├── http_server.py   stdlib HTTP server (routes /, /static, /content, /status, /health)
├── state.py         singleton state + .mcp_state.json persistence
├── export/
│   ├── to_pptx.py   HTML to PPTX: slide detection, charter chrome, block flow, renderers
│   ├── pptx_style.py      Box geometry, CSS/colour parsing, themes, typographic scale
│   ├── pptx_components.py table grid (spans), Gantt maths, low level pptx helpers
│   ├── to_docx.py   HTML to DOCX via pandoc (single title, charter, diagnostics)
│   ├── reference_docx.py  generates/caches a charter reference.docx for pandoc
│   ├── docx_header_footer.py  repeated Word header/footer parts of a charter
│   └── docx_assets.py     base64 assets embedded in the reference documents
└── static/
    ├── editor.html      iframe shell + toolbar
    ├── editor.js        polling, rich-text, slide insert, doc-block insert, image embed, drag-reorder blocks + move arch-nodes
    ├── slide-layouts.js per-template slide layouts (carbon / ei)
    ├── doc-blocks.js    document block definitions (title, subtitle, h1-h5, paragraph, table, list)
    └── editor.css       toolbar, overlay, picker styles
templates/          versioned templates (bootstrap + reference)
tests/              pytest suite (see .agent_docs/testing.md)
tools/              maintenance scripts
                    gen_ei_bootstrap.py  regenerate the EI bootstrap from the EI reference
                    check_ei_insert.py   browser check of EI slide insertion (logo + numbering)
skill/              skill docs (served by `mcp-htmleditor skill`)
dynamic-skills/     dynamic Pi skill + routing doc (installed to ~/.pi/agent/dynamic-skills)
.agent_docs/        detailed docs for AI agents (python, makefile, architecture, ...)
Dockerfile, docker-compose.yml, docker-compose.prod.yml
Makefile            single entry point for every operation
```

## Documentation

- `AGENTS.md`: compact index for AI agents (commands, conventions, doc index)
- `.agent_docs/python.md`: Python standards and documented deviations
- `.agent_docs/makefile.md`: every make target and install override
- `.agent_docs/architecture.md`: module map, save path, export pipeline
- `.agent_docs/observability.md`: logs, span inventory, OTLP export
- `.agent_docs/testing.md`: test map, coverage, export regression set
- `.agent_docs/docker.md`: image, compose, container checks
- `.agent_docs/html-conventions.md`: invariants the exporters rely on

## How it works

1. The HTTP server serves the editor shell at `http://localhost:<port>/` (7842 if free, otherwise an auto-picked free port in 7840-7849, or whatever `--port` was given explicitly)
2. The target HTML file is rendered as-is inside an iframe (`GET /content-frame`)
3. In edit mode, editable zones become contenteditable; saves go via `POST /content`
   (the server strips editor artifacts before writing, keeping the file clean)
4. The browser polls `GET /status` every `poll_interval` ms
5. If the file mtime changes (LLM wrote to it), the iframe reloads
6. `update_start()` / `update_end()` show/hide a "modification en cours" overlay

## Skill documentation

Run `mcp-htmleditor skill` for the full skill (index + workflows + per-type rules).
Source files live in `skill/`. The dynamic Pi skill in `.pi/skills/mcp-htmleditor/`
triggers on "html powerpoint" / "html edition" / "html doc" and defers to the CLI.
