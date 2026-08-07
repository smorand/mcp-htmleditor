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
mcp-htmleditor templates                          # list templates: ei, carbon, doc
mcp-htmleditor new ei ma-presentation.html --serve # create + open editor
```

### Visual editor

```bash
mcp-htmleditor serve path/to/file.html            # open existing file
mcp-htmleditor serve file.html --port 7842 --poll 500
```

Edit mode toggle (top-right "Édition"): in-place rich-text editing, format toolbar
on selection, insert image (local file picker or drag-drop, embedded as base64),
insert table, and slide insert/delete (presentation mode) with a template-aware picker.

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
│   ├── slides-ei-empty.html       key: ei     (Euro-Information)
│   ├── slides-empty.html          key: carbon (IBM Carbon)
│   └── document-empty.html        key: doc    (Word-like document)
└── reference/                     rich examples to clone (read-only via server)
    ├── slides/
    │   ├── euro-information.html   EI: title + agenda + content, embedded logos
    │   ├── ibm-carbon.html         IBM Carbon: 9 slides, all components
    │   ├── presentation-standard.html
    │   └── roadmap-one-pager.html
    └── documents/
        └── report-standard.html
```

Add your own templates by dropping files into `~/.config/mcp-htmleditor/templates/`
or by committing to `templates/` in this repo.

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
│   ├── to_pptx.py   HTML → PPTX via python-pptx
│   └── to_docx.py   HTML → DOCX via pandoc
└── static/
    ├── editor.html      iframe shell + toolbar
    ├── editor.js        polling, rich-text, slide insert, image embed
    ├── slide-layouts.js per-template slide layouts (carbon / ei)
    └── editor.css       toolbar, overlay, picker styles
templates/          versioned templates (bootstrap + reference)
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
