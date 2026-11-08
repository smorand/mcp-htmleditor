# Pointer in presentation mode: functional specification

> Id: SPEC-0017
> Nature: FEAT
> Depth: M
> Depth evidence: 2 areas (the deck being presented, the editor page), 14 requirements, no persisted concept, no public contract change; the files written by the agent keep their format
> Status: implemented
> Amended: 2026-11-08 (BL-0040: E2E-008 steps match FR-NEW-006; FR-NEW-005 rules 3 to 5 and the page number made explicit)
> Generated on: 2026-11-08
> Project: existing
> From backlog: n/a
> Depends on: SPEC-0001 (FR-026 to FR-028, presentation mode), SPEC-0016 (key table, editor relay, presenting of the reference decks)
> Ported from: the sibling product snxt-deck-builder, branch develop, README section "Present on two screens", paragraph "**Pointer**, beside **Full screen** (or **L**...)" (read only reference)
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

Nature: FEAT (Q1 yes: no key or control shows a pointer while presenting, see 14.1 E4 to E7; Q2 no authority
defines a pointer, so nothing is violated).

## 1. Summary

A person presenting a deck full screen, in the editor or from the file opened directly in a browser, has no
way to show the room or a call watching a shared screen what they are talking about: the system cursor is
small and easily lost on a projected slide. This increment adds a pointer: the L key, or a Pointeur control
beside the present control, turns the mouse into a red dot over the slide, and a click rings the box it lands
on (a card, a tile, a table, or the headline or paragraph when there is no box). It is a port of the same
pointer in snxt-deck-builder, reduced to the single window presentation html-editor has, and it changes
nothing in the file, the exports or the editing.

## 2. Current State

### 2.1 What users can do today

- A presentation is shown in the editor page inside a preview frame. A present control (an icon button,
  tooltip `Mode présentation plein écran`) is shown for presentations only, in view mode and in edit mode
  alike (E1, E2).
- Pressing it puts the deck's own page full screen; the deck then hides its own toolbar and status bar and
  scales the current slide uniformly to fill the screen on black. If the browser refuses, the preview frame
  itself goes full screen as a fallback, and the deck does not scale (E3, E4).
- Every presentation template (3 starting points and 8 reference decks, 11 files) carries its own present
  control (tooltip `Présenter (F)`) and its own keys: Right, Down and Space next, Left and Up previous, Home
  first, End last, F to enter, Escape to leave. The keys are ignored while a text field or an editable text
  holds the focus. The same deck file therefore presents the same way when opened directly as a file (E5, E6).
- While presenting from the editor, the editor page forwards arrows, Space, Home, End and Escape to the deck
  when the keyboard focus stayed in the editor page; nothing else is forwarded (E7).
- In edit mode, typing navigation keys in an editable text never moves the slide (E8).
- No key, control or mode shows a pointer, a highlight or a ring on a slide; the only pointer on screen is
  the system cursor (E5, E6, E7; searched, no hit, E9).
- Saving from the editor removes the editor's helpers and the presenting state from a copy of the page
  before writing, and the server removes the editor's helpers again; PPTX and DOCX exports are produced
  from the file on disk, never from what the browser shows (E10, E11, E12).

### 2.2 Specs governing this area

- SPEC-0001/FR-026 to FR-028: presentation mode puts the deck full screen, hides the chrome, scales the
  slide, and moves on the listed keys whichever document holds focus. This increment keeps them unchanged
  and adds the L key and the pointer while presenting.
- SPEC-0016, its key table and editor relay requirements (no relay outside presenting) and its presenting
  requirements (the five building blocks of every presentation template, presenting the reference decks, same
  behavior opened directly or served): kept. This increment adds one key to the table and one control
  beside the present control in every presentation template, and the guard over every presentation
  template gains the pointer.
- SPEC-0015/FR-NEW-010 and SPEC-0009: nothing of the editor is ever saved. This increment extends the rule
  to the pointer.

### 2.3 What is verified today

Real browser tests present the reference decks opened directly and in the editor, and check the keys, the
relay from the editor page, the scaling and the leaving (E13, E14). A guard checks that every presentation
template carries the building blocks of presentation mode (E15). Nothing tests a pointer, since none exists.

## 3. Scope

### 3.1 In scope

- The pointer while a deck is presented full screen: in the editor's presentation and in a deck opened
  directly as a file. The deck carries the behavior, so it is the same in both.
- Every presentation template: the 3 starting points (so every deck created from them carries the pointer)
  and the 8 reference decks.
- The L key, the Pointeur control in the editor toolbar and beside each template's own present control, the red dot, the
  ring, its rules for choosing the box, one ring at a time, the ring removed on slide change.
- Behavior with scaling, outside the slide, without a mouse, over links and controls, inside text fields,
  with reduced motion, on dark and light slides.
- The guard that keeps every presentation template carrying the pointer, and the documentation for the
  person and the agent.

### 3.2 Out of scope, and why

- A presenter view with an audience window (notes, timer, next slide, a second window following the first):
  html-editor presents in one window only. Deferred to BL-0037 (Nature FEAT), from the snxt-deck-builder
  README section "Present on two screens".
- The pointer in decks created before this version: they carry their own script and do not have it. The
  editor shows no Pointeur control for such a deck and L does nothing there; their presentation is
  otherwise unchanged. Bringing it to them (for example by adding it to an existing file on request) is
  deferred to BL-0038 (Nature FEAT).
- The pointer outside full screen (a deck looked at in its normal page, the editor preview in view mode):
  the pointer is a presenting aid only, as in the sibling product, which offers it in presenter mode only.
