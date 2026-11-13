# AGENTS.md, mcp-htmleditor

## Overview

WYSIWYG HTML editor plus MCP server, with PPTX and DOCX export. LLM agents modify HTML
files on disk; the browser renders them in an iframe and reloads on mtime change.
Python 3.13+, uv, click, FastMCP, python-pptx, BeautifulSoup4, pandoc for DOCX.

## Key commands

`make` is the only entry point. Never call uv, ruff, mypy or pytest directly.

```bash
make sync        # uv sync (deps + dev group)
make check       # GATE: check-generated + lint + format-check + typecheck + security + test-cov (80 %)
make test        # pytest -v            (ARGS='-k pptx' for a subset)
make test ARGS='-m slow'  # real 30 s and 5 min HTTP bounds, literal 60 s / 900 s test limits, 30 s stdio bound (minutes, not run by make check)
make install     # uv tool install (with the render extra) + templates + log dir + Pi skill
make install-browser  # Chromium for `render` (needs the render extra)
make run ARGS='export pptx in.html out.pptx'
make docker-build / run-up / run-down
make bootstrap-ei  # regenerate the EI bootstrap from the EI reference
make sync-medical-css  # propagate the medical charter CSS to the reference decks
make check-generated  # verify both generated template families are fresh (writes nothing)
make help        # every target
```

CLI (same after `make install`):

```bash
mcp-htmleditor --version
mcp-htmleditor templates                   # ei, carbon, medical, doc, doc-perso, doc-ei, mail, website
mcp-htmleditor new ei pres.html --serve
mcp-htmleditor new medical talk.html --serve
mcp-htmleditor serve file.html [-v|-q] [--host] [--port] [--poll] [--no-browser]
mcp-htmleditor mcp                         # MCP server (stdio)
mcp-htmleditor export pptx in.html out.pptx
mcp-htmleditor export docx in.html out.docx
mcp-htmleditor arch-layout in.html         # compute arch-diagram positions from topology
mcp-htmleditor arch-checklist               # print the editable arch-diagram QA checklist
mcp-htmleditor skill                       # skill core (rules, tools, topic index)
mcp-htmleditor skill --type <topic>        # one of the 15 topics
mcp-htmleditor skill --all                 # core then every topic
mcp-htmleditor requests file.html          # requests queued from the editor, oldest first
mcp-htmleditor request-done file.html R-0001
mcp-htmleditor request-skip file.html R-0002 --reason "why"
mcp-htmleditor review file.html [--write list.json]   # AI suggestions; --write replaces them
mcp-htmleditor skill-audit [--json]        # sizes, tool list, stale statements; exit 1 on a problem
mcp-htmleditor render file.html [--slide ID] [--scale 0.5] [--report] [--json]  # PNG of a slide in <tmp>/htmleditor-render
mcp-htmleditor render file.html --report-only [--json]  # layout problems of every slide, no picture; exit 1 on a problem
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
  is generated, edit the EI reference then `make bootstrap-ei`. For the `medical` charter
  it is the reverse: the bootstrap `<style>` is the source, edit it then
  `make sync-medical-css` to propagate the copy into the two reference decks.
- A `medical` deck cites every third party image (non empty `.med-source` in the footer
  band) and anonymizes every patient image (no name, initials, MRN, care date, full date
  of birth; DICOM header **and** burned in pixels cleaned): see `skill/topics/medical.md`.
  Its flex rows (`.med-strip`, `.med-split`, `.med-cols`, `.med-compare`, `.med-steps`,
  `.med-stats`, `.med-timeline`, `.med-section-figs`) need an explicit width class
  (`w-25` to `w-70`) on every child, otherwise the PPTX export flattens the row into a
  vertical stack.
- After editing anything under `templates/`, run `make install` or export
  `HTMLEDITOR_TEMPLATES_DIR=$PWD/templates`, otherwise the installed copy wins.
- Every slide template (current and future) must ship fullscreen support (`:fullscreen`
  CSS, `#btn-present` button, `enterPresentation`/`exitPresentation`/
  `updateFullscreenScale` JS): see `.agent_docs/html-conventions.md` § Fullscreen. A
  presentation file missing it (e.g. created before this convention) is a bug to patch,
  not a valid variant. The five reference decks comply, and
  `tests/test_presentation_templates_fullscreen.py` enforces it on every presentation file under `templates/`.
  The same files carry the presentation pointer (SPEC-0017): three parts per file (the block holding
  `window.togglePointer = function`, a Pointeur control, the L key). Edit the block only in
  `templates/bootstrap/slides-empty.html` (between `<!-- deck-pointer:begin -->` and `<!-- deck-pointer:end -->`), then run
  `make sync-deck-pointer` (`make check-generated` fails on a stale copy); the guard reports `<stem>: missing
  pointer|Pointeur control|L key`. See `.agent_docs/html-conventions.md` § Presentation pointer.
