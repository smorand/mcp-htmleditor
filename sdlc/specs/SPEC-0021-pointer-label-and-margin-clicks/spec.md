# Pointer clicks on a field's caption and on the black margins: functional specification

> Id: SPEC-0021
> Nature: FEAT
> Depth: M
> Depth evidence: classified S (one observable behavior: which clicks change the pointer's ring; one area, the pointer carried by every presentation starting point; no public contract or persisted change), escalated to M in gate round 1: 3 requirements, 14 new tests and 1 modified test, length over the S budget
> Status: specified
> Generated on: 2026-11-09
> Project: existing
> From backlog: BL-0041
> Depends on: SPEC-0017 (presentation pointer)
> Security: n/a
> CVSS: n/a
> Affected: n/a
> Fixed in: n/a

Nature: FEAT (backlog `Nature: FEAT`, routing rule 1; confirmed by Q2: SPEC-0017/FR-NEW-008 names "a link, a
button or a form field" and says an element inside a link or a button counts as it, but says nothing of a
field's caption, and FR-NEW-006 says nothing of a click outside the slide (14.1 E5, E6). The intent of
FR-NEW-008 points to the caption, but no authority states it, so nothing is violated: the behavior is decided
here, not restored.)

## 1. Summary

While presenting with the pointer, a click on the caption written beside a form field (`Note` in front of its
text field) gives the field the keyboard focus and, at the same time, moves the red ring onto the caption: the
presenter who only wanted to type in the field loses the ring they had placed. This increment makes a caption
tied to a field or a button behave like that field or button: the click keeps its usual effect and the ring does
not change. It also writes down and tests what a click on the black margins around the slide does (nothing to
the ring), and hardens one flaky acceptance test of the pointer in the editor.

## 2. Current State

### 2.1 What users can do today

- While a deck is presented with the pointer on, a click on a box of the current slide rings it, moves the ring
  to it, or removes the ring when the box is already ringed; a click on the slide where no box is found removes
  the ring (E1).
- A click on a link, a button or a form field of the slide keeps its usual effect and leaves the ring as it was;
  an element inside a link or a button counts as the link or the button (E2).
- A click on the text of a form field's caption is not treated as a click on the field: the caption's line is
  taken as a text block and ringed (the ring moves there, or is removed when that line was already ringed),
  while the browser also gives the field the keyboard focus. Observed on 2026-11-09 with Deck P presented at
  1600 by 900: `Tile A` ringed, a click on the word `Note` leaves one ring, around the line `Note` and its
  field, and the field `Note` has the focus (E3).
- A click on the black margins around the slide, while presenting in a window of another shape than the slide,
  changes nothing: the ring stays (observed on 2026-11-09 at 1600 by 1000, click at (800, 20), `Tile A` still
  ringed) (E4).
- Every presentation starting point offered by the product (11 of them) carries the same pointer (E7). A deck
  carries its own copy of the pointer from the day it was created.

### 2.2 Specs governing this area

SPEC-0017 (status implemented, amended 2026-11-08): FR-NEW-004 (dot hidden over the margins), FR-NEW-005 (box
choice), FR-NEW-006 (one ring at a time), FR-NEW-008 (links, buttons and fields keep their click), EXC-002c,
SPEC-0017 E2E-013, E2E-014, E2E-019, E2E-021 (mouse moves over the margins; no click). This increment modifies
SPEC-0017/FR-NEW-008 (FR-MOD-001) and adds one rule next to FR-NEW-006 (FR-NEW-001). SPEC-0017 is not edited.

### 2.3 What is verified today

Links (SPEC-0017 E2E-013), buttons (SPEC-0017 E2E-014) and a text field (SPEC-0017 E2E-019, which clicks the field `Note` with `Tile A`
ringed and checks the ring) are tested with the pointer on; no test clicks a field's caption or the black
margins (E5). One acceptance test of the editor's Pointeur control (SPEC-0017
E2E-004) failed 3 times under load: it reads the presented deck while the editor is replacing it after an
agent's write, and finds no page there (E8).

## 3. Scope

### 3.1 In scope

