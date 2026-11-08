# US-0098: Presentation mode of the stacked decks

> Spec: SPEC-0016 (sdlc/specs/SPEC-0016-reference-decks-and-editor-residues/)
> Nature: BUG
> Priority: P1
> Depends on: US-0097
> min_tier: 1
> Files touched: 3
> Closes spec: no

## Objective

`presentation-standard.html` (4 slides) and `roadmap-one-pager.html` (1 slide) show every slide one under the other,
with no script at all: no presentation mode, no key navigation. After this story they keep that stacked layout
outside presenting, gain a current slide moved by the keys, and present that one slide alone, uniformly scaled, from
`file://` or the editor, with a PPTX export byte identical.

Silent pitfalls (why tier 1): their slides are `width:1280px; min-height:720px; margin:40px auto` and must be measured
at scale 1 and centered with that margin removed while presenting; any marker the script writes into the DOM is
saved by the editor if it outlives presenting; the export must not move (DEC-007).

## Requirements covered

- SPEC-0016/BR-009 (partial: the two stacked decks): Each of the five decks SHALL contain a `:fullscreen` CSS rule, one element with `id="btn-present"` whose activation calls `enterPresentation()`, and script functions named `enterPresentation`, `exitPresentation` and `updateFullscreenScale`.
- SPEC-0016/BR-010: WHEN a deck among the five enters presenting, by activating `#btn-present`, by the key `f` or `F`, or by the editor page's `#present-btn` THE deck SHALL show exactly one slide, the current one, centered, with `--fs-scale` set on `<html>` to `s` and its visible box measuring `w * s` by `h * s` within 1 pixel.
- SPEC-0016/BR-011: WHILE a deck among the five is presenting THE deck SHALL display no element outside the current slide: its `.toolbar`, `.shell-header`, `.nav-arrow`, `.status-bar`, `#btn-present` and every other slide have computed `display: none` or lie entirely outside the viewport.
- SPEC-0016/BR-012: WHILE a deck among the five is open and its focused element is none of editable text, an `<input>`, a `<textarea>` or a `<select>` THE deck SHALL move one slide forward on `ArrowRight`, `ArrowDown` or space, one slide back on `ArrowLeft` or `ArrowUp`, to the first slide on `Home`, to the last on `End`, enter presenting on `f` or `F`, and leave presenting on `Escape`.
- SPEC-0016/BR-013: WHEN a deck among the five leaves presenting THE deck SHALL remove `--fs-scale` from `<html>`, keep the current slide current, and show its layout of before entering: the shell deck with its toolbar and the current slide, the stacked deck with every slide one under the other and the current slide's top edge inside the viewport.
- SPEC-0016/BR-014: WHEN the viewport changes size while a deck among the five is presenting THE deck SHALL set `--fs-scale` to the `s` of the new size.
- SPEC-0016/BR-015: The five decks SHALL NOT change their PPTX export: the slide XML hashes recorded for `ibm-carbon.html`, `example-ei-complete.html`, `presentation-standard.html` and `roadmap-one-pager.html` stay equal to their golden values, and `example-carbon-complete.html` exports 9 slides whose slide XML is byte identical to its export at c507194.
- SPEC-0016/BR-017: Each of the five decks SHALL behave per BR-010 to BR-014 both when opened as a `file://` URL and when shown in the editor page.

Business rules (spec, verbatim): "The current slide ... of a stacked deck, the first slide. The page background behind
the slide is `rgb(0, 0, 0)`." "In a stacked deck outside presenting, the moves change which slide is current (used on
entering, BR-010, and on leaving, BR-013) and scroll it into view." "Outside presenting ... a stacked deck shows every
slide one under the other as today, plus `#btn-present`, which is not inside any slide." Design reading (DEC-008):
the current slide starts at the first one and the keys move it; entering shows the current slide.

## Independent Test

`make test ARGS='-k reference_decks_present'`: the stacked deck cases and BT-018 red before (no `#btn-present`, no
script), green after, with the shell cases of US-0097 still green; `make test ARGS='-k golden'` unchanged.

## Design excerpt

### Decisions
- DEC-008 (SPEC-0016): "Stacked decks: `#btn-present` is the first child of `<body>`, outside every slide, `position:fixed; top:16px; right:16px`; a script at the end of `<body>` holds `slides`, `current = 0`, `render`, `navigate`, `goToSlide` and the building blocks. While presenting, only the slide carrying `data-fs-current` shows ... The marker exists only while presenting (set in `render` and on `fullscreenchange` entering, removed on leaving), then the current slide is scrolled into view (`scrollIntoView({block:'start'})`). The current slide starts at the first one; moves outside presenting change it and entering shows it."
- DEC-007 (SPEC-0016): every added selector contains `:` or `[`; no class or attribute added in the file inside a slide; added elements (`<button>`, `<script>`) outside every slide.
- DEC-009 (SPEC-0016): append the two stacked decks to `DECKS` in `tests/test_reference_decks_present_e2e.py`; same `file` and `editor` tests.
- DEC-014 (SPEC-0016): the SPEC-0016 browser tests take at most 40 s together.

