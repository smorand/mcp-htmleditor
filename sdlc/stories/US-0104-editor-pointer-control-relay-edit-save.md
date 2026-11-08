# US-0104: Editor Pointeur control, relay, edit mode and save

> Spec: SPEC-0017 (sdlc/specs/SPEC-0017-presentation-pointer/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0103
> min_tier: 1
> Files touched: 6
> Closes spec: no

## Objective

In the editor the presenter cannot start a presentation with the pointer, an L typed while the focus stayed in the
editor page is lost, and nothing keeps edit mode and saves away from the pointer. After this story the editor toolbar
shows `Pointeur` beside the present control, forwards L like the other presenting keys, pushes edit mode into the
deck (no pointer while editing), shows no control for a deck created before this version, and never writes anything
of the pointer into the file.

Silent pitfalls (why tier 1): headless Chromium keeps the focus in the iframe, so a relay test must dispatch on the
parent `document` or it proves nothing; the editor's whole file save reformats the deck, so byte comparisons start
from the editor's own baseline save; the fallback presentation must leave nothing armed.

## Requirements covered

- SPEC-0017/FR-NEW-001: WHEN the presenter presses L while a deck is presented full screen THE deck presentation SHALL turn the pointer on if it was off, and off if it was on.
- SPEC-0017/FR-NEW-002 (partial: the editor toolbar control): WHEN the presenter presses the Pointeur control THE deck presentation SHALL present the deck full screen with the pointer on.
- SPEC-0017/FR-NEW-003: WHEN a presentation starts by any means other than the Pointeur control THE deck presentation SHALL start with the pointer off.
- SPEC-0017/FR-NEW-010: The editor page SHALL NOT write into the saved file anything that the pointer added to the shown deck.
- SPEC-0017/FR-NEW-011: The deck presentation SHALL NOT change what Right, Down, Space, Left, Up, Home, End, F and Escape do, with the pointer on or off, opened directly or in the editor.
- SPEC-0017/FR-NEW-012: The deck presentation SHALL NOT turn the pointer on while edit mode is on, nor when L is typed in a text field or an editable text.

Business rules (spec, verbatim): FR-NEW-001 "In the editor the key works whichever page holds the keyboard focus (the
deck or the editor page), as the other presenting keys do; one press toggles once." FR-NEW-002 "In the editor it shows
exactly when the present control shows, except that it is hidden while edit mode is on and for a deck that does not
carry the pointer. ... If the browser refuses the deck's own full screen, the control starts the fallback
presentation exactly as the present control does, with no pointer." Label `Pointeur`; tooltip and accessible name
`Présenter avec le pointeur (L)`. FR-NEW-003 "A deck reloaded after the agent rewrote the file shows the pointer off,
whether or not it is still full screen." FR-NEW-010 "pointing never saves: a presentation with the pointer, its
clicks and its rings leave the file byte identical. A save made later in the same page (edit mode turned on after
presenting) writes the edit and nothing of the dot, the ring, the hidden cursor or the pointer's state; the deck's
own pointer behavior, which lives in the deck file, is kept as it is." FR-NEW-011 "the editor page keeps forwarding
the keys it forwards today, and now also L; it forwards nothing while not presenting." FR-NEW-012 "while edit mode is
on, L in an editable text types the letter, L elsewhere does nothing, the Pointeur control is hidden, and a
presentation started from edit mode has no pointer."

## Independent Test

`make test ARGS='-k pointer_served'`: the eight tests red before the editor changes (no `#pointer-btn`, L from the
editor page lost, `Pointeur` absent), green after; `make test ARGS='-k "fullscreen or reference_decks_present"'`
unchanged.

## Design excerpt

