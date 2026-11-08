# US-0095: End relayed by the editor page

> Spec: SPEC-0016 (sdlc/specs/SPEC-0016-reference-decks-and-editor-residues/)
> Nature: BUG
> Priority: P2
> Depends on: main
> min_tier: 1
> Files touched: 2
> Closes spec: no

## Objective

A presenter whose browser leaves the keyboard focus on the editor page cannot jump to the last slide: the editor
page relays every navigation key to the deck except `End`. This story adds `End` to the relay and, for the first
time, tests the relay itself rather than the deck's own handler.

Silent pitfall (why tier 1): in headless Chromium the focus stays in the iframe whatever the test focuses, so a key
pressed with `page.keyboard.press` reaches the deck, never the relay, and a test written that way passes before the
fix. The relay tests must dispatch the event on the editor page's `document`.

## Requirements covered

- SPEC-0016/BR-001: WHILE the deck shown in `#content-frame` is presenting THE editor page SHALL show the deck's last slide when a `keydown` whose `key` is `End` reaches the editor page's `document`.
- SPEC-0016/BR-002: WHILE the deck shown in `#content-frame` is presenting THE editor page and the deck together SHALL move exactly one slide forward on `ArrowRight`, `ArrowDown` or ` ` (space), one slide back on `ArrowLeft` or `ArrowUp`, to the first slide on `Home`, to the last slide on `End`, and leave presenting on `Escape`, whichever of the two documents receives the `keydown`.
- SPEC-0016/BR-003: IF the deck shown in `#content-frame` defines no `goToSlide` function THEN THE editor page SHALL ignore `End` and `Home` without raising a page error.
- SPEC-0016/BR-004: The editor page SHALL NOT act on `End`, `Home`, arrows, space or `Escape` while the deck is not presenting.

Business rules (spec, verbatim): "show the last slide" means the deck's `goToSlide(n - 1)` with `n` the number of
slides, the same call the deck's own `End` handler makes; its default action (page scroll) is prevented. Forward on
the last slide and back on the first change nothing; one key press never moves two slides.

## Independent Test

`make test ARGS='-k fullscreen'`: BT-001 is red before the change (`#progress-tag` stays `1 / 3`) and green after;
the four existing fullscreen tests pass unchanged.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0016): "The relay gains an `End` branch: guarded by `typeof win.goToSlide === 'function'`, slide count `win.document.querySelectorAll('[data-type=\"slide\"]').length`, `preventDefault` then `win.goToSlide(count - 1)`, nothing when the count is 0." `TOTAL` is a `const` in the decks, absent from `window`.
- DEC-002 (SPEC-0016): "Relay tests dispatch `new KeyboardEvent('keydown', {key, bubbles: true, cancelable: true})` on the editor page's `document` with `page.evaluate` and read `defaultPrevented` from the returned event; they live in `tests/test_fullscreen_e2e.py` and reuse its `deck_server` fixture and `_three_slide_deck`."
- DEC-014 (SPEC-0016): the SPEC-0016 browser tests take at most 40 s together; report this file's durations.

### Contracts
In `src/mcp_htmleditor/static/editor.js`, inside the existing parent `keydown` listener (`:152` to `:167`), after the
`Home` branch and before `Escape`:

```js
} else if (e.key === 'End' && typeof win.goToSlide === 'function') {
  const count = win.document.querySelectorAll('[data-type="slide"]').length;
  if (count > 0) { e.preventDefault(); win.goToSlide(count - 1); }
}
```

The first line of the listener (`if (!document.fullscreenElement) return;`) stays: it is BR-004.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor.js` | modify: `End` branch |
| `tests/test_fullscreen_e2e.py` | modify: add BT-001, BT-010, BT-011, BT-012; the four existing tests unchanged |

### Existing patterns
- `deck_server` fixture and `_three_slide_deck` (`tests/test_fullscreen_e2e.py:66`, `:93`): D3, a 3 slide EI deck.
- Entering presenting from the editor page and waiting: `test_exiting_fullscreen_keeps_the_current_slide_and_restores_the_ui` (`tests/test_fullscreen_e2e.py:271`).
- Waits: `tests/browser_wait.py` `wait_for_js`, `wait_until`; no `wait_for_timeout` without `# pacing:`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Location `tests/test_fullscreen_e2e.py`. Viewport 1600x900. `D3` is `_three_slide_deck`. `#progress-tag` is read
inside `#content-frame`. Dispatch helper (test side): `page.evaluate("k => { const e = new KeyboardEvent('keydown', {key: k, bubbles: true, cancelable: true}); document.dispatchEvent(e); return e.defaultPrevented; }", key)`.