- The pointer in the fallback presentation (the preview frame put full screen when the browser refuses the
  deck's own full screen): in that case the deck does not know it is presented, so the pointer stays
  unavailable; this fallback is rare and already degraded (no scaling, E4).
- Documents, websites and mails: they have no presentation mode.
- A toggle control visible during the presentation: the screen shows nothing but the slide while presenting
  (SPEC-0016, nothing but the slide while presenting), so the pointer is turned on and off with L while presenting, and the Pointeur control
  starts a presentation with the pointer already on.
- Drawing, annotating or several rings at once: one ring at a time, as in the sibling product.

### 3.3 Constraints imposed by the context

- A deck file keeps presenting on its own when opened directly, without the editor (SPEC-0016, same behavior
  opened directly or served;
  imposed by the project owner: decks are handed to people who do not run the editor).
- The test suite step stays within its time budget, imposed by the project owner in the request for this
  spec: about 235 to 270 s for the gate, never above the 330 s limit (14.1 E16, last measured 320.14 s).

## 4. Actors

| Actor | Who | What they do here |
|---|---|---|
| Presenter | the person showing a deck to a room or a call | presents, turns the pointer on and off, points, rings boxes |
| Editor user | the person editing a presentation in the editor page | edits and saves, possibly after presenting |
| Agent | the AI agent that writes the file | reads and writes the deck; finds nothing of the pointer in it |
| Operator | the maintainer running the test suite | is told by the suite when a presentation template lacks the pointer |

## 4.5 Bounded contexts

| Context | What it owns | Key concepts |
|---|---|---|
| Deck presentation | showing one slide at a time full screen, its keys and its own controls, in the deck file itself | presenting, current slide, pointer, dot, ring, box |
| Editor page | the toolbar around the preview, edit mode, saving, exports, the key relay while presenting | present control, Pointeur control, edit mode, relay, save, export |

## 5. Usage scenarios

### SC-001: Point and ring while presenting from the editor
**Actor:** Presenter
**Preconditions:** a presentation created from a current starting point is open in the editor page, edit
mode is off.
**Flow:**
1. The presenter presses the present control → the deck goes full screen, the pointer is off.
2. They press L → the system cursor disappears over the slide and a red dot follows the mouse there.
3. They click a tile → a red ring surrounds the tile.
4. They click the same tile again → the ring disappears.
5. They press Right → the next slide shows, no ring, the dot still follows the mouse.
6. They press L → the dot disappears and the system cursor is back.
**Postconditions:** the file on disk is unchanged.
**Exceptions:**
- EXC-001a: at step 2 the keyboard focus stayed in the editor page → L still turns the pointer on.
- EXC-001b: at step 3 the click lands on the slide background, outside any box → no ring.
- EXC-001c: at step 1 edit mode is on → no Pointeur control is shown and L does nothing.
- EXC-001d: the deck was created before this version → no Pointeur control, L does nothing, the keys work.
**Interactions:** SC-003 (on, off, leaving), SC-004 (editing after presenting).

### SC-002: Present a deck opened directly as a file
**Actor:** Presenter
**Preconditions:** a deck file from a current template is opened directly in a browser, not served by the
editor.
**Flow:**
1. The presenter presses the deck's own Pointeur control → the deck goes full screen with the pointer on.
2. They move the mouse over the slide → the red dot follows it, the system cursor is hidden over the slide.
3. They click the headline, which has no box → the headline is ringed.
**Postconditions:** the file is unchanged.
**Exceptions:**
- EXC-002a: L pressed while the deck is not presented → nothing happens.
- EXC-002b: L typed in a text field on the slide → the letter is typed, the pointer does not change.
- EXC-002c: the mouse moves to the black margins around the slide → no dot there, the system cursor shows.
- EXC-002d: the presenter touches the screen or uses a pen → the dot hides; a tap rings a box like a click;
  the next mouse move over the slide shows the dot again.

### SC-003: Turn the pointer on and off, change slides, leave
**Actor:** Presenter
**Preconditions:** a deck is presented, pointer on, one tile ringed.
**Flow:**
1. They click another tile → only that tile is ringed.
2. They click a link on the slide → the link is followed, the ring is unchanged.
3. They press L → dot and ring disappear.
4. They press L → the dot is back, no ring.
5. They press Escape → the presentation ends; dot and ring are gone.
6. They present again → the pointer is off.
**Postconditions:** the next presentation starts with the pointer off.
**Exceptions:**
- EXC-003a: Ctrl, Cmd or Alt held with L → the pointer does not change.
- EXC-003b: a button on the slide is clicked → its action runs, the ring is unchanged.

### SC-004: Edit, save and export after pointing
**Actor:** Editor user, Agent, Operator
**Preconditions:** a presentation was presented with the pointer on and a box ringed, then the presentation
ended.
**Flow:**
1. The editor user turns edit mode on, changes a word and the change is saved → the file holds the new word
   and nothing of the pointer.
2. They export the deck to PPTX → the export is the same as before the pointer existed.
3. The agent reads the file → it finds the deck as written, with no trace of the session.
**Postconditions:** file and exports carry nothing of the pointer.
**Exceptions:**
- EXC-004a: a presentation template lacks the pointer → the test suite fails and names the file.
- EXC-004b: the deck is printed while presenting with the pointer on → no dot and no ring on paper.

## 6. Functional requirements

### 6.1 New

#### FR-NEW-001 [EARS-E]: L turns the pointer on and off while presenting
> WHEN the presenter presses L while a deck is presented full screen THE deck presentation SHALL turn the
> pointer on if it was off, and off if it was on.

- **Business rules:** L and l both count. A press with Ctrl, Cmd or Alt held does nothing. In the editor the
  key works whichever page holds the keyboard focus (the deck or the editor page), as the other presenting
  keys do; one press toggles once. While the deck is not presented full screen, L does nothing.
- **User visible text:** none.
- **Scenario:** SC-001, SC-002, SC-003
- **Priority:** Must

#### FR-NEW-002 [EARS-E]: The Pointeur control
> WHEN the presenter presses the Pointeur control THE deck presentation SHALL present the deck full screen
> with the pointer on.

- **Business rules:** the control sits immediately after the present control, in the editor toolbar and in
  each presentation template's own toolbar. In a stacked deck, which has no toolbar, the Pointeur control is
  a button of the same look as the deck's `Présenter` button, pinned to the window and placed immediately to
  the left of it, 8 page pixels apart, with its top edge aligned with it; like that button, it is hidden
  while presenting. In the editor it shows exactly when the present control shows,
  except that it is hidden while edit mode is on and for a deck that does not carry the pointer. It is
  hidden while presenting, like the rest of the deck's toolbar. It is a button reachable with Tab and
  activated with Enter or Space. If the browser refuses the deck's own full screen, the control starts the
  fallback presentation exactly as the present control does, with no pointer.
- **User visible text:** visible label `Pointeur`; tooltip and accessible name
  `Présenter avec le pointeur (L)`.
- **Scenario:** SC-001, SC-002
- **Priority:** Must

#### FR-NEW-003 [EARS-E]: Off at the start of every presentation
> WHEN a presentation starts by any means other than the Pointeur control THE deck presentation SHALL start
> with the pointer off.

- **Business rules:** "any means" is the editor's present control, the deck's own present control and the F
  key. When the presentation ends (Escape, or leaving full screen any other way) the pointer is turned off and
  the dot and the ring are removed. A deck reloaded after the agent rewrote the file shows the pointer off,
  whether or not it is still full screen.
- **User visible text:** none.
- **Scenario:** SC-001, SC-003
- **Priority:** Must

#### FR-NEW-004 [EARS-S]: The red dot
> WHILE the pointer is on and the mouse is over the current slide THE deck presentation SHALL show a red dot
> centered on the mouse position in place of the system cursor.

- **Business rules:** the dot is a disc 18 slide pixels across, red `#FA4D56`, ringed by a 2 slide pixel
  white `#FFFFFF` halo, so it shows on a dark slide as on a light one. Dot and halo scale with the slide:
  at a scale factor s, the dot is 18 × s screen pixels across. The dot moves with every mouse move; its
  centre is within 1 screen pixel of the mouse position. Over the black margins around the slide and when
  the mouse leaves the window, there is no dot and the system cursor shows over the margins. When the
  pointer is turned on, or the slide changes, the dot shows at once at the last known mouse position if it
  is over the current slide; if the mouse has not moved since the page loaded, the dot shows at the first
  mouse move. The dot follows mouse input only: a touch or pen contact neither shows nor moves the dot and
  hides it if shown; the next mouse move over the current slide shows it again. The dot is drawn above everything on the
  slide and never takes a click. In a stacked deck, presented one slide at a time like the other decks,
  only the slide shown is the current slide.
- **User visible text:** none.
- **Scenario:** SC-001, SC-002
- **Priority:** Must

#### FR-NEW-005 [EARS-E]: A click rings its box
> WHEN the presenter clicks or taps the current slide while the pointer is on THE deck presentation SHALL
> ring the box the click lands in.

- **Business rules:** the box is found by going up from what was clicked, toward the slide:
  1. a drawing counts as one element: a click on one of its shapes starts from the whole drawing;
  2. inside a table, the table is the box;
  3. otherwise the first element that is not one of the slide's own layout areas (its header, body, footer
     or frame) and that has a background colour or picture other than transparent and other than the
     slide's own background colour, or a shadow, or a visible border on all four sides, such as a card or a
     tile, is the box; a container whose direct children include two or more boxes under this rule is never
     a box itself (only its direct children count, each judged on its own appearance, not on what it
     contains); an element with a border on only some sides (a header with a bottom rule, a table cell)
     is never a box by this rule;
  4. with no such element, the nearest block holding text directly (a headline, a paragraph, a list item) or
     an image or drawing is the box; a block whose text sits only in text set inside a line (a paragraph
     made of one bold span) holds that text; one of the slide's own layout areas is never the box by this
     rule either;
  5. text set inside a line (a bold word, a span, a pill sitting in a line of text) is never a box itself,
     whatever its fill or border; images and drawings are not text set inside a line; the slide itself is
     never a box;
  6. an element whose own area is 85 % or more of the slide's area is skipped and the search continues
     upward from it; when it reaches the slide with no box found by rule 3, rule 4 applies.
  The ring is a red `#DA1E28` line 3 slide pixels thick, whose outer edge lies 6 slide pixels outside the box
  on every side, with the box's corner rounding grown by 6 slide pixels (a circle stays a circle). It scales
  with the slide and stays on its box when the box moves (an entrance animation, the window resized). It is
  drawn above the slide and never takes a click. The ring is clipped to the slide: any part of it outside
  the slide is not shown.
  The slide's own layout areas, never a box by rule 3, are, in every template: the area holding the
  eyebrow, headline, rule and subtitle; the body area; the footer or foot band with its page number; the
  grey top band; and the inner frame surrounding the content. The page number is part of its footer or foot
  band and is never a box. Whatever else sits inside these areas is judged on its own by rules 1 to 6.
