# US-0139: The PPTX exporter can be confined to pictures held in the presentation

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P2
> Depends on: main
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Add one keyword to the PPTX exporter so that a build can refuse every picture address that is not a data URI: a relative path, an absolute path, a `file:` address or a remote address is skipped with a warning and nothing is read from disk. The default stays the previous behavior, so the local mode is byte identical.

## Requirements covered

- SPEC-0025/FR-NEW-052 (partial: the PPTX build reads no file outside the presentation (class sweep A#8 and A#9)): The web library mode SHALL NOT let a script contained in a presentation read what the browser keeps for the library, act with the identity of the person viewing it, or reach another folder.
  - Business rules: The scripts still run for the presentation itself (navigation, animations), as in the local mode.

## Independent Test

Run `make test ARGS='-k export_pptx_library'`. The assertion that is not a mock: a deck whose slide holds `<img src="../secret.png">`, `<img src="/abs/secret.png">` and `<img src="file:///.../secret.png">` is exported once with the default (the picture bytes are in the PPTX media, unchanged behavior) and once with `embedded_pictures_only=True` (no media part contains the bytes of `secret.png`, three warnings are reported).

## Design excerpt

### Decisions

- DEC-043 (SPEC-0025): The library PPTX download calls `to_pptx(path, out, paint=False, embedded_pictures_only=True)`: the flow engine only (no Chromium in the image, no script of the deck ever executed on the machine) and a picture is read only from a `data:` URI; any other `src` is skipped with a report warning. The painted path gets the same flag. Obliged by: SPEC-0025/FR-NEW-052, SPEC-0025/FR-NEW-022.

### Data model

No change.

### Contracts

`to_pptx(input_html: str, output_pptx: str, *, paint: bool = True, embedded_pictures_only: bool = False) -> ExportReport` (`export/to_pptx.py:66`); `_build_pptx` passes the flag into `_Context` (`export/pptx_model.py:177`), whose new field is `embedded_pictures_only: bool = False`. In `ImagesMixin._image_source` (`export/pptx_images.py:93-125`): when the flag is set and `src` does not start with `data:` return `None` after `self.ctx.report.warn("Image non incluse dans le fichier, ignoree.")`, before the remote, absolute and `base_dir` branches (lines `:112-117`). In the painted path (`export/pptx_paint_shapes.py:179-200`, `_bytes`) the painted context carries the same flag and a `src` that is not `data:` returns `None` with a warning before the `file:` and `base_dir / src` branches. `_build_pptx` threads the flag to both. Default `False` keeps every existing exporter test unchanged. No CLI flag, no MCP parameter: the flag is for the library (US-0140).

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/export/to_pptx.py` | modify | keyword `embedded_pictures_only` |
| `src/mcp_htmleditor/export/pptx_model.py` | modify | context field |
| `src/mcp_htmleditor/export/pptx_images.py` | modify | `_image_source` guard |
| `src/mcp_htmleditor/export/pptx_paint_shapes.py` | modify | `_bytes` guard |
| `tests/test_export_pptx_library.py` | create | exporter tests |

### Existing patterns

`tests/test_export_pptx.py` and `tests/test_pptx_names.py` for exporter tests and fixtures; `tests/test_pptx_paint_generic.py` for the painted context.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

This story maps no test of the spec; its tests are the story tests below.

### Story tests (not spec tests)

`tests/test_export_pptx_library.py`: with the flag a relative path, an absolute path, a `file:` URL and a remote URL produce no picture and one warning each; a data URI produces a picture; without the flag the local behavior (a relative file picture is embedded) is unchanged; the painted context test mirrors the flow one with a stubbed measure.

## Constraints

- Default behavior of `to_pptx` is unchanged: existing exporter tests pass unmodified; `make pptx-fidelity` is not run here.
- No Chromium or Playwright import added.
- Scope boundary: the library route that uses the flag (US-0140).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/architecture.md` (Export pipeline: the new keyword), `.agent_docs/pptx-fidelity.md` (one line).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] Note: Red first: with no flag in the code the keyword is an unexpected argument (TypeError), then the default behavior test pins the previous result.
- [ ] One commit `US-0139: The PPTX exporter can be confined to pictures held in the presentation` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
