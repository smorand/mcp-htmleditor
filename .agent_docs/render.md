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

## 2026-11-05 US-0065: font, script and image problems

- Order of every report: slide `-`, slide document order, kind `script`, `image`, `font`, `overflow`, `clipped`, then
  collection order (`build_problems(slides, images, errors)` in `problems.py`; the sort is stable).
- `font`: `MEASURE_SLIDE_JS` reads the computed `font-family` of the slide and of each descendant with a direct non
  blank text node (script, style, noscript and template are skipped). Names are split with quotes removed;
  `sans-serif`, `serif`, `monospace`, `system-ui` are ignored. A list is reported when none of its names is installed,
  naming the first one; one line per name per slide. Installed = after `await document.fonts.load('72px "name"')`
  the canvas width of `"name",base` differs from `base` alone for one of monospace, serif, sans-serif.
  `document.fonts.check` is useless here: it answers true for a name that does not exist.
  `fonts.load` rejects when the page declares an `@font-face` for that name whose source fails (missing file, invalid
  data); the rejection is caught and the name counts as not installed, so it never aborts the run.
- The EI stack ends with Arial and the medical stack with Arial or Helvetica, so DECK-EI and DECK-MED stay clean on a
  machine without Segoe UI or Calibri (checked on macOS: `report: OK` for both).
- `script`: `page.on("pageerror")` is registered before `goto`; `PageSignals.current` is `-` until a slide is shown and
  the slide id from the start of each measure. Text is `Error.name: Error.message`. Identical (slide, text) pairs are
  kept once. A late error is attributed to the slide still shown, so a test observer must throw only when its slide
  is active (leaving a slide changes the class again).
- `--report` keeps the errors of `-` and of the rendered slide, and only the images of the rendered slide.
- `image`: `IMAGES_JS` runs once after `load`: an `img` inside a slide with a `src` attribute, `complete` and
  `naturalWidth` 0. The `src` is printed as written; a data address longer than 40 characters is cut to 40 plus `...`
  (`shorten_source`). `requestfailed` is not used. A viewBox only SVG has a non zero `naturalWidth`, but without
  width and height it is drawn very large and gives an `overflow`, so give it a size in tests.