- **User visible text:** none.
- **Scenario:** SC-001, SC-002
- **Priority:** Must

#### FR-NEW-006 [EARS-U]: One ring at a time
> The deck presentation SHALL show at most one ring.

- **Business rules:** a click on another box moves the ring there. A click on the ringed box removes the
  ring. A click on the slide where FR-NEW-005 finds no box (the slide background) removes the
  ring if there is one, and adds none.
- **User visible text:** none.
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-007 [EARS-E]: Changing slide removes the ring
> WHEN the current slide changes while the pointer is on THE deck presentation SHALL remove the ring and
> keep the pointer on.

- **Business rules:** every way of changing slide counts (Right, Down, Space, Left, Up, Home, End, the
  editor's relay). Coming back to the slide shows no ring. Pressing Left on the first slide or Right on the
  last, which change nothing, keeps the ring.
- **User visible text:** none.
- **Scenario:** SC-001, SC-003
- **Priority:** Must

#### FR-NEW-008 [EARS-UB]: Links, buttons and fields keep their click
> The deck presentation SHALL NOT ring a box nor change the ring when the click lands on a link, a button or
> a form field of the slide.

- **Business rules:** such a click does what it did without the pointer: the link is followed, the button's
  action runs, the field takes the focus. An element inside a link or a button (an icon, a span) counts as
  the link or the button.
- **User visible text:** none.
- **Scenario:** SC-003, SC-002
- **Priority:** Must

#### FR-NEW-009 [EARS-E]: Turning the pointer off
> WHEN the pointer is turned off THE deck presentation SHALL remove the dot and the ring and show the system
> cursor again.

- **Business rules:** turning it on again shows no ring until the next click.
- **User visible text:** none.
- **Scenario:** SC-001, SC-003
- **Priority:** Must

#### FR-NEW-010 [EARS-UB]: Nothing of the pointer in the file
> The editor page SHALL NOT write into the saved file anything that the pointer added to the shown deck.

- **Business rules:** pointing never saves: a presentation with the pointer, its clicks and its rings leave
  the file byte identical. A save made later in the same page (edit mode turned on after presenting) writes
  the edit and nothing of the dot, the ring, the hidden cursor or the pointer's state; the deck's own
  pointer behavior, which lives in the deck file, is kept as it is.
- **User visible text:** none.
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-011 [EARS-UB]: Existing keys and relay unchanged
> The deck presentation SHALL NOT change what Right, Down, Space, Left, Up, Home, End, F and Escape do, with
> the pointer on or off, opened directly or in the editor.

- **Business rules:** the editor page keeps forwarding the keys it forwards today, and now also L; it
  forwards nothing while not presenting (SPEC-0016, no relay outside presenting).
- **User visible text:** none.
- **Scenario:** SC-003, SC-001
- **Priority:** Must

#### FR-NEW-012 [EARS-UB]: Never in edit mode, never while typing
> The deck presentation SHALL NOT turn the pointer on while edit mode is on, nor when L is typed in a text
> field or an editable text.

- **Business rules:** while edit mode is on, L in an editable text types the letter, L elsewhere does
  nothing, the Pointeur control is hidden, and a presentation started from edit mode has no pointer. A
  pointer that is on while a text field on the slide takes the focus stays on; L typed in that field types
  the letter.
- **User visible text:** none.
- **Scenario:** SC-001, SC-002, SC-004
- **Priority:** Must

#### FR-NEW-013 [EARS-UB]: Exports and printing unchanged
> The deck presentation SHALL NOT change the PPTX export of a deck, nor show the dot or the ring when the
> deck is printed.

- **Business rules:** the PPTX export of each presentation template, once it carries the pointer, has the
  same slides, shapes, positions and texts as its export before this increment. Printing while presenting
  with the pointer on and a ring shown prints no dot and no ring. DOCX export concerns documents only and is
  untouched.
- **User visible text:** none.
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-014 [EARS-U]: Every presentation template carries the pointer
> The deck presentation SHALL offer the pointer in every presentation template, the same way opened directly
> and in the editor.

- **Business rules:** the 11 presentation templates (3 starting points, 8 reference decks), and therefore
  every deck created from a starting point, carry the pointer, the Pointeur control and the L key, in both
  deck families (one slide at a time, and slides stacked one under the other). When a presentation template
  lacks one of them, the test suite fails and names the file and what is missing.
- **User visible text:** one failure line per missing part, exactly `<template>: missing pointer`,
  `<template>: missing Pointeur control` or `<template>: missing L key`, where `<template>` is the template's
  file name without its folder and without `.html` (for example `roadmap-one-pager: missing pointer`,
  `slides-empty: missing L key`).
- **Scenario:** SC-002, SC-004
- **Priority:** Must

### 6.2 Modified

None. SPEC-0001/FR-026 to FR-028 and the SPEC-0016 requirements on keys, relay and presenting keep their wording; FR-NEW-011 and
FR-NEW-014 add to them without changing them.

### 6.3 Removed

None.

## 7. Non functional requirements (user observable)

### 7.1 Performance

The dot keeps up with the mouse: it is redrawn at least once per displayed frame while the mouse moves, with
no visible lag on a 60 Hz screen.

### 7.4 Usability and accessibility

- WHILE the system asks for reduced motion THE deck presentation SHALL show the ring at full opacity at once,
  with no fade or scale animation.
- WHILE the system does not ask for reduced motion THE deck presentation SHALL show the ring at full opacity
  within 200 ms of the click.
- The Pointeur control has its accessible name and keyboard access (FR-NEW-002).
- The dot is visible on a white slide and on a slide of `#161616` alike (FR-NEW-004).

### 7.6 Operability

The README section on presenting and the agent guidance topic on slides each state, in one sentence, the L
key, the Pointeur control, the click that rings a box, that the pointer starts off and that it never reaches
the file.

## 8. Edge cases

| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Empty states | slide with only a background, no box | a click rings nothing, removes any ring | E2E-010 |
| Empty states | deck created before this version | no Pointeur control, L does nothing, keys work | E2E-035 |
| Boundary values | element covering 85 % or more of the slide | skipped, the search continues upward, then falls to the nearest text block | E2E-007 |
| Boundary values | Left on the first slide, Right on the last | slide unchanged, ring kept | E2E-012 |
| Boundary values | box touching the slide edge | ring clipped to the slide | E2E-037 |
| Boundary values | slide layout areas (inner frame, footer, header, top band) | never a box | E2E-036, E2E-007 |
| Boundary values | pointer turned on without a mouse move | dot at the last mouse position at once | E2E-001 |
| Boundary values | stacked deck, 1280 pixels wide, at scale 1.25 | dot 18 pixels of that deck's own design, 22.5 screen pixels | E2E-032 |
| Boundary values | scale factor 1.6667 then 1.3333 | dot and ring keep their slide pixel sizes | E2E-024 |
| Concurrent actions | two clicks on two boxes | only the second is ringed | E2E-011 |
| Concurrent actions | L pressed while the focus is in the editor page | one toggle, not two | E2E-003 |
| Slow or lost connectivity | not applicable: the pointer runs in the browser with no server call | n/a | n/a |
| Access states | edit mode on | no pointer, no control | E2E-018 |
| Access states | fallback presentation of the preview frame | pointer unavailable (scope 3.2) | not tested: fallback forced only by a browser refusal; covered by the rule that L outside the deck's own full screen does nothing, E2E-017 |
| Data variations | dark slide `#161616`, white slide | dot visible on both | E2E-023 |
| Data variations | drawing with several shapes | the whole drawing ringed | E2E-025 |
| Data variations | table cell with its own border | the whole table ringed | E2E-008 |
| Data variations | link, button, text field on a slide | they keep their click, no ring change | E2E-013, E2E-014, E2E-019 |
| Navigation | leaving with Escape, presenting again | pointer off | E2E-016 |
| Navigation | agent rewrites the file while presenting | the deck reloads with the pointer off | E2E-004 |
| Partial operations | mouse leaves the window | dot removed | E2E-022 |
| Partial operations | mouse in the black margins | no dot, system cursor | E2E-021 |
| Dependency failures | browser refuses full screen | fallback, pointer unavailable | scope 3.2, E2E-017, E2E-039 |
| Ordering and timing | slide entrance animation moving the box | ring follows the box | E2E-024 |
| Ordering and timing | reduced motion | ring at full opacity at once | E2E-027 |
| Exhaustion | not applicable: one ring, one dot, nothing accumulates | n/a | n/a |
| Input devices | touch or pen contact, then a mouse move | the contact hides the dot, a tap rings, the next mouse move shows the dot | E2E-026 |
| Input devices | Ctrl, Cmd or Alt with L | no toggle | E2E-020 |

## 9. Acceptance tests (the contract)

> Behavioral and technology agnostic. /sdlc-design maps each test to a driver. An implementing agent uses
> this as its definition of done.

### 9.0 Fixtures

- **Deck P**: a deck made from the IBM Carbon starting point, with 3 slides, shown in a 1600 × 900 window
  (slide 960 × 540, scale factor 1.6667 while presenting). Slide 1, white: the headline `Pointer test` (no
  box), a paragraph `Plain paragraph` (no box), two tiles with a grey fill titled `Tile A` and `Tile B`, a
  table of 2 rows whose cells have a bottom border, a link `Docs` leading to the address fragment `#docs`, a
  button `Count` whose click changes its label to `Count 1`, a text field labelled `Note`, a drawing of two
  shapes. Slide 2, background `#161616`: a paragraph `Dark paragraph` and a grey filled tile `Edge tile` touching
  the slide's left edge. Slide 3, white: a grey filled panel
  covering 90 % of the slide, holding a paragraph `Last`. On slide 1 the paragraph reads `Plain paragraph`
  with the word `paragraph` in bold, and the headline `Pointer test` sits in the slide's header area, which
  has a bottom rule only.
- **Deck S**: a copy of the stacked reference deck `presentation-standard`.
- **Deck O**: Deck P in the form written before this increment: no pointer, no Pointeur control.
- "Served" means shown in the editor page; "opened directly" means opened as a file in the browser.

### 9.1 Summary

| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | journey | SC-002 | FR-NEW-001, FR-NEW-003, FR-NEW-004, FR-NEW-014 | Critical |
| E2E-002 | New | journey | SC-001 | FR-NEW-001, FR-NEW-004, FR-NEW-009, FR-NEW-014 | Critical |
| E2E-003 | New | edge | SC-001 | FR-NEW-001, FR-NEW-009, FR-NEW-011 | High |
| E2E-004 | New | journey | SC-001 | FR-NEW-002, FR-NEW-003 | Critical |
| E2E-005 | New | journey | SC-002 | FR-NEW-002, FR-NEW-003 | High |
| E2E-006 | New | requirement | SC-001 | FR-NEW-005 | Critical |
| E2E-007 | New | edge | SC-002 | FR-NEW-005 | High |
| E2E-008 | New | edge | SC-001 | FR-NEW-005 | High |
| E2E-009 | New | state transition | SC-003 | FR-NEW-006 | High |
| E2E-010 | New | failure | SC-001 | FR-NEW-006, FR-NEW-005 | High |
| E2E-011 | New | state transition | SC-003 | FR-NEW-006 | High |
| E2E-012 | New | edge | SC-003 | FR-NEW-007, FR-NEW-011 | High |
| E2E-013 | New | failure | SC-003 | FR-NEW-008 | High |
| E2E-014 | New | failure | SC-003 | FR-NEW-008 | High |
| E2E-015 | New | state transition | SC-003 | FR-NEW-009 | High |
| E2E-016 | New | state transition | SC-003 | FR-NEW-003, FR-NEW-009 | High |
| E2E-017 | New | failure | SC-002 | FR-NEW-001 | High |
| E2E-018 | New | failure | SC-004 | FR-NEW-002, FR-NEW-010, FR-NEW-012 | Critical |
| E2E-019 | New | failure | SC-002 | FR-NEW-008, FR-NEW-012, FR-NEW-001 | High |
| E2E-020 | New | failure | SC-003 | FR-NEW-001, FR-NEW-011 | Medium |
| E2E-021 | New | edge | SC-002 | FR-NEW-004 | High |
| E2E-022 | New | edge | SC-002 | FR-NEW-004 | Medium |
| E2E-023 | New | edge | SC-002 | FR-NEW-004 | High |
| E2E-024 | New | edge | SC-001 | FR-NEW-004, FR-NEW-005 | High |
| E2E-025 | New | edge | SC-002 | FR-NEW-005 | Medium |
| E2E-026 | New | edge | SC-002 | FR-NEW-004, FR-NEW-005 | Medium |
| E2E-027 | New | edge | SC-002 | FR-NEW-005 | Medium |
| E2E-028 | New | journey | SC-004 | FR-NEW-010 | Critical |
| E2E-029 | New | edge | SC-004 | FR-NEW-013, FR-NEW-010 | Critical |
| E2E-030 | New | side effect | SC-004 | FR-NEW-013 | High |
| E2E-031 | New | journey | SC-003 | FR-NEW-011, FR-NEW-007 | Critical |
| E2E-032 | New | requirement | SC-002 | FR-NEW-014, FR-NEW-007, FR-NEW-002, FR-NEW-004 | High |
| E2E-033 | New | failure | SC-004 | FR-NEW-014 | High |
| E2E-034 | New | side effect | SC-004 | FR-NEW-014 | Low |
| E2E-035 | New | failure | SC-001 | FR-NEW-002, FR-NEW-011 | High |
| E2E-036 | New | edge | SC-001 | FR-NEW-005, FR-NEW-006 | Medium |
| E2E-037 | New | edge | SC-002 | FR-NEW-005 | Medium |
| E2E-038 | New | failure | SC-001 | FR-NEW-012, FR-NEW-001 | High |
| E2E-039 | New | failure | SC-002 | FR-NEW-002, FR-NEW-013 | Medium |

Coverage: happy 6 (journey E2E-001, E2E-002, E2E-004, E2E-005, E2E-028, E2E-031), failure 11, side effect 2,
edge 14, state transition 4, requirement 2, security 0 (no security surface: the pointer reads and writes
nothing). Total 39. Happy to failure ratio 1:1.83.

### 9.2 New tests

#### E2E-001: Pointer in a deck opened directly
- **Category:** journey
- **Scenario:** SC-002
- **Requirements:** FR-NEW-001, FR-NEW-003, FR-NEW-004, FR-NEW-014
- **Given** Deck P opened directly, presented with F, the mouse at screen point (800, 450)
- **When** the presenter moves the mouse by 1 pixel, then presses L, then moves the mouse to (400, 300)
- **Then** before L there is no red dot and the system cursor shows; right after L, before any further move,
  a red dot shows centred within 1 pixel of (801, 450); after the move a red dot 30 ± 1 screen pixels across
  is centred within 1 pixel of (400, 300) and the system cursor is hidden over the slide
- **Priority:** Critical

#### E2E-002: Pointer in the editor's presentation, focus in the deck
- **Category:** journey
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-004, FR-NEW-009, FR-NEW-014
- **Given** Deck P served, edit mode off, presented with the editor's present control, the keyboard focus in
  the deck
- **When** the presenter presses L, moves the mouse to (800, 450), then presses L again
- **Then** after the first L a red dot is centred on (800, 450); after the second the dot is gone and the
  system cursor shows
- **Priority:** Critical

#### E2E-003: L from the editor page toggles once
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-009, FR-NEW-011
- **Given** Deck P served and presented, the keyboard focus left in the editor page
- **When** the presenter presses L, moves the mouse to (800, 450), presses Right, then presses L
- **Then** after the first L the dot shows (on, toggled once, not twice); Right shows slide 2; after the
  second L the dot is gone
- **Priority:** High

#### E2E-004: The editor's Pointeur control
- **Category:** journey
- **Scenario:** SC-001
- **Requirements:** FR-NEW-002, FR-NEW-003
- **Given** Deck P served, edit mode off
- **When** the editor user looks at the toolbar, then presses `Pointeur`, then moves the mouse to (800, 450)
- **Then** `Pointeur` sits immediately after the present control, its tooltip and accessible name read
  `Présenter avec le pointeur (L)`; after the press the deck is full screen and the red dot shows at once
- **And** after Escape and the present control, a mouse move shows no dot (off again)
- **And** after `Pointeur` again, the agent rewriting the file with the paragraph `Plain paragraph` changed to
  `Changed paragraph` reloads the deck, which shows `Changed paragraph` and no dot on a mouse move
- **Priority:** Critical

#### E2E-005: The deck's own Pointeur control, by keyboard
- **Category:** journey
- **Scenario:** SC-002
- **Requirements:** FR-NEW-002, FR-NEW-003
- **Given** Deck P opened directly, not presented
- **When** the presenter tabs to the control after `Présenter (F)` and presses Enter, then moves the mouse
  to (800, 450)
- **Then** the focused control is labelled `Pointeur` with the name `Présenter avec le pointeur (L)`; the
  deck is full screen and the dot shows
- **Priority:** High

#### E2E-006: A click rings a tile
- **Category:** requirement
- **Scenario:** SC-001
- **Requirements:** FR-NEW-005
- **Given** Deck P served, presented, pointer on
- **When** the presenter clicks the middle of `Tile A`
- **Then** one red ring shows around `Tile A`: its outer edge is 10 ± 1 screen pixels outside the tile's edge
  on each side (6 slide pixels × 1.6667) and its line is 5 ± 1 screen pixels thick; `Tile A` itself looks
  as before
- **Priority:** Critical

#### E2E-007: Headline and paragraph without a box
- **Category:** edge
- **Scenario:** SC-002
- **Requirements:** FR-NEW-005
- **Given** Deck P opened directly, presented, pointer on
- **When** the presenter clicks the bold word inside `Plain paragraph`, then clicks `Pointer test`, then
  presses End and clicks `Last`
- **Then** after the first click the whole paragraph `Plain paragraph` is ringed (not the bold word); after
  the second only the headline `Pointer test` is ringed (not the header area holding it); on slide 3 only
  the paragraph `Last` is ringed, not the panel
- **Priority:** High

#### E2E-008: A table is one box
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-005
- **Given** Deck P served, presented, pointer on
- **When** the presenter clicks the second row's first cell, then an empty area of the slide background,
  then the first row's last cell
- **Then** after each cell click the ring surrounds the whole table, not a cell; after the background click
  no ring shows; the ring after the last click is the same as after the first (a second cell clicked while
  the table is ringed would remove the ring, FR-NEW-006)
- **Priority:** High

#### E2E-009: Clicking the ringed box again removes the ring
- **Category:** state transition
- **Scenario:** SC-003
- **Requirements:** FR-NEW-006
- **Given** Deck P presented, pointer on, `Tile A` ringed
- **When** the presenter clicks `Tile A` again, then once more
- **Then** after the first click no ring shows; after the second `Tile A` is ringed again
- **Priority:** High

#### E2E-010: A click outside any box
- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-NEW-006, FR-NEW-005
- **Given** Deck P presented, pointer on, `Tile B` ringed
- **When** the presenter clicks an empty area of the slide background, then clicks it again
- **Then** after the first click no ring shows and the slide itself is not ringed; after the second still no
  ring
- **Priority:** High

#### E2E-011: Only one ring
- **Category:** state transition
- **Scenario:** SC-003
- **Requirements:** FR-NEW-006
- **Given** Deck P presented, pointer on, `Tile A` ringed
- **When** the presenter clicks `Tile B`
- **Then** exactly one ring shows, around `Tile B`
- **Priority:** High

#### E2E-012: Changing slide removes the ring
- **Category:** edge
- **Scenario:** SC-003
- **Requirements:** FR-NEW-007, FR-NEW-011
- **Given** Deck P presented, pointer on, slide 1 shown, `Tile A` ringed
- **When** the presenter presses Left, then Right, then Left
- **Then** after the first Left slide 1 still shows and `Tile A` is still ringed; after Right slide 2 shows,
  no ring, the dot follows the mouse; after the second Left slide 1 shows with no ring
- **Priority:** High

#### E2E-013: A link is followed, the ring unchanged
- **Category:** failure
- **Scenario:** SC-003
- **Requirements:** FR-NEW-008
- **Given** Deck P opened directly, presented, pointer on, `Tile A` ringed
- **When** the presenter clicks `Docs`
- **Then** the page address ends with `#docs` and `Tile A` is still the only ring
- **Priority:** High

#### E2E-014: A button runs, the ring unchanged
- **Category:** failure
- **Scenario:** SC-003
- **Requirements:** FR-NEW-008
- **Given** Deck P served, presented, pointer on, no ring
- **When** the presenter clicks the label text inside `Count`
- **Then** the button reads `Count 1` and no ring shows
- **Priority:** High

#### E2E-015: L turns dot and ring off, and back on without a ring
- **Category:** state transition
- **Scenario:** SC-003
- **Requirements:** FR-NEW-009
- **Given** Deck P presented, pointer on, `Tile A` ringed, mouse over the slide
- **When** the presenter presses L, then L again and moves the mouse
- **Then** after the first L no dot and no ring show and the system cursor shows; after the second the dot
  shows and no ring
- **Priority:** High

#### E2E-016: Leaving ends the pointer, presenting again starts off
- **Category:** state transition
- **Scenario:** SC-003
- **Requirements:** FR-NEW-003, FR-NEW-009
- **Given** Deck P opened directly, presented, pointer on, `Tile A` ringed
- **When** the presenter presses Escape, then F, then moves the mouse to (800, 450)
- **Then** after Escape the deck is out of full screen with no dot and no ring; after F it is presented with
  no dot and no ring
- **Priority:** High

#### E2E-017: L outside a presentation does nothing
- **Category:** failure
- **Scenario:** SC-002
- **Requirements:** FR-NEW-001
- **Given** Deck P opened directly, not presented, the mouse over slide 1
- **When** the presenter presses L, then F, then moves the mouse
- **Then** after L no dot shows and the deck is unchanged; after F the deck is presented with the pointer off
- **Priority:** High

#### E2E-018: Edit mode has no pointer, and a save after pointing keeps none
- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-002, FR-NEW-010, FR-NEW-012
- **Given** Deck P served; it was presented with the pointer on and `Tile A` ringed, then left with Escape
- **When** the editor user turns edit mode on, looks at the toolbar, presents with the present control,
  presses L, moves the mouse, presses Escape, places the caret at the end of `Plain paragraph` and types `l`,
  then the change is saved
- **Then** no `Pointeur` control shows while edit mode is on; while presented L shows no dot; the paragraph
  reads `Plain paragraphl`; the file holds `Plain paragraphl` and is otherwise identical to before, with
  nothing of a dot, a ring, a hidden cursor or a pointer state
- **Priority:** Critical

#### E2E-019: L typed in a text field
- **Category:** failure
- **Scenario:** SC-002
- **Requirements:** FR-NEW-008, FR-NEW-012, FR-NEW-001
- **Given** Deck P opened directly, presented, pointer on, `Tile A` ringed
- **When** the presenter clicks the field `Note`, types `L`
- **Then** the field holds `L`, the pointer is still on, `Tile A` is still the only ring
- **Priority:** High

#### E2E-020: Modifier keys with L
- **Category:** failure
- **Scenario:** SC-003
- **Requirements:** FR-NEW-001, FR-NEW-011
- **Given** Deck P opened directly, presented, pointer off
- **When** the presenter presses Alt+L, then Ctrl+L, then Meta+L, each as delivered to the page by the
  test browser
- **Then** after each one no dot shows and the slide is unchanged
- **Priority:** Medium

#### E2E-021: Over the black margins
- **Category:** edge
- **Scenario:** SC-002
- **Requirements:** FR-NEW-004
- **Given** Deck P opened directly, presented in a 1600 × 1000 window (black bands of 50 pixels above and
  below the slide), pointer on
- **When** the presenter moves the mouse to (800, 20), then to (800, 500)
- **Then** at (800, 20) no dot shows and the system cursor shows; at (800, 500) the dot shows there
- **Priority:** High

#### E2E-022: Mouse leaves the window
- **Category:** edge
- **Scenario:** SC-002
- **Requirements:** FR-NEW-004
- **Given** Deck P opened directly, presented, pointer on, dot shown at (800, 450)
- **When** the mouse leaves the window
- **Then** no dot shows
- **Priority:** Medium

#### E2E-023: Visible on dark and light slides
- **Category:** edge
- **Scenario:** SC-002
- **Requirements:** FR-NEW-004
- **Given** Deck P opened directly, presented, pointer on
- **When** the mouse is at (800, 450) on an empty spot of slide 1 (white), then on an empty spot of slide 2
  (`#161616`)
- **Then** on both slides the pixels under the dot hold red `#FA4D56` at its centre and white `#FFFFFF` in a
  ring around it
- **Priority:** High

#### E2E-024: Scaling and resizing
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-004, FR-NEW-005
- **Given** Deck P served, presented at scale 1.6667, pointer on, `Tile A` ringed
- **When** the window is resized to 1280 × 720 (scale 1.3333) and the mouse moved to (640, 360)
- **Then** the dot is 24 ± 1 screen pixels across, centred on (640, 360); the ring's outer edge is 8 ± 1
  screen pixels outside `Tile A` on each side, around the tile's new place
- **Priority:** High

#### E2E-025: A drawing is one box
- **Category:** edge
- **Scenario:** SC-002
- **Requirements:** FR-NEW-005
- **Given** Deck P opened directly, presented, pointer on
- **When** the presenter clicks the second shape of the drawing
- **Then** the ring surrounds the whole drawing
- **Priority:** Medium

#### E2E-026: Touch then mouse
- **Category:** edge
- **Scenario:** SC-002
- **Requirements:** FR-NEW-004, FR-NEW-005
- **Given** Deck P opened directly on a screen taking both touch and a mouse, presented, pointer turned on
  with L, the mouse moved to (800, 450) so the dot shows there
- **When** the presenter taps `Tile B`, then taps `Tile B` again, then moves the mouse to (400, 300)
- **Then** after the first tap no dot shows and `Tile B` is ringed; after the second no dot and no ring show;
  after the mouse move the dot shows centred within 1 pixel of (400, 300)
- **Priority:** Medium

#### E2E-027: Reduced motion
- **Category:** edge
- **Scenario:** SC-002
- **Requirements:** FR-NEW-005
- **Given** Deck P opened directly with the system asking for reduced motion, presented, pointer on
- **When** the presenter clicks `Tile A`
- **Then** the ring shows at full opacity and final size on the first frame after the click, with no
  animation running
- **Priority:** Medium

#### E2E-028: Pointing leaves the file byte identical
- **Category:** journey
- **Scenario:** SC-004
- **Requirements:** FR-NEW-010
- **Given** Deck P served, edit mode off, its file contents noted
- **When** the presenter presents, turns the pointer on, rings `Tile A`, `Tile B`, the table, changes slide,
  turns the pointer off and leaves, then waits 3 seconds
- **Then** the file is byte identical to the noted contents and the editor shows no save or conflict notice
- **Priority:** Critical

#### E2E-029: PPTX export unchanged
- **Category:** edge
- **Scenario:** SC-004
- **Requirements:** FR-NEW-013, FR-NEW-010
- **Given** each of the 11 presentation templates, and a baseline kept with the tests, captured from the
  product as shipped before this increment: for each template the slide count and, per slide, each shape's
  kind, position, size and text
- **When** each template, now carrying the pointer, is exported to PPTX, once directly and once after a
  served presentation with the pointer on and a ring shown
- **Then** both exports give the same slide count and, slide by slide, the same shapes, positions, sizes and
  texts as before
- **Priority:** Critical

#### E2E-030: Printing while pointing
- **Category:** side effect
- **Scenario:** SC-004
- **Requirements:** FR-NEW-013
- **Given** Deck P opened directly, presented, pointer on, dot shown, `Tile A` ringed
- **When** the deck is printed (to a PDF)
- **Then** no page shows a red dot or a red ring, and the pages are identical to a print made with the pointer
  never turned on
- **Priority:** High

#### E2E-031: Existing keys with the pointer on, opened directly and served
- **Category:** journey
- **Scenario:** SC-003
- **Requirements:** FR-NEW-011, FR-NEW-007
- **Given** Deck P, presented with the pointer on and a ring, once opened directly and once served with the
  focus in the editor page
- **When** the presenter presses Right, Space, Left, End, Home, then Escape
- **Then** the slides shown are 2, 3, 2, 3, 1 in that order, no ring shows after the first key, and Escape
  leaves full screen, exactly as with the pointer off
- **Priority:** Critical

#### E2E-032: Stacked deck and every template
- **Category:** requirement
- **Scenario:** SC-002
- **Requirements:** FR-NEW-014, FR-NEW-007, FR-NEW-002, FR-NEW-004
- **Given** Deck S opened directly, and a new deck created from each of the 3 starting points (`carbon`,
  `ei`, `medical`) served
- **When** in each, the presenter presents with the Pointeur control, moves the mouse to (800, 450), clicks
  the slide's headline, then presses Right
- **Then** in each the dot shows, the headline is ringed, and after Right the next slide shows without a ring
- **And** in Deck S, before presenting, `Pointeur` shows immediately left of `Présenter`, 8 page pixels
  apart, their top edges aligned, and neither overlaps the other
- **And** in Deck S presented in a 1600 × 900 window (slide 1280 × 720, scale factor 1.25), the dot is
  22.5 ± 1 screen pixels across (18 slide pixels × 1.25)
- **Priority:** High

#### E2E-033: A template without the pointer fails the suite
- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-014
- **Given** a copy of the templates where the reference deck `roadmap-one-pager` has lost the pointer
- **When** the operator runs the template guard of the test suite on that copy
- **Then** it fails with the line `roadmap-one-pager: missing pointer`, and passes on
  the unmodified templates
- **And** on a copy where `roadmap-one-pager` lost only the Pointeur control, it fails with exactly
  `roadmap-one-pager: missing Pointeur control`, and on one where it lost only the L key, with exactly
  `roadmap-one-pager: missing L key`
- **Priority:** High

#### E2E-034: Documentation states the pointer
- **Category:** side effect
- **Scenario:** SC-004
- **Requirements:** FR-NEW-014
- **Given** the README and the agent guidance topic on slides as shipped
- **When** the operator reads the presenting section of each
- **Then** each holds one sentence naming the L key, the `Pointeur` control, the click that rings a box, the
  pointer starting off, and that nothing of it reaches the file
- **Priority:** Low

#### E2E-035: A deck created before this version
- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-NEW-002, FR-NEW-011
- **Given** Deck O served, edit mode off
- **When** the editor user looks at the toolbar, presents with the present control, presses L, moves the
  mouse, then presses Right and Escape
- **Then** no `Pointeur` control shows; L shows no dot and changes nothing; Right shows slide 2; Escape
  leaves full screen
- **Priority:** High

#### E2E-036: Layout areas of the EI starting point are not boxes
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-005, FR-NEW-006
- **Given** a deck created from the `ei` starting point with one content slide holding a paragraph
  `EI paragraph` and no tile, served, presented, pointer on
- **When** the presenter clicks an empty spot of the white inner frame, then the footer's page number, then
  `EI paragraph`
- **Then** no ring shows after the first two clicks; after the third only `EI paragraph` is ringed
- **Priority:** Medium

#### E2E-037: Ring clipped at the slide edge
- **Category:** edge
- **Scenario:** SC-002
- **Requirements:** FR-NEW-005
- **Given** Deck P opened directly, presented, pointer on, slide 2 shown
- **When** the presenter clicks `Edge tile`
- **Then** the ring shows on the top, right and bottom of `Edge tile`, and no red shows left of the slide's
  left edge
- **Priority:** Medium

#### E2E-038: L typed in an editable text in edit mode, not presenting
- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-NEW-012, FR-NEW-001
- **Given** Deck P served, edit mode on, not presented, the caret at the end of `Tile A`'s title
- **When** the editor user types `L`, then clicks outside any text and presses L
- **Then** the title reads `Tile AL`; no dot shows after either press; the slide shown is unchanged
- **Priority:** High

#### E2E-039: Pointeur control when full screen is refused
- **Category:** failure
- **Scenario:** SC-002
- **Requirements:** FR-NEW-002, FR-NEW-013
- **Given** Deck P opened directly in a browser that refuses full screen
- **When** the presenter presses `Pointeur`, then L, then moves the mouse over slide 1, then prints to PDF
- **Then** the deck is not presented, no dot shows, the slide is unchanged, and the PDF matches a print made
  without pressing `Pointeur`
- **Priority:** Medium

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001 to FR-NEW-007, FR-NEW-009, FR-NEW-011, FR-NEW-012 | E2E-002, E2E-004; requirement E2E-006 | E2E-010, E2E-035, E2E-038 | E2E-003, E2E-008, E2E-024, E2E-036 |
| SC-002 | FR-NEW-001 to FR-NEW-005, FR-NEW-008, FR-NEW-012, FR-NEW-014 | E2E-001, E2E-005; requirement E2E-032 | E2E-017, E2E-019, E2E-039 | E2E-007, E2E-021, E2E-022, E2E-023, E2E-025, E2E-026, E2E-027, E2E-037 |
| SC-003 | FR-NEW-001, FR-NEW-003, FR-NEW-006 to FR-NEW-009, FR-NEW-011 | E2E-031; transitions E2E-009, E2E-011, E2E-015, E2E-016 | E2E-013, E2E-014, E2E-020 | E2E-012 |
| SC-004 | FR-NEW-010, FR-NEW-012 to FR-NEW-014 | E2E-028; side effects E2E-030, E2E-034 | E2E-018, E2E-033 | E2E-029 |

Requirement coverage (tests per requirement): FR-NEW-001: 001, 002, 003, 017, 019, 020, 038. FR-NEW-002: 004, 005,
018, 032, 035, 039. FR-NEW-003: 001, 004, 005, 016. FR-NEW-004: 001, 002, 021, 022, 023, 024, 026, 032. FR-NEW-005: 006, 007,
008, 010, 024, 025, 026, 027, 036, 037. FR-NEW-006: 009, 010, 011, 036. FR-NEW-007: 012, 031, 032. FR-NEW-008: 013, 014, 019.
FR-NEW-009: 002, 003, 015, 016. FR-NEW-010: 018, 028, 029. FR-NEW-011: 003, 012, 020, 031, 035. FR-NEW-012:
018, 019, 038. FR-NEW-013: 029, 030, 039. FR-NEW-014: 001, 002, 032, 033, 034.

## 11. Open questions

- Test plan approved by default, not by an explicit answer: the requester asked for the whole spec with no
  questions and the recommended defaults. Does not change observable behavior.
- Scope choices taken by default and recorded in Section 3: the deck carries the behavior (works opened
  directly and in the editor); every presentation template, not only the five reference decks of SPEC-0016;
  no toggle control visible while presenting, the Pointeur control starts a presentation with the pointer on;
  no pointer in the fallback presentation nor in decks created before this version (BL-0038). Does not
  change observable behavior beyond what Sections 3 and 6 state.
- The test designer was the requirements author (no separate test designer run). Does not change observable
  behavior.

## 12. Glossary

| Term | Definition | Context |
|---|---|---|
| Deck | a presentation file: slides shown one at a time, with its own toolbar and keys | Deck presentation |
| Presenting | the deck shown full screen, current slide scaled to the screen on black | Deck presentation |
| Slide pixel | a pixel of the slide at the deck's own design width (960 for the starting points and the other reference decks, 1280 for the two stacked decks); on screen it is multiplied by the scale factor | Deck presentation |
| Scale factor | how much the slide is enlarged while presenting (in a 1600 × 900 window: 1.6667 for a 960 wide slide, 1.25 for a 1280 wide one) | Deck presentation |
| Pointer | the presenting aid turned on with L or the Pointeur control: the dot plus the ring | Deck presentation |
| Dot | the red disc with a white halo that follows the mouse over the slide | Deck presentation |
| Ring | the red line drawn around the box last clicked | Deck presentation |
| Box | the element a click rings, chosen by the rules of FR-NEW-005 | Deck presentation |
| Drawing | a vector picture on a slide, made of shapes, ringed as one | Deck presentation |
| Starting point | a template a new deck is created from (`carbon`, `ei`, `medical`) | Deck presentation |
| Reference deck | one of the 8 complete example decks shipped with the product | Deck presentation |
| Stacked deck | a deck whose slides stand one under the other outside a presentation | Deck presentation |
| Preview frame | the area of the editor page where the deck is shown | Editor page |
| Present control | the button that starts a presentation, in the editor toolbar and in the deck's toolbar | Editor page |
| Pointeur control | the button beside the present control that presents with the pointer on | Editor page |
| Edit mode | the editor state in which texts are typeable and changes are saved | Editor page |
| Relay | the editor page passing presenting keys to the deck when the focus stayed in the editor page | Editor page |
| Fallback presentation | the preview frame itself put full screen when the browser refuses the deck's own full screen | Editor page |
| Opened directly | a deck file opened in a browser without the editor | Deck presentation |
| Served | a deck shown in the editor page | Editor page |
| Template guard | the part of the test suite that checks every presentation template | Editor page |

## 13. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 3 | 0 | NOT-IMPLEMENTABLE |
| 2 | 3 | 3 | NOT-IMPLEMENTABLE |
| 3 | 5 | 2 | NOT-IMPLEMENTABLE |
| 4 | 6 | 0 | NOT-IMPLEMENTABLE |

**Amendments applied:** round 1: box rule 3 (borders on all four sides), rule 6 (85 % elements skipped), E2E-020
(Meta+L), fixture slide 3 panel, E2E-007 extended; self consistency: 7.4 modal removed, traceability and
categories fixed. Round 2: rule 3 (fill means a colour other than transparent and other than the slide's,
layout areas excluded, containers of two boxes excluded), fixture of E2E-007, E2E-029 baseline, budget
wording, I7 signal and E2E-004 reload step, cross spec ids replaced by topics. Round 3: dot at the last mouse
position when turned on, layout areas listed, guard lines per missing part, ring clipped to the slide,
stacked deck current slide, E2E-036, E2E-037, I10 to I12. Round 4 (precision only, applied): guard line
`<template>` spelled as the file name, Pointeur control on a refused full screen, E2E-038, E2E-039, E2E-028
narrowed to FR-NEW-010. Round 4 verdict NOT-IMPLEMENTABLE (6 F: 5 precision amendments applied, 3 product
choices answered by the recommended defaults): F1, in the two stacked decks the Pointeur control is a matching
button pinned 8 page pixels left of `Présenter`, tops aligned, hidden while presenting (FR-NEW-002, E2E-032);
F2, the slide pixel is the deck's own design width, 960 or 1280 (glossary, E2E-032 checks 22.5 ± 1 screen
pixels on Deck S at scale 1.25); F5, the dot is per input: a touch or pen contact hides it, the next mouse
move shows it again (FR-NEW-004, EXC-002d, E2E-026).
**Not re-audited:** the amendments of rounds 3 and 4, and these product choice answers, were NOT audited
again. The user authorized a fourth round only; the spec is closed on that decision.
**No implementation detail outside Section 14:** PASS (self consistency rounds 1 to 4, check 14).
**Amendment 2026-11-08 (BL-0040, after implementation, not re-audited):** E2E-008 steps aligned with
FR-NEW-006; FR-NEW-005 rules 3, 4 and 5 and the layout areas paragraph state the readings the tests encode
(see 14.3 I13). No behavior, test id or count changed.