- A click on a caption tied to a form field or a button keeps its usual effect and leaves the ring unchanged.
- A click on the black margins around the slide leaves the ring unchanged; stated and tested.
- The flaky acceptance test of the Pointeur control made reliable, its behavior unchanged (E2E-MOD-001).
  Folded here rather than in SPEC-0020 or a separate debt: it tests this same pointer in the same group of
  tests this increment extends, its gap is a test reading a deck in transition (no product behavior moves), and
  a separate debt document for one wait would cost more than the fix.

### 3.2 Out of scope, and why

- Decks created before this change keep the pointer they carry, with today's caption behavior: the product
  never rewrites an existing deck's own code (same rule as SPEC-0017 section 3.2; bringing the pointer to older
  decks is BL-0038).
- A caption tied to nothing is ordinary text and keeps the box rules of SPEC-0017/FR-NEW-005.
- Presenter view and a second window: BL-0037.

### 3.3 Constraints imposed by the context

- The user (2026-11-09): the full gate's test step stays under 330 s, about 270 to 300 s on a quiet machine; the
  tests of this increment reuse the pages already opened by their test groups, add at most 4 s together, and
  never wait a fixed time.

## 4. Actors

- **Presenter:** presents a deck full screen, from the editor or from the file opened directly, with the
  pointer on.
- **Agent:** writes the deck file while it is presented in the editor (E2E-MOD-001 only).

## 4.5 Bounded contexts

| Context | What it owns | Key concepts |
|---|---|---|
| Deck presentation | what the presented deck shows and how it answers clicks and keys | slide, pointer, ring, box, caption |
| Editor | the page that serves, reloads and presents the deck | Pointeur control, agent update, reload |

## 5. Usage scenarios

### SC-001: Fill a field while pointing
**Actor:** Presenter
**Preconditions:** a deck made after this change is presented with the pointer on; `Tile A` is ringed; the slide
holds a text field with the caption `Note`.
**Flow:**
1. The presenter clicks the word `Note` → the field `Note` takes the keyboard focus; `Tile A` stays the only
   ring.
2. They type `abc` → the field reads `abc`; the ring is unchanged.
**Postconditions:** `Tile A` ringed, the field holds `abc`, the file is unchanged.
**Exceptions:**
- EXC-001a: the caption is tied to no field → it is ordinary text: its line is ringed as any paragraph.
- EXC-001b: no ring was shown → none appears; the field takes the focus.
- EXC-001c: the caption names a field placed elsewhere on the slide → that field takes the focus; ring unchanged.
- EXC-001d: the caption's field is disabled → nothing takes the focus; ring unchanged.
- EXC-001e: the caption names a field of another slide → the caption is ordinary text: its line is ringed.
- EXC-001f: the caption names a progress bar or a computed value, which is not a field → ordinary text.
- EXC-001g: the caption names a hidden field → ordinary text.
- EXC-001h: text beside a field neither wraps nor names it → ordinary text; no field takes the focus.

### SC-002: Click beside the slide
**Actor:** Presenter
**Preconditions:** a deck presented with the pointer on in a window taller than the slide's shape, so black
bands show above and below the slide; `Tile A` is ringed.
**Flow:**
1. The presenter clicks in the black band above the slide → nothing changes: `Tile A` stays ringed, the same
   slide shows.
2. They click `Tile B` → `Tile B` is the only ring.
**Postconditions:** the pointer keeps working after a click in a margin.
**Exceptions:**
- EXC-002a: no ring was shown → a margin click adds none.
- EXC-002b: the click lands on the slide's own top edge, one pixel inside it → it is a click on the slide
  (SPEC-0017/FR-NEW-006 applies).

## 6. Functional requirements

### 6.1 New

#### FR-NEW-001 [EARS-UB]: A click outside the slide changes nothing
> The deck presentation SHALL NOT ring a box, move the ring, nor remove the ring when a click lands outside the
> current slide.