### Decisions
- DEC-013 (SPEC-0017): "`#pointer-btn` after `#present-btn`; `presentDeck(withPointer)` shares today's present path, arming before the request and disarming in each fallback branch; visibility rule; relay branch for L that skips edit mode and modifiers; `syncPointerAllowed()` on edit toggle and frame load."
- DEC-014 (SPEC-0017): "`stripPresentingState(root)` (`editor-save.js:63`) also removes `#deck-pointer-layer` from the clone and `data-deck-pointer` from the clone's root; the server strip is unchanged."
- DEC-006 (SPEC-0017): the deck turns the pointer on at `fullscreenchange` only when armed; `armPointer(false)` disarms.
- DEC-017 (SPEC-0017): relay tests dispatch `new KeyboardEvent('keydown', {key, bubbles: true, cancelable: true})` on the editor page's `document`; Deck O = Deck P with the deck-pointer block, the `#btn-pointer` element and the L line removed; E2E-028's 3 seconds are 3 status polls (`wait_polls`, `tests/width_support.py:277`); POST `/content` counted by the init script of `tests/width_support.py` (`SAVE_COUNTER_SCRIPT`).
- DEC-019 (SPEC-0017): E2E-018 compares against the editor's own baseline save taken before any pointer use; saved == baseline with the paragraph's serialized markup replaced once by its new serialized markup, and holds none of `deck-pointer-layer`, `data-deck-pointer`, `cursor:none`.

### Contracts
`editor.html`, right after `#present-btn`:
`<button id="pointer-btn" type="button" title="Présenter avec le pointeur (L)" aria-label="Présenter avec le pointeur (L)" style="display:none">Pointeur</button>`

`editor.js`:
- `presentBtn` click: `presentDeck(false)`; `pointerBtn` click: `presentDeck(true)`. `presentDeck(withPointer)` is today's handler body (`editor.js:114` to `:135`) preceded by `if (withPointer && typeof win.armPointer === 'function') win.armPointer(true)` and with `win.armPointer(false)` (when the function exists) in the `.catch` fallback and the `catch (e)` fallback.
- `updateSlideActionsVisibility()`: `pointerBtn.style.display = (isPresentation && !editMode && deckCarriesPointer()) ? 'inline-flex' : 'none'`; `deckCarriesPointer()` true when `frame.contentWindow` has `presentWithPointer`, `armPointer`, `togglePointer`, `setPointerAllowed` as functions.
- Relay, a branch before `Escape` in the listener of `editor.js:152`:
  ```js
  } else if ((e.key === 'l' || e.key === 'L') && !e.ctrlKey && !e.metaKey && !e.altKey && !editMode
             && typeof win.togglePointer === 'function') {
    e.preventDefault();
    win.togglePointer();
  ```
`editor-edit.js`: `function syncPointerAllowed()` calls `frame.contentWindow.setPointerAllowed(!editMode)` when it
exists; called last in `applyEditMode()` and from `onFrameLoad()` (`editor.js:204`).
`editor-save.js`: in `stripPresentingState(root)`, `root.querySelectorAll('#deck-pointer-layer').forEach(n => n.remove())`
and `root.removeAttribute('data-deck-pointer')`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor.html` | modify: `#pointer-btn` |
| `src/mcp_htmleditor/static/editor.js` | modify: `presentDeck`, visibility, relay L, call `syncPointerAllowed` on frame load |
| `src/mcp_htmleditor/static/editor-edit.js` | modify: `syncPointerAllowed` |
| `src/mcp_htmleditor/static/editor-save.js` | modify: strip pointer state |
| `tests/pointer_support.py` | modify: `deck_o()`, served helpers (open editor, present, relay dispatch) |
| `tests/test_pointer_served_e2e.py` | modify: the eight tests below |

