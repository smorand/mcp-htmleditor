# Tests

```bash
make test                 # pytest -v
make test ARGS='-k pptx'  # subset
make test-cov             # coverage, gate 80 %
```

`make sync` also runs `playwright install chromium` (no-op if already cached) so the
browser E2E tests below can run without a manual step.

`pythonpath = ["src"]` makes the suite read the working tree. Without it a previously
installed non editable copy shadows `src/` and the suite silently measures old code.

## Files

| File | Covers |
|------|--------|
| `conftest.py` | `reset_settings` (autouse, drops the memoized `Settings`), `reset_state` / `fresh_state` (EditorState singleton), `html_file` |
| `test_config.py` | Backward compatible accessors: XDG defaults, env overrides, invalid port |
| `test_settings.py` | The `Settings` model: defaults, memoization per environment signature, `HTMLEDITOR_LOG_DIR` over `HTMLEDITOR_LOGS`, `~` expansion, blank value means unset, OTel fields, unknown prefixed variable ignored |
| `test_logging_config.py` | Handler installation, stderr console, `omit_repeated_times=False` plus a rendering check that two consecutive lines both carry a timestamp, file output, idempotence, noisy loggers pinned, unwritable log dir degrades to console only |
| `test_tracing.py` | JSONL serialization, parent/child links, span without end, export failure, `configure_tracing` idempotence, exception recording |
| `test_state.py` | EditorState singleton, persistence, mtime |
| `test_http_helpers.py` | `_strip_editor_artifacts`, `_rebuild_full_html` |
| `test_http_assets.py` | `data-asset-*` preservation when rebuilding a document |
| `test_http_health.py` | `/health` payload (status, version, file, port) |
| `test_templates.py` | Registry and search path resolution |
| `test_skill_content.py` | `mcp-htmleditor skill` assembly |
| `test_export_pptx.py` | Slide detection on all templates, no `<script>` or shell text in the output, base64 and relative images, table spans and column widths, Gantt geometry, arch node shapes, annotation placement, geometry and style helpers |
| `test_export_docx.py` | HTML preprocessing (single title), charter detection, `word/styles.xml` patching, header and footer parts, cache and fallbacks, end to end pandoc exports guarded by `skipif` when pandoc is absent |
| `test_fullscreen_e2e.py` | SC-008 / FR-026-028 (see retrospective spec): fullscreen presentation mode via a real `ThreadingHTTPServer` + real headless Chromium (`pytest-playwright`). Toolbar/nav-arrow hiding, slide filling the screen, keyboard navigation independent of focus, the parent-side fallback CSS safety net, and exit-preserves-position. Guarded by `skipif` when Chromium is not installed |

### Browser E2E (`test_fullscreen_e2e.py`)

Uses `pytest-playwright`'s `page` fixture (headless by default) against a real
`start_http_server()`/`stop_http_server()` instance on a free port, serving a 3-slide
deck built from the real `templates/bootstrap/slides-ei-empty.html` (never the
`~/.config` installed copy: the fixture forces `HTMLEDITOR_TEMPLATES_DIR`). Reaches into
the content iframe's own document via `document.getElementById('content-frame').
contentDocument` since the slide template's `:fullscreen` CSS and `navigate()`/
`goToSlide()` globals live there, not in the parent shell.

One known Playwright/CDP limitation: headless Chromium under automation does not
reliably enforce a `sandbox` iframe missing `allow-fullscreen` the way a real,
interactively-driven browser does (verified empirically), so the exact permission
denial that caused the original bug cannot be forced end to end in this suite. The test
instead exercises the deterministic part of the contract: the parent-side CSS safety net
(`body:has(#content-frame:fullscreen) #toolbar` in `editor.css`) that must hide the shell
toolbar if the fallback (fullscreening the `<iframe>` element itself) is ever taken, for
whatever reason.

This differs from `tools/check_ei_insert.py`, which stays a manual, screenshot-based
visual check (its own docstring explains why it is not a unit test): the fullscreen
contract is fully assertable (computed styles, `fullscreenElement`, counters), so it
belongs in the automated suite and in `make check` instead.

`trace.set_tracer_provider()` accepts one call per process, so `test_tracing.py` shares a
single session scoped configuration for the tests that need the global tracer and uses a
local `TracerProvider` for the exporter internals.

## Coverage

Gate 80 %, actual around 95 %. Omitted: `cli.py`, `mcp_server.py`, `__main__.py` (thin
wrappers). `# pragma: no cover` marks the `_EditorHandler` network class and the server
lifecycle functions in `http_server.py`.

## Validating an export change

Never trust the slide count alone, look at the pixels:

```bash
mcp-htmleditor export pptx pres.html /tmp/out.pptx
soffice --headless --convert-to pdf /tmp/out.pptx --outdir /tmp/
pdftoppm -jpeg -r 72 /tmp/out.pdf /tmp/slide   # then read /tmp/slide-N.jpg
```

Regression set (expected slide counts):

| File | Slides |
|------|--------|
| `templates/reference/slides/euro-information.html` | 3 |
| `templates/reference/slides/example-ei-complete.html` | 9 |
| `templates/reference/slides/ibm-carbon.html` | 9 (no `data-type`) |
| `templates/reference/slides/example-carbon-complete.html` | 9 |
| `templates/reference/slides/presentation-standard.html` | 4 (legacy `<section>`) |
| `templates/reference/slides/roadmap-one-pager.html` | 1 (gantt with `margin-left`) |

To prove an internal refactor did not move a single shape, export with the previous
revision in a throwaway worktree and compare the shape fingerprints:

```bash
git worktree add /tmp/ht-baseline HEAD
# export with /tmp/ht-baseline/src on sys.path, then compare
# (name, shape_type, left, top, width, height, text) tuples slide by slide
git worktree remove /tmp/ht-baseline --force
```

For DOCX, compare the `<w:t>` runs and the `w:pStyle` sequence of `word/document.xml`
between the two exports.
