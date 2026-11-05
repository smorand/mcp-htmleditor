# Visual render (SPEC-0008)

Package `src/mcp_htmleditor/render/`: `__init__` (errors, result, canvas constants, no I/O), `options.py`
(scale and size), `files.py` (picture path, atomic write, stale cleanup), `service.py` (Chromium session).
`render/` never prints; `cli.py` echoes. Playwright is imported on demand, never at package import.

## 2026-11-05 US-0062: slide and scale

### Picture rules
- One PNG of one slide, the 960x540 canvas clipped from the live page; the file is only read.
- Slide id is `slide_id(tag)`, else `slide-<index>`. Default slide is the first.
- The browser shows only that slide (`SHOW_SLIDE_JS` in `render/scripts.py`); the HTML file is never written.

### Output directory and cleanup
- `<tempfile.gettempdir()>/htmleditor-render/<file stem>-<slide id>.png`; `/`, `\` and NUL in the id become `_`.
- After a successful render, pictures of the presentation's own slide ids other than the new one are removed.
  Pictures of other files and unrelated names stay. A failed render deletes nothing.

### Scale and size
- `--scale` is a TEXT click option (a float option would exit 2 on `abc`). `None` means 0.5.
- `parse_scale`: strip, `Decimal(text)` (a float uses `Decimal(repr(value))`), finite, within [0.1, 1].
  Accepted: `.5`, `1e-1`, ` 0.5 `. Refused: `0.09`, `1.01`, `0`, `-1`, empty, `abc`, `nan`, `inf`, `1,5`.
  Message: `Scale must be between 0.1 and 1`, exit 1.
- `output_size`: `Decimal` and `ROUND_HALF_UP` on 960 x scale and 540 x scale (0.125 gives 120x68). Never `round()`
  on floats. `device_scale_factor = float(scale)`; the PNG header read after capture must equal the expected size,
  else `Rendering failed: picture is <w>x<h>, expected <w>x<h>`.

### Check order
scale, file not found, not a presentation, browser missing, unknown slide id. The browser is launched BEFORE the
id is validated (DEC-005), so on a machine without Chromium an unknown id gives the install message.
Unknown id: `Unknown slide id "slide-9". Valid ids: slide-0, slide-1, ...` (all ids, in order).

### Fixtures and install
- Fixtures come from `tests/render_support.py` (`ei_deck_html`, `med_deck_html`); the output directory is
  redirected with `monkeypatch.setattr(tempfile, "tempdir", ...)`.
- Browser tests carry `@needs_chromium` (skipped without `make install-browser`). CLI runs go through a thread
  because the Playwright sync API refuses to start inside a running event loop.
- The DECK-MED dark slide pixel (2, 300) at scale 1 is exactly `#0B0E11` (`--med-dark`).

## 2026-11-05 US-0064: report only

- `--report-only`: one page load, every slide shown and measured in document order (`_measure_all`), no screenshot,
  no output directory access (no mkdir, no cleanup). Output: problem lines then the final line, no `Rendered` line.
  `RenderResult(path=None, width=None, height=None, slide=None, problems=...)`; span `render.mode` is `report_only`.
- `check_options` is the first call of `render_deck`. With `--slide`, `--scale` (even `0.5`) or `--report` it raises
  `RenderUsageError`; the command prints `Error: <message>` on stderr (no usage block) and exits 2. Other errors keep
  `error: ` and status 1. Check order: conflict, scale, file, presentation, browser, unknown slide id.
- DECK-MED in `tests/render_support.py` adds a height class (`h-md`) to its figures: the medical stylesheet needs one,
  `deck_med()` has none and would report `overflow` on every slide.