## 14. Evidence appendix (for /sdlc-design and the auditor, not for the product owner)

### 14.1 Current State evidence

| Id | Claim (Section 2) | Evidence |
|---|---|---|
| E1 | present control in the editor toolbar, tooltip | `src/mcp_htmleditor/static/editor.html:41` |
| E2 | shown for presentations only, in both modes | `src/mcp_htmleditor/static/editor.js:263` (inside `updateSlideActionsVisibility`, `:261`) |
| E3 | the deck's own document is put full screen, focus moved to the frame | `src/mcp_htmleditor/static/editor.js:114` to `:135`, `:136` to `:143` |
| E4 | fallback: the iframe element full screen, deck not scaled | `src/mcp_htmleditor/static/editor.js:130` to `:133`; `src/mcp_htmleditor/static/editor.css:217` to `:226` |
| E5 | template keys, ignored in fields and editable text; F, Escape | `templates/bootstrap/slides-empty.html:396` to `:405`; stacked: `templates/reference/slides/presentation-standard.html:315` to `:324` |
| E6 | template present control, full screen CSS and scaling | `templates/bootstrap/slides-empty.html:243` to `:259`, `:291`, `:373` to `:387`, `:407` to `:417`; `templates/bootstrap/slides-ei-empty.html:271`; `templates/bootstrap/slides-medical-empty.html:451`; `templates/reference/slides/roadmap-one-pager.html:95`, `:99` |
| E6b | 11 presentation templates | `rg -l 'data-doc-type="presentation"' templates` gives 11 files; `tests/test_presentation_templates_fullscreen.py:18` to `:30` (`EXPECTED_TODAY`, 11 entries) |
| E7 | editor relay: arrows, Space, Home, End, Escape only, while full screen | `src/mcp_htmleditor/static/editor.js:152` to `:171` |
| E8 | navigation keys stopped in editable text in edit mode | `src/mcp_htmleditor/static/editor-edit.js:11` to `:17` |
| E9 | no pointer anywhere | `rg -n "e.key === '[lL]'" src templates` gives no hit; `rg -n -i 'pointer\|laser' sdlc/specs sdlc/backlog` finds no pointer feature |
| E10 | save strips on a detached clone, presenting state removed | `src/mcp_htmleditor/static/editor-save.js:26` to `:34`, `:63` |
| E11 | server strips editor artifacts again | `src/mcp_htmleditor/http_server.py:795`, `:838`, `:854` |
| E12 | exports from the file on disk | `src/mcp_htmleditor/static/editor.js:292` to `:297` (request with no body) |
| E13 | browser tests of presenting and relay | `tests/test_fullscreen_e2e.py:1` to `:23`; `tests/test_reference_decks_present_e2e.py:1` to `:12` |
| E14 | 13 browser test functions across both files | `rg -n '^def test_' tests/test_fullscreen_e2e.py tests/test_reference_decks_present_e2e.py` gives 13 |
| E15 | guard over presentation templates (substring markers) | `tests/test_presentation_templates_fullscreen.py:13`, `:51` |
| E16 | test step budget | `.agent_docs/testing.md:225` to `:232` |

