# AGENTS.md, mcp-htmleditor

## Overview

WYSIWYG HTML editor plus MCP server, with PPTX and DOCX export. LLM agents modify HTML
files on disk; the browser renders them in an iframe and reloads on mtime change.
Python 3.13+, uv, click, FastMCP, python-pptx, BeautifulSoup4, pandoc for DOCX.

## Key commands

`make` is the only entry point. Never call uv, ruff, mypy or pytest directly.

```bash
make sync        # uv sync (deps + dev group)
make check       # GATE: lint + format-check + typecheck + security + test-cov (80 %)
make test        # pytest -v            (ARGS='-k pptx' for a subset)
make install     # uv tool install + templates + log dir + Pi skill
make run ARGS='export pptx in.html out.pptx'
make docker-build / run-up / run-down
make bootstrap-ei  # regenerate the EI bootstrap from the EI reference
make help        # every target
```

CLI (same after `make install`):

```bash
mcp-htmleditor --version
mcp-htmleditor templates                   # ei, carbon, doc, doc-perso, doc-ei
mcp-htmleditor new ei pres.html --serve
mcp-htmleditor serve file.html [-v|-q] [--host] [--port] [--poll] [--no-browser]
mcp-htmleditor mcp                         # MCP server (stdio)
mcp-htmleditor export pptx in.html out.pptx
mcp-htmleditor export docx in.html out.docx
mcp-htmleditor skill                       # full skill content
```

## Essential conventions

- LLM workflow: `update_start()` then write the HTML file then `update_end()`. Never
  write the file without those flanking calls.
- Configuration only through `Settings` in `config.py` (pydantic-settings,
  `HTMLEDITOR_*`). No `os.environ` read anywhere else.
- Logging: `logger = logging.getLogger(__name__)`, `%` lazy formatting, console on
  stderr. `click.echo` is for user output only. Never log on stdout: the MCP protocol
  and the CLI output live there.
- Tracing: wrap every external call in `trace_span("category.operation", {...})`. Never
  put document content, prompts or credentials in an attribute.
- `data-doc-type` on `<html>` drives the mode, `data-type="slide"` needs `data-id` and
  `data-title`, document headings are semantic `<h1>` to `<h5>`.
- Templates are read only through the server; `templates/bootstrap/slides-ei-empty.html`
  is generated, edit the EI reference then `make bootstrap-ei`.
- After editing anything under `templates/`, run `make install` or export
  `HTMLEDITOR_TEMPLATES_DIR=$PWD/templates`, otherwise the installed copy wins.
- `.mcp_state.json` is written next to the edited file. It is gitignored, never commit it.
- JS has no build step: `node --check src/mcp_htmleditor/static/*.js`.
- `src/mcp_htmleditor/version.py` stays committed with `"dev"`; the build overwrites it
  from the git tag.

## Documentation index

Load only what the task needs.

| File | Content |
|------|---------|
| `.agent_docs/python.md` | Python standards applied here, tooling, config/logging/tracing patterns, documented deviations (sync I/O, click, pptx typing, bandit skips) |
| `.agent_docs/makefile.md` | Every make target, install path overrides, why `install` uses a uv tool |
| `.agent_docs/architecture.md` | Module map, save path, export pipeline, browser side, templates and tools |
| `.agent_docs/observability.md` | Log files, console rules, span inventory, OTLP export, JSONL recipes |
| `.agent_docs/testing.md` | Test file map, coverage decisions, export regression set and validation procedure |
| `.agent_docs/docker.md` | Image, compose, prod overlay, container checks |
| `.agent_docs/html-conventions.md` | Invariants the exporters and the editor depend on |

Authoring rules for slides and documents live in the skill: run `mcp-htmleditor skill`
(sources in `skill/`, `skill/workflow-*.md`, `skill/types/*.md`).
