# US-0153: render aborts outside file requests

> Spec: SPEC-0026 (sdlc/specs/SPEC-0026-pictures-outside-deck-folder/)
> Nature: BUG
> Priority: P1
> Depends on: US-0150, US-0151
> min_tier: 2
> Files touched: 2
> Closes spec: no

## Objective
`render` no longer paints a picture, a style sheet or a frame that lies outside the deck's folder into the PNG it returns; an aborted picture shows up in the existing report as `<src> did not load`.

## Requirements covered
- SPEC-0026/BR-003 (partial: the render page) [EARS-E]: WHEN the browser used to measure a deck for the PPTX export, or to render a deck, requests a `file://` resource whose resolved path is outside the deck's folder, THE product SHALL abort that request, for every resource type (picture, font, style sheet, frame).
- SPEC-0026/BR-006 (partial: the render) [EARS-U]: The product SHALL judge a picture by its resolved real path.
- SPEC-0026/BR-007 [EARS-E]: WHEN `render` aborts a picture request under BR-003, THE render SHALL report it through the existing image problem line `<src> did not load` (kind `image`), and SHALL NOT add any new message.

## Independent Test
`make test ARGS='tests/test_render_outside.py'` is green with Chromium installed (`needs_chromium`). BT-014 re-reads the PNG: no red pixel in the picture's box.

## Design excerpt
### Decisions
- DEC-004: `guard_browser(target, root)` (created in US-0151) on the render context. DEC-010: no new message; the aborted image is reported by `_failed_images` (`render/service.py:232`).
### Contracts
In `src/mcp_htmleditor/render/service.py` `_open_page` (line 201): after `context = browser.new_context(...)` and before `page.goto(...)`: `guard_browser(context, Path(file).resolve().parent)`. A context level route also covers frames. Import `guard_browser` from `..deck_folder`.
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/render/service.py` | modify |
| `tests/test_render_outside.py` | create |
### Existing patterns
Render CLI tests and fixtures: `tests/render_support.py` (`needs_chromium`, helpers), run with `run_cli("render", deck, "--slide", "slide-1", "--report")`; the report line format `image slide-N: <src> did not load` (`render/service.py:232`).

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.

### SPEC-0026/BT-014: render, an outside picture (occurrence `render/service.py:211`)
- Level / Driver / Location: exploit / CLI `render <deck> --slide slide-1 --report` / `tests/test_render_outside.py`
- Red before the fix because: the PNG shows the red picture (pixel at the picture centre is (255, 0, 0)) and the report has no `did not load`.
- Given `tmp/deck/deck.html` slide `slide-1` holding `<img src="../secret.png" style="width:200px;height:200px">`, `tmp/secret.png` a 200x200 red PNG
- When the user renders slide-1 with `--report`
- Then the output has the line `image slide-1: ../secret.png did not load`, and the PNG (re-read with Pillow) has no pixel of (255, 0, 0) in the picture's box

### SPEC-0026/BT-017: render, an outside style sheet and an outside frame (BR-003)
- Red before the fix because: the PNG slide background is (0, 0, 255) and the frame area is (255, 0, 0); the two "no pixel" assertions fail.
- Given `tmp/out.css` (`.slide{background:#0000FF}`), `tmp/frame.html` (a page with a red background), and a deck whose head holds `<link rel="stylesheet" href="../out.css">` and whose slide 1 holds `<iframe src="../frame.html" style="width:200px;height:200px"></iframe>`
- When the user renders slide-1
- Then the PNG holds no pixel of (0, 0, 255) and none of (255, 0, 0)

## Constraints
- Files not to touch: `export/`, existing tests.
- Dependencies not to add: none.
- Patterns to avoid: a new problem kind or message in `render/problems.py` (BR-007).
- Scope boundary: documentation and non regression are US-0154.

## Definition of done
- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit.
- [ ] Non regression: existing render tests (`tests/test_render_*.py`) unchanged and green.
- [ ] Self review: the guard is registered before `goto`; the deck itself and in folder resources load.
- [ ] One commit `US-0153: render aborts outside file requests` on the work branch, body with `Summary:`, `Spec: SPEC-0026` and the requirement ids.