### Existing patterns
- Relay tests and their dispatch: `tests/test_fullscreen_e2e.py:302` to `:360`.
- Save while presenting writes no presenting state: `tests/test_reference_decks_present_e2e.py:256` to `:315`.
- Baseline save then byte comparison: `tests/test_width_drag_e2e.py:139` to `:159`.
- Agent write reloading the frame: `tests/test_width_agent_e2e.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Deck P (spec 9.0) and Deck O (Deck P without the pointer) served in the editor page at 1600 × 900, location
`tests/test_pointer_served_e2e.py`, functional e2e; "focus in the editor page" means keys dispatched on the parent
`document`.

### SPEC-0017/E2E-002: Pointer in the editor's presentation, focus in the deck
- Given Deck P served, edit mode off, presented with the editor's present control, the keyboard focus in the deck
- When the presenter presses L, moves the mouse to (800, 450), then presses L again
- Then after the first L a red dot is centred on (800, 450); after the second the dot is gone and the system cursor shows

### SPEC-0017/E2E-003: L from the editor page toggles once
- Given Deck P served and presented, the keyboard focus left in the editor page
- When the presenter presses L, moves the mouse to (800, 450), presses Right, then presses L
- Then after the first L the dot shows (on, toggled once, not twice); Right shows slide 2; after the second L the dot is gone

### SPEC-0017/E2E-004: The editor's Pointeur control
- Given Deck P served, edit mode off
- When the editor user looks at the toolbar, then presses `Pointeur`, then moves the mouse to (800, 450)
- Then `Pointeur` sits immediately after the present control (next element sibling, and its left edge right of the present control's right edge), its tooltip and accessible name read `Présenter avec le pointeur (L)`; after the press the deck is full screen and the red dot shows at once
- And after Escape and the present control, a mouse move shows no dot (off again)
- And after `Pointeur` again, the agent rewriting the file with the paragraph `Plain paragraph` changed to `Changed paragraph` reloads the deck, which shows `Changed paragraph` and no dot on a mouse move

### SPEC-0017/E2E-018: Edit mode has no pointer, and a save after pointing keeps none
- Given Deck P served; it was presented with the pointer on and `Tile A` ringed, then left with Escape (baseline save taken before, DEC-019)
- When the editor user turns edit mode on, looks at the toolbar, presents with the present control, presses L, moves the mouse, presses Escape, places the caret at the end of `Plain paragraph` and types `l`, then the change is saved
- Then no `Pointeur` control shows while edit mode is on; while presented L shows no dot; the paragraph reads `Plain paragraphl`; the file holds `Plain paragraphl` and is otherwise identical to before, with nothing of a dot, a ring, a hidden cursor or a pointer state

### SPEC-0017/E2E-028: Pointing leaves the file byte identical
- Given Deck P served, edit mode off, its file contents noted
- When the presenter presents, turns the pointer on, rings `Tile A`, `Tile B`, the table, changes slide, turns the pointer off and leaves, then waits 3 seconds (3 status polls)
- Then the file is byte identical to the noted contents and the editor shows no save or conflict notice (no POST `/content` sent)

### SPEC-0017/E2E-031: Existing keys with the pointer on, opened directly and served
- Given Deck P, presented with the pointer on and a ring, once opened directly and once served with the focus in the editor page
- When the presenter presses Right, Space, Left, End, Home, then Escape
- Then the slides shown are 2, 3, 2, 3, 1 in that order, no ring shows after the first key, and Escape leaves full screen, exactly as with the pointer off

### SPEC-0017/E2E-035: A deck created before this version
- Given Deck O served, edit mode off
- When the editor user looks at the toolbar, presents with the present control, presses L, moves the mouse, then presses Right and Escape
- Then no `Pointeur` control shows; L shows no dot and changes nothing; Right shows slide 2; Escape leaves full screen

### SPEC-0017/E2E-038: L typed in an editable text in edit mode, not presenting
- Given Deck P served, edit mode on, not presented, the caret at the end of `Tile A`'s title
- When the editor user types `L`, then clicks outside any text and presses L
- Then the title reads `Tile AL`; no dot shows after either press; the slide shown is unchanged
- Red before the fix because (E2E-002 to E2E-004, E2E-035 with the toolbar): `#pointer-btn` does not exist and the relay drops L.

## Constraints

- Files not to touch: the templates, `src/mcp_htmleditor/http_server.py` (server strip unchanged, DEC-014), `tests/test_fullscreen_e2e.py` assertions.
- Dependencies not to add: none.
- Patterns to avoid: relay tests that press keys with the focus in the iframe; comparing saved bytes to the fixture text; fixed waits; any call into the deck not guarded by `typeof === 'function'`.
- Scope boundary: other templates, the guard and the docs come later.

## Definition of done

- [ ] RED evidence recorded for every new test before the editor edits, in `.implement/US-0104-red.log`.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_fullscreen_e2e.py` (relay table, End, fallback), `tests/test_reference_decks_present_e2e.py` (save while presenting), US-0102 and US-0103 tests green; `node --check` on the four static files passes.
- [ ] Durations reported (`make test ARGS='-k pointer_served --durations=0'`), served module about 12 s in total.
- [ ] Docs updated: none in this story (US-0110).
- [ ] Self review: full (tier 1).
- [ ] One commit `US-0104: Editor Pointeur control, relay, edit mode and save`, body `Spec: SPEC-0017` and FR-NEW-001 to FR-NEW-003, FR-NEW-010 to FR-NEW-012.
