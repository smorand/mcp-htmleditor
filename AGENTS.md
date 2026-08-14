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
mcp-htmleditor templates                   # ei, carbon, doc, doc-perso, doc-ei, mail
mcp-htmleditor new ei pres.html --serve
mcp-htmleditor serve file.html [-v|-q] [--host] [--port] [--poll] [--no-browser]
mcp-htmleditor mcp                         # MCP server (stdio)
mcp-htmleditor export pptx in.html out.pptx
mcp-htmleditor export docx in.html out.docx
mcp-htmleditor arch-layout in.html         # compute arch-diagram positions from topology
mcp-htmleditor arch-checklist               # print the editable arch-diagram QA checklist
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
- Every slide template (current and future) must ship fullscreen support (`:fullscreen`
  CSS, `#btn-present` button, `enterPresentation`/`exitPresentation`/
  `updateFullscreenScale` JS): see `.agent_docs/html-conventions.md` § Fullscreen. A
  presentation file missing it (e.g. created before this convention) is a bug to patch,
  not a valid variant.
- Architecture diagrams (`data-type="arch-diagram"`) with 4+ nodes or a multi-row flow:
  never write `data-x`/`data-y` by hand, author the declarative topology (`arch-row` /
  `arch-node` / `arch-col` / `arch-edge` / `arch-lane` / `arch-spacer`) and run
  `mcp-htmleditor arch-layout` (or the `layout_arch_diagram` MCP tool) to compute
  positions. See `skill/types/arch-diagram.md` and `src/mcp_htmleditor/arch_layout.py`.
  The old manual `data-x`/`data-y` format stays valid for 2-3 node diagrams only.
- After every `arch-layout` run, spawn a dedicated review sub-agent against
  `mcp-htmleditor arch-checklist` before considering the diagram done (protocol:
  `skill/workflow-arch-qa.md`). The checklist itself is user-editable at
  `~/.config/mcp-htmleditor/arch-checks/arch-diagram-checklist.md`, never in code.
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

Specifications live in `specs/*.md` (never modify an existing one, only reference and
flag inconsistencies). Deferred feature ideas not yet worth a full spec are tracked in
`specs/BACKLOG.md`.