### Contracts
CSS (DEC-008, verbatim selectors):

```css
:fullscreen body { margin:0; height:100vh; overflow:hidden; display:flex; align-items:center; justify-content:center; background:#000; }
:fullscreen section[data-type="slide"]:not([data-fs-current]) { display:none; }
:fullscreen section[data-type="slide"][data-fs-current] { margin:0; box-shadow:none; flex:none; scale:var(--fs-scale, 1); transform-origin:center center; }
:fullscreen #btn-present { display:none; }
```

Script globals (function declarations, so the editor relay of US-0095 finds `navigate` and `goToSlide` on `window`):
`slides` (`Array.from(document.querySelectorAll('[data-type="slide"]'))`), `current`, `render()`, `navigate(dir)`
(bounded), `goToSlide(idx)`, `updateFullscreenScale()` (measures `slides[current]`, same formula as the bootstraps),
`enterPresentation()`, `exitPresentation()`, a `fullscreenchange` listener (render then scale on entering; on leaving
remove every `data-fs-current`, remove `--fs-scale`, `slides[current].scrollIntoView({block:'start'})`), a `resize`
listener, and the keydown table with the focus exception of the bootstraps. Button:
`<button id="btn-present" onclick="enterPresentation()" title="Présenter (F)" style="position:fixed;top:16px;right:16px;z-index:10">Présenter</button>`.

### Paths
| Path | Action |
|---|---|
| `templates/reference/slides/presentation-standard.html` | modify: CSS rules, button first in `<body>`, script last in `<body>` |
| `templates/reference/slides/roadmap-one-pager.html` | modify: same |
| `tests/test_reference_decks_present_e2e.py` | modify: two stacked decks in `DECKS`, BT-018 test |

### Existing patterns
- Building blocks: `templates/bootstrap/slides-empty.html:373` to `:410`; the shell decks after US-0097.
- Stacked slide box: `presentation-standard.html:21` to `:27`, slides at `:195`, `:204`, `:241`, `:255`; `roadmap-one-pager.html:21`, slide at `:94`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Location `tests/test_reference_decks_present_e2e.py`. This story makes the BT-003, BT-017, BT-019 and BT-020
cases owned by US-0097 pass for the two stacked decks (parameters appended; the current slide is the one carrying
`data-fs-current` while presenting; for `roadmap-one-pager.html`, which has one slide, BT-017's "one before the last"
is the last). It owns BT-018 for both families.

### SPEC-0016/BT-018: Leaving presenting
- Level / Driver: functional e2e; Playwright on the `file://` copy
- Given a shell deck (`example-ei-complete.html`) presenting on slide 3 (`End`, then `ArrowLeft` until slide 3)
- When `Escape`
- Then `document.fullscreenElement` is `null`, `--fs-scale` is absent from `<html>`'s inline style, slide 3 is current (`.slide.active` is `#slide-2`) and the `.toolbar` is displayed
- Given `presentation-standard.html` presenting on slide 3
- When `Escape`
- Then the four slides are displayed one under the other (each `display` not `none`, tops strictly increasing), `--fs-scale` is absent, no element carries `data-fs-current`, and slide 3's top edge lies between 0 and the viewport height
- Red before the fix because: the stacked deck cannot present at all (no `#btn-present`, no `f`).

## Constraints

- Files not to touch: the shell decks, the bootstraps, `tests/testdata/pptx_slide_hashes.json`, any slide's markup.
- Dependencies not to add: none.
- Patterns to avoid: a class marker or inline `display` written on slides; a marker that stays after leaving; selectors without `:` or `[`; fixed waits.
- Scope boundary: the guard over every template is US-0099.

## Definition of done

- [ ] RED evidence recorded for the stacked cases and BT-018 before the deck edits, in `.implement/US-0098-red.log`.
- [ ] Every acceptance test above green, the stacked cases of BT-003, BT-017, BT-019, BT-020 green; `make check` green; main stays green after the squash.
- [ ] Non regression: golden hashes of `presentation-standard.html` and `roadmap-one-pager.html` unchanged (BT-031); a save from the editor outside presenting writes no `data-fs-current` and no `--fs-scale` (checked once by hand or in the `editor` test: read the file after leaving).
- [ ] Durations reported, the SPEC-0016 browser tests at most 40 s in total so far.
- [ ] Self review: full (tier 1).
- [ ] One commit `US-0098: Presentation mode of the stacked decks`, body `Spec: SPEC-0016` and BR-009 to BR-015, BR-017.
