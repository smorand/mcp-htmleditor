# mcp-htmleditor

WYSIWYG HTML editor for LLM-assisted document creation. Combines a GrapesJS-powered browser editor with a FastMCP server, enabling AI agents to create, modify, and export HTML presentations and documents.

## Stack

- Python 3.11+, FastMCP, python-pptx, BeautifulSoup4, Click
- GrapesJS 0.21.13 via CDN (no Node.js, no build step)
- pandoc for DOCX export
- stdlib `http.server` for the local HTTP server

## Installation

```bash
pip install -e /path/to/html-editor
```

## Usage

### Visual editor

```bash
# Open a file in the browser editor
mcp-htmleditor serve path/to/file.html

# Custom port and poll interval
mcp-htmleditor serve file.html --port 7842 --poll 500
```

### MCP server (stdio)

```bash
mcp-htmleditor mcp
```

Connect your LLM agent via stdin/stdout (e.g. Claude Desktop, Cursor, pi).

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

```
skill/templates/
├── bootstrap/
│   ├── slides-empty.html       Minimal presentation starter
│   └── document-empty.html     Minimal document starter
└── reference/
    ├── slides/
    │   ├── presentation-standard.html  4-slide standard deck
    │   └── roadmap-one-pager.html      Q1-Q4 Gantt roadmap
    └── documents/
        └── report-standard.html        Standard report with table
```

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
| `HTMLEDITOR_POLL_INTERVAL` | `1000` | Browser polling interval in ms |

## Project structure

```
src/mcp_htmleditor/
├── cli.py          CLI entry point (serve, mcp, export commands)
├── mcp_server.py   FastMCP server with 6 tools
├── http_server.py  stdlib HTTP server (ThreadingHTTPServer)
├── state.py        Singleton state + .mcp_state.json persistence
├── export/
│   ├── to_pptx.py  HTML → PPTX via python-pptx
│   └── to_docx.py  HTML → DOCX via pandoc
└── static/
    ├── editor.html GrapesJS shell
    ├── editor.js   Init, polling, slide nav, context menus, blocks
    └── editor.css  Overlay and nav styles
```

## How it works

1. The HTTP server serves GrapesJS at `http://localhost:7842/`
2. GrapesJS loads the HTML file content via `GET /content`
3. On every edit, GrapesJS auto-saves via `POST /content` (debounced 500ms)
4. The browser polls `GET /status` every `poll_interval` ms
5. If the file mtime changes (LLM wrote to it), the browser reloads the content
6. `update_start()` / `update_end()` show/hide a "modification en cours" overlay

## Skill documentation

See `skill/SKILL.md` for LLM agent instructions, workflow guides, and type references.
