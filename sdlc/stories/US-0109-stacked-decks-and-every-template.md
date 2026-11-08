# US-0109: Stacked decks and every template

> Spec: SPEC-0017 (sdlc/specs/SPEC-0017-presentation-pointer/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0104, US-0108
> min_tier: 1
> Files touched: 4
> Closes spec: no

## Objective

The two stacked reference decks (`presentation-standard.html`, `roadmap-one-pager.html`) have no toolbar: their
`Présenter` button is pinned to the window. After this story each gets a matching `Pointeur` button pinned just left
of it, the L line and the pointer block, so all 11 presentation templates carry the pointer; the guard's pending set
disappears, and two sweeps prove the pointer works in every starting point and the stacked deck, and that pointing
in the editor leaves every template's PPTX export as before.

Silent pitfalls (why tier 1): the stacked slide is 1280 slide pixels wide (scale 1.25 in 1600 × 900, not 1.6667);
moving `#btn-present` into a wrapper must keep the SPEC-0016 presenting tests green (it stays hidden while
presenting); the sweep switches the served file in one server to stay within the run time budget.

## Requirements covered

- SPEC-0017/FR-NEW-002 (the stacked deck placement): WHEN the presenter presses the Pointeur control THE deck presentation SHALL present the deck full screen with the pointer on.
- SPEC-0017/FR-NEW-004 (scale 1.25 of the stacked deck): WHILE the pointer is on and the mouse is over the current slide THE deck presentation SHALL show a red dot centered on the mouse position in place of the system cursor.
- SPEC-0017/FR-NEW-007 (every template): WHEN the current slide changes while the pointer is on THE deck presentation SHALL remove the ring and keep the pointer on.
- SPEC-0017/FR-NEW-013 (every template's PPTX export): The deck presentation SHALL NOT change the PPTX export of a deck, nor show the dot or the ring when the deck is printed.
- SPEC-0017/FR-NEW-014: The deck presentation SHALL offer the pointer in every presentation template, the same way opened directly and in the editor.

Business rules (spec, verbatim): FR-NEW-002 "In a stacked deck, which has no toolbar, the Pointeur control is a
button of the same look as the deck's `Présenter` button, pinned to the window and placed immediately to the left of
it, 8 page pixels apart, with its top edge aligned with it; like that button, it is hidden while presenting."
FR-NEW-004 "In a stacked deck, presented one slide at a time like the other decks, only the slide shown is the
current slide." FR-NEW-013 "the PPTX export of each presentation template, once it carries the pointer, has the same
slides, shapes, positions and texts as its export before this increment." FR-NEW-014 "the 11 presentation templates
(3 starting points, 8 reference decks), and therefore every deck created from a starting point, carry the pointer,
the Pointeur control and the L key, in both deck families". Glossary: "Slide pixel: a pixel of the slide at the
deck's own design width (960 for the starting points and the other reference decks, 1280 for the two stacked decks)".

## Independent Test

`make test ARGS='-k "pointer_templates or presentation_templates_fullscreen or golden or reference_decks_present"'`:
E2E-029 and E2E-032 red before (the stacked decks have no pointer), green after; the guard runs with no pending set
over the 11 files; SPEC-0016 presenting tests of both stacked decks green.

## Design excerpt

### Decisions
- DEC-015 (SPEC-0017): "`#btn-present` moves into a new first child of `<body>`, `<div id=\"deck-controls\" style=\"position:fixed;top:16px;right:16px;z-index:10;display:flex;gap:8px;align-items:flex-start\">`, holding `#btn-pointer` then `#btn-present`; both buttons carry the same inline look (none today beyond the browser default) and `#btn-present` loses only its positioning declarations. The deck's own CSS gains `:fullscreen #deck-controls { display:none; }` and keeps `:fullscreen #btn-present { display:none; }`."
- DEC-003 (SPEC-0017): the L line `if ((e.key === 'l' || e.key === 'L') && !e.ctrlKey && !e.metaKey && !e.altKey) togglePointer();` in each stacked deck's key table (SPEC-0016 US-0098 script).
- DEC-004 (SPEC-0017): the current slide is `[data-type="slide"][data-fs-current]` in a stacked deck; `s = rect.width / slide.offsetWidth` gives 1.25.
- DEC-012 (SPEC-0017): baseline of E2E-029 = `tests/testdata/pptx_slide_hashes.json` (ten templates) and `tests/testdata/example_carbon_complete_slide_hashes.json`; equal slide XML hashes imply the same slides, shapes, positions, sizes and texts; never regenerated.
- DEC-016 (SPEC-0017): delete `PENDING_POINTER` and its skip; the guard then checks the three parts on every discovered presentation file.
- DEC-017 (SPEC-0017): the sweep keeps one editor server and switches the served file with a second `start_http_server(path)` call (idempotent switch, `src/mcp_htmleditor/http_server.py:1051`), then `page.goto` the editor; export in process with `to_pptx` and `slide_hashes()` of `tests/test_export_golden.py:41`.
- DEC-018 (SPEC-0017): `tests/test_pointer_templates_e2e.py` about 12 s in total (E2E-036 included).

### Contracts
Stacked controls, first child of `<body>`:
```html
<div id="deck-controls" style="position:fixed;top:16px;right:16px;z-index:10;display:flex;gap:8px;align-items:flex-start">
  <button id="btn-pointer" onclick="presentWithPointer()" title="Présenter avec le pointeur (L)" aria-label="Présenter avec le pointeur (L)">Pointeur</button>
  <button id="btn-present" onclick="enterPresentation()" title="Présenter (F)">Présenter</button>
</div>
```

### Paths
| Path | Action |
|---|---|
| `templates/reference/slides/presentation-standard.html` | modify: controls wrapper, `#btn-pointer`, `:fullscreen #deck-controls` rule, L line, block |
| `templates/reference/slides/roadmap-one-pager.html` | modify: same |
| `tests/test_presentation_templates_fullscreen.py` | modify: remove `PENDING_POINTER` and its skip |
| `tests/test_pointer_templates_e2e.py` | modify: E2E-029, E2E-032 |

### Existing patterns
- Stacked script and CSS: SPEC-0016 US-0098 in both decks (`data-fs-current`, `:fullscreen #btn-present`).
- Golden hashes: `tests/test_export_golden.py:28` to `:41`.
- Creating a deck from a starting point: `mcp-htmleditor new carbon|ei|medical`, in process through the code the CLI calls, or a copy of the bootstrap file.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Location `tests/test_pointer_templates_e2e.py`, module page at 1600 × 900.

### SPEC-0017/E2E-029: PPTX export unchanged
- Level / Driver: functional e2e plus integration; one served page over the 11 templates, then `to_pptx` in process
- Given each of the 11 presentation templates, and a baseline kept with the tests, captured from the product as shipped before this increment: for each template the slide count and, per slide, each shape's kind, position, size and text (DEC-012: the golden slide XML hashes)
- When each template, now carrying the pointer, is exported to PPTX, once directly and once after a served presentation with the pointer on and a ring shown (a copy served, `Pointeur` pressed, the mouse moved over the slide, a click on the slide's headline, Escape; the copy's bytes still equal the template's)
- Then both exports give the same slide count and, slide by slide, the same shapes, positions, sizes and texts as before (slide XML hashes equal to the baseline)

### SPEC-0017/E2E-032: Stacked deck and every template
- Level / Driver: functional e2e; Deck S (a copy of `presentation-standard.html`) opened as `file://`, decks created from `carbon`, `ei`, `medical` served
- Given Deck S opened directly, and a new deck created from each of the 3 starting points (`carbon`, `ei`, `medical`) served
- When in each, the presenter presents with the Pointeur control, moves the mouse to (800, 450), clicks the slide's headline, then presses Right
- Then in each the dot shows, the headline is ringed, and after Right the next slide shows without a ring (a starting point holding one slide gets a second slide in its copy before the test, so Right has a next slide)
- And in Deck S, before presenting, `Pointeur` shows immediately left of `Présenter`, 8 page pixels apart, their top edges aligned, and neither overlaps the other
- And in Deck S presented in a 1600 × 900 window (slide 1280 × 720, scale factor 1.25), the dot is 22.5 ± 1 screen pixels across (18 slide pixels × 1.25)

## Constraints

- Files not to touch: the other templates, the golden fixtures, `src/`.
- Dependencies not to add: none.
- Patterns to avoid: one server per template in the sweep (budget); regenerating golden data; a selector without `:` or `[` in the stacked decks' CSS.
- Scope boundary: documentation and the spec converge are US-0110.

## Definition of done

- [ ] RED evidence recorded for E2E-029, E2E-032 and the guard without the pending set, in `.implement/US-0109-red.log`.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: SPEC-0016 presenting and leaving tests of both stacked decks green (BT-018 included); golden hashes unchanged.
- [ ] Durations reported (`make test ARGS='-k pointer --durations=0'`), all SPEC-0017 browser tests at most 40 s so far.
- [ ] Self review: full (tier 1).
- [ ] One commit `US-0109: Stacked decks and every template`, body `Spec: SPEC-0017` and FR-NEW-002, FR-NEW-004, FR-NEW-007, FR-NEW-013, FR-NEW-014.
