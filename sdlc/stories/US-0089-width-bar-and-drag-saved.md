# US-0089: Width bar and drag saved as one declaration

> Spec: SPEC-0015 (sdlc/specs/SPEC-0015-text-max-width-handle/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 1
> Files touched: 8
> Closes spec: no

## Objective

In edit mode the author can point at a text, press the thin bar on its right edge and drag it: the text reflows
live, the bar reads the value in slide pixels, and letting go saves exactly one inline declaration `max-width:Npx`
without rewriting a single character of the other declarations. This is the minimum that delivers SC-001. The silent
pitfall is that the browser's style object rewrites the whole attribute (`#0F62FE` becomes `rgb(15, 98, 254)`): the
saved text must be rebuilt as text, and the live preview must never reach a save.

## Requirements covered

- SPEC-0015/FR-NEW-001 (partial: the bar shows on the pointed text block, on its right edge, as tall as the block, with its accessible name and tooltip; hiding rules and focus are US-0090 and US-0091): WHILE edit mode is on THE editor SHALL show the width bar on the right edge of the text block under the pointer.
- SPEC-0015/FR-NEW-002 (partial: paragraphs, inline words resolve to their paragraph; list items, captions and the exclusions are US-0091): The editor SHALL treat as a text block the innermost element under the pointer that is inside an editable text zone, is a paragraph, a heading of level 1 to 6, a list item, a quotation, a figure caption or the editable text zone itself, and is not laid out inline within a line of text.
- SPEC-0015/FR-NEW-004: WHEN the author drags the width bar THE editor SHALL set the text's maximum width to its width at the press plus the pointer's horizontal travel, both counted in the slide's own pixels.
- SPEC-0015/FR-NEW-005: WHEN the author lets go of the width bar after moving it THE editor SHALL save the text's inline style with the declaration `max-width:Npx`, N being the last value shown.
- SPEC-0015/FR-NEW-010 (partial: the preview never reaches a save; the full marker and cancel cases are US-0092): The editor SHALL NOT save the width bar, its readout, any marker of the pointed text, or a width still being dragged.
- SPEC-0015/FR-NEW-012 (partial: other declarations and the rest of the file untouched by a drag): The editor SHALL NOT change, through a width action, any text, any other element, or the written form of any other declaration of the text's style.
- SPEC-0015/FR-NEW-013 (partial: the release goes through the normal save and its status; conflict and error paths are US-0092): The editor SHALL save a width change through the same save as every other edit, with its status, conflict notice and error notice.
- SPEC-0015/NFR-001: WHILE the author drags the bar THE editor SHALL reflow the text with each pointer move, with no visible lag on a slide of 30 text blocks.

Business rules to honour (spec, verbatim where quoted):
- The bar "is as tall as the block and sits on its right edge, inside the window". Accessible name `Largeur du texte`; tooltip `Glisser pour régler la largeur, double clic pour revenir à la largeur du modèle`.
- "the slide's own pixels are the document's, whatever size the slide is shown at: on a slide shown at half size, 50 pixels of pointer travel are 100 slide pixels. The value is rounded to the nearest multiple of 10, or to the nearest whole pixel while Alt is held, then kept between 80 and 1280 included. The text reflows live. While dragging, the bar shows the value as the number, a space and `px` (example `650 px`); the readout disappears when the drag ends."
- "the inline style is rebuilt as: its declarations split on `;`, each trimmed, empty ones and any existing `max-width` declaration (whatever its unit) dropped, the others kept in their order and with their exact text, then `max-width:Npx` appended, all joined with `; `. A text with no style gets `style="max-width:Npx"`. [...] A `;` inside parentheses or inside a quoted string is part of its declaration and is not a separator; such a declaration is kept character for character."

## Independent Test

`make test ARGS='-k width_drag'` (part of `make check`): the eight tests below pass; each reads the saved file on
disk (not a value the script computed), for example paragraph B's style reads exactly
`color:#0F62FE; font-weight:600; max-width:650px` and the rest of the file is byte identical to before.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0015): "The bar is one element of the shell page (`#width-bar` with its `#width-readout`), placed with `position: fixed` over the frame at `frameRect.left + blockRect.right` and `frameRect.top + blockRect.top`, height `blockRect.height`, its left clamped to `window.innerWidth - barWidth`. It is never inserted into the framed document."
- DEC-002 (SPEC-0015): "A new classic script `static/editor-width.js`, loaded right after `editor-drag.js` (thirteen editor scripts), holds the style text functions and the bar. Its function names are unique across the editor scripts (checked by `tests/test_static_scripts.py`)."
- DEC-003 (SPEC-0015): "The saved style is rebuilt as text from the attribute text read before the action and written with `setAttribute('style', text)`, or `removeAttribute('style')` when the reset leaves nothing. The element's style object is used only for the live preview." Measured: `el.style.maxWidth` rewrites the whole attribute (hex to `rgb(...)`, spaces, quotes in `url(...)`), while clearing an absent property (`el.style.outline = ''` in the existing save clone) leaves the text untouched.
- DEC-004 (SPEC-0015): "`withWidthPreviewSuspended(fn)`: while a drag preview is applied, it sets the original attribute text back (or removes the attribute when it was absent), runs `fn` synchronously, then re-applies the preview with `style.setProperty('max-width', v + 'px')`. `runSave` wraps its `cloneNode(true)`; `captureDomSnapshot` wraps its `outerHTML`." This story wraps `runSave` (`editor-save.js:24`); US-0090 wraps `captureDomSnapshot`.
- DEC-006 (SPEC-0015): show, hide and position are synchronous in the event handlers (`pointermove` on the framed document), no `requestAnimationFrame` throttling.
- DEC-007 (SPEC-0015), drag part: "`pointerdown` on the bar (primary button) calls `preventDefault`, `focus()` and `setPointerCapture`, and records `widthDrag` with the original attribute text; `pointermove` computes the value, applies the preview and shows the readout; `pointerup` hides the readout and, when the pointer moved and `styleWithWidth(original, value)` differs from the original text, commits [...]. Commit: original text back, `snapshotForUndo()`, new text set, `markPending()`, `saveContent()`." Calling `snapshotForUndo()` here is harmless before US-0090 (it pushes the existing pre mutation snapshot).
- DEC-011 (SPEC-0015): one Chromium page per test module (module scoped context, viewport 1280 by 900), one server per test with the existing `_start` pattern; per test: write the fixture, `page.goto(base_url)`, wait for the frame document `readyState` `complete`, click `#edit-mode-btn`. Budget of the 43 tests of the spec: 25 s in total.

