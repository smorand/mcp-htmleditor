# US-0097: Presentation mode of the shell decks

> Spec: SPEC-0016 (sdlc/specs/SPEC-0016-reference-decks-and-editor-residues/)
> Nature: BUG
> Priority: P1
> Depends on: main
> min_tier: 1
> Files touched: 6
> Closes spec: no

## Objective

The three shell reference decks (`ibm-carbon.html`, `example-ei-complete.html`, `example-carbon-complete.html`) have
a toolbar and one slide at a time, but no presentation mode: no `#btn-present`, no `f`, and the editor's present
button gives an unscaled page with its toolbar. After this story each of them presents like the bootstraps, opened
directly or in the editor, and its PPTX export is byte identical.

Silent pitfalls (why tier 1): a CSS rule whose selector the PPTX style resolver indexes changes the golden hashes of
two decks; the scale must be measured at scale 1 on the current slide (`ibm-carbon.html` slides have different
heights, up to 773 px), and recomputed on every slide change and resize.

## Requirements covered

- SPEC-0016/BR-009 (partial: the three shell decks): Each of the five decks SHALL contain a `:fullscreen` CSS rule, one element with `id="btn-present"` whose activation calls `enterPresentation()`, and script functions named `enterPresentation`, `exitPresentation` and `updateFullscreenScale`.
- SPEC-0016/BR-010 (partial: shell decks): WHEN a deck among the five enters presenting, by activating `#btn-present`, by the key `f` or `F`, or by the editor page's `#present-btn` THE deck SHALL show exactly one slide, the current one, centered, with `--fs-scale` set on `<html>` to `s` and its visible box measuring `w * s` by `h * s` within 1 pixel.
- SPEC-0016/BR-011 (partial: shell decks): WHILE a deck among the five is presenting THE deck SHALL display no element outside the current slide: its `.toolbar`, `.shell-header`, `.nav-arrow`, `.status-bar`, `#btn-present` and every other slide have computed `display: none` or lie entirely outside the viewport.
- SPEC-0016/BR-012 (partial: shell decks): WHILE a deck among the five is open and its focused element is none of editable text, an `<input>`, a `<textarea>` or a `<select>` THE deck SHALL move one slide forward on `ArrowRight`, `ArrowDown` or space, one slide back on `ArrowLeft` or `ArrowUp`, to the first slide on `Home`, to the last on `End`, enter presenting on `f` or `F`, and leave presenting on `Escape`.
- SPEC-0016/BR-013 (partial: shell decks): WHEN a deck among the five leaves presenting THE deck SHALL remove `--fs-scale` from `<html>`, keep the current slide current, and show its layout of before entering: the shell deck with its toolbar and the current slide, the stacked deck with every slide one under the other and the current slide's top edge inside the viewport.
- SPEC-0016/BR-014 (partial: shell decks): WHEN the viewport changes size while a deck among the five is presenting THE deck SHALL set `--fs-scale` to the `s` of the new size.
- SPEC-0016/BR-015 (partial: shell decks): The five decks SHALL NOT change their PPTX export: the slide XML hashes recorded for `ibm-carbon.html`, `example-ei-complete.html`, `presentation-standard.html` and `roadmap-one-pager.html` stay equal to their golden values, and `example-carbon-complete.html` exports 9 slides whose slide XML is byte identical to its export at c507194.
- SPEC-0016/BR-017 (partial: shell decks): Each of the five decks SHALL behave per BR-010 to BR-014 both when opened as a `file://` URL and when shown in the editor page.

Definitions and business rules (spec, verbatim): "Let `w` and `h` be the width and height of the current slide's box
at scale 1, `W` and `H` the viewport's inner width and height, and `s = min(W / w, H / h)`." "The current slide of a
shell deck is the one shown before entering. The page background behind the slide is `rgb(0, 0, 0)`." "Forward on
the last slide and back on the first change nothing." "Outside presenting, a shell deck shows what it shows today."

## Independent Test

`make test ARGS='-k "reference_decks_present or golden"'`: the six shell deck tests (three decks, `file` and
`editor`) red before (no `#btn-present`), green after; the golden hashes and the BT-032 fixture unchanged.

## Design excerpt

