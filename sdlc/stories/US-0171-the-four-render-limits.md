# US-0171: the four render limits

> Spec: SPEC-0033 (sdlc/specs/SPEC-0033-render-limits/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 4
> Closes spec: yes

## Objective
`render` pictures a slide that starts below the window, does not report the system font stack, prints a script error on one line and a missing image once per slide and address (an empty address named). Closes SPEC-0033.

## Requirements covered
- SPEC-0033/FR-NEW-001: WHEN the slide asked for starts below the visible window THE render SHALL bring it into view before taking its picture and give the same 960 by 540 slide, scaled as asked.
- SPEC-0033/FR-NEW-002 and FR-MOD-001: the font check never reports `serif`, `sans-serif`, `monospace`, `cursive`, `fantasy`, `system-ui`, `ui-serif`, `ui-sans-serif`, `ui-monospace`, `ui-rounded`, `emoji`, `math`, `fangsong`, `-apple-system`, `BlinkMacSystemFont` (any case, quoted or not); a stack with uninstalled named fonts gives one `font` line naming its first named font, only when none is installed.
- SPEC-0033/FR-NEW-003: a script error (an `Error` thrown by the page) is one line: runs of white space (spaces, tabs, line breaks, non breaking spaces) become one space, ends trimmed; two alike after that are one line per slide.
- SPEC-0033/FR-NEW-004 and FR-MOD-002: an image that did not load is reported once per slide and address (compared in full as written), in the order of first use.
- SPEC-0033/FR-NEW-005: an image with an empty address is reported `image <slide>: (empty address) did not load`.

## Independent Test
`make test ARGS='tests/test_render_limits_e2e.py tests/test_render_report.py tests/test_render_picture.py'` green, `make check` green.

## Design excerpt
### Decisions
DEC-001 scroll before reading the box; DEC-002 generic list; DEC-003 normalise in `PageSignals.record`; DEC-004 de duplicate failed images.
### Contracts
`src/mcp_htmleditor/render/scripts.py` `MEASURE_SLIDE_JS`: `const generic = ['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui', 'ui-serif', 'ui-sans-serif', 'ui-monospace', 'ui-rounded', 'emoji', 'math', 'fangsong', '-apple-system', 'blinkmacsystemfont'];` (names are compared lower case).
`src/mcp_htmleditor/render/service.py`:
- `_shoot`: replace `box = page.locator(SLIDE_SELECTOR).nth(target.index).bounding_box()` by `locator = page.locator(SLIDE_SELECTOR).nth(target.index)`, `locator.scroll_into_view_if_needed()`, `box = locator.bounding_box()`.
- `PageSignals.record`: `text = " ".join(f"{name}: {message}".split())`.
- `_failed_images`: iterate `dict.fromkeys((item["slide_index"], item["src"]) for item in page.evaluate(IMAGES_JS) if item["slide_index"] in ids)`; message `f"{shorten_source(src) or '(empty address)'} did not load"`.
Docs: `.agent_docs/render.md` (the rules: scroll into view, generic list, one line per script error, image lines).
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/render/scripts.py` | modify |
| `src/mcp_htmleditor/render/service.py` | modify |
| `tests/test_render_limits_e2e.py` | create |
| `.agent_docs/render.md` | modify (keep within 220 lines) |
### Existing patterns
`tests/test_render_report.py` (`run_cli` in a thread, `out_dir` fixture, `_deck`, `rs.append_to_slide`, `rs.add_script`, `_article_style`), `tests/render_support.py` (`ei_deck_html`, `png_pixel`, `png_size`), `tests/test_render_picture.py::test_a_carbon_slide_keeps_its_own_border_in_the_picture`.

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc. In `tests/test_render_limits_e2e.py`; decks come from `rs.ei_deck_html()` (slides `slide-0`...). Fixtures: "red block" `<div style="width:100px;height:100px;background:#FF0000"></div>` appended to slide 0's body; "tall block" `<div style="height:1200px"></div>` as the first child of `<body>` with `body{margin:0}`.
### SPEC-0033/E2E-001: a slide below the window
- Given the deck with the red block and the tall block / When `render <deck> --slide slide-0` / Then stdout `Rendered slide-0 to <path> (480x270)`, status 0, and the picture (scale 0.5) has at least 1000 pixels of (255, 0, 0)
### SPEC-0033/E2E-002: system font stack (cases)
- `font-family:-apple-system, BlinkMacSystemFont, sans-serif` (a); `ui-sans-serif, ui-serif, ui-monospace, ui-rounded` (b); `cursive, fantasy, emoji, math, fangsong, system-ui` (c) on a slide 0 text / `render <deck> --slide slide-0 --report` / Then no `font` line in each case
### SPEC-0033/E2E-003: a named font after generic ones
- `font-family:-APPLE-SYSTEM, "Nope Sans", sans-serif` / Then exactly one `font slide-0: "Nope Sans" is not available, fallback used`; with `"Nope Sans", "Other Nope", "sans-serif", serif` also exactly one line naming `Nope Sans`
### SPEC-0033/E2E-004: multi line script error (cases)
- A page script (`rs.add_script`) throwing at load `new Error("first line\r\nsecond line  ")` (a), `new Error("a\tb\n\nc")` (b), `new Error("x\u00a0y")` (c) / `--report` / Then exactly one `script` line each: `script -: Error: first line second line`, `script -: Error: a b c`, `script -: Error: x y`
### SPEC-0033/E2E-005: missing image repeated (cases)
- (a) slide 0 uses `missing.png` twice and `other.png` once, slide 1 uses `missing.png`; `render <deck> --report-only` / Then three lines in order `image slide-0: missing.png did not load`, `image slide-0: other.png did not load`, `image slide-1: missing.png did not load`
- (b) two different undecodable `data:image/png;base64,` addresses on slide 0 that share their first 40 characters / Then two lines, alike (first 40 characters then `...`)
- (c) `missing.png` on slides 0 and 1 and an undecodable data address used twice on slide 0 / Then `image slide-0: missing.png did not load`, the data address line once, `image slide-1: missing.png did not load`
### SPEC-0033/E2E-006: empty address (cases)
- (a) `<img src="">` on slide 0 / Then `image slide-0: (empty address) did not load`; (b) `<img src="">` before `<img src="missing.png">` / that line then `image slide-0: missing.png did not load`; (c) `<img src="">` twice / the line once
### SPEC-0033/E2E-007: the picture is the slide
- The deck of E2E-001 and the same deck without the tall block, scale 1 / Then the two decoded pictures of slide 0 are equal pixel for pixel
### SPEC-0033/E2E-008: the slide starts exactly at the bottom edge
- The tall block's height is 900 minus the slide's top without the block (measured in the test with the block absent) / Then the picture is produced with at least 1000 red pixels
### SPEC-0033/E2E-009: the same script error twice
- A page script throwing at load `new Error("first line\nsecond line")` and `new Error("first line second line")` / Then exactly one `script -: Error: first line second line` line

## Constraints
- Files not to touch: `render/problems.py`, other render modules, existing tests.
- Dependencies not to add: none.

## Definition of done
- [ ] RED evidence for E2E-001, E2E-002, E2E-004, E2E-005, E2E-006 before the fix (others may already pass).
- [ ] Every test above green; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_render_*.py` unchanged and green.
- [ ] Docs updated: `.agent_docs/render.md`.
- [ ] One commit `US-0171: the four render limits`, body with `Summary:`, `Spec: SPEC-0033` and the requirement ids.
