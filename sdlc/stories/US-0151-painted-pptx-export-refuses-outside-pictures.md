# US-0151: painted PPTX export refuses outside pictures

> Spec: SPEC-0026 (sdlc/specs/SPEC-0026-pictures-outside-deck-folder/)
> Nature: BUG
> Priority: P1
> Depends on: US-0150
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective
The painted PPTX export (the default finish when Chromium is installed) stops reading outside pictures, both where it reads the bytes of a measured picture and where Chromium itself loads files for the measure. The command line reproduction BT-001 turns green.

## Requirements covered
- SPEC-0026/BR-002 [EARS-U]: The painted PPTX export SHALL NOT read a measured picture whose address, a `file://` address or a path, resolves outside the deck's folder.
- SPEC-0026/BR-003 (partial: the measure page of the export) [EARS-E]: WHEN the browser used to measure a deck for the PPTX export, or to render a deck, requests a `file://` resource whose resolved path is outside the deck's folder, THE product SHALL abort that request, for every resource type (picture, font, style sheet, frame).
- SPEC-0026/BR-005 (partial: the painted export) [EARS-O]: IF an export refuses a picture because it is outside the deck's folder, THEN THE export SHALL continue without it and SHALL add to its warnings the text `Image hors du dossier du deck, ignoree: <src>`. In the painted export the `<src>` is the address the browser reports (the absolute `file://` form), cut at 60 characters; a refused picture adds no shape.
- SPEC-0026/BR-006 (partial: the painted export) [EARS-U]: The product SHALL judge a picture by its resolved real path.

## Independent Test
`make test ARGS='tests/test_export_pptx_outside_painted.py'` is green (the Chromium tests run when Chromium is installed, else skip like the other `needs_chromium` tests). BT-012 decodes every picture under `ppt/media/` and finds no pixel of colour (1, 2, 3).

## Design excerpt
### Decisions
- DEC-004: `guard_browser(target, root)` registers `route("file://**")`; the handler continues a request whose `url_to_path` is inside `root`, aborts it otherwise, for every resource type. DEC-003: `_bytes` keeps reading `file://` through `url_to_path`. DEC-005: `outside_warning(src)`. DEC-009: a refused picture adds no shape (`_bytes` returns `None`, `picture()` returns at `if data is None`). DEC-007: `embedded_pictures_only` stays checked first.
### Contracts
In `src/mcp_htmleditor/deck_folder.py` add:
```python
def guard_browser(target: Any, root: Path) -> None:
    def handle(route: Any) -> None:
        path = url_to_path(route.request.url)
        if path is not None and is_inside(root, path):
            route.continue_()
        else:
            route.abort()

    target.route("file://**", handle)
```
In `src/mcp_htmleditor/export/pptx_paint.py` `_measure_pages` (line 155-157 today), right after `page.route(REMOTE, ...)` and before `page.goto(...)`: `guard_browser(page, html_path.resolve().parent)`.
In `src/mcp_htmleditor/export/pptx_paint_shapes.py` `_bytes` (lines 199-204 today), after the `REMOTE` check and path build:
```python
if not is_inside(self.base_dir, path):
    self.report.warn(outside_warning(src))
    return None
```
before `path.is_file()`. For a `file://` address `path` comes from `url_to_path` as today; for a plain path `self.base_dir / src` (an absolute `src` replaces the base, as today, and is then judged).
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck_folder.py` | modify (add `guard_browser`) |
| `src/mcp_htmleditor/export/pptx_paint.py` | modify |
| `src/mcp_htmleditor/export/pptx_paint_shapes.py` | modify |
| `tests/test_export_pptx_outside_painted.py` | create |
### Existing patterns
`Painter._bytes` tests: `tests/test_export_pptx_library.py:84-100` (`pptx_paint.Painter(mock.MagicMock(), report, folder)`). Chromium marker: `needs_chromium` in `tests/render_support.py:39`. CLI driver: `run_cli` in `tests/deck_support.py:244`.

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.
All in `tests/test_export_pptx_outside_painted.py`; `secret.png` is written by the test outside the deck folder.

### SPEC-0026/BT-001: the flow and painted export of a deck naming `../secret.png` (reproduction)
- Level / Driver: functional e2e / CLI `export pptx`
- Red before the fix because: `pptx_images.py` and the painter embed `../secret.png` (the flow part is green after US-0150; the painted part is still red until this story when Chromium is installed).
- Given `tmp/deck/deck.html` (a real presentation file whose slide 1 holds `<img src="../secret.png" alt="x">`) and `tmp/secret.png` (a 2x2 red PNG)
- When the user runs `export pptx tmp/deck/deck.html tmp/out.pptx`
- Then exit status 0, no file under `ppt/media/` of `out.pptx` has the bytes of `secret.png`, and the error stream holds a line starting `Attention: Image hors du dossier du deck, ignoree: `

### SPEC-0026/BT-011: painted export bytes (occurrence `pptx_paint_shapes.py:199-204`)
- Level / Driver: exploit / direct call of `Painter._bytes`
- Red before the fix because: `painter._bytes("../secret.png")` returns the bytes of `secret.png` instead of `None`.
- Given a `Painter` on base folder `tmp/deck/`, `tmp/secret.png`
- When `_bytes` receives `../secret.png`, `<tmp>/secret.png`, `file://<tmp>/secret.png`
- Then each returns `None` and the report holds three warnings starting `Image hors du dossier du deck, ignoree: `; and `_bytes("local.png")` for a file in `tmp/deck/` still returns its bytes