- **Business rules:** outside the slide means the black margins shown around the slide while presenting. The
  slide shown, the pointer state (on) and the dot rules of SPEC-0017/FR-NEW-004 do not change. The next click on
  the slide follows SPEC-0017/FR-NEW-006. A click one screen pixel inside the slide's edge is on the slide.
- **User visible text:** none.
- **Scenario:** SC-002
- **Priority:** Must

### 6.2 Modified

#### FR-MOD-002 [EARS-UB]: Which captions are tied (modifies SPEC-0017/FR-NEW-008)
> The deck presentation SHALL NOT treat a caption as tied to a control unless the caption wraps the control or
> names it by the control's own identifier, and the control is a button or a data entry field shown on the
> current slide.

- **Before:** SPEC-0017 does not define captions (Section 2.2).
- **After:** "a button or a data entry field" is every kind of button (including submit and reset) and every
  data entry control: text field of any kind (text, number, email, date, color, and the like), range slider, file
  chooser, check box, radio choice, choice list, text area; a disabled or read only one counts (ring unchanged;
  a disabled one takes no focus). Not one: a progress bar, a meter, a computed value. A control not shown on
  the current slide (on another slide, or hidden) leaves the caption ordinary text. Text placed near a control
  without wrapping or naming it is ordinary text. Ordinary text follows SPEC-0017/FR-NEW-005.
- **Reason:** one predictable rule for the presenter: only a caption that acts on a usable control of the shown
  slide keeps the click away from the ring, and the controls are those SPEC-0017/FR-NEW-008 already protects.
- **User visible text:** none.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-MOD-001 [EARS-UB]: Links, buttons, fields and their captions keep their click (modifies SPEC-0017/FR-NEW-008)
> The deck presentation SHALL NOT ring a box nor change the ring when the click lands on a link, a button, a form
> field, or a caption tied to a button or a form field.

- **Before:** a click on a field's caption rings the caption's line, moves or removes the ring (Section 2.1).
- **After:** the statement above. A caption is tied to a control as stated in FR-MOD-002; it then counts as
  that control, wherever the control sits on the current slide, and an element inside the caption counts as
  the caption. The click does what it does without the pointer: the field or the button takes the focus, a
  check box or a choice toggles, a button's action runs. A caption tied to nothing is ordinary text
  (SPEC-0017/FR-NEW-005 applies).
- **Reason:** a presenter who fills a field by its caption keeps the ring they placed, as with the field itself.
- **User visible text:** none.
- **Scenario:** SC-001
- **Priority:** Must

## 7. Non functional requirements (user observable)

### 7.1 Performance
- The ring answers a caption or margin click within the same frame budget as any click (SPEC-0017, unchanged).
- The full gate's test step stays under 330 s; this increment's tests add at most 4 s (Section 3.3).