Test command: `make test` (subset: `make test ARGS='-k "fullscreen or present"'`).

### 14.3 Design inputs

- I1. The relay forwards only the listed keys (`src/mcp_htmleditor/static/editor.js:152` to `:171`); L must be
  added, calling the deck's own toggle, without double toggling when the key event reached the deck itself
  (separate documents, no bubbling, `:149` to `:151`). Signal: E2E-003.
- I2. Each of the 11 templates carries its own copy of the navigation script; the EI starting point is
  generated from the EI reference (`Makefile:251` to `:253`, `make check-generated` at `:259` to `:261`) and
  the medical sync copies only the style (`Makefile:255` to `:257`). Parity across 11 copies, and the
  generated EI file, must be kept. Signal: `make check-generated`, E2E-032, E2E-033.
- I3. The editor must know whether the shown deck carries the pointer to show or hide its Pointeur control
  (FR-NEW-002); how it detects it is open. Signal: E2E-035.
- I4. Hidden cursor and any marker set on the live page while pointing must never reach a save; the save
  clone strip (`src/mcp_htmleditor/static/editor-save.js:26` to `:34`, `:63`) and the server strip
  (`src/mcp_htmleditor/http_server.py:854`) are the two places; BL-0034 documents that the clone strip
  rewrites a `style` holding `cursor`. Signal: E2E-018, E2E-028.