### Data model
In memory only: `widthBlock` (Element or null), `widthDrag` (`{block, originalStyle, startWidth, startX, ratio, value, moved, pointerId}` or null), constants `WIDTH_MIN = 80`, `WIDTH_MAX = 1280`, `WIDTH_STEP = 10`.

### Contracts
Shell markup in `static/editor.html`, after the frame, before the scripts:
```html
<div id="width-bar" role="separator" aria-orientation="vertical" aria-label="Largeur du texte"
     title="Glisser pour régler la largeur, double clic pour revenir à la largeur du modèle" tabindex="0" hidden>
  <span id="width-readout" hidden></span>
</div>
```
`static/editor-width.js`:
```js
function splitStyleDeclarations(text)       // (string|null) -> string[]; ';' inside (...), '...', "..." (backslash escapes) is not a separator
function styleDeclarationName(declaration)  // text before the first ':', trimmed, lower case
function styleHasWidth(text)                // true when a max-width declaration exists, any unit
function styleWithWidth(text, px)           // others verbatim and in order, max-width dropped, `max-width:${px}px` appended, joined '; '
function styleWithoutWidth(text)            // others verbatim, joined '; '; null when none left (used by US-0090)
function widthBlockAt(doc, target)          // this story: walk up to p/h1-h6/li/blockquote/figcaption/zone, not display inline*
function widthBarAttach(doc)                // called at the end of injectEditMode(doc)
function widthBarDetach(doc)                // called in removeEditMode(doc)
function withWidthPreviewSuspended(fn)
```
Value: `v = startWidth + (clientX - startX) / ratio`, `startWidth = parseFloat(getComputedStyle(block).width)` at the
press, `ratio = block.getBoundingClientRect().width / block.offsetWidth` (1 when `offsetWidth` is 0); `Math.round(v / 10) * 10`,
or `Math.round(v)` while `event.altKey`; clamped to `[80, 1280]`. Readout text `${value} px`.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/static/editor-width.js` | create |
| `src/mcp_htmleditor/static/editor.html` | modify: bar markup, `<script src="/static/editor-width.js"></script>` after `editor-drag.js` |
| `src/mcp_htmleditor/static/editor.css` | modify: `#width-bar` (fixed, 6 px wide, `cursor: ew-resize`, `--lg-*` free, above the frame), `#width-readout` |
| `src/mcp_htmleditor/static/editor-edit.js` | modify: `widthBarAttach(doc)` at the end of `injectEditMode`, `widthBarDetach(doc)` in `removeEditMode` |
| `src/mcp_htmleditor/static/editor-save.js` | modify: `const clone = withWidthPreviewSuspended(() => doc.documentElement.cloneNode(true));` |
| `tests/test_static_scripts.py` | modify: `"editor-width.js"` after `"editor-drag.js"` in `EXPECTED_SCRIPT_ORDER` |
| `tests/width_support.py` | create: fixture writers D1, D3 (D2, M1, W1 added by later stories), module page fixture, `open_editor(page, path)`, `drag_bar(page, block_selector, dx, *, alt=False, steps=5)` returning the readouts seen, `style_in_file(path, text)` (BeautifulSoup lookup of the element whose text starts with `text`, returns its `style` attribute or `None`), the `__widthSaves` fetch counter init script |
| `tests/test_width_drag_e2e.py` | create |