### Decisions
- DEC-006 (SPEC-0016): "Shell decks get the bootstrap's building blocks unchanged in behavior: the `:fullscreen` CSS block of `slides-empty.html:243` to `:259` adapted to each deck's classes (`.shell-header`, `.toolbar`, `.nav-arrow`, `.status-bar` hidden, `.stage` and `body` black, `.slide-frame` without padding, `.slide` scaled by `var(--fs-scale, 1)` from its center), a `<button id=\"btn-present\" onclick=\"enterPresentation()\">` inside `.toolbar`, `updateFullscreenScale()` as the last statement of `render()`, the two listeners, and the keydown table with the focus exception (adds space, `f`, `F`, `Escape` and the exception to today's handler)."
- DEC-007 (SPEC-0016): "Export invariance rule for every deck edit: each added CSS selector contains `:` (all start with `:fullscreen`) or `[`, so `_selector_target` rejects it (`pptx_style.py:558` `_SELECTOR_REJECT`); no class or attribute is added in the file to any element inside a slide; added elements are `<button>` and `<script>`, both in `SKIP_TAGS`, and lie outside every slide."
- DEC-009 (SPEC-0016): "Deck browser tests live in one module `tests/test_reference_decks_present_e2e.py`, parametrized over a `DECKS` tuple of `(file name, family, slide count)`; per deck two tests: `file` ... and `editor` ... Viewport 1600x900; asynchronous results through `wait_for_js`." This story lists the three shell decks; US-0098 appends the two stacked ones.
- DEC-010 (SPEC-0016): "The c507194 reference of `example-carbon-complete.html` is a fixture `tests/testdata/example_carbon_complete_slide_hashes.json`, written with `slide_hashes()` of `tests/test_export_golden.py:41` from `git show c507194:templates/reference/slides/example-carbon-complete.html` before the deck is edited; the BT-032 test sits in `tests/test_export_golden.py` and reads that fixture, never `pptx_slide_hashes.json`."
- DEC-014 (SPEC-0016): the SPEC-0016 browser tests take at most 40 s together; report this file's durations.

### Contracts
Building blocks (as `templates/bootstrap/slides-empty.html:373` to `:410`):

```js
function updateFullscreenScale() {
  const slide = document.querySelector('.slide.active');
  const root = document.documentElement;
  if (!document.fullscreenElement || !slide) { root.style.removeProperty('--fs-scale'); return; }
  root.style.setProperty('--fs-scale', '1');
  const rect = slide.getBoundingClientRect();
  root.style.setProperty('--fs-scale', String(Math.min(window.innerWidth / rect.width, window.innerHeight / rect.height)));
}
document.addEventListener('fullscreenchange', updateFullscreenScale);
window.addEventListener('resize', updateFullscreenScale);
function enterPresentation() { /* documentElement.requestFullscreen, webkit fallback */ }
function exitPresentation() { /* document.exitFullscreen when fullscreen */ }
```

Keydown: return when `document.activeElement` is content editable or an `INPUT`, `TEXTAREA`, `SELECT`; `ArrowRight`,
`ArrowDown`, `' '` with `preventDefault` → `navigate(1)`; `ArrowLeft`, `ArrowUp` → `navigate(-1)`; `Home` →
`goToSlide(0)`; `End` → `goToSlide(TOTAL - 1)`; `f`, `F` → `enterPresentation()`; `Escape` → `exitPresentation()`.
CSS: every selector begins with `:fullscreen ` (for example `:fullscreen .toolbar`, `:fullscreen .slide`); the
centering of the active slide uses the deck's existing `.stage` / `.slide-frame` flex containers; the slide is scaled
with the CSS `scale` property (offset sizes stay at scale 1).

Test measure (from the design): `w = slide.offsetWidth`, `h = slide.offsetHeight`, `s = Math.min(innerWidth / w, innerHeight / h)`,
`--fs-scale` from `getComputedStyle(document.documentElement).getPropertyValue('--fs-scale')`, visible box from
`getBoundingClientRect()`; the current slide of a shell deck is `.slide.active`.

### Paths
| Path | Action |
|---|---|
| `tests/testdata/example_carbon_complete_slide_hashes.json` | create FIRST, from the c507194 file, before any deck edit |
| `tests/test_export_golden.py` | modify: add `test_example_carbon_complete_export_is_unchanged` (BT-032) |
| `templates/reference/slides/ibm-carbon.html` | modify: CSS block, button in `.toolbar` (`:507`), script (`:1225` to `:1305`) |
| `templates/reference/slides/example-ei-complete.html` | modify: same (`.toolbar` `:271`, script from `:727`) |
| `templates/reference/slides/example-carbon-complete.html` | modify: same (`.toolbar` `:182`, script from `:691`) |
| `tests/test_reference_decks_present_e2e.py` | create: `DECKS` with the three shell decks, `file` and `editor` tests |

