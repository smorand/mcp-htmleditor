# Architecture

Single page HTML is the source of truth. The browser renders the file as is inside an iframe, the LLM agent writes
the file on disk, the browser notices the new mtime and reloads. No build step, no framework, no database.

```
LLM agent ──MCP(stdio)──▶ mcp_server ──▶ state ◀── http_server ◀──HTTP──▶ browser
                                          │                                 │
                                          ▼                                 ▼
                                  state dir (history)               file.html (disk)
                                                                            │
                                                             export/ ──▶ .pptx / .docx
```

## Core modules

| Module | Role |
|--------|------|
| `config.py` | `Settings` (pydantic-settings) plus the path/scalar accessors used everywhere |
| `logging_config.py` | `setup_logging()`: rich console on stderr, rotating file in the log dir |
| `tracing.py` | `configure_tracing()`, `trace_span()`, `JsonlSpanExporter` |
| `version.py` | `__version__`, written at build time from the git tag |
| `state.py` | `EditorState` singleton (current file, port, pid, poll interval, update flag) plus per file records in the state directory (`HTMLEDITOR_STATE_DIR`), the update flag expiring after 120 s |
| `fileio.py` | `atomic_write(path, data, reason=, history=)`: temp file, fsync, rename; snapshots the previous content first when a `reason` is given; `WriteError` |
| `history.py` | `HistoryStore` (20 versions per file under `<state>/files/<key>/history/`), `list_versions`, `restore_version`, `HistoryError`; used by the `history` / `restore` commands and tools |
| `http_server.py` | `ThreadingHTTPServer`. Routes: `/`, `/static/*`, `/content` (GET raw, POST save), `/content-frame`, `/download` (the loaded file byte for byte, `Content-Type: text/html; charset=utf-8`, `Content-Disposition: attachment` with an ASCII `filename` and a percent encoded `filename*`, `no-store`, no state write; 404 `No file loaded` without a file; same host and origin gate as `/status`), `/status` (polling), `/health` (`ok`, `status`, `pid`, `file`, `page`, `port`, `version`, `started` UTC ISO, `uptime_seconds`; no file read, no write, open to any host; `file`/`page` null without a file; agents use it to check which file a running server serves and its pid), `/export/pptx`, `/export/docx`, `POST /arch-layout`, `GET /requests`, `POST /requests`, `POST /requests/delete`, `POST /review/apply`; `/status` also carries `requests_revision` (0 when the record is absent or unreadable). Binds `HTMLEDITOR_HOST` (localhost by default, `0.0.0.0` in a container). Request gate (2026-10-10, SPEC-0005): every route but `/health` answers 403 unless the `Host` name is `localhost`, `127.0.0.1`, `[::1]` or the bind host (port ignored), and any `Origin` is exactly `http://<Host>`; no CORS headers are ever sent |
| `mcp_server.py` | FastMCP, 22 tools (`start_server`, `stop_server`, `get_status`, `open_file`, `update_start`, `update_end`, `layout_arch_diagram`, `get_skill`, `outline`, `get_slide`, `patch`, `lint`, `list_templates`, `new_file`, `export`, `history`, `restore`, `list_requests`, `clear_requests`, `complete_request`, `write_review`, `render`), each traced as `mcp.<tool>`; `registered_tool_names()` lists them |
| `cli.py` | click group with `-v/-q` and `--version`; subcommands `templates`, `new`, `serve`, `skill`, `skill-audit`, `mcp`, `export`. Subcommand imports are lazy on purpose to keep startup fast |
| `request_store.py` | `RequestStore`, `Record`, `Request`, `Suggestion`: one `record.json` per file in `<state>/files/<key>/requests/` (`<key>` = `sha256(realpath)[:32]`, the SPEC-0009 key). Layout: `version`, `file`, `revision`, `next_id`, `requests`, `review`. `update()` takes an exclusive `fcntl.flock` on the sibling `record.lock`, applies the change and writes with an atomic rename; reads take no lock; an invalid record raises and is never reset. `fcntl` only (macOS, Linux, Docker) |
| `request_service.py` | `RequestService` and `RequestError(kind, message)`: queue, list, `list_positioned` (adds `position`, the 1 based index of the slide's `data-id` in the file read at list time, null when none or gone; optional `slide`/`status` filters; nothing stored, `/requests` unchanged), `clear` (scope `finished` or `all`, through `RequestStore.update`, no revision bump when nothing is removed; tool `clear_requests`, CLI `request-clear [--all]`, no HTTP route or UI), complete, delete, apply a suggestion, write and read the review. All rules and messages live here; the routes map `kind` to a status, the tools raise `ToolError(message)`, the commands print `error: <message>` (parity by construction). Nothing is created next to the user's file |
| `templates.py` | Template registry (key to bootstrap file) and search path resolution |
| `deck_files.py` | `deck_file(current_file, raw_path)`: the file next to the open deck a GET names, or `None` (reserved first segments, hidden segments, NUL, lexical `..` above the folder, resolved location outside it, types of `DECK_FILE_TYPES`); `http_server._serve_deck_file` answers it after the gate with nosniff and an SVG sandbox (SPEC-0023) |
| `breathe/inline.py` | `embed_assets(file, link=)`: the `breathe-inline` command; checks in the spec order before any read or write; bundled catalogue `templates/assets/breathe`; history reason `breathe-inline` |
| `skill_content.py` | `SkillLibrary`: core (`skill/core.md`, 7000 bytes max), 17 topics (`skill/topics/<t>.md`, 8000 max), `--all`; `arch-qa` appends the checklist (user one if any, else the shipped `skill/checks/`) |
| `skill_audit.py` | `run_audit`, `find_stale`, `listed_tools`: sizes, budgets, core `## Tools` lines versus `registered_tool_names()`, stale statements in core, topics and routing skill |

`_EditorHandler` and the server lifecycle functions are the I/O boundary and are marked `# pragma: no cover`; the
pure helpers next to them (`_strip_editor_artifacts`, `_rebuild_full_html`, `health_payload`) are fully tested.

## Request gate

SPEC-0013 (US-0071): `_refuse_untrusted_request` runs on every `GET` except `/health` and every `POST`, unknown
paths included, and starts with `_refuse_ambiguous_headers`. Its order is fixed: a folded header value (`\r` or
`\n` inside, the stdlib keeps the continuation line), a repeated `Host`, `Origin`, `Content-Length` or
`Content-Type` (first repeated name in that order, even when the lines are identical), any `Transfer-Encoding`, a
`Host` holding `@`. Each answers `400` through `_refuse_request`, logs one warning `Refused <METHOD> <path>: <error>`
(no header value, no body) and reads no body. Only then come the SPEC-0005 host and origin checks (403). `OPTIONS`
(405) and other methods (stdlib 501) stay outside the gate. Tests send raw bytes with `tests/http_support.py`
(`exchange`, `RawReply`, `json_body`) because a standard client merges duplicated headers.

## Time bounds

SPEC-0013: `http_deadline.py`. `DeadlineReader` waits at most `WAIT_SECONDS` (30 s) per byte and cuts the request
`TOTAL_SECONDS` (300 s) after the connection's first byte (`_arm`: min of wait and total left; injected `clock`),
receiving the request only, not running it nor the answer (`DeadlineWriter`: a wait per chunk). `RequestTimeout`
with bytes answers `408` plus one `Refused` warning, without bytes it closes silently. The constants are a test
seam, never a setting.

## Stop sequence

SPEC-0014 (US-0082): `stop_http_server` clears the globals under `_server_lock`, then
`shutdown()` (ends the loop only), `server_close()` (closes the listener: connect refused, port rebindable at once
thanks to the stdlib `allow_reuse_address`; daemon handler threads, nothing joined), `connections.close_idle()`.
`http_connections.ConnectionRegistry` (one per `_EditorServer`, one lock): `setup` adds the socket (shut at once
when already closing), `parse_request` marks it busy once line and headers are complete (refused unanswered when
closing), `handle_one_request` ends it in a `finally`, `finish` removes it. Idle sockets get `shutdown(SHUT_RDWR)`:
the blocked `recv` returns `b""` (a `close()` from another thread does not wake it, checked on macOS). Busy ones
answer, then close. Gotcha: a connection still in the listen backlog at the stop is reset by the kernel.

## Save path

The editor posts the whole document. Before writing, the server strips everything the browser injected (list in
`html-conventions.md` § Editor artifacts, plus `_mcp_*` classes) and clears the generated `#slide-select` options,
so the file on disk stays clean for the next agent. A save targeting `templates/bootstrap/` or
`templates/reference/` is ignored: those files are meant to be copied, not edited. The 409 check (`base_mtime`) and
the write run in one process only; an agent or another process writing the file directly is not covered. The write
is `fileio.atomic_write` with reason `browser-save` (`keep-mine` when forced), traced as `file.write`; the
previous content goes to the history first (`history.snapshot`) and is discarded if the replace fails.
`patch` and `restore` use the same writer (reasons `patch`, `restore`).

## Export pipeline

| Module | Role |
|--------|------|
| `export/to_pptx.py` | HTML to PPTX entry point. Keeps `ExportReport` (re-exported from `pptx_model.py`), `to_pptx`, `_build_pptx`, `find_slides` and the composed `_SlideBuilder` (`__init__`, `build`, `_slide_kind`), built from the mixins below. Slide detection (`data-type="slide"` on any tag, `article.slide` fallback). Returns an `ExportReport` (slide count, charter, warnings); the CLI prints it and exits non zero when nothing was exported. Traced as `export.pptx` |
| `export/pptx_model.py` | Shared model: `ExportReport`, `_Context`, `_Block`, `_Column`, `_Region`, `_Para`, column width helpers and `_BuilderBase`, the base class of every mixin (declares the shared instance attributes and stubs for cross mixin calls) |
| `export/pptx_text.py` | `TextMixin`: HTML elements to styled paragraphs and runs, text frames, rectangle and textbox primitives |
| `export/pptx_images.py` | `ImagesMixin`: annotated images, plain images, picture primitives (source decoding, aspect probing, insertion) |
| `export/pptx_vectors.py` | Pure per slide pre pass `vector_figure_warnings(slide, number)` called by `to_pptx` before each slide build: one warning per inline `<svg>` or vector `<img>` (`.svg` or `data:image/svg`), skipping nested svg and figures under button, script, template, noscript, select; reuses `to_docx.SVG_ADVICE`. `pptx_images._image_source` returns `None` silently for a vector `src` (2026-11-08, SPEC-0016) |
| `export/pptx_arch.py` | `ArchMixin`: `_render_arch`, nodes as native shapes, edges as segments, arrow tips, step badges, labels |
| `export/pptx_gantt.py` | `GanttMixin`: Gantt head, bars, legend, plus the class-free fallback `_is_inline_gantt`: structural detection of a hand-authored, fully inline-styled Gantt, see `skill/topics/gantt.md` § Variante |
| `export/pptx_blocks.py` | `BlocksMixin`: block measurement and renderers (grid, panel, table, rule, hbar) and the block dispatcher |
| `export/pptx_flow.py` | `FlowMixin`: vertical block flow and flex rows. A generic `display:flex` row of 2+ sized columns (`_is_flex_row` / `_flex_row_block`, checked structurally, no marker attribute) is split into independent `_Region`s that each recurse through the normal flow, so a column shrinks-to-fit on its own; a column with no resolvable `flex`/`flex-basis`/`width` hint falls back to the ordinary single column flow (`_column_widths` returns `None`), and a column carrying its own `data-type` keeps its own renderer |
| `export/pptx_chrome.py` | `ChromeMixin`: per charter chrome (EI, Carbon, medical with `_chrome_medical`, Breathe degraded `_chrome_breathe`, generic): backgrounds, frames, footers, content regions |
| `export/pptx_paint.py` | Breathe painted finish, called by `to_pptx` after the flowed build: `measure` (Chromium, worker thread, remote requests aborted), `Painter` (background, rects, pictures, no wrap text boxes); `PaintUnavailable(reason)` gives the degraded warning |
| `export/charters.py` | `REGISTRY`, a tuple of `CharterSpec` (key, kind, template, description, detection tokens, DOCX key). Stdlib only. Read by `templates.py` (`TEMPLATES`), `pptx_style.detect_theme` and `reference_docx.charter_for`. The JavaScript detector in `static/slide-layouts.js` stays; parity is tested by `tests/test_charter_detection.py` |
| `export/pptx_style.py` | `Box` geometry in inches on the 960x540 canvas (1 CSS px = 1 pt), CSS parsing (lengths, colours, custom properties), `Theme` charters (ei / carbon / medical / generic), `TextStyle` scale per class (`_CLASS_STYLES`) and per theme tag defaults (`_THEME_TAG_STYLES`, used by the medical charter whose body scale is stated on descendant selectors), `StyleResolver`. The resolver indexes three rule shapes: `.name`, `.name.variant` (applied only when the element carries every class of the compound) and `.a.b .name` (applied only when `active_scope`, set per slide from the article's classes, contains the ancestor classes). That is what makes `.slide.dark .med-caption` reach the right elements without leaking, and `.cds-notification.error` stop leaking onto plain notifications |
| `export/pptx_components.py` | Pure helpers: `TableGrid` (colspan/rowspan occupancy, column widths), Gantt period maths, CSS transform composition, table cell borders, theme style removal (python-pptx has no API for those) |
| `export/to_docx.py` | HTML to DOCX through pandoc `-f html`. Lifts `.doc-title` / `.doc-subtitle` into pandoc metadata so the title is emitted once, applies the charter with `--reference-doc`, reports SVG and pandoc warnings. Traced as `export.docx`, the pandoc run as `tool.pandoc` |
| `export/reference_docx.py` | Generates a charter `reference.docx` by patching `word/styles.xml` of pandoc's own default, cached in `<cache dir>/reference/` and keyed by a fingerprint of the charter plus the pandoc version. Charters `perso` and `ei` |
| `export/docx_header_footer.py` | Builds `word/header1.xml` / `word/footer1.xml` (plus their relationships, media and page geometry) so the HTML letterhead becomes a real repeated Word header instead of body paragraphs |
| `export/docx_assets.py` | Base64 assets embedded in the generated reference documents (EI logo), kept as Python so a plain wheel ships them |

## Browser side (no build step)

| File | Role |
|------|------|
| `static/editor.html` | Iframe shell plus toolbar |
| `static/editor-undo.js` | Undo and redo: whole document snapshots, key handling, button state |
| `static/editor-edit.js` | Edit mode: injection and removal of `contenteditable`, editor styles |
| `static/editor-format.js` | Floating format bar, insert bar, image embed as base64, table and link insert |
| `static/editor-menus.js` | Context menus, table row and column actions, arch node add, remove, rename, connect |
| `static/editor-save.js` | Client side save (`saveContent`) |
| `static/editor-slides.js` | Slide picker, insert, delete, `renumberSlides` |
| `static/editor-blocks.js` | Document block picker and insert before or after |
| `static/editor-drag.js` | Drag reorder of document blocks, mouse move of arch nodes (`data-x`/`data-y` in %) |
| `static/editor-width.js` | Text width bar (SPEC-0015): `#width-bar` and `#width-readout` live in the shell page, never in the framed document; drag, keys, reset; `withWidthPreviewSuspended`. Hooks: `widthBarAttach`/`widthBarDetach` in `editor-edit.js`, the suspended clone in `editor-save.js`, the suspended `outerHTML` in `editor-undo.js`, `widthBarOnFrameLoad`, `widthBarOnAgentUpdate` and `widthDragActive` (no external-change reload during a drag) in `editor.js` |
| `static/editor-requests.js` | Ask AI panel (`#ask-ai-btn`, `#ask-ai-panel`), side list `#requests-side` (`Requests (n)`), suggestion Apply buttons; polls `requests_revision` from `/status` and refetches `GET /requests` when it moves |
| `static/editor.js` | State declarations, start up block, polling; loaded last |
| `static/slide-layouts.js` | Per template slide layouts (`LAYOUT_SETS.carbon`, `.ei`) |
| `static/doc-blocks.js` | Document block definitions (title, subtitle, h1 to h5, paragraph, table, list) |
| `static/editor.css` | Toolbar, overlay and picker styles |
| all `static/*.js` | Validate with `node --check src/mcp_htmleditor/static/*.js` |

### Fullscreen presentation mode (gotcha)

The present button fullscreens the inner document (`frame.contentDocument.documentElement`), not the `<iframe>`, so
the template's own `:fullscreen` CSS (`html-conventions.md` § Fullscreen presentation mode) hides the nav bar and
resizes the slide. Two things must hold:

- The `<iframe>` in `editor.html` needs `sandbox="... allow-fullscreen"` (plus `allow="fullscreen"`). Without it
  `requestFullscreen()` is silently denied and `editor.js` falls back to fullscreening the `<iframe>` itself,
  where the template CSS never matches.
- Fullscreen does not move focus into the iframe, so `editor.js` calls `frame.focus()` once granted and forwards
  arrows, space, `Home`, `End` and `Escape` from the parent into the iframe's `navigate()` / `goToSlide()` while
  `document.fullscreenElement` is set; `End` counts `[data-type="slide"]` and calls `goToSlide(count - 1)`
  because `TOTAL` is a `const`, not a window property.

### Presentation pointer (SPEC-0017)

The pointer is deck code (one block in every presentation template, see `.agent_docs/html-conventions.md` §
Presentation pointer). The editor only relays: `#pointer-btn` (`editor.js`, shown only when `deckCarriesPointer()`,
so a deck made before the pointer has none), the L key forwarded to `togglePointer()` except in edit mode,
`setPointerAllowed(!editMode)` from `editor-edit.js`, and `editor-save.js` strips `#deck-pointer-layer` and
`data-deck-pointer` from the save's detached clone, like `data-fs-current`.

### Shell pieces of SPEC-0022 (2026-05)

* `#requests-toggle` (toolbar) opens `#requests-side`, closed by default, `aria-expanded` and `aria-controls` in sync,
  label `Requests (n)` (`editor-requests.js`).
* `#notes-btn` and `#notes-panel` (`editor-notes.js`): bottom textarea bound to the current slide's aside, writes it
  (created when missing, removed when emptied) and schedules the normal save; relays the change to an open presenter.
* `#presenter-btn` calls the deck's `togglePresenter()`. The shell accepts `{type:'deck-key', key:'e'}` only when
  `event.source === frame.contentWindow`; keys typed in the shell itself are forwarded to the deck for F P S.
* Shortcuts help (2026-11-14): `#help-btn` (icon, last toolbar control) toggles `#help-panel` (static table in `editor.html`, code in
  `editor.js`: `toggleHelp`, `setHelpOpen`). `?` from the shell (`onShellKey`) or `{type:'deck-key', key:'?'}` from the framed deck
  (`onDeckMessage`, `event.source` checked) toggles it; hidden in full screen. A new shortcut means a row in that table.
* Icon toolbar (2026-11-14): every `#toolbar` control is an SVG icon (`.tb-btn`) with `aria-label`, `data-tip` and optional `data-keys`, no `title`.
  One shared `#tb-tip` is filled by `initToolbarTips()` (`editor-menus.js`); the 1 s delay is the CSS `transition-delay` of `#tb-tip.armed`. JS that renames
  a control sets `data-tip` and `aria-label`. `#requests-badge` holds `(n)`; `#download-btn` is `<a href="/download" download>` before `#help-btn`. Guard: `tests/test_toolbar_icons_e2e.py`.
* The iframe `sandbox` gains `allow-popups allow-popups-to-escape-sandbox` so the presenter and its previews can open.
* PPTX export of the notes: `.agent_docs/html-conventions.md` § Speaker notes.

## Templates and tools

Template resolution order: `HTMLEDITOR_TEMPLATES_DIR`, then `~/.config/mcp-htmleditor/templates/` (written by
`make install`), then `<repo>/templates/`. After editing anything under `templates/`, either run `make install` or
export `HTMLEDITOR_TEMPLATES_DIR=$PWD/templates`, otherwise the installed copy wins and the change looks like it
did nothing. `templates/bootstrap/slides-ei-empty.html` is generated by `make bootstrap-ei`
(`tools/gen_ei_bootstrap.py`) from `templates/reference/slides/euro-information.html`, the single source of the EI
charter CSS: never hand edit the bootstrap. `tools/check_ei_insert.py` drives a real browser (playwright) to check EI slide
insertion (footer logo, `.logo-disc`, renumbering) and writes PNG captures; it stays out of `make check` on
purpose. Run it after touching the EI bootstrap, `slide-layouts.js` or `renumberSlides` / `resolveTemplateAssets`.

**`mail` template.** Document family charter (`data-doc-template="mail"`). Email clients ignore `<head><style>`,
so every colour and spacing that matters is inline `style=""` and the layout is nested `<table>` (no flexbox, grid
or `position:absolute`). `charter_for("mail")` returns `None`: no `reference.docx`, a mail is sent as is. Blocks
from the `+ Bloc` picker land unstyled; clone a styled section instead (`skill/topics/mail.md`).

**`website` template.** `data-doc-type="website"` is tracked by an `isWebsite` flag in `editor.js`: it reuses the
document block insert and drag machinery (`article[data-type="document"]`) but shows neither export button
(`updateDocActionsVisibility()` gates the block toolbar on `isDocument || isWebsite` and the DOCX button on
`isDocument`). No exporter reads `data-doc-type`; a CLI export of a website file is not defended against. See
`skill/topics/website.md`.

## LLM workflow

`update_start()` → write the HTML file → `update_end()`. `update_start()` raises the overlay in the browser and
suppresses mtime reloads, `update_end()` clears it and lets the next poll reload the content. Never write the file
without those flanking calls.

SPEC-0012 (DEC-001, DEC-002): the `_SlideBuilder` mixins of § Export pipeline inherit `_BuilderBase`, which stubs
every method called across mixins (strict typing without `type: ignore`). The editor is split into classic scripts,
not ES modules, so `file://` and the global function names keep working. Load order is fixed in `editor.html`:
`slide-layouts.js`, `doc-blocks.js`, `editor-undo.js`, `editor-edit.js`, `editor-format.js`, `editor-menus.js`,
`editor-save.js`, `editor-slides.js`, `editor-blocks.js`, `editor-drag.js`, `editor-requests.js`, `editor.js`. The
top level `let` and `const` of `editor.js` are touched by the other scripts only inside functions.

SPEC-0006 (US-0034), progressive skill: `mcp-htmleditor skill` prints the core, `--type <t>` one topic, `--all` the
core then the 17 topics; `get_skill(type=None)` returns the same text over MCP (this superseded SPEC-0001 FR-009
without editing it). Test seams: `HTMLEDITOR_SKILL_DIR` points at another skill tree, `HTMLEDITOR_ROUTING_SKILL` at
another routing skill file (the installed `~/.pi/agent/dynamic-skills/html-editor/SKILL.md` wins when the variable
is unset and the file exists, else the source tree one is checked). Tool line rule (DEC-010): a story that
registers a tool adds one `- <name>: <description>` line to the `## Tools` section of `skill/core.md` in the same
story, otherwise `skill-audit` reports it. The skill text never states a tool count. The old skill is frozen in
`docs/skill-archive/`.

## Deck service layer (`deck/`, `fileio.py`)

| Module | Role |
|--------|------|
| `deck/__init__.py` | `Deck`, `DeckError`, `load_deck(file)` and `deck_from_text(file, text)` (parse text without the disk), charter and type detection |
| `deck/scan.py` | Tag scanner with source offsets, image hiding, slide ranges |
| `deck/read.py` | `outline` (per slide `problems` = lint count, warnings included, whole file problems excluded) and `get_slide` |
| `deck/patch.py` | `apply_patch`: atoms with `touched`, one atomic write; `problems` = lint of the assembled, renumbered text restricted to touched slides |
| `deck/renumber.py` | Renumbering of ids, counters, `TOTAL`, `slideNames` after a structural patch |
| `deck/lint.py` | `lint_deck`, `Problem`, rules L001 to L006, reports |
| `deck/charter_rules.py` | Charter rules L007 to L011 |
| `deck/tools.py` | `create_file`, `export_file`, `template_listing` |
