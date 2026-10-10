# mcp-htmleditor core: Design (as-built)

> Spec: SPEC-0001
> Status: as-built
> Generated on: 2026-10-10 at 2521c331564328c9ca35fbfef372586cadbc12dd
> Source: docs/none; legacy spec (see Legacy mapping)

## 1. Components

| Component | Responsibility | Location |
|---|---|---|
| CLI | `templates`, `new`, `serve`, `mcp`, `export`, `skill`, `arch-layout`, `arch-checklist` | `src/mcp_htmleditor/cli.py` |
| MCP server | FastMCP stdio, 7 tools | `src/mcp_htmleditor/mcp_server.py` |
| HTTP server | stdlib threading server: shell, static, content, status, health, export, save, arch layout | `src/mcp_htmleditor/http_server.py` |
| State | Process singleton `EditorState`, persisted to `.mcp_state.json` | `src/mcp_htmleditor/state.py` |
| Templates registry | `TEMPLATES` dict key to bootstrap file, search path | `src/mcp_htmleditor/templates.py:39` |
| Config | pydantic-settings `Settings`, `HTMLEDITOR_*`, XDG, memoized by env signature | `src/mcp_htmleditor/config.py` |
| PPTX export | python-pptx native shapes, CSS resolver, charter chrome | `src/mcp_htmleditor/export/to_pptx.py`, `pptx_style.py`, `pptx_components.py` |
| DOCX export | BeautifulSoup preprocessing, pandoc, patched reference.docx cache | `src/mcp_htmleditor/export/to_docx.py`, `reference_docx.py`, `docx_header_footer.py` |
| Logging / tracing | Rich console + rotating file; OTel JSONL or OTLP/HTTP | `src/mcp_htmleditor/logging_config.py`, `tracing.py` |
| Browser shell | Vanilla JS, iframe renderer, polling | `src/mcp_htmleditor/static/editor.js`, `editor.html` |

## 2. Flows

- Create: `cli.py:84` resolves key, `cli.py:94` refuses existing dest, copies bootstrap, optional serve.
- Agent update: `update_start` sets flag (`mcp_server.py:145`), browser `pollStatus` shows overlay (`static/editor.js:306`), reloads after the flag drops (`static/editor.js:319`).
- Save: `POST /content` (`http_server.py:129`) parses JSON or raw body, rebuilds fragments (`http_server.py:291`), strips artifacts (`http_server.py:294`), skips template paths (`http_server.py:300`), writes under span `file.write` (`http_server.py:306`).
- Port: `find_free_port` (`http_server.py:561`) tries preferred then 7840..7849 (`config.py:287`).
- PPTX: `to_pptx` (`export/to_pptx.py:207`) sets 16:9 (`:238`), `find_slides` (`:272`), body fallback (`:244`), images (`:2211`).
- DOCX: `to_docx` (`export/to_docx.py:97`) preprocesses (`:186`), detects charter (`:230`), `reference_docx_for` (`export/reference_docx.py:330`) caches in `reference_dir`, pandoc via subprocess arg list.

## 3. Interfaces

- HTTP: `GET /`, `/static/<name>` (basename only), `/content`, `/content-frame`, `/status`, `/health`, `/export/pptx`, `/export/docx`; `POST /content`, `POST /arch-layout`; `OPTIONS` 204; CORS `*` (`http_server.py:87`, `:101`, `:129`).
- `/status` body: `mtime`, `update_in_progress`, `filename`, `poll_interval`, `port` (`http_server.py:255`).
- `/health` body: `status`, `version`, `file`, `port` (`http_server.py:423`).
- MCP tools: `start_server(file, port=None)`, `stop_server()`, `get_status()`, `open_file(file)`, `update_start()`, `update_end()`, `layout_arch_diagram(file, diagram_id=None)` (`mcp_server.py:31`..`:166`).
- Template-path save skip answers `{"ok": true, "skipped": "template file is read-only"}` (`http_server.py:302`).

## 4. Data and state

