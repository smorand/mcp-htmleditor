# US-0102: Pointer dot, L key and the deck's Pointeur control

> Spec: SPEC-0017 (sdlc/specs/SPEC-0017-presentation-pointer/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 1
> Files touched: 3
> Closes spec: no

## Objective

A presenter showing a deck full screen has nothing but the small system cursor to point with. After this story a
deck made from the IBM Carbon starting point (`templates/bootstrap/slides-empty.html`), opened directly as a file,
turns the mouse into a red dot over the slide with L, and its own `Pointeur` control presents with the dot already
on. The ring (clicks) comes in US-0103, the editor in US-0104, the other templates from US-0106.

Silent pitfalls (why tier 1): the block's CSS must keep the PPTX export byte identical (no class selector); full
screen is entered asynchronously, so the pointer is armed before the request and decided on `fullscreenchange`; the
dot is measured in screen pixels while sizes are given in slide pixels.

## Requirements covered

- SPEC-0017/FR-NEW-001 (partial: the deck's own L key, opened directly): WHEN the presenter presses L while a deck is presented full screen THE deck presentation SHALL turn the pointer on if it was off, and off if it was on.
- SPEC-0017/FR-NEW-002 (partial: the control in the deck's own toolbar): WHEN the presenter presses the Pointeur control THE deck presentation SHALL present the deck full screen with the pointer on.
- SPEC-0017/FR-NEW-003: WHEN a presentation starts by any means other than the Pointeur control THE deck presentation SHALL start with the pointer off.
- SPEC-0017/FR-NEW-004: WHILE the pointer is on and the mouse is over the current slide THE deck presentation SHALL show a red dot centered on the mouse position in place of the system cursor.
- SPEC-0017/FR-NEW-009 (partial: the dot and the cursor; the ring is US-0103): WHEN the pointer is turned off THE deck presentation SHALL remove the dot and the ring and show the system cursor again.
- SPEC-0017/FR-NEW-013 (partial: the Carbon starting point's PPTX export, printing after a refused full screen): The deck presentation SHALL NOT change the PPTX export of a deck, nor show the dot or the ring when the deck is printed.
- SPEC-0017/FR-NEW-014 (partial: the Carbon starting point carries the three parts): The deck presentation SHALL offer the pointer in every presentation template, the same way opened directly and in the editor.

Business rules (spec, verbatim, the parts this story builds): "L and l both count. A press with Ctrl, Cmd or Alt
held does nothing. ... While the deck is not presented full screen, L does nothing." "the control sits immediately
after the present control ... It is a button reachable with Tab and activated with Enter or Space. If the browser
refuses the deck's own full screen, the control starts the fallback presentation exactly as the present control
does, with no pointer." Label `Pointeur`, tooltip and accessible name `Présenter avec le pointeur (L)`. "'any means'
is the editor's present control, the deck's own present control and the F key. When the presentation ends (Escape,
or leaving full screen any other way) the pointer is turned off and the dot and the ring are removed." "the dot is a
disc 18 slide pixels across, red `#FA4D56`, ringed by a 2 slide pixel white `#FFFFFF` halo ... at a scale factor s,
the dot is 18 × s screen pixels across. ... its centre is within 1 screen pixel of the mouse position. Over the black
margins around the slide and when the mouse leaves the window, there is no dot and the system cursor shows over the
margins. When the pointer is turned on, or the slide changes, the dot shows at once at the last known mouse position
if it is over the current slide; if the mouse has not moved since the page loaded, the dot shows at the first mouse
move. The dot follows mouse input only: a touch or pen contact neither shows nor moves the dot and hides it if
shown ... The dot is drawn above everything on the slide and never takes a click."

## Independent Test

`make test ARGS='-k pointer_dot'`: the eight tests red before the block exists (no `#btn-pointer`, no dot), green
after; `make test ARGS='-k "golden or fullscreen or reference_decks_present"'` unchanged (the Carbon starting point
is in the golden set, its slide XML hashes must not move).

## Design excerpt

### Decisions
- DEC-001 (SPEC-0017): the pointer lives in one block per template, source `templates/bootstrap/slides-empty.html` (this story writes the source); the button and the L line are hand edits.
- DEC-002 (SPEC-0017): block = `<!-- deck-pointer:begin -->`, `<style id="deck-pointer-style">`, `<script id="deck-pointer-script">` with one IIFE assigning the API to `window`, `<!-- deck-pointer:end -->`, immediately before `</body>`.
- DEC-003 (SPEC-0017): the L key is one line in the deck's own `keydown` table, under its focus exception: `if ((e.key === 'l' || e.key === 'L') && !e.ctrlKey && !e.metaKey && !e.altKey) togglePointer();`. This exact text is a guard marker: it must not appear inside the block.
- DEC-004 (SPEC-0017): "when the pointer turns on, the block appends `#deck-pointer-layer` to `<body>` and sets `data-deck-pointer` on `<html>`; one `requestAnimationFrame` loop runs while on. Each frame it finds the current slide (`[data-type="slide"].active, [data-type="slide"][data-fs-current]`, else the first slide), places the layer at the slide's `getBoundingClientRect()`, computes `s = rect.width / slide.offsetWidth`, ... and, when the current slide element differs from the previous frame's, ... redraws the dot at the last mouse point. The dot is placed at `lastPoint - layer origin - 9 * s`, shown only while `lastPoint` lies inside the slide rect. Pointer off removes the layer, the attribute and the loop."
- DEC-005 (SPEC-0017): the cursor is hidden only by `:fullscreen[data-deck-pointer] [data-type="slide"], :fullscreen[data-deck-pointer] [data-type="slide"] * { cursor:none !important; }`; never an inline style on a slide.
- DEC-006 (SPEC-0017): state `allowed` (default true), `armed`, `on`; `fullscreenchange` entering sets `on = armed` then `armed = false`, leaving sets `on = false`; `presentWithPointer()` arms, requests full screen, disarms on rejection or error.
- DEC-007 (SPEC-0017, the dot part): `pointermove` with `pointerType === 'mouse'` records `lastPoint` from page load and moves the dot; `pointerdown` of another type hides it; `mouseout` on `document` with `relatedTarget === null` hides it.
- DEC-011 (SPEC-0017): `@media print { #deck-pointer-layer { display:none !important; } }`.
- DEC-012 (SPEC-0017): no class selector in the block; nothing added inside a slide; the golden hashes are the PPTX baseline, never regenerated.
- DEC-017 (SPEC-0017): `tests/pointer_support.py` with Deck P, `POINTER_STATE`, module page fixture `pointer_file_page`; mouse leaving = `mouseout` with `relatedTarget: null` dispatched on the element under the mouse; prints compared after removing `/CreationDate (...)` and `/ModDate (...)`, each print test first asserts two prints of the unchanged page are equal.
- DEC-018 (SPEC-0017): `test_pointer_dot_e2e.py` about 6 s, part of the spec's 40 s.

### Contracts
Window API of the block (5.1): `presentWithPointer()`, `armPointer(on)` (`armed = !!on && allowed`), `togglePointer()`
(no effect unless `document.fullscreenElement` and `allowed`), `setPointerAllowed(allowed)` (`false` also disarms and
turns off; the editor uses it in US-0104).

Block CSS (5.3, this story's part):
```css
:fullscreen[data-deck-pointer] [data-type="slide"],
:fullscreen[data-deck-pointer] [data-type="slide"] * { cursor:none !important; }
#deck-pointer-layer { position:fixed; overflow:hidden; pointer-events:none; z-index:2147483647; margin:0; padding:0; }
#deck-pointer-dot, #deck-pointer-ring { position:absolute; pointer-events:none; box-sizing:border-box; margin:0; }
#deck-pointer-dot { border-radius:50%; background:#FA4D56; }
#deck-pointer-ring { border-style:solid; border-color:#DA1E28; background:transparent; }
@media print { #deck-pointer-layer { display:none !important; } }
```
Dot inline sizes: `width = height = 18 * s` px, `box-shadow: 0 0 0 <2 * s>px #FFFFFF`.

Button, immediately after `#btn-present` in `.toolbar`:
`<button class="cds-btn-icon" id="btn-pointer" onclick="presentWithPointer()" title="Présenter avec le pointeur (L)" aria-label="Présenter avec le pointeur (L)" style="width:auto;padding:0 12px">Pointeur</button>`

Test contract (ids read by `POINTER_STATE`): `#deck-pointer-layer`, `#deck-pointer-dot`, `#deck-pointer-ring`, `html[data-deck-pointer]`.

### Paths
| Path | Action |
|---|---|
| `templates/bootstrap/slides-empty.html` | modify: block before `</body>`, `#btn-pointer`, L line in the key table |
| `tests/pointer_support.py` | create: `deck_p()` (spec 9.0, from the Carbon bootstrap, 3 slides), `POINTER_STATE`, `pointer_file_page` (module scope, 1600 × 900), `print_pdf_normalized(page)` |
| `tests/test_pointer_dot_e2e.py` | create: the eight tests below |

### Existing patterns
- Deck building blocks and key table: `templates/bootstrap/slides-empty.html:373` to `:417`.
- Module page and fixture builders: `tests/width_support.py:113` to `:166`.
- Opening a deck copy as `file://` and presenting: `tests/test_reference_decks_present_e2e.py:139` to `:186`.
- Bounded observation: `tests/browser_wait.py` (`wait_until`); fixed waits are refused by `tests/test_no_fixed_waits.py`.
- Pillow screenshot reads: `tests/render_support.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Deck P (spec 9.0): from the IBM Carbon starting point, 3 slides, 1600 × 900 window (slide 960 × 540, scale
1.6667). Slide 1 white: headline `Pointer test` in the header area, paragraph `Plain paragraph` (word `paragraph`
bold), tiles `Tile A`, `Tile B` (grey fill), a 2 row table (cells with a bottom border), link `Docs` to `#docs`,
button `Count` (click sets `Count 1`), text field `Note`, a drawing of two shapes. Slide 2 `#161616`: `Dark paragraph`,
grey `Edge tile` touching the left edge. Slide 3 white: grey panel covering 90 % of the slide holding `Last`.
All in `tests/test_pointer_dot_e2e.py`, functional e2e, Playwright on Deck P opened as `file://` unless stated.

### SPEC-0017/E2E-001: Pointer in a deck opened directly
- Given Deck P opened directly, presented with F, the mouse at screen point (800, 450)
- When the presenter moves the mouse by 1 pixel, then presses L, then moves the mouse to (400, 300)
- Then before L there is no red dot and the system cursor shows; right after L, before any further move, a red dot shows centred within 1 pixel of (801, 450); after the move a red dot 30 ± 1 screen pixels across is centred within 1 pixel of (400, 300) and the system cursor is hidden over the slide (the current slide's computed `cursor` is `none`)

### SPEC-0017/E2E-005: The deck's own Pointeur control, by keyboard
- Given Deck P opened directly, not presented
- When the presenter tabs to the control after `Présenter (F)` and presses Enter, then moves the mouse to (800, 450)
- Then the focused control is labelled `Pointeur` with the name `Présenter avec le pointeur (L)`; the deck is full screen and the dot shows

### SPEC-0017/E2E-017: L outside a presentation does nothing
- Given Deck P opened directly, not presented, the mouse over slide 1
- When the presenter presses L, then F, then moves the mouse
- Then after L no dot shows and the deck is unchanged; after F the deck is presented with the pointer off

### SPEC-0017/E2E-020: Modifier keys with L
- Given Deck P opened directly, presented, pointer off
- When the presenter presses Alt+L, then Ctrl+L, then Meta+L, each as delivered to the page by the test browser
- Then after each one no dot shows and the slide is unchanged

### SPEC-0017/E2E-021: Over the black margins
- Given Deck P opened directly, presented in a 1600 × 1000 window (black bands of 50 pixels above and below the slide), pointer on
- When the presenter moves the mouse to (800, 20), then to (800, 500)
- Then at (800, 20) no dot shows and the system cursor shows; at (800, 500) the dot shows there

### SPEC-0017/E2E-022: Mouse leaves the window
- Given Deck P opened directly, presented, pointer on, dot shown at (800, 450)
- When the mouse leaves the window (driver: `mouseout` with `relatedTarget: null`, DEC-017)
- Then no dot shows

### SPEC-0017/E2E-023: Visible on dark and light slides
- Given Deck P opened directly, presented, pointer on
- When the mouse is at (800, 450) on an empty spot of slide 1 (white), then on an empty spot of slide 2 (`#161616`)
- Then on both slides the pixels under the dot hold red `#FA4D56` at its centre and white `#FFFFFF` in a ring around it (screenshot read with Pillow; tolerance 8 per channel for antialiasing)

### SPEC-0017/E2E-039: Pointeur control when full screen is refused
- Given Deck P opened directly in a browser that refuses full screen (init script: `Element.prototype.requestFullscreen = () => Promise.reject(new TypeError('refused'))`)
- When the presenter presses `Pointeur`, then L, then moves the mouse over slide 1, then prints to PDF
- Then the deck is not presented, no dot shows, the slide is unchanged, and the PDF matches a print made without pressing `Pointeur` (normalized per DEC-017)
- Red before the fix because: no `#btn-pointer` exists.

## Constraints

- Files not to touch: every other template, `src/mcp_htmleditor/static/*`, `tests/testdata/*`, `tests/test_export_golden.py`.
- Dependencies not to add: none (Pillow is already importable through python-pptx and used by `tests/render_support.py`).
- Patterns to avoid: class selectors in the block; any element or attribute added inside a slide; `@keyframes`; top level globals other than the four API functions; fixed waits.
- Scope boundary: clicks and the ring are US-0103; the editor is US-0104; the sync tool and the guard are US-0105.

## Definition of done

- [ ] RED evidence recorded for every new test before the template edit, in `.implement/US-0102-red.log`.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: the golden hashes of `templates/bootstrap/slides-empty.html` unchanged; `tests/test_fullscreen_e2e.py`, `tests/test_reference_decks_present_e2e.py`, `tests/test_strip_idempotent.py` unchanged and green; `node --check` on the block's script (extracted) passes.
- [ ] Durations reported (`make test ARGS='-k pointer_dot --durations=0'`), about 6 s.
- [ ] Docs updated: none in this story (US-0110).
- [ ] Self review: full (tier 1).
- [ ] One commit `US-0102: Pointer dot, L key and the deck's Pointeur control`, body `Spec: SPEC-0017` and FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-009, FR-NEW-013, FR-NEW-014.