### Existing patterns
- Server start and Chromium skip: `tests/test_undo_redo_e2e.py` (`_start`, `needs_chromium`, `reset_state`).
- Frame access from a test: `_inner(page, js)` in `tests/test_undo_redo_e2e.py:152`.
- Waits: `tests/browser_wait.py` (`wait_for_file`, `wait_for_js`, `wait_until`); no `wait_for_timeout(` without `# pacing: <reason>` (`tests/test_no_fixed_waits.py`).
- Fixture D1 (spec 9.0): Carbon bootstrap `templates/bootstrap/slides-empty.html` grown to three slides; slide 2 body holds `<div style="width:800px">` containing, in order, each with `data-editable="text"`: A `<p style="max-width:600px">Chiffres clés du trimestre</p>`; B `<p style="color:#0F62FE;font-weight:600">Note de synthèse <span class="tag-blue">Nouveau</span></p>`; H `<p style="max-width: 40em;color:#525252;font-size:10px">Objectifs</p>`; I `<p style="max-width:85px">Mini</p>`; J `<p style="color:#123456">Hors charte</p>`; K `<p style="max-width:1250px">Large</p>`; P `<p style="max-width:50%">Agent</p>`; Q `<p style="background:url(data:image/png;base64,AAA);color:#123456">Fond</p>`; `<ul data-editable="text"><li>Premier point</li><li>Second point</li></ul>`; `<table data-type="table"><thead><tr><th>Indicateur</th></tr></thead><tbody><tr><td>Valeur A1</td></tr></tbody></table>`; `<img alt="logo" src="data:image/png;base64,...">` (1x1 PNG). Slide 3: arch node `Serveur MCP`, Gantt task `Cadrage`, annotation `Pic`. Update `TOTAL` and `slideNames`. D3 = D1 plus `<style>.slide{transform:scale(0.5);transform-origin:top left}</style>` in the head.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

All: Level functional e2e; Driver Playwright Chromium on the shared module page, one server per test; Location
`tests/test_width_drag_e2e.py`. Preconditions: the fixture written to `tmp_path`, editor open on slide 2, edit mode on.
Cleanup: server stopped by the fixture. "the file" means the served file read on disk after `wait_for_file`.