- I5. The PPTX resolver indexes stylesheet rules by class (`src/mcp_htmleditor/export/pptx_style.py:601`);
  new rules for the dot and ring must not be picked up as content styles. Signal: E2E-029.
- I6. The guard checks substring markers (`tests/test_presentation_templates_fullscreen.py:13`, BL-0036); the
  pointer marker and the failure line `<file>: missing pointer` extend it. Signal: E2E-033.
- I7. ASSUMED: an agent write reloads the frame and the inner full screen ends with the replaced document; to
  be confirmed during design. FR-NEW-003 does not rest on it (pointer off after a reload either way). Signal:
  E2E-004, last And.
- I8. Suite budget (E16): E2E-001 to E2E-031 and E2E-035 are meant to share a small number of browser
  sessions (one opened directly, one served, plus the touch and reduced motion contexts); E2E-029 is a non
  browser export comparison except its one served presentation.
- I10. The deck has no notion of the editor's edit mode (its key handler only looks at the focused element,
  `templates/bootstrap/slides-empty.html:396` to `:405`; edit mode lives in the editor page,
  `src/mcp_htmleditor/static/editor-edit.js:11` to `:17`): the deck must learn it from the editor page, and
  the relay must not forward L in edit mode. Signal: E2E-018.
- I11. The slide is enlarged by a scale property while presenting (`templates/bootstrap/slides-empty.html:254`
  to `:258`); dot and ring geometry must be computed in slide pixels, then multiplied by the scale factor.
  Signal: E2E-006, E2E-024.