### SPEC-0016/BT-001: End relayed by the editor page
- Level / Driver / Location: functional e2e / Playwright on the editor page serving D3 / `tests/test_fullscreen_e2e.py`
- Given D3 served, the editor page loaded, `#present-btn` clicked and the deck's `<html>` fullscreen (wait until `frame.contentDocument.fullscreenElement === frame.contentDocument.documentElement`)
- When `End` is dispatched on the editor page's `document`
- Then the deck's `#progress-tag` reads `3 / 3` (observed with `wait_for_js`)
- Red before the fix because: the relay has no `End` branch, `#progress-tag` stays `1 / 3`.

### SPEC-0016/BT-010: Full key table through the relay
- Given D3 presenting in the editor page, on slide 1
- When keydowns are dispatched on the editor page's `document` in the order `End`, `End`, `ArrowLeft`, `Home`, ` `, `ArrowDown`, `ArrowUp`, `ArrowRight`, `ArrowRight`
- Then `#progress-tag` reads, after each, `3 / 3`, `3 / 3`, `2 / 3`, `1 / 3`, `2 / 3`, `3 / 3`, `2 / 3`, `3 / 3`, `3 / 3`
- And each dispatched `End`, ` ` and arrow event returns `defaultPrevented` `true`
- When `Escape` is dispatched the same way
- Then `document.fullscreenElement` is `null` within 2 seconds (`wait_until` with a 2 s bound)

### SPEC-0016/BT-011: One move per key whichever document gets it
- Given D3 presenting in the editor page, on slide 1, `document.activeElement.id` is `content-frame`
- When `page.keyboard.press("End")`, then `page.keyboard.press("ArrowLeft")`
- Then `#progress-tag` reads `3 / 3`, then `2 / 3` (one move each, never two)

### SPEC-0016/BT-012: Relay tolerates a deck without navigation
- Given the editor page serving the `doc` bootstrap (`templates/bootstrap/document-empty.html` copied to `tmp_path`) with its `<html>` fullscreen (`document.getElementById('content-frame').contentDocument.documentElement.requestFullscreen()` run from a click handler or `page.evaluate` after a user gesture), a `pageerror` listener attached
- When `End` and `Home` keydowns are dispatched on the editor page's `document`
- Then no `pageerror` fired and the framed document's `body.innerText` is unchanged
- Given D3 in the editor page, edit mode on (`#edit-mode-btn`), not presenting, caret inside the slide title
- When `End` is dispatched on the editor page's `document`
- Then `#progress-tag` still reads `1 / 3` (absence read after `settle(page)`)

### SPEC-0016/BT-030: Existing fullscreen tests unchanged
- When the four existing tests of `tests/test_fullscreen_e2e.py` run
- Then they pass with their current assertions (no line of them edited)

## Constraints

- Files not to touch: every template, every other editor script, the four existing tests' bodies.
- Dependencies not to add: none.
- Patterns to avoid: `page.keyboard.press` to exercise the relay (reaches the deck, not the relay); `document.body.focus()` to move focus out of the frame (does not work, E4); fixed waits.
- Scope boundary: `Home` keeps its current behavior (no `preventDefault` added); the decks' own handlers are US-0097 and US-0098.

## Definition of done

- [ ] RED evidence recorded for BT-001 and BT-010 (and BT-012's first half if red) before the production code, in `.implement/US-0095-red.log`.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: SPEC-0001 E2E-038 to E2E-041 (the four existing tests) unchanged and green.
- [ ] `node --check src/mcp_htmleditor/static/editor.js` passes.
- [ ] Durations of the new tests reported (`make test ARGS='-k fullscreen --durations=0'`), within DEC-014.
- [ ] Docs updated: none in this story (US-0101 documents the relay).
- [ ] Self review: full (tier 1).
- [ ] One commit `US-0095: End relayed by the editor page`, body `Spec: SPEC-0016` and BR-001, BR-002, BR-003, BR-004.