### SPEC-0026/BT-012: Chromium measure draws an outside picture (occurrence `pptx_paint.py:155-157`)
- Level / Driver: exploit / CLI `export pptx`, `needs_chromium`
- Red before the fix because: the raster picture of the figure holds the pixels of `secret.png`; `assert not any(pixel == (1, 2, 3) ...)` fails. This payload does not go through the byte reader, so the `_bytes` fix cannot turn it green.
- Given `tmp/secret.png` a 4x4 PNG of the single colour (1, 2, 3), and a deck whose slide 1 holds `<svg width="80" height="80"><image href="file://<tmp>/secret.png" width="80" height="80"/></svg>`
- When the user exports it with the painted finish
- Then no pixel of colour (1, 2, 3) appears in any picture under `ppt/media/` (each decoded with Pillow), and the export did not fall back to the degraded warning (`Deck exported without the rendered finish`)

### SPEC-0026/BT-016: an outside style sheet in the measure (BR-003)
- Level / Driver: exploit / CLI `export pptx`, `needs_chromium`
- Red before the fix because: slide 1 of the PPTX holds a fill of `0000FF` taken from the outside style sheet; `assert "0000FF" not in slide1_xml` fails.
- Given `tmp/out.css` holding `.slide{background:#0000FF}` and a deck whose head holds `<link rel="stylesheet" href="../out.css">`
- When the user exports it with the painted finish
- Then the XML of slide 1 holds no `0000FF`

## Constraints
- Files not to touch: `pptx_images.py`, `to_docx.py`, `render/`, existing tests.
- Dependencies not to add: none.
- Patterns to avoid: filtering only images in the route (BR-003 says every type); a placeholder shape for a refused picture.
- Scope boundary: the render page guard is US-0153.

## Definition of done
- [ ] RED evidence recorded for every new test before the production code (Chromium tests: if Chromium is missing, say so and run them where it is installed; `make install-browser`).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_export_pptx_library.py` (`test_the_painted_path_refuses_the_same_addresses`, default `_bytes("local.png")`), `tests/test_pptx_paint_generic.py` unchanged and green.
- [ ] Self review: the guard is registered before `goto`; the deck file itself loads; the `REMOTE` abort is untouched.
- [ ] One commit `US-0151: painted PPTX export refuses outside pictures` on the work branch, body with `Summary:`, `Spec: SPEC-0026` and the requirement ids.
