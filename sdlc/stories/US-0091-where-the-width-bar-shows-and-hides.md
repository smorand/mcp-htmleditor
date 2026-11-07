# US-0091: Where the width bar shows and hides

> Spec: SPEC-0015 (sdlc/specs/SPEC-0015-text-max-width-handle/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0090
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

The bar appears only where a width makes sense (text blocks, list items, mail paragraphs, documents) and never on
images, tables, diagram nodes, Gantt tasks, annotations, inline labels, outside edit mode, in the fullscreen
presentation or during an agent update; it follows its text on scroll and hides on a slide change, an empty area
and a reload.

## Requirements covered

- SPEC-0015/FR-NEW-001: WHILE edit mode is on THE editor SHALL show the width bar on the right edge of the text block under the pointer.
- SPEC-0015/FR-NEW-002: The editor SHALL treat as a text block the innermost element under the pointer that is inside an editable text zone, is a paragraph, a heading of level 1 to 6, a list item, a quotation, a figure caption or the editable text zone itself, and is not laid out inline within a line of text.
- SPEC-0015/FR-NEW-003: The editor SHALL NOT show the width bar on an image, on a table or anything inside it, on a diagram node or edge, on a Gantt task, on an annotation, on the editor's own controls, outside edit mode, during the fullscreen presentation, or while an agent update is in progress.

Business rules (spec, verbatim): FR-NEW-001 "the bar is as tall as the block and sits on its right edge, inside the
window. It stays on that edge while the page scrolls or the window is resized. It hides when the pointer leaves both
the block and the bar (except during a drag), when the slide changes, when edit mode is turned off and when the
document reloads. It takes the keyboard focus when clicked." FR-NEW-002 "when the pointer is on an inline piece of
text (a word, a tag), the enclosing text block gets the bar. A list item inside a list inside a zone: the list item
gets the bar." FR-NEW-003 "a text block inside a table cell gets no bar. A text block with no width on screen
(hidden) gets no bar."

## Independent Test

`make test ARGS='-k width_visibility'`: the eight tests below pass; the bar's `hidden` state and its rectangle are
read right after each pointer action (synchronous handlers, DEC-006) and compared with the block's rectangle on screen;
saved results are read in the file.

## Design excerpt

### Decisions
- DEC-005 (SPEC-0015): "`widthBlockAt(doc, target)`: return `null` when `target.closest(EXCLUDED)` matches, with `EXCLUDED = 'img, picture, svg, video, canvas, table, [data-type="arch-node"], [data-type="arch-edge"], [data-type="gantt-task"], [data-type="annotation"], #_mcp_format_bar, #_mcp_insert_bar, ._mcp_drag_handle, #_editor_ctx_host'`; else walk from `target` (its parent when it is a text node) up through ancestors while the element is inside a zone (`el.closest('[data-editable~="text"]')`), and return the first element that matches `p, h1, h2, h3, h4, h5, h6, li, blockquote, figcaption, [data-editable~="text"]` and whose computed `display` does not start with `inline` and is not `contents`; `null` when the walk leaves the zone, when the result has a zero width rectangle, when edit mode is off, when `document.fullscreenElement` or `doc.fullscreenElement` is set, or when the update overlay shows (`overlay.style.display === 'flex'`)."
- DEC-006 (SPEC-0015): "Show, hide and position are synchronous in the event handlers: `pointermove` on the framed document (attached by `widthBarAttach`), `pointerleave` of the bar and of the frame's root (hide unless the pointer goes to the block or the bar), `scroll` on the framed document in the capture phase and `resize` on the shell window (reposition; hide when the block is disconnected or has a zero width), `click` and `keyup` on the framed document (same check, which hides the bar after a slide change). No `requestAnimationFrame` throttling."
- DEC-008 (SPEC-0015), visibility part: `onFrameLoad` (`editor.js:199`) calls `widthBarOnFrameLoad()` first (bar hidden until the pointer moves); `pollStatus` (`editor.js:309`) calls `widthBarOnAgentUpdate()` when it shows the update overlay.
- DEC-011 (SPEC-0015): shared module page, one server per test.

### Contracts
`function widthBarOnFrameLoad()`, `function widthBarOnAgentUpdate()` (new globals in `editor-width.js`); the update
flag is set in a test with `mcp_htmleditor.state.get_state().set_update_flag(True)` (in process server), cleared with
`False` (`state.py:115`).

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-width.js` | modify: full `widthBlockAt`, hide rules, scroll and resize follow |
| `src/mcp_htmleditor/static/editor.js` | modify: `widthBarOnFrameLoad()` first in `onFrameLoad`; `widthBarOnAgentUpdate()` in `pollStatus` overlay branch |
| `tests/width_support.py` | modify: fixture writers D2 (`document-perso-empty.html`, title `Rapport Q1`, `Paragraphe 1` to `Paragraphe 40`, paragraph 1 `style="max-width:500px"`), M1 (`mail-empty.html` as is), W1 (`website-empty.html` as is); `bar_rect(page)`, `block_rect(page, selector)` in shell coordinates |
| `tests/test_width_visibility_e2e.py` | create |

### Existing patterns
- Fullscreen in a test: `tests/test_fullscreen_e2e.py` (click `#present-btn`, observe `document.fullscreenElement`).
- Document reorder handle drag: `tests/test_undo_redo_e2e.py` (document block reorder test).
- Agent write from a test: write the file, then observe the frame reload with `wait_for_js`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

All: functional e2e, Playwright Chromium, shared module page, `tests/test_width_visibility_e2e.py`.

### SPEC-0015/E2E-021: No bar on sized or positioned things
- Given D1 in edit mode / When the author points in turn at the cell `Valeur A1`, the header `Indicateur`, the image `logo`, then on slide 3 at `Serveur MCP`, `Cadrage` and `Pic`
- Then no width bar shows for any of them
- And pointing at the word `Nouveau` shows the bar on paragraph B's right edge, as tall as B

### SPEC-0015/E2E-022: No bar outside editing
- Given D1 / When the author points at A with edit mode off; then in the fullscreen presentation; then in edit mode while the agent's update overlay shows
- Then no width bar shows in any of the three

### SPEC-0015/E2E-023: Nested list item
- Given D1 / When the author points at `Second point` and drags its bar left until the readout shows `300 px` and lets go
- Then the bar was as tall as that item only; the item's style reads `max-width:300px`; the list and `Premier point` have no style

### SPEC-0015/E2E-024: Document, scrolled, with the reorder handle
- Given D2 in edit mode, scrolled so `Paragraphe 30` is in view / When the author points at it, scrolls 200 pixels, then drags its bar until the readout shows `500 px` and lets go
- Then after the scroll the bar is still on that paragraph's right edge; its style reads `max-width:500px`
- And dragging `Paragraphe 30` by its reorder handle above `Paragraphe 29` still works and the moved paragraph keeps `max-width:500px`

### SPEC-0015/E2E-025: The bar hides
- Given D1, the bar shown on A / When the author moves the pointer to an empty area of the page; then points at A again and goes to slide 3 with the next arrow
- Then the bar hides in both cases

### SPEC-0015/E2E-031: Mail paragraph
- Given M1 in edit mode / When the author drags the intro paragraph's bar until the readout shows `400 px` and lets go
- Then that paragraph's style holds all its previous declarations in order, each with its exact text, followed by `; max-width:400px`, and nothing after it (expected: `margin:0; font-family:Helvetica,Arial,sans-serif; font-size:15px; line-height:1.6; color:#1a1a1a; text-align:justify; max-width:400px`)

### SPEC-0015/E2E-033: Inline label in a clickable control
- Given W1 in edit mode / When the author points at the tab label `Vue d'ensemble`
- Then no width bar shows (the label is inline and its enclosing control is not a text block)

### SPEC-0015/E2E-043: The agent writes the file while the bar shows
- Given D1, the bar shown on A, no drag / When the agent writes the file with A's style `max-width:500px` and the editor reloads the document
- Then the bar is hidden until the pointer moves again; pointing at A shows it on A's new right edge (A 500 wide); the file holds the agent's `max-width:500px` and the editor saved nothing (`settle` then `window.__widthSaves` unchanged)

## Constraints

- Files not to touch: `editor-save.js`, `editor-undo.js`, `http_server.py`, Python product modules.
- Dependencies not to add: none.
- Patterns to avoid: an asynchronous show or hide (rAF, observers); a marker class or attribute on the pointed text.
- Scope boundary: drag cancel on reload and the poll guard for an active drag are US-0092.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_fullscreen_e2e.py`, `tests/test_website_template_e2e.py`, the document reorder tests of `tests/test_undo_redo_e2e.py`, and the earlier width files.
- [ ] Run time: `make test ARGS='-k width_visibility --durations=0'` recorded; the file takes at most 6 s.
- [ ] Docs updated: none in this story (US-0093).
- [ ] Self review: full (tier 2).
- [ ] One commit `US-0091: Where the width bar shows and hides`, body `Spec: SPEC-0015` and FR-NEW-001, FR-NEW-002, FR-NEW-003.