- `.mcp_state.json` next to the edited file: `current_file`, `port`, `server_pid`, `update_in_progress`, `poll_interval` (`state.py:63`). `EditorState.load()` (`state.py:68`) has no production caller.
- reference.docx cache: `<cache>/reference/<charter>-<fingerprint>.docx` (`export/reference_docx.py:347`).
- No database.

## 5. Configuration

| Name | Source | Default | Evidence |
|---|---|---|---|
| `HTMLEDITOR_HOST` | env | `localhost` (container `0.0.0.0`) | `config.py`, `Dockerfile:33` |
| `HTMLEDITOR_PORT` | env, `--port` | 7842, invalid falls back | `config.py:42`, `config.py:113` |
| `HTMLEDITOR_POLL_INTERVAL` | env, `serve --poll` | 1000 ms | `config.py:43`, `cli.py:165` |
| `HTMLEDITOR_TEMPLATES_DIR` | env | `~/.config/mcp-htmleditor/templates` | `templates.py` |
| `HTMLEDITOR_ARCH_CHECKS_DIR` | env | `~/.config/mcp-htmleditor/arch-checks` | `arch_checks.py:39` |
| `HTMLEDITOR_LOG_DIR` / `HTMLEDITOR_LOGS` | env | `<cache>/logs` | `config.py` |
| `HTMLEDITOR_CACHE_DIR`, `HTMLEDITOR_BIN_DIR` | env | `~/.cache/mcp-htmleditor`, `~/.local/bin` | `config.py` |
| `HTMLEDITOR_OTEL_DESTINATION`, `HTMLEDITOR_OTEL_API_KEY` | env | none (JSONL local) | `tracing.py:119`, `tracing.py:174` |

## 6. Observability

Logs: console stderr (Rich) + `<log_dir>/mcp-htmleditor.log` rotating 2 MB x 3 (`logging_config.py:58`).
Spans: `mcp.*`, `export.pptx`, `export.docx`, `export.reference_docx`, `tool.pandoc`, `file.write`, JSONL `<log_dir>/mcp-htmleditor-otel.log` or OTLP/HTTP with Bearer key.

## 7. Decisions (migrated)

| ID | Decision | Evidence | Rationale |
|---|---|---|---|
| DEC-001 | Native HTML render in an iframe, GrapesJS abandoned | `static/editor.html` | Fidelity to source; commit "fix: replace GrapesJS with iframe renderer" |
| DEC-002 | HTTP polling of `/status` (1 s) instead of WebSocket/SSE | `static/editor.js:298` | Simplicity, single local user |
| DEC-003 | Server state persisted to `.mcp_state.json` | `state.py:63` | Survive agent restart (not realized: no reader, BL-0009) |
| DEC-004 | Fixed registry of charters, no plugin system | `templates.py:39` | YAGNI (grew from 5 to 8 entries since) |
| DEC-005 | PPTX via native python-pptx shapes, not screenshots | `export/to_pptx.py` | Editable deliverable |
| DEC-006 | DOCX via pandoc plus patched reference.docx | `export/to_docx.py`, `export/reference_docx.py` | Reuse pandoc conversion |
| DEC-007 | Strip editing artifacts on every save | `http_server.py:443` | Source file stays clean for the agent |
| DEC-008 | Human edits found on disk are intentional, never overwritten; no lock, no merge | AGENTS/skill convention | Simplicity, single user |
| DEC-009 | No CI, `make check` locally plus pre-commit | `Makefile` | Solo project |
| DEC-010 | Configuration only through `Settings` | `config.py:216` | Testability, single source |
| DEC-011 | Fullscreen: `allow-fullscreen` sandbox token, `frame.focus()`, parent key relay | `static/editor.js:103`, `static/editor.js:141` | Two real bugs fixed |
| DEC-012 | Fullscreen zoom via `scale: var(--fs-scale)` on a native 960x540 slide | slide bootstraps | Uniform zoom, no stretch |
| DEC-013 | Split `scale` and `translate` to stop fade-in from overriding zoom | slide bootstraps | No flash on slide change |
| DEC-014 | Auto port 7842 then 7840..7849, one server per process | `http_server.py:561` | Several decks in parallel; registry rejected by user |
| DEC-015 | Carbon slide canvas fixed 960x540 like EI | `templates/bootstrap/slides-empty.html` | Chosen by user; overflowing content now clipped |