### 7.5 Reliability
- E2E-MOD-001 never fails for lack of a deck to read while the editor reloads it (10 runs in a row under the
  full suite's load).

## 8. Edge cases

| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Empty states | no ring shown, caption or margin click | no ring appears | E2E-002, E2E-007 |
| Boundary values | click one pixel inside the slide's top edge | it is a slide click | E2E-009 |
| Concurrent actions | agent write while presented with the pointer | reloaded deck, pointer off | E2E-MOD-001 |
| Slow or lost connectivity | not applicable: the pointer runs in the deck, no network | n/a | n/a |
| Access states | disabled field | caption still tied, ring unchanged | E2E-010 |
| Data variations | caption wrapping vs naming; caption of a non field; caption tied to nothing | Section 6.2 | E2E-001, E2E-004, E2E-012, E2E-003 |
| Navigation | caption naming a field of another slide | ordinary text | E2E-011 |
| Partial operations | not applicable: one click, no multi step | n/a | n/a |
| Dependency failures | not applicable: no service involved | n/a | n/a |
| Ordering and timing | margin click then slide click | the slide click follows SPEC-0017/FR-NEW-006 | E2E-008 |
| Exhaustion | not applicable: one ring at most (SPEC-0017) | n/a | n/a |

## 9. Acceptance tests (the contract)

> Behavioral and technology agnostic. /sdlc-design maps each test to a driver. Test plan approved under the
> 2026-11-09 instruction (recommended defaults, no question); written by the requirements author at depth S.

**Fixtures.** Deck P is the deck of SPEC-0017 section 9.0 (1600 by 900 window, scale 1.6667; slide 1 holds
`Tile A`, `Tile B`, a link `Docs`, a button `Count`, a text field captioned `Note` wrapped by its caption).
For this increment its slide 2 (dark) also holds, each on its own line and inside the area of the slide's text:
a caption `Remarque` tied to no field, inside a paragraph; a caption `Email` that names a text field `email`
placed on the next line, not wrapped by it; a caption `Locked` wrapping a disabled text field; a caption
`Elsewhere` naming the field `Note` of slide 1; a caption `Progress` naming a progress bar; a caption `Volume`
wrapping a range slider; a caption `Ghost` naming a text field that is hidden; the word `Nearby` in a paragraph
beside a text field, neither wrapping nor naming it. A deck opened directly as a file is used unless a test says
"served". "X ringed" means one ring, around X, as defined by SPEC-0017.

### 9.1 Summary

| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 | New | failure | SC-001 | FR-MOD-001 | Critical |
| E2E-002 | New | failure | SC-001 | FR-MOD-001 | High |
| E2E-003 | New | happy | SC-001 | FR-MOD-001 | High |
| E2E-004 | New | edge | SC-001 | FR-MOD-001 | High |
| E2E-005 | New | edge | SC-001 | FR-MOD-001, FR-MOD-002 | Medium |
| E2E-006 | New | failure | SC-002 | FR-NEW-001 | Critical |
| E2E-007 | New | failure | SC-002 | FR-NEW-001 | High |
| E2E-008 | New | happy | SC-002 | FR-NEW-001 | High |
| E2E-009 | New | edge | SC-002 | FR-NEW-001 | Medium |
| E2E-010 | New | failure | SC-001 | FR-MOD-002 | High |
| E2E-011 | New | failure | SC-001 | FR-MOD-002 | High |
| E2E-012 | New | edge | SC-001 | FR-MOD-002 | Medium |
| E2E-013 | New | failure | SC-001 | FR-MOD-002 | Medium |
| E2E-014 | New | failure | SC-001 | FR-MOD-002 | Medium |
| E2E-MOD-001 | Modified | state transition | SPEC-0017 SC-001 | SPEC-0017/FR-NEW-002, FR-NEW-003 | High |

Coverage: happy 2, failure 8, edge 4, state transition 1 (modified), side effect 1 (the typed text of
E2E-001), security 0 (not a security increment). Happy to failure ratio 1:4. FR-MOD-002 has E2E-005, E2E-010 to
E2E-014, and E2E-003 and E2E-004 (a caption tied to nothing, a caption naming a field elsewhere).

### 9.2 New tests

#### E2E-001: The caption gives the field the focus, the ring stays
- **Category:** failure (the click is refused as a ring change)
- **Scenario:** SC-001
- **Requirements:** FR-MOD-001
- **Given** Deck P presented, pointer on, `Tile A` ringed
- **When** the presenter clicks the middle of the word `Note`, then types `abc`
- **Then** `Tile A` is the only ring, the field `Note` has the keyboard focus and reads `abc`
- **And** slide 1 still shows and the pointer is still on
- **Priority:** Critical

#### E2E-002: The caption with no ring adds none
- **Category:** failure
- **Scenario:** SC-001 (EXC-001b)
- **Requirements:** FR-MOD-001
- **Given** Deck P presented, pointer on, no ring
- **When** the presenter clicks the middle of the word `Note`
- **Then** no ring shows and the field `Note` has the keyboard focus
- **Priority:** High

#### E2E-003: A caption tied to nothing is ordinary text
- **Category:** happy
- **Scenario:** SC-001 (EXC-001a)
- **Requirements:** FR-MOD-001
- **Given** Deck P presented on slide 2, pointer on, no ring
- **When** the presenter clicks the middle of the word `Remarque`
- **Then** the paragraph holding `Remarque` is ringed, as a click on a plain paragraph would ring it
- **Priority:** High

#### E2E-004: A caption naming a field elsewhere
- **Category:** edge
- **Scenario:** SC-001 (EXC-001c)
- **Requirements:** FR-MOD-001
- **Given** Deck P presented on slide 2, pointer on, `Edge tile` ringed
- **When** the presenter clicks the middle of the word `Email`
- **Then** `Edge tile` is the only ring and the field `email` has the keyboard focus
- **Priority:** High

#### E2E-005: A caption of a range slider is tied
- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-MOD-001, FR-MOD-002
- **Given** Deck P presented on slide 2, pointer on, `Edge tile` ringed
- **When** the presenter clicks the middle of the word `Volume`
- **Then** `Edge tile` is the only ring
- **Priority:** Medium

#### E2E-006: A margin click keeps the ring
- **Category:** failure
- **Scenario:** SC-002
- **Requirements:** FR-NEW-001
- **Given** Deck P presented in a 1600 by 1000 window (black bands of 50 pixels above and below the slide),
  pointer on, `Tile A` ringed
- **When** the presenter clicks at (800, 20)
- **Then** `Tile A` is the only ring, slide 1 still shows, the pointer is still on and no dot shows at (800, 20)
- **Priority:** Critical

#### E2E-007: A margin click adds no ring
- **Category:** failure
- **Scenario:** SC-002 (EXC-002a)
- **Requirements:** FR-NEW-001
- **Given** Deck P presented in a 1600 by 1000 window, pointer on, no ring
- **When** the presenter clicks at (800, 980)
- **Then** no ring shows and slide 1 still shows
- **Priority:** High

#### E2E-008: The pointer works after a margin click
- **Category:** happy
- **Scenario:** SC-002
- **Requirements:** FR-NEW-001
- **Given** Deck P presented in a 1600 by 1000 window, pointer on, `Tile A` ringed
- **When** the presenter clicks at (800, 20), then clicks the middle of `Tile B`
- **Then** `Tile B` is the only ring
- **Priority:** High

#### E2E-009: One pixel inside the slide's edge is the slide
- **Category:** edge
- **Scenario:** SC-002 (EXC-002b)
- **Requirements:** FR-NEW-001 (boundary), SPEC-0017/FR-NEW-006
- **Given** Deck P presented in a 1600 by 1000 window, pointer on, `Tile A` ringed
- **When** the presenter clicks at (800, 51), in the slide's header area where no box is found
- **Then** no ring shows (the click was on the slide background and removed the ring)
- **Priority:** Medium

#### E2E-010: A caption of a disabled field is still tied
- **Category:** failure
- **Scenario:** SC-001 (EXC-001d)
- **Requirements:** FR-MOD-002
- **Given** Deck P presented on slide 2, pointer on, `Edge tile` ringed
- **When** the presenter clicks the middle of the word `Locked`
- **Then** `Edge tile` is the only ring and no field of the slide has the keyboard focus
- **Priority:** High

#### E2E-011: A caption naming a field of another slide is ordinary text
- **Category:** failure (the caption is refused as tied)
- **Scenario:** SC-001 (EXC-001e)
- **Requirements:** FR-MOD-002
- **Given** Deck P presented on slide 2, pointer on, no ring
- **When** the presenter clicks the middle of the word `Elsewhere`
- **Then** the paragraph holding `Elsewhere` is the only ring and slide 2 still shows
- **Priority:** High

#### E2E-012: A caption naming a progress bar is ordinary text
- **Category:** edge
- **Scenario:** SC-001 (EXC-001f)
- **Requirements:** FR-MOD-002
- **Given** Deck P presented on slide 2, pointer on, no ring
- **When** the presenter clicks the middle of the word `Progress`
- **Then** the paragraph holding `Progress` is the only ring
- **Priority:** Medium

#### E2E-013: A caption of a hidden field is ordinary text
- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-MOD-002
- **Given** Deck P presented on slide 2, pointer on, no ring
- **When** the presenter clicks the middle of the word `Ghost`
- **Then** the paragraph holding `Ghost` is the only ring
- **Priority:** Medium

#### E2E-014: Text beside a field is not its caption
- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-MOD-002
- **Given** Deck P presented on slide 2, pointer on, no ring
- **When** the presenter clicks the middle of the word `Nearby`
- **Then** the paragraph holding `Nearby` is the only ring and no field of the slide has the keyboard focus
- **Priority:** Medium

### 9.4 Modified tests

#### E2E-MOD-001: The Pointeur control, reliable across an agent's write (was SPEC-0017 E2E-004)
- **Validated before:** the Pointeur control's place and names, presenting with it turns the pointer on, the
  present control does not, and an agent's write while presenting with the pointer reloads the deck with the
  pointer off.
- **Validates now:** the same, plus two added checks on the reloaded deck (no ring shows, the system cursor
  shows over the slide), with the last checks made only on the reloaded deck: while the editor is replacing
  the deck, the deck is read as "not reloaded yet", never as a failure.
- **Given** Deck P served, the editor shown at 1600 by 900, presented with the Pointeur control, pointer on
- **When** an agent replaces `Plain` by `Changed` in the file while the deck is presented
- **Then** within 10 s the editor shows the reloaded deck holding `Changed paragraph`, and on it the pointer is
  off: no dot and no ring show, and the system cursor shows over the slide
- **And** run 10 times in a row while the full suite runs in parallel, it never fails for lack of a deck to read
- **Priority:** High

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-MOD-001, FR-MOD-002 | E2E-003 | E2E-001, E2E-002, E2E-010, E2E-011, E2E-013, E2E-014 | E2E-004, E2E-005, E2E-012 |
| SC-002 | FR-NEW-001 | E2E-008 | E2E-006, E2E-007 | E2E-009 |
| SPEC-0017 SC-001 (served) | SPEC-0017/FR-NEW-002, FR-NEW-003 | E2E-MOD-001 | n/a | n/a |

## 11. Open questions

- Test plan approved under the 2026-11-09 instruction (recommended defaults, no question asked); the tests were
  written by the requirements author, not a separate test designer. Does not change observable behavior.

## 12. Glossary

| Term | Definition | Context |
|---|---|---|
| Caption | The text written beside a form field or a button to name it | the slide's content |
| Tied | Said of a caption that wraps or names, by its identifier, a button or a data entry field shown on the current slide (FR-MOD-002) | the slide's content |
| Ring | The red outline the pointer draws around one box of the current slide (SPEC-0017) | presenting |
| Black margins | The black bands around the slide while presenting in a window of another shape than the slide | presenting |
| Pointer | The red dot and the ring shown while presenting after L or the Pointeur control (SPEC-0017) | presenting |
| Deck P | The test deck of SPEC-0017 section 9.0, extended in Section 9 | tests |

## 13. Implementability gate

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 1 (G1: disabled control, control on another slide, non field target) | 0 | NOT-IMPLEMENTABLE |
| 2 | 1 (G1, G2: kinds of controls, hidden control, text near a field) | 3 (E2E-019 tests a field click; E2E-MOD-001 adds checks; a doubled signal line) | NOT-IMPLEMENTABLE |
| 3 | 0 | 2 (test count in the front block; SPEC-0017 test ids prefixed) | IMPLEMENTABLE |

Each round by a fresh `pi -p` auditor given only the path and the audit contract. Self consistency (Phase 10)
checked inline and by the auditors (statistics, traceability, glossary).

**Amendments applied:** round 1: FR-MOD-002, E2E-010 to E2E-012, depth escalated to M; round 2: FR-MOD-002
rewritten (kinds of controls, hidden, text near a field), E2E-005 replaced (range slider), E2E-013, E2E-014,
2.3 and E5 corrected, E2E-MOD-001 checks declared; round 3: the two A findings.
**No implementation detail outside Section 14:** PASS

## 14. Evidence appendix (for /sdlc-design and the auditor, not for the product owner)

### 14.1 Current State evidence

| Claim (Section 2) | Evidence |
|---|---|
| E1. click rings, moves or removes | `templates/bootstrap/slides-empty.html:574-584` (click handler), `:518-561` (`findBox`) |
| E2. controls keep their click | `templates/bootstrap/slides-empty.html:442` (`CONTROLS = 'a[href], button, input, select, textarea'`), `:577-578` |
| E3. caption click rings the caption's line | no `label` in `CONTROLS` (`:442`); the label is a flex item of a column flex container, hence blockified, and holds text (`holdsText`, `:563-572`); observed in Chromium 2026-11-09, `ring_around(page, "label")` equals the ring, `document.activeElement.id == "note"` |
| E4. margin click changes nothing | `templates/bootstrap/slides-empty.html:576` returns when the target is outside the current slide; observed 2026-11-09 at 1600 by 1000, click (800, 20), target `.slide-frame`, `Tile A` still ringed |
| E5. no test clicks a caption or the margins | `tests/test_pointer_ring_e2e.py` E2E-013 (`click_centre(page, "#link-docs")`), E2E-014, E2E-019 (`:236-247`, clicks `#note`); `tests/test_pointer_dot_e2e.py:158-172` (`test_pointer_dot_over_the_black_margins`, mouse moves only); `rg -n "label" tests/test_pointer_*.py` finds no caption click |
| E6. FR-NEW-006 and FR-NEW-008 wording | `sdlc/specs/SPEC-0017-presentation-pointer/spec.md:299-307`, `:320-328`, `:1101-1102` (I13 leaves both open) |
| E7. 11 starting points carry the block | `rg -l "var CONTROLS = 'a\[href\], button, input, select, textarea'" templates` (11 files), synced by `make sync-deck-pointer` (`Makefile:259-261`, `tools/sync_deck_pointer.py`) |
| E8. the flaky test | `tests/test_pointer_served_e2e.py:261-295` (`test_pointer_served_pointeur_control`); `:289` evaluates `(document.getElementById('content-frame').contentDocument).body.textContent`, which throws while the frame holds a document without `body` during the reload; `wait_until` (`tests/browser_wait.py:23-41`) does not catch an exception of its observation |
| Deck P fixture | `tests/pointer_support.py:55` (`<label>Note <input id="note" type="text"></label>` in a flex column, `:52`) |

Test command: `make test ARGS='-k pointer'`; gate `make check`.

### 14.3 Design inputs

- The control test is a selector list (`slides-empty.html:442`); a caption is an HTML `label`, and "tied" is the
  browser's own association (`label.control`: wrapping or `for`), narrowed by FR-MOD-002 to `button`, `input`,
  `select`, `textarea` inside the current slide and rendered (`label.control` also returns `meter`, `output`,
  `progress`; a hidden `input` or one on another slide is not rendered on the current slide).
  A `label` tied to nothing has `control === null`. Detection signal: E2E-003, E2E-004, E2E-005, E2E-010 to E2E-014.
- The block lives in 11 files kept equal by `make sync-deck-pointer` and checked by
  `tests/test_presentation_templates_fullscreen.py`; `make install` must run after the change (AGENTS.md).
  Detection signal: the pointer template tests over every presentation template (`tests/test_pointer_templates_e2e.py`).
- Deck P is shared by the pointer test groups (`tests/pointer_support.py:185`, fixture `pointer_file_page` at `:190`); slide 1 positions are asserted by
  many tests, so the new captions go on slide 2, below its existing content, and must not move `Edge tile`; if slide 2 has no room for the new lines below its content, the tests may
add them to the deck before presenting it, as long as each line sits inside the slide's text area. Detection
signal: the existing slide 2 tests (`tests/test_pointer_ring_e2e.py`) and a caption click landing on the slide
  (E2E-003).
- E2E-MOD-001: the observation must read the frame's document defensively (absent document or body reads as not
  yet reloaded) and wait for the reloaded deck to be complete before reading the pointer state; no fixed wait
  (`tests/test_no_fixed_waits.py`). Detection signal: the 10 run repetition under load.
- Time: the module pages `pointer_file_page` (`tests/pointer_support.py`) are reused; E2E-006 to E2E-009 can share
  one presentation at 1600 by 1000 with E2E-021.