### SPEC-0015/E2E-001: Drag a paragraph's width and save it
- Given D1 on slide 2, edit mode on
- When the author points at paragraph A, presses the bar on its right edge, moves the pointer 47 pixels to the right and lets go
- Then while moving the bar reads `650 px`, after letting go the readout is gone
- And the file's paragraph A style reads `max-width:650px` and the save status shows saved (status dot colour `rgb(66, 190, 101)`)
- And after a reload paragraph A is 650 pixels wide

### SPEC-0015/E2E-002: Alt gives single pixels
- Given D1 on slide 2 / When the author drags A's bar 47 pixels right with Alt held and lets go
- Then the readout showed `647 px` and A's style reads `max-width:647px`

### SPEC-0015/E2E-003: Lower bound
- Given D1 on slide 2 / When the author drags A's bar 600 pixels left and lets go
- Then the readout showed `80 px` and A's style reads `max-width:80px`

### SPEC-0015/E2E-004: Upper bound
- Given D1 on slide 2, window 2400 pixels wide (`page.set_viewport_size({"width": 2400, "height": 900})`, restored after) / When the author drags A's bar 900 pixels right and lets go
- Then the readout showed `1280 px` and A's style reads `max-width:1280px`

### SPEC-0015/E2E-005: Slide pixels on a scaled slide
- Given D3 on slide 2 (shown at half size) / When the author drags A's bar 50 screen pixels right and lets go
- Then A's style reads `max-width:700px` (not `650px`)

### SPEC-0015/E2E-006: Other declarations and their colour kept verbatim
- Given D1 on slide 2, B is 800 pixels wide / When the author drags B's bar 153 pixels left and lets go
- Then B's style reads exactly `color:#0F62FE; font-weight:600; max-width:650px`
- And no style in the file holds `rgb(`; the rest of the file is byte identical to before (compare the file with the fixture text where only B's `style` attribute value is replaced)

### SPEC-0015/E2E-007: An existing width in another unit is replaced
- Given D1 on slide 2, H rendered 400 pixels wide (40em at 10 pixels) / When the author drags H's bar 200 pixels right and lets go
- Then H's style reads exactly `color:#525252; font-size:10px; max-width:600px`

### SPEC-0015/E2E-042: A `;` inside a value is not a separator
- Given D1, paragraph Q is 800 pixels wide / When the author drags Q's bar 153 pixels left and lets go
- Then Q's style reads exactly `background:url(data:image/png;base64,AAA); color:#123456; max-width:650px`

## Constraints

- Files not to touch: `src/mcp_htmleditor/http_server.py` (the bar never enters the framed document, no strip entry); every Python product module.
- Dependencies not to add: none (no JS build, no npm).
- Patterns to avoid: writing the saved width through `el.style` or `style.cssText`; inserting any node or attribute into the framed document; `time.sleep` or an unjustified `wait_for_timeout(` in tests; a late save variant.
- Scope boundary: keyboard, double click reset, undo wrapping of `captureDomSnapshot` are US-0090; hide rules, exclusions, list items, scroll are US-0091; cancel, reload, conflict are US-0092; docs are US-0093.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (`.implement/US-0089-red.log`).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] `node --check src/mcp_htmleditor/static/editor-width.js` passes (part of the static scripts test).
- [ ] Non regression: `tests/test_undo_redo_e2e.py`, `tests/test_autosave_focus_e2e.py`, `tests/test_save_ui_e2e.py`, `tests/test_strip_idempotent.py`, `tests/test_static_scripts.py` pass unchanged except the one line of the order list.
- [ ] Run time: `make test ARGS='-k width_drag --durations=0'` output recorded; the file takes at most 6 s.
- [ ] Docs updated: none in this story (US-0093).
- [ ] Self review: full (tier 1): walk through what happens if the blur save fires between `pointerdown` and the first `pointermove`.
- [ ] One commit `US-0089: Width bar and drag saved as one declaration`, body `Spec: SPEC-0015` and FR-NEW-001, FR-NEW-002, FR-NEW-004, FR-NEW-005, FR-NEW-010, FR-NEW-012, FR-NEW-013, NFR-001.
