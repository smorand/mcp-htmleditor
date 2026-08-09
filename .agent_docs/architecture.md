# Architecture

Single page HTML is the source of truth. The browser renders the file as is inside an
iframe, the LLM agent writes the file on disk, the browser notices the new mtime and
reloads. No build step, no framework, no database.

```
LLM agent ──MCP(stdio)──▶ mcp_server ──▶ state ◀── http_server ◀──HTTP──▶ browser
                                          │                                 │
                                          ▼                                 ▼
                                    .mcp_state.json                  file.html (disk)
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
| `state.py` | `EditorState` singleton (current file, port, pid, poll interval, update flag) plus `.mcp_state.json` persistence next to the edited file |
| `http_server.py` | `ThreadingHTTPServer`. Routes: `/`, `/static/*`, `/content` (GET raw, POST save), `/content-frame`, `/status` (polling), `/health` (status + version). Binds `HTMLEDITOR_HOST` (localhost by default, `0.0.0.0` in a container) |
| `mcp_server.py` | FastMCP, 6 tools, each traced as `mcp.<tool>` |
| `cli.py` | click group with `-v/-q` and `--version`; subcommands `templates`, `new`, `serve`, `skill`, `mcp`, `export`. Subcommand imports are lazy on purpose to keep startup fast |
| `templates.py` | Template registry (key to bootstrap file) and search path resolution |
| `skill_content.py` | Assembles the `mcp-htmleditor skill` output from `skill/` |

`_EditorHandler` and the server lifecycle functions are the I/O boundary and are marked
`# pragma: no cover`; the pure helpers next to them (`_strip_editor_artifacts`,
`_rebuild_full_html`, `health_payload`) are fully tested.

## Save path

The editor posts the whole document. Before writing, the server strips everything the
browser injected (format bar, insert bar, style tag, context menu host, drag handles,
drop indicator, `contenteditable`, `_mcp_*` classes, browser extension attributes) and
clears the generated `#slide-select` options, so the file on disk stays clean for the
next agent. A save targeting `templates/bootstrap/` or `templates/reference/` is
ignored: those files are meant to be copied, not edited. The write itself is traced as
`file.write` with the path and the size.

## Export pipeline

| Module | Role |
|--------|------|
| `export/to_pptx.py` | HTML to PPTX. Slide detection (`data-type="slide"` on any tag, `article.slide` fallback), per charter chrome, vertical block flow, one renderer per component (text, grid, panel, table, gantt, arch diagram, annotated image, image, hbar). Returns an `ExportReport` (slide count, charter, warnings); the CLI prints it and exits non zero when nothing was exported. Traced as `export.pptx` |
| `export/pptx_style.py` | `Box` geometry in inches on the 960x540 canvas (1 CSS px = 1 pt), CSS parsing (lengths, colours, custom properties), `Theme` charters (ei / carbon / generic), `TextStyle` scale per class, `StyleResolver` |
| `export/pptx_components.py` | Pure helpers: `TableGrid` (colspan/rowspan occupancy, column widths), Gantt period maths, CSS transform composition, table cell borders, theme style removal (python-pptx has no API for those) |
| `export/to_docx.py` | HTML to DOCX through pandoc `-f html`. Lifts `.doc-title` / `.doc-subtitle` into pandoc metadata so the title is emitted once, applies the charter with `--reference-doc`, reports SVG and pandoc warnings. Traced as `export.docx`, the pandoc run as `tool.pandoc` |
| `export/reference_docx.py` | Generates a charter `reference.docx` by patching `word/styles.xml` of pandoc's own default, cached in `<cache dir>/reference/` and keyed by a fingerprint of the charter plus the pandoc version. Charters `perso` and `ei` |
| `export/docx_header_footer.py` | Builds `word/header1.xml` / `word/footer1.xml` (plus their relationships, media and page geometry) so the HTML letterhead becomes a real repeated Word header instead of body paragraphs |
| `export/docx_assets.py` | Base64 assets embedded in the generated reference documents (EI logo), kept as Python so a plain wheel ships them |

## Browser side (no build step)

| File | Role |
|------|------|
| `static/editor.html` | Iframe shell plus toolbar |
| `static/editor.js` | Polling, rich text toolbar, slide insert, document block insert before/after, image embed as base64, drag reorder of document blocks, mouse move of arch nodes (`data-x`/`data-y` in %) |
| `static/slide-layouts.js` | Per template slide layouts (`LAYOUT_SETS.carbon`, `.ei`) |
| `static/doc-blocks.js` | Document block definitions (title, subtitle, h1 to h5, paragraph, table, list) |
| `static/editor.css` | Toolbar, overlay and picker styles |

Validate JS with `node --check src/mcp_htmleditor/static/*.js`.

### Fullscreen presentation mode (gotcha)

The present button fullscreens the *inner* document (`frame.contentDocument.
documentElement`), not the `<iframe>` element, so the slide template's own
`:fullscreen .toolbar/.nav-arrow/.slide` CSS (defined inside the served HTML,
not in `editor.css`) is what hides the nav bar and resizes the slide to fill
the screen. Two things are required for this to work, both easy to regress:

- The `<iframe>` in `editor.html` needs `sandbox="... allow-fullscreen"`
  (plus `allow="fullscreen"` / `allowfullscreen` for older engines). A
  sandboxed iframe without `allow-fullscreen` silently denies
  `requestFullscreen()` on its content; `editor.js` then falls back to
  fullscreening the `<iframe>` element itself in the *parent* document,
  where the slide template's `:fullscreen` CSS never matches anything
  (wrong document) — the toolbar stays visible and the slide keeps its
  normal padded size.
- Entering fullscreen does not move keyboard focus into the iframe, so the
  slide template's own arrow-key `keydown` listener (`navigate()`) never
  fires if focus stays on the outer `#present-btn`. `editor.js` calls
  `frame.focus()` after fullscreen is granted, and additionally forwards
  arrow/space/escape keydowns from the *parent* document straight into the
  iframe's `navigate()`/`goToSlide()` globals whenever `document.
  fullscreenElement` is set, so navigation works regardless of which
  document actually holds focus in a given browser.

## Templates and tools

Template resolution order: `HTMLEDITOR_TEMPLATES_DIR`, then
`~/.config/mcp-htmleditor/templates/` (written by `make install`), then `<repo>/templates/`.
After editing anything under `templates/`, either run `make install` or export
`HTMLEDITOR_TEMPLATES_DIR=$PWD/templates`, otherwise the installed copy wins and the
change looks like it did nothing.

`templates/bootstrap/slides-ei-empty.html` is generated by `make bootstrap-ei`
(`tools/gen_ei_bootstrap.py`) from `templates/reference/slides/euro-information.html`:
the reference is the single source of the EI charter CSS. Never hand edit the bootstrap.

`tools/check_ei_insert.py` drives a real browser (playwright) to check EI slide
insertion (footer logo, `.logo-disc`, renumbering) and writes PNG captures. It stays
out of `make check` on purpose. Run it after touching the EI bootstrap,
`slide-layouts.js` or `renumberSlides` / `resolveTemplateAssets`.

## LLM workflow

```
update_start() → write the HTML file → update_end()
```

`update_start()` raises the overlay in the browser and suppresses mtime reloads,
`update_end()` clears it and lets the next poll reload the content. Never write the file
without those flanking calls.