- Speaker notes (SPEC-0022): `<aside data-role="speaker-notes">` direct child of a slide, hidden by an attribute selector
  rule, exported to the PPTX notes page, never a shape. Keys F P S E, the presenter block and the shell pieces:
  `.agent_docs/html-conventions.md` § Speaker notes, `.agent_docs/architecture.md` § Shell pieces of SPEC-0022.
- Architecture diagrams (`data-type="arch-diagram"`) with 4+ nodes or a multi-row flow:
  never write `data-x`/`data-y` by hand, author the declarative topology (`arch-row` /
  `arch-node` / `arch-col` / `arch-edge` / `arch-lane` / `arch-spacer`) and run
  `mcp-htmleditor arch-layout` (or the `layout_arch_diagram` MCP tool) to compute
  positions. See `skill/topics/arch-diagram.md` and `src/mcp_htmleditor/arch_layout.py`.
  The old manual `data-x`/`data-y` format stays valid for 2-3 node diagrams only.
- After every `arch-layout` run, spawn a dedicated review sub-agent against
  `mcp-htmleditor arch-checklist` before considering the diagram done (protocol:
  `skill/topics/arch-qa.md`). The checklist itself is user-editable at
  `~/.config/mcp-htmleditor/arch-checks/arch-diagram-checklist.md`, never in code.
- Editor state (file history, server records) lives in the state directory (`HTMLEDITOR_STATE_DIR`, default
  `~/.local/state/mcp-htmleditor`), never next to the edited file. `.mcp_state.json` is only a leftover of older versions; it stays gitignored.
- Browser tests (`tests/test_*_e2e.py`) observe asynchronous results with `tests/browser_wait.py` (`wait_until`, at most 100 ms
  apart, 10 s bound), never after a fixed delay. A `wait_for_timeout(` that stays carries a trailing `# pacing: <reason>`;
  `tests/test_no_fixed_waits.py` fails the gate otherwise. Child processes over stdio go through `tests/stdio_support.py`.
- JS has no build step: `node --check src/mcp_htmleditor/static/*.js`.
- The editor is thirteen classic scripts loaded in the order of `editor.html`; the PPTX exporter
  is a composed `_SlideBuilder` of mixins (`export/pptx_*.py`). See `.agent_docs/architecture.md`.
- `src/mcp_htmleditor/version.py` stays committed with `"dev"`; the build overwrites it
  from the git tag.

## Documentation index

Load only what the task needs.

| File | Content |
|------|---------|
| `.agent_docs/python.md` | Python standards applied here, tooling, config/logging/tracing patterns, documented deviations (sync I/O, click, pptx typing, bandit skips) |
| `.agent_docs/makefile.md` | Every make target, install path overrides, why `install` uses a uv tool |
| `.agent_docs/architecture.md` | Module map, stop sequence and connection registry, save path, export pipeline, browser side, templates and tools, request loop (`request_store.py`, `request_service.py`, `/requests` routes, `editor-requests.js`) |
| `.agent_docs/observability.md` | Log files, console rules, span inventory, OTLP export, JSONL recipes |
| `.agent_docs/testing.md` | Test file map, time limits and slow marker, browser waits and pacing rule, stdio sessions, port range and lifecycle tests, coverage decisions, export regression set |
| `.agent_docs/docker.md` | Image, compose, prod overlay, container checks |
| `.agent_docs/html-conventions.md` | Invariants the exporters and the editor depend on |
| `.agent_docs/agent-editing.md` | Deck service layer (`src/mcp_htmleditor/deck/`: `read`, `scan`, `renumber`, `patch`, `lint`, `tools`): outline, get-slide, the five `patch` operations, lint rules, templates/new/export, the 21 tool surface, scanner and renumbering rules, gotchas |
| `.agent_docs/render.md` | Visual render: picture rules, output directory and cleanup, scale and size rounding, check order, fixtures and install |

Authoring rules for slides and documents live in the skill: run `mcp-htmleditor skill`
(sources in `skill/core.md`, `skill/topics/`, `skill/checks/`). `docs/skill-archive/` keeps the
previous monolithic skill, reference only.

The MCP server exposes twenty one tools, `get_skill`, `outline`, `get_slide`, `patch`, `lint`, `list_templates`, `new_file`, `export`, `history`, `restore`, `list_requests`, `complete_request`, `write_review` and `render` included. A story that registers a tool adds
one `- <name>: <description>` line to the `## Tools` section of `skill/core.md` in the same
story (`skill-audit` fails otherwise); see `.agent_docs/architecture.md`.

Specifications live in `sdlc/specs/SPEC-NNNN-<slug>/` (never modify an existing one, only reference and
flag inconsistencies). Deferred ideas are tracked one per file in `sdlc/backlog/BL-NNNN-<slug>.md`.
