# mcp-htmleditor

WYSIWYG HTML editor for LLM-assisted document creation. A browser editor renders
the HTML file as-is in an iframe (all styles/JS intact), with lightweight in-place
editing; a FastMCP server lets AI agents create, modify, and export HTML
presentations and documents.

## Stack

- Python 3.11+, FastMCP, python-pptx, BeautifulSoup4, Click
- No Node.js, no build step (iframe renderer + vanilla JS)
- pandoc for DOCX export
- stdlib `http.server` for the local HTTP server

## Installation

### Development (editable)

```bash
pip install -e /path/to/html-editor
```

### System install (XDG-compliant)

```bash
make install
```

`make install` performs:
1. Installs the `mcp-htmleditor` CLI into `~/.local/bin/` (symlink; ensure it is on your PATH)
2. Copies templates into `~/.config/mcp-htmleditor/templates/`
3. Creates the log dir `~/.cache/mcp-htmleditor/logs/`
4. Installs the dynamic Pi skill into `~/.pi/agent/dynamic-skills/html-editor/`
   (then add the routing rule to `~/.pi/agent/dynamic_prompt.yaml`, see
   `dynamic-skills/README.md` — zero overlap with the `pptx`/`docx` skills via the
   word "html")

All targets are overridable via env vars (see below). `make uninstall` reverses it.

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
```

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
| `start_server(file, port=7842)` | Start HTTP server + open browser. Idempotent. |
| `stop_server()` | Stop the HTTP server. |
| `get_status()` | Current state: file, port, pid, mtime, running. |
| `open_file(file)` | Switch to a different HTML file. |
| `update_start()` | Signal modification start (shows overlay in browser). |
| `update_end()` | Signal modification complete (browser reloads). |

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

| Variable | Default | Description |
|----------|---------|-------------|
| `HTMLEDITOR_PORT` | `7842` | Default HTTP port |
| `HTMLEDITOR_POLL_INTERVAL` | `1000` | Browser polling interval in ms |
| `HTMLEDITOR_TEMPLATES_DIR` | `~/.config/mcp-htmleditor/templates` | Templates directory |
| `HTMLEDITOR_LOG_DIR` | `~/.cache/mcp-htmleditor/logs` | Log directory |
| `HTMLEDITOR_BIN_DIR` | `~/.local/bin` | CLI install target |
| `XDG_CONFIG_HOME` | `~/.config` | Base for config |
| `XDG_CACHE_HOME` | `~/.cache` | Base for cache |

## Project structure

```
src/mcp_htmleditor/
├── cli.py           CLI: templates, new, serve, skill, mcp, export
├── config.py        XDG paths + env-var overrides
├── templates.py     template registry + search-path resolution
├── skill_content.py assembles `mcp-htmleditor skill` output
├── mcp_server.py    FastMCP server with 6 tools
├── http_server.py   stdlib HTTP server (ThreadingHTTPServer)
├── state.py         singleton state + .mcp_state.json persistence
├── export/
│   ├── to_pptx.py   HTML → PPTX: slide detection, charter chrome, block flow, renderers
│   ├── pptx_style.py      Box geometry, CSS/colour parsing, themes, typographic scale
│   ├── pptx_components.py table grid (spans), Gantt maths, low level pptx helpers
│   ├── to_docx.py   HTML → DOCX via pandoc (single title, charter, diagnostics)
│   └── reference_docx.py  generates/caches a charter reference.docx for pandoc
└── static/
    ├── editor.html      iframe shell + toolbar
    ├── editor.js        polling, rich-text, slide insert, doc-block insert, image embed, drag-reorder blocks + move arch-nodes
    ├── slide-layouts.js per-template slide layouts (carbon / ei)
    ├── doc-blocks.js    document block definitions (title, subtitle, h1-h5, paragraph, table, list)
    └── editor.css       toolbar, overlay, picker styles
templates/          versioned templates (bootstrap + reference)
tools/              maintenance scripts
                    gen_ei_bootstrap.py  regenerate the EI bootstrap from the EI reference
                    check_ei_insert.py   browser check of EI slide insertion (logo + numbering)
skill/              skill docs (served by `mcp-htmleditor skill`)
dynamic-skills/     dynamic Pi skill + routing doc (installed to ~/.pi/agent/dynamic-skills)
```

## How it works

1. The HTTP server serves the editor shell at `http://localhost:7842/`
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