### Existing patterns
- Building blocks and button markup: `templates/bootstrap/slides-empty.html:243` to `:259` (CSS), `:291` (button), `:373` to `:410` (JS).
- Editor server fixture: `deck_server` in `tests/test_fullscreen_e2e.py:93` (`HTMLEDITOR_TEMPLATES_DIR` to the repo, `start_http_server`, `reset_state`).
- Golden hashing: `slide_hashes()` in `tests/test_export_golden.py:41`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

`DECK` ranges over the three shell decks, each copied to `tmp_path`. Viewport 1600x900.

### SPEC-0016/BT-003: Each reference deck presents like a bootstrap
- Level / Driver / Location: functional e2e / Playwright on the `file://` URL of the copy, and on the editor page / `tests/test_reference_decks_present_e2e.py` (`file` and `editor` tests)
- Given `DECK` opened / When `#btn-present` is clicked
- Then the deck's `<html>` is `document.fullscreenElement`, `--fs-scale` equals `s` within `1e-6`, the current slide's bounding box measures `w * s` by `h * s` within 1 pixel, and BR-011 holds (`.toolbar`, `.shell-header`, `.nav-arrow`, `.status-bar`, `#btn-present` and every non current `.slide` have computed `display` `none` or a bounding box outside the viewport)
- And for the editor path: with `DECK` served and `#present-btn` clicked, the same three assertions hold inside `#content-frame`
- Red before the fix because: `#btn-present` does not exist; in the editor path `--fs-scale` is empty and the toolbar shows.

### SPEC-0016/BT-017: Presenting hides everything else, keys work
- Given `DECK` presenting from `file://`, entered by the key `f` (focus on the page body)
- Then BR-010's measures hold, every element of BR-011 is hidden or outside, and exactly 1 slide intersects the viewport
- When `End`, then `ArrowLeft`, then `Home`, then `ArrowLeft` are pressed
- Then the current slide is, after each, the last, the one before the last, the first, the first
- And the scale assertions of BR-010 hold after each move

### SPEC-0016/BT-019: Resize while presenting
- Given `DECK` presenting at 1600x900
- When the viewport becomes 1200x900 (`page.set_viewport_size`)
- Then `--fs-scale` equals the new `s` within `1e-6`

### SPEC-0016/BT-020: Editor and file paths agree
- Given `DECK` served and shown in the editor page
- When `#present-btn` is clicked, then `End` pressed with focus in `#content-frame`
- Then BR-010's measures hold in `#content-frame` and the last slide is current

### SPEC-0016/BT-031: Golden PPTX hashes unchanged
- When `tests/test_export_golden.py::test_exported_slide_xml_matches_golden_hashes` runs
- Then every template, `ibm-carbon.html` and `example-ei-complete.html` included, matches `tests/testdata/pptx_slide_hashes.json`, which is not regenerated

### SPEC-0016/BT-032: `example-carbon-complete.html` export unchanged
- Given the fixture of its export at c507194 (9 slide XML hashes)
- When the fixed file is exported
- Then 9 slides, each `ppt/slides/slideK.xml` hash equal to the fixture

## Constraints

- Files not to touch: `tests/testdata/pptx_slide_hashes.json`, the bootstraps, the stacked decks, any slide's markup (`<article class="slide" ...>` and its content).
- Dependencies not to add: none.
- Patterns to avoid: any added CSS selector without `:` or `[` (DEC-007); stretching the slide (width/height) instead of scaling it; fixed waits.
- Scope boundary: the stacked decks (US-0098); BT-018 (leaving) is asserted in US-0098 for both families, but leaving must already work here (`exitPresentation`, `--fs-scale` removed on `fullscreenchange`).

## Definition of done

- [ ] The BT-032 fixture is committed from the c507194 file before the deck edits (the diff shows it computed from `git show c507194:...`).
- [ ] RED evidence recorded for BT-003, BT-017, BT-019, BT-020 on the three decks before the deck edits, in `.implement/US-0097-red.log`.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_export_pptx.py::test_ibm_carbon_template_exports_nine_slides` and `test_script_and_shell_are_never_exported`, `tests/test_strip_idempotent.py`, `tests/test_deck_get_slide.py` template tests, `tests/test_skill_shipped.py` reference mapping, all unchanged and green.
- [ ] Durations of the new tests reported, within DEC-014.
- [ ] Docs updated: none in this story (US-0101).
- [ ] Self review: full (tier 1).
- [ ] One commit `US-0097: Presentation mode of the shell decks`, body `Spec: SPEC-0016` and BR-009, BR-010, BR-011, BR-012, BR-013, BR-014, BR-015, BR-017.