## 8. Requirement to code map

| Requirement | Files |
|---|---|
| SPEC-0001/FR-001, FR-002, FR-030 | `cli.py:84`, `cli.py:88`, `cli.py:94`, `templates.py:39` |
| SPEC-0001/FR-003, FR-004 | `static/editor.js:298`, `mcp_server.py:133`, `mcp_server.py:150` |
| SPEC-0001/FR-005, FR-006, FR-007 | `http_server.py:291`, `:294`, `:300`, `:443`, `:499` |
| SPEC-0001/FR-008 | `static/editor.js:1580` |
| SPEC-0001/FR-009, FR-031 | `mcp_server.py:31`..`:166`, `http_server.py:599` |
| SPEC-0001/FR-029, FR-032 | `http_server.py:561`, `:588`, `:643`, `cli.py:178` |
| SPEC-0001/FR-010 | `state.py:63` |
| SPEC-0001/FR-011, FR-012 | `static/editor.js:194`, `templates.py:39` |
| SPEC-0001/FR-013, FR-014, FR-033 | `export/to_pptx.py:238`, `:244`, `:272`, `:2211` |
| SPEC-0001/FR-015..FR-018, FR-034 | `export/reference_docx.py:330`, `:357`, `export/to_docx.py:186`, `:230`, `:249`, `cli.py:277` |
| SPEC-0001/FR-019..FR-023 | `config.py`, `logging_config.py`, `tracing.py` |
| SPEC-0001/FR-024, FR-025 | `http_server.py:423`, `cli.py:39`, `Makefile:186` |
| SPEC-0001/FR-026..FR-028 | `static/editor.js:103`, `:141`, slide bootstraps |

## Legacy mapping

Source: specs/2026-08-07_16-31-00-mcp-htmleditor-retrospective.md (commit 5e22a15)

| Old id | New id | Note |
|---|---|---|
| SC-001..SC-008 | SC-001..SC-008 | kept, rewritten functional |
| FR-001..FR-006, FR-008, FR-011, FR-013..FR-015, FR-017, FR-019..FR-029 | same ids | verified against code |
| FR-007 | FR-007 | legacy "save rejected"; code skips with success marker; BL-0006 |
| FR-009 | FR-009 | legacy "exactly 6 tools"; code has 7 |
| FR-010 | FR-010 | legacy "reloaded at init"; no caller of `load()`; BL-0006, BL-0009 |
| FR-012 | FR-012 | legacy "exactly 5 charters"; code has 8 |
| FR-016 | FR-016, FR-034 | legacy "pandoc absent: default styles, no exception"; code fails explicitly when pandoc missing |
| FR-018 | FR-018 | legacy "PPTX and DOCX"; deck warning not found, scoped to DOCX |
| EXC-001b | FR-030 | legacy "silent overwrite"; code refuses |
| EXC-001a..EXC-008c (others) | folded into FR rows or BL-0006 | |
| E2E-001..E2E-044 | same ids | E2E-006 and E2E-011 now point to existing tests |
| TBD-001 | FR-030 | resolved by code |
| TBD-002, TBD-003, TBD-004 | BL-0010 | untested requirements |
| TBD-005, TBD-006, TBD-007, TBD-009 | BL-0006 | open questions, kept as evidence |
| TBD-008 | BL-0005 | unauthenticated server exposed in container |
| TBD-010 | dropped | resolved |
| TBD-011 | BL-0007 | reference decks without fullscreen |
| DEC-001..DEC-015 | DEC-001..DEC-015 | kept |
| Sections 7, 8, 10, 11 (legacy) | sections 1 to 6 here | mechanism moved to design |
