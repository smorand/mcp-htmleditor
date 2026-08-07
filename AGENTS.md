# AGENTS.md — mcp-htmleditor

## Overview

WYSIWYG HTML editor + MCP server. LLM agents modify HTML files on disk; the browser auto-reloads via polling.

## Key commands

```bash
pip install -e .                          # Install
mcp-htmleditor serve file.html            # Open editor in browser
mcp-htmleditor mcp                        # MCP server (stdio)
mcp-htmleditor export pptx in.html out.pptx
mcp-htmleditor export docx in.html out.docx
```

### Dev commands (Makefile)

```bash
make sync        # pip install -e .
make lint        # ruff check src/
make lint-fix    # ruff check --fix src/
make format      # ruff format src/
make typecheck   # mypy src/ (strict)
make test        # pytest tests/
make test-cov    # pytest with coverage (gate 70%)
make check       # lint + typecheck + test-cov
make clean       # remove build/test/cache artifacts
```

Tooling note: `ruff` and `mypy` are invoked as direct binaries (global installs),
not `python3 -m ruff`. `pytest` runs via `python3 -m pytest`. `mypy` runs in its
own uv-isolated env, so third-party import stubs are handled via
`[[tool.mypy.overrides]]` (bs4, pptx, fastmcp, click) with `ignore_missing_imports`.

## Architecture

- `state.py` — singleton in-process state + `.mcp_state.json` on disk
- `http_server.py` — ThreadingHTTPServer, routes: `/`, `/static/*`, `/content`, `/status`
- `mcp_server.py` — FastMCP with 6 tools
- `cli.py` — Click CLI: `serve`, `mcp`, `export`
- `export/to_pptx.py` — HTML → PPTX (python-pptx, parses data-type attributes)
- `export/to_docx.py` — HTML → DOCX (pandoc subprocess)
- `static/editor.js` — GrapesJS init, polling, slide nav, context menus, blocks

## LLM workflow pattern

```
update_start() → write HTML file → update_end()
```

Never modify the file without these flanking calls.

## HTML conventions

- `data-doc-type="presentation"` on `<html>` → slide navigation active
- `data-doc-type="document"` → Word-like mode
- `data-type="slide"` requires `data-id` (unique) and `data-title`
- `data-editable="text"` on editable text elements

## State file

`.mcp_state.json` is written next to the current HTML file.
It is gitignored. Do not commit it.

## Tests

`tests/` targets pure logic only (no network I/O):
- `test_state.py` — EditorState singleton, persistence, mtime.
- `test_http_helpers.py` — `_strip_editor_artifacts`, `_rebuild_full_html`.
- `test_export_pptx.py` — `to_pptx` + position parsing helpers.

The `_EditorHandler` network class and server-lifecycle functions in
`http_server.py` are marked `# pragma: no cover` (I/O boundary). Coverage omits
the thin CLI/tool wrappers (`cli.py`, `mcp_server.py`, `to_docx.py`). Gate: 70%
(actual ~93%). `conftest.py` resets the EditorState singleton between tests.

## Skill docs

- `skill/SKILL.md` — main skill index (load first)
- `skill/workflow-create.md` — creating/modifying HTML
- `skill/workflow-export.md` — export workflows
- `skill/workflow-templates.md` — converting PPTX/DOCX to templates
- `skill/types/*.md` — per-type rules (slides, gantt, arch-diagram, etc.)
