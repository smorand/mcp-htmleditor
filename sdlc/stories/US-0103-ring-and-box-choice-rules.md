# US-0103: Ring and the box choice rules

> Spec: SPEC-0017 (sdlc/specs/SPEC-0017-presentation-pointer/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0102
> min_tier: 1
> Files touched: 4
> Closes spec: no

## Objective

With the dot on, the presenter can show where they are but not what: after this story a click (or a tap) on the
slide rings the box it lands in (a tile, a table, a drawing, else the headline or paragraph), one ring at a time,
removed when the slide changes or the pointer is turned off, never on links, buttons or fields, never printed.
Built in the source block of `templates/bootstrap/slides-empty.html`.

Silent pitfalls (why tier 1): FR-NEW-005's six rules admit several readings, decided once in DEC-008 below and not
to be re-decided; the ring lives in an unscaled overlay, so every size is multiplied by the scale factor; the ring
must follow its box through an entrance animation and a resize.

## Requirements covered

- SPEC-0017/FR-NEW-005: WHEN the presenter clicks or taps the current slide while the pointer is on THE deck presentation SHALL ring the box the click lands in.
- SPEC-0017/FR-NEW-006: The deck presentation SHALL show at most one ring.
- SPEC-0017/FR-NEW-007: WHEN the current slide changes while the pointer is on THE deck presentation SHALL remove the ring and keep the pointer on.
- SPEC-0017/FR-NEW-008: The deck presentation SHALL NOT ring a box nor change the ring when the click lands on a link, a button or a form field of the slide.
- SPEC-0017/FR-NEW-009: WHEN the pointer is turned off THE deck presentation SHALL remove the dot and the ring and show the system cursor again.
- SPEC-0017/FR-NEW-012 (partial: a field on the slide while presenting): The deck presentation SHALL NOT turn the pointer on while edit mode is on, nor when L is typed in a text field or an editable text.
- SPEC-0017/FR-NEW-013 (partial: printing while pointing): The deck presentation SHALL NOT change the PPTX export of a deck, nor show the dot or the ring when the deck is printed.

FR-NEW-005 business rules (spec, verbatim):
"the box is found by going up from what was clicked, toward the slide:
1. a drawing counts as one element: a click on one of its shapes starts from the whole drawing;
2. inside a table, the table is the box;
3. otherwise the first element that is not one of the slide's own layout areas (its header, body, footer or frame) and that has a background colour or picture other than transparent and other than the slide's own background colour, or a shadow, or a visible border on all four sides, such as a card or a tile, is the box; a container whose direct children include two or more boxes under this rule is never a box itself; an element with a border on only some sides (a header with a bottom rule, a table cell) is never a box by this rule;
4. with no such element, the nearest block holding text directly (a headline, a paragraph, a list item) or an image or drawing is the box;
5. text set inside a line (a bold word, a span) is never a box itself, and the slide itself is never one;
6. an element whose own area is 85 % or more of the slide's area is skipped and the search continues upward from it; when it reaches the slide with no box found by rule 3, rule 4 applies.
The ring is a red `#DA1E28` line 3 slide pixels thick, whose outer edge lies 6 slide pixels outside the box on every side, with the box's corner rounding grown by 6 slide pixels (a circle stays a circle). It scales with the slide and stays on its box when the box moves (an entrance animation, the window resized). It is drawn above the slide and never takes a click. The ring is clipped to the slide: any part of it outside the slide is not shown.
The slide's own layout areas, never a box by rule 3, are, in every template: the area holding the eyebrow, headline, rule and subtitle; the body area; the footer or foot band with its page number; the grey top band; and the inner frame surrounding the content. Whatever sits inside these areas is judged on its own by rules 1 to 6."

Other business rules: FR-NEW-006 "a click on another box moves the ring there. A click on the ringed box removes the
ring. A click on the slide where FR-NEW-005 finds no box (the slide background) removes the ring if there is one, and
adds none." FR-NEW-007 "every way of changing slide counts ... Coming back to the slide shows no ring. Pressing Left on
the first slide or Right on the last, which change nothing, keeps the ring." FR-NEW-008 "such a click does what it did
without the pointer ... An element inside a link or a button (an icon, a span) counts as the link or the button."
FR-NEW-009 "turning it on again shows no ring until the next click." FR-NEW-012 "A pointer that is on while a text
field on the slide takes the focus stays on; L typed in that field types the letter." NFR 7.4: reduced motion, ring
at full opacity at once; otherwise at full opacity within 200 ms of the click.

## Independent Test

`make test ARGS='-k "pointer_ring or pointer_served"'`: the 18 tests red before the ring exists (a click changes
nothing), green after; `make test ARGS='-k "pointer_dot or golden"'` unchanged.

## Design excerpt

### Decisions
- DEC-007 (SPEC-0017, the click part): "`click` on `document` (bubble phase): ignored unless the pointer is on and the target is inside the current slide; ignored when `target.closest('a[href], button, input, select, textarea')` is inside the slide (FR-NEW-008: no `preventDefault`, ring unchanged); otherwise `findBox(target)` and the one ring rule: same box removes the ring, another box moves it, no box removes it. A tap produces a `click`, so it rings like a click." `pointerdown` of a non mouse type hides the dot (US-0102).
- DEC-008 (SPEC-0017), the algorithm, verbatim: "Notation: `slide` the current slide, `area(e)` the product of `getBoundingClientRect()` width and height, `big(e)` is `area(e) >= 0.85 * area(slide)`, `layout(e)` is `e.matches(LAYOUT_AREAS)`, `inline(e)` is a computed `display` starting with `inline` for an element other than `img`, `svg`, `video`, `canvas`.
  1. start = `target`; if it has an ancestor or self `svg` inside the slide, start = the outermost such `svg`.
  2. if start has an ancestor or self `table` inside the slide, return the nearest one.
  3. walk e from start up to, excluding, `slide`: skip e when `layout(e)`, `inline(e)` or `big(e)`; return e when it is `candidate(e)` and fewer than two of its element children are `candidate`. `candidate(e)`: not `layout`, not `inline`, not `big`, and (computed `background-image` is not `none`, or `background-color` has alpha above 0 and differs from the slide's computed `background-color`, or `box-shadow` is not `none`, or each of the four sides has `border-*-style` other than `none` and `hidden`, width above 0 and colour alpha above 0).
  4. walk e again from start up to, excluding, `slide`: skip `layout`, `inline` and `big` elements; return the first e that is `img` or `svg`, or has a child text node with non whitespace text.
  5. return null (the slide itself is never a box).
  Readings decided: rule 4 never returns a layout area, and the page number is part of its footer area ...; the container test counts children by `candidate`, not recursively; 'set inside a line' is every inline level display, so an `inline-block` pill is not a box, replaced elements excepted."
- DEC-009 (SPEC-0017): `LAYOUT_AREAS = '.slide-header, .slide-title-area, .med-head, .slide-body, .slide-footer, .slide-footer-right, .slide-foot, .slide-foot-page, .med-foot, .med-cover-foot, .med-band, .slide-inner'` (one constant in the block; it serves every template).
- DEC-010 (SPEC-0017): ring at `left = b.left - o.left - 6 * s`, `top = b.top - o.top - 6 * s`, size `b.width + 12 * s` by `b.height + 12 * s`, `border-width = 3 * s`; each corner radius from the box's computed `border-*-radius`: a percentage kept as is, a length scaled by `s` then grown by `6 * s`. `ring.animate([{opacity: 0, scale: 0.92}, {opacity: 1, scale: 1}], {duration: 150, easing: 'ease-out'})` unless `matchMedia('(prefers-reduced-motion: reduce)').matches`, then no animation.
- DEC-004 (SPEC-0017, the ring part): the rAF loop redraws the ring around its box every frame (moving box, resize) and removes it when the current slide element changes; turning the pointer off removes the layer.
- DEC-011, DEC-012 (SPEC-0017): print hides `#deck-pointer-layer`; no class selector, nothing inside a slide.
- DEC-017 (SPEC-0017): modules `tests/test_pointer_ring_e2e.py` (file page, touch page `has_touch=True` with `page.touchscreen.tap`, reduced motion page `reduced_motion="reduce"`, prints) and `tests/test_pointer_served_e2e.py` (editor page; one `serve_deck` server per test); pixels with Pillow; prints normalized, each print test first asserts two prints of the unchanged page are equal.
- DEC-018 (SPEC-0017): ring module about 10 s, served module about 12 s in total (this story's four served tests about 5 s).

### Contracts
`POINTER_STATE` (US-0102) gains, if absent: the ring rect, its computed `border-top-width`, the number of
`#deck-pointer-ring` elements shown, the ringed element (a `data-test` read: the test identifies the expected box
by comparing the ring rect with the expected element's rect, never by an id the block writes).

Served presentation: editor page `http://127.0.0.1:<port>/`, `#present-btn` click, focus in the deck (the editor
moves it, `editor.js:136` to `:143`); L pressed with `page.keyboard`.

### Paths
| Path | Action |
|---|---|
| `templates/bootstrap/slides-empty.html` | modify: the block gains `findBox`, the ring, the click and slide change handling |
| `tests/pointer_support.py` | modify: ring helpers, touch and reduced motion pages, served page helpers |
| `tests/test_pointer_ring_e2e.py` | create: E2E-007, 009, 010, 011, 012, 013, 015, 016, 019, 025, 026, 027, 030, 037 |
| `tests/test_pointer_served_e2e.py` | create: E2E-006, 008, 014, 024 |

### Existing patterns
- Editor page presenting a served deck: `tests/test_reference_decks_present_e2e.py:210` to `:254`; `serve_deck`, `tests/conftest.py:243`.
- Viewport resize while presenting: `tests/test_reference_decks_present_e2e.py:129`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Deck P as in US-0102 (spec 9.0). "Presented, pointer on": presented with F (or `#present-btn` when served), L
pressed. Rings are compared by rect: "X ringed" means one ring shown whose outer edge lies 6 × s ± 1 screen pixels
outside X's rect on each side.

### SPEC-0017/E2E-006: A click rings a tile (served)
- Given Deck P served, presented, pointer on
- When the presenter clicks the middle of `Tile A`
- Then one red ring shows around `Tile A`: its outer edge is 10 ± 1 screen pixels outside the tile's edge on each side (6 slide pixels × 1.6667) and its line is 5 ± 1 screen pixels thick; `Tile A` itself looks as before (its computed `outline`, `box-shadow`, `border`, `background-color`, `transform` unchanged)
- And (NFR 7.4) the ring's animation, when present, has a duration of at most 200 ms

### SPEC-0017/E2E-007: Headline and paragraph without a box
- Given Deck P opened directly, presented, pointer on
- When the presenter clicks the bold word inside `Plain paragraph`, then clicks `Pointer test`, then presses End and clicks `Last`
- Then after the first click the whole paragraph `Plain paragraph` is ringed (not the bold word); after the second only the headline `Pointer test` is ringed (not the header area holding it); on slide 3 only the paragraph `Last` is ringed, not the panel

### SPEC-0017/E2E-008: A table is one box (served)
- Given Deck P served, presented, pointer on
- When the presenter clicks the second row's first cell, then the first row's last cell
- Then after each click the ring surrounds the whole table, not a cell; after the second click the ring is the same as after the first

### SPEC-0017/E2E-009: Clicking the ringed box again removes the ring
- Given Deck P presented, pointer on, `Tile A` ringed
- When the presenter clicks `Tile A` again, then once more
- Then after the first click no ring shows; after the second `Tile A` is ringed again

### SPEC-0017/E2E-010: A click outside any box
- Given Deck P presented, pointer on, `Tile B` ringed
- When the presenter clicks an empty area of the slide background, then clicks it again
- Then after the first click no ring shows and the slide itself is not ringed; after the second still no ring

### SPEC-0017/E2E-011: Only one ring
- Given Deck P presented, pointer on, `Tile A` ringed
- When the presenter clicks `Tile B`
- Then exactly one ring shows, around `Tile B`

### SPEC-0017/E2E-012: Changing slide removes the ring
- Given Deck P presented, pointer on, slide 1 shown, `Tile A` ringed
- When the presenter presses Left, then Right, then Left
- Then after the first Left slide 1 still shows and `Tile A` is still ringed; after Right slide 2 shows, no ring, the dot follows the mouse; after the second Left slide 1 shows with no ring

### SPEC-0017/E2E-013: A link is followed, the ring unchanged
- Given Deck P opened directly, presented, pointer on, `Tile A` ringed
- When the presenter clicks `Docs`
- Then the page address ends with `#docs` and `Tile A` is still the only ring

### SPEC-0017/E2E-014: A button runs, the ring unchanged (served)
- Given Deck P served, presented, pointer on, no ring
- When the presenter clicks the label text inside `Count`
- Then the button reads `Count 1` and no ring shows

### SPEC-0017/E2E-015: L turns dot and ring off, and back on without a ring
- Given Deck P presented, pointer on, `Tile A` ringed, mouse over the slide
- When the presenter presses L, then L again and moves the mouse
- Then after the first L no dot and no ring show and the system cursor shows; after the second the dot shows and no ring

### SPEC-0017/E2E-016: Leaving ends the pointer, presenting again starts off
- Given Deck P opened directly, presented, pointer on, `Tile A` ringed
- When the presenter presses Escape, then F, then moves the mouse to (800, 450)
- Then after Escape the deck is out of full screen with no dot and no ring; after F it is presented with no dot and no ring

### SPEC-0017/E2E-019: L typed in a text field
- Given Deck P opened directly, presented, pointer on, `Tile A` ringed
- When the presenter clicks the field `Note`, types `L`
- Then the field holds `L`, the pointer is still on, `Tile A` is still the only ring

### SPEC-0017/E2E-024: Scaling and resizing (served)
- Given Deck P served, presented at scale 1.6667, pointer on, `Tile A` ringed
- When the window is resized to 1280 × 720 (scale 1.3333) and the mouse moved to (640, 360)
- Then the dot is 24 ± 1 screen pixels across, centred on (640, 360); the ring's outer edge is 8 ± 1 screen pixels outside `Tile A` on each side, around the tile's new place

### SPEC-0017/E2E-025: A drawing is one box
- Given Deck P opened directly, presented, pointer on
- When the presenter clicks the second shape of the drawing
- Then the ring surrounds the whole drawing

### SPEC-0017/E2E-026: Touch then mouse
- Given Deck P opened directly on a screen taking both touch and a mouse (`has_touch=True`), presented, pointer turned on with L, the mouse moved to (800, 450) so the dot shows there
- When the presenter taps `Tile B`, then taps `Tile B` again, then moves the mouse to (400, 300)
- Then after the first tap no dot shows and `Tile B` is ringed; after the second no dot and no ring show; after the mouse move the dot shows centred within 1 pixel of (400, 300)

### SPEC-0017/E2E-027: Reduced motion
- Given Deck P opened directly with the system asking for reduced motion, presented, pointer on
- When the presenter clicks `Tile A`
- Then the ring shows at full opacity and final size on the first frame after the click, with no animation running (`ring.getAnimations().length === 0`, computed `opacity` `1`, read in the first `requestAnimationFrame` after the click)

### SPEC-0017/E2E-030: Printing while pointing
- Given Deck P opened directly, presented, pointer on, dot shown, `Tile A` ringed
- When the deck is printed (to a PDF)
- Then no page shows a red dot or a red ring, and the pages are identical to a print made with the pointer never turned on (the reference print is taken in the same session, presented, before L; normalized per DEC-017)

### SPEC-0017/E2E-037: Ring clipped at the slide edge
- Given Deck P opened directly, presented, pointer on, slide 2 shown
- When the presenter clicks `Edge tile`
- Then the ring shows on the top, right and bottom of `Edge tile` (red pixels there), and no red shows left of the slide's left edge
- Driver (DEC-017): the check of the left side runs with the window at 1800 × 900, where the slide has black side bands, reading the pixel column just left of the slide; at 1600 × 900 the ring's left part lies outside the layer, which ends at the slide edge.

## Constraints

- Files not to touch: every other template, `src/mcp_htmleditor/static/*`, `tests/testdata/*`.
- Dependencies not to add: none.
- Patterns to avoid: re-deciding a reading of DEC-008; marking the ringed element (no attribute or class written on slide content); `preventDefault` on a link, button or field click; CSS `@keyframes`; fixed waits.
- Scope boundary: the editor's control, relay, edit mode and save are US-0104.

## Definition of done

- [ ] RED evidence recorded for every new test before the block edit, in `.implement/US-0103-red.log`.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: US-0102's tests, the golden hashes of `slides-empty.html`, `tests/test_fullscreen_e2e.py`, `tests/test_reference_decks_present_e2e.py` green; `node --check` on the block's script passes.
- [ ] Durations reported (`make test ARGS='-k "pointer_ring or pointer_served" --durations=0'`).
- [ ] Docs updated: none in this story (US-0110).
- [ ] Self review: full (tier 1), including a walk through DEC-008 on each Deck P element.
- [ ] One commit `US-0103: Ring and the box choice rules`, body `Spec: SPEC-0017` and FR-NEW-005 to FR-NEW-009, FR-NEW-012, FR-NEW-013.