- I12. The layout areas of FR-NEW-005 differ per template (Carbon header with a bottom rule,
  `templates/bootstrap/slides-empty.html:98`; EI inner frame; medical top band and foot band); the design
  maps each template's areas. Signal: E2E-007, E2E-036.
- I9. The fixture sizes (1600 × 900, slide 960 × 540) follow the existing deck browser tests
  (`tests/test_reference_decks_present_e2e.py:3`).
- I13. Amendment from BL-0040 (2026-11-08): E2E-008 clicks the slide background between the two cell clicks,
  as `tests/test_pointer_served_e2e.py::test_pointer_served_table_is_one_box` does; FR-NEW-005 states the
  readings of design DEC-008 (container test on direct children only; rule 4 never a layout area; page number
  part of the footer, `LAYOUT_AREAS` of DEC-009; a block whose text sits only in inline descendants is the box,
  `holdsText` in `templates/bootstrap/slides-empty.html`; every `inline*` display except `img`, `svg`, `video`,
  `canvas` is text inside a line). Design corrections for whoever reads design.md (not edited): the guard marker
  is `window.togglePointer = function` (`tests/test_presentation_templates_fullscreen.py:17`), not
  `function togglePointer(` (design.md, US-0105); DEC-015 needs `:fullscreen #deck-controls { display:none
  !important; }` because the container's inline `display:flex` wins
  (`templates/reference/slides/presentation-standard.html:196`). Left open in BL-0041: a click on a form
  field's label, and a click on the black margins, neither tested.
