# SPEC-0017: Pointer in presentation mode, design

> Spec: sdlc/specs/SPEC-0017-presentation-pointer/spec.md
> Nature: FEAT
> Depth: M
> Security: n/a
> Designed on: 2026-11-08
> Target tier: 2 (user instruction for this run: tier 2 by default, stories with silent pitfalls at `min_tier` 1; no `Tier:` in `sdlc/constitution.md`, no `.spec.json`)

Run mode: unattended (the user asked for no questions and the recommended defaults). No new dependency, no new
route, no new setting, no data format change. Project state: existing (`ls src/mcp_htmleditor` lists the product
package; `git log --oneline -1` is `3ba0b97`).

Counts (by command on `spec.md`): 14 requirements (`FR-NEW-001` to `FR-NEW-014`; `FR-026` and `FR-028` are
SPEC-0001 references), 39 acceptance tests (`E2E-001` to `E2E-039`), 4 scenarios (`SC-001` to `SC-004`).

Gate note (spec section 13): the round 3 and 4 amendments were not independently audited. This design read
FR-NEW-005 rule by rule against every acceptance test. Three places admit more than one reading; for each, one
reading is forced by an acceptance test or yields no observable difference on any fixture, so no spec issue was
filed and the reading is recorded as a decision (DEC-008): rule 4 never picks a layout area (forced by E2E-036);
the "container of two boxes" test is not recursive; "text set inside a line" means every inline level display,
replaced elements excepted. These are spec leaks to fold into the next amendment of SPEC-0017, not blockers.

## 1. Stack and skills

| Element | Choice | Version | DEC |
|---|---|---|---|
| Deck behavior | self contained HTML templates, inline CSS and classic `<script>`, no build step | n/a | existing, DEC-001 |
| Shared pointer code | one marked block per template, synced from `templates/bootstrap/slides-empty.html` by `tools/sync_deck_pointer.py` | n/a | DEC-001, DEC-002 |
| Editor (browser) | classic scripts `static/editor.js`, `editor-edit.js`, `editor-save.js`, `editor.html` | n/a | existing, DEC-013, DEC-014 |
| PPTX exporter | `export/pptx_style.py` indexes class selectors only (`_SELECTOR_REJECT`, `:558`) | python-pptx as locked | existing, DEC-012 |
| Browser tests | pytest, pytest-playwright (Chromium), `tests/browser_wait.py`, `tests/conftest.py` `serve_deck` | as locked | existing, DEC-017 |
| Pixel reads | Pillow, already used by the tests (`tests/render_support.py`), installed with python-pptx | as locked | existing, DEC-017 |

Skills loaded: `python` (via `load_dynamic_context`, injected for this run). Effect: `make check` is the gate
(check-generated, lint, format-check, typecheck strict, bandit, coverage 80 %); tests run through `make test` only
(`make test ARGS='-k pointer'`); constants at the top of modules, no `print`, f strings, `%` logging. Project
conventions applied: `AGENTS.md` (fullscreen rule, browser waits and pacing rule, `node --check` on static JS),
`.agent_docs/testing.md` (test step at most 330 s, `browser_wait`, shared module pages of SPEC-0015),
`sdlc/constitution.md` (fullscreen guard row).

## 2. Approaches

The main HOW question is sharing one behavior across 11 single file templates that must keep working opened
directly (`file://`, decks handed to people without the editor).

### Chosen: one marked block per template, synced from a source template, checked by `make check-generated`

The pointer CSS and script live between `<!-- deck-pointer:begin -->` and `<!-- deck-pointer:end -->` just before
`</body>` of every presentation template. `templates/bootstrap/slides-empty.html` is the source; a tool rewrites the
block in every other presentation template holding the markers, and its `--check` mode joins `check-generated`
(the pattern of `tools/sync_medical_css.py` and `tools/gen_ei_bootstrap.py`). The per template parts (the Pointeur
button, one line in the deck's own key table) are hand edits, checked by the template guard. Pros: decks stay single
file and work from `file://`; one source of truth, drift fails the gate; generic code (current slide, layout areas,
scale) so the block is byte identical everywhere. Cons: a new tool and make target; the block carries the union of
every template's layout area class names. Best suited when the files must stay standalone, which they must.

### Rejected: hand duplication kept equal by a byte comparison test

Same runtime result, no tool. Rejected (DEC-001): every snippet fix becomes 11 hand edits, and the test only
reports drift, it cannot repair it; the repository already chose generation for the EI bootstrap and the medical CSS.

### Rejected: an external script file, or injection by the server

A `<script src>` breaks decks handed off as a single file and opened from `file://` (spec 3.3); server injection
gives nothing to a deck opened directly (SC-002) and risks being saved by the editor, which serializes the live DOM
(spec 2.1, E10). See DEC-001.

### Rejected: dot and ring placed inside the slide element

Free scaling and clipping, but a child added to the slide changes `:last-child` and flex layouts of the templates
while presenting and lives in the slide that saves and exports read. A fixed overlay outside every slide is
chosen (DEC-004).

## 3. Architecture

```
 deck file (every presentation template)
   deck's own script (hand edited)        key table: ... F, Escape, and now
                                          (e.key === 'l' || e.key === 'L') && no Ctrl/Meta/Alt -> togglePointer()
   toolbar or fixed controls              #btn-present (existing)  #btn-pointer onclick="presentWithPointer()" (new)
   deck-pointer block (synced)            <style id="deck-pointer-style">  <script id="deck-pointer-script">
     window API: presentWithPointer() armPointer(on) togglePointer() setPointerAllowed(allowed)
     state: allowed (true), armed (false), on (false), last mouse point (null)
     fullscreenchange: entering -> on = armed && allowed, armed = false ; leaving -> pointer off
     pointer on: <html data-deck-pointer>, #deck-pointer-layer (fixed at the current slide's rect,
                 overflow hidden) holding #deck-pointer-dot and #deck-pointer-ring, one rAF loop
     pointermove (mouse) -> dot ; pointerdown (touch, pen) -> dot hidden ; click -> findBox -> ring

 editor page (static/)
   editor.html   #pointer-btn "Pointeur" right after #present-btn
   editor.js     presentDeck(withPointer): win.armPointer(true) then the existing fullscreen request path,
                 win.armPointer(false) on every fallback; relay: L -> win.togglePointer() unless edit mode;
                 #pointer-btn shown when presentation && !editMode && the framed deck has the API
   editor-edit.js syncPointerAllowed(): win.setPointerAllowed(!editMode), on toggle and on frame load
   editor-save.js stripPresentingState(clone) also removes #deck-pointer-layer and data-deck-pointer

 tools/sync_deck_pointer.py [--check]   source block -> every presentation template holding the markers
 tests/test_presentation_templates_fullscreen.py   pointer guard: three parts per template, failure lines
```

Bounded contexts (spec 4.5): deck presentation owns the block, the button, the key line and the whole pointer
state; the editor page owns the Pointeur control of its toolbar, the relay, the edit mode flag it pushes into the
deck, and the save strip. The deck never reads editor state; the editor only calls the four API functions, each
guarded by `typeof === 'function'` so a deck created before this version (Deck O) is untouched.

## 4. Data model

No persisted data. Runtime only, never in a file written by the editor (FR-NEW-010):

| Item | Where | Lifetime |
|---|---|---|
| `allowed`, `armed`, `on`, `lastPoint`, `ringBox` | closure of the deck block's IIFE | page lifetime; reset by a reload |
| `data-deck-pointer` attribute | `<html>` of the deck | while the pointer is on |
| `#deck-pointer-layer` with `#deck-pointer-dot`, `#deck-pointer-ring` | last children of `<body>` | created on pointer on, removed on pointer off |

## 5. Contracts and interfaces

### 5.1 Deck window API (block script, functions assigned to `window`)

| Function | Contract |
|---|---|
| `presentWithPointer()` | `armPointer(true)`, then `document.documentElement.requestFullscreen()` (webkit variant when absent); a rejected promise or a thrown error calls `armPointer(false)`. Same fallback nothing as `enterPresentation()` otherwise. |
| `armPointer(on)` | `armed = !!on && allowed`. |
| `togglePointer()` | returns without effect unless `document.fullscreenElement` and `allowed`; else turns the pointer on if off, off if on. |
| `setPointerAllowed(allowed)` | stores it; `false` also disarms and turns the pointer off. |

`fullscreenchange`: entering (`document.fullscreenElement` not null) sets the pointer to `armed`, then `armed =
false`; leaving turns it off. A reload starts with every value at its default (off), which is FR-NEW-003's reload
rule whatever the full screen state.

### 5.2 Per template hand edits (checked by the guard, DEC-016)

- Key table of the deck's own `keydown` handler, after the `F` line and under its existing focus exception:
  `if ((e.key === 'l' || e.key === 'L') && !e.ctrlKey && !e.metaKey && !e.altKey) togglePointer();`
- Shell decks (toolbar): `<button id="btn-pointer" onclick="presentWithPointer()" title="Présenter avec le pointeur (L)"
  aria-label="Présenter avec le pointeur (L)">Pointeur</button>` immediately after `#btn-present`, with the same
  `class` as `#btn-present` and inline `style="width:auto;padding:0 12px"` so the label fits an icon sized class.
- Stacked decks: DEC-015.

### 5.3 Block CSS (byte identical in every template)

Selectors only of these shapes: starting with `:fullscreen`, or an id or attribute selector, inside `@media print`
for printing. No class selector anywhere in the block (DEC-012).

```css
:fullscreen[data-deck-pointer] [data-type="slide"],
:fullscreen[data-deck-pointer] [data-type="slide"] * { cursor:none !important; }
#deck-pointer-layer { position:fixed; overflow:hidden; pointer-events:none; z-index:2147483647; margin:0; padding:0; }
#deck-pointer-dot, #deck-pointer-ring { position:absolute; pointer-events:none; box-sizing:border-box; margin:0; }
#deck-pointer-dot { border-radius:50%; background:#FA4D56; }   /* red #FA4D56; white #FFFFFF halo set inline as a box-shadow */
#deck-pointer-ring { border-style:solid; border-color:#DA1E28; background:transparent; }   /* red #DA1E28 */
@media print { #deck-pointer-layer { display:none !important; } }
```

Sizes are set inline by the script from the scale factor `s` (DEC-004): dot `width = height = 18 * s` (the red
disc, so its rect measures 18 slide pixels: E2E-001 expects 30 ± 1 at 1.6667, E2E-032 22.5 ± 1 at 1.25), halo
`box-shadow: 0 0 0 <2 * s>px #FFFFFF` outside the disc (a shadow does not change the rect); ring border width `3 * s`.

### 5.4 Editor (DEC-013, DEC-014)

- `editor.html`: `<button id="pointer-btn" type="button" title="Présenter avec le pointeur (L)" aria-label="Présenter
  avec le pointeur (L)" style="display:none">Pointeur</button>` immediately after `#present-btn`.
- `editor.js`: `presentBtn` click calls `presentDeck(false)`, `pointerBtn` click calls `presentDeck(true)`;
  `presentDeck` is today's present handler body plus the arming of 5.1. `updateSlideActionsVisibility()` sets
  `pointerBtn.style.display = (isPresentation && !editMode && deckCarriesPointer()) ? 'inline-flex' : 'none'`,
  with `deckCarriesPointer()` true when the framed window has `presentWithPointer`, `armPointer`, `togglePointer`
  and `setPointerAllowed` as functions. Relay branch, before `Escape`:
  ```js
  } else if ((e.key === 'l' || e.key === 'L') && !e.ctrlKey && !e.metaKey && !e.altKey && !editMode
             && typeof win.togglePointer === 'function') {
    e.preventDefault();
    win.togglePointer();
  ```
- `editor-edit.js`: `syncPointerAllowed()` calls `win.setPointerAllowed(!editMode)` when the function exists; called
  at the end of `applyEditMode()` and from `onFrameLoad()` (`editor.js:204`).
- `editor-save.js`: `stripPresentingState(root)` also removes `#deck-pointer-layer` from the clone and
  `data-deck-pointer` from its root.

### 5.5 Sync tool (`tools/sync_deck_pointer.py`)

```
python tools/sync_deck_pointer.py           # rewrite the block in every target
python tools/sync_deck_pointer.py --check   # report freshness per target, write nothing, exit 1 when stale
```

Source `templates/bootstrap/slides-empty.html`; block = from `<!-- deck-pointer:begin -->` to
`<!-- deck-pointer:end -->` inclusive. Targets: every `templates/**/*.html` whose opening `<html ...>` tag holds
`data-doc-type="presentation"`, that contains the begin marker, other than the source. Source without the block:
`SystemExit` naming the file. Output lines through `tools/freshness.py` `report_line`. Make targets:
`sync-deck-pointer` (writes), and `check-generated` gains `uv run python tools/sync_deck_pointer.py --check || rc=1`.
The EI bootstrap holds the block and is a target too; `gen_ei_bootstrap.py` copies it unchanged from the EI
reference, so both checks agree (order of a template story: `make sync-deck-pointer`, then `make bootstrap-ei`).

### 5.6 Guard (`tests/test_presentation_templates_fullscreen.py`, extended)

```python
POINTER_PARTS = (("pointer", "function togglePointer("),
                 ("Pointeur control", 'id="btn-pointer"'),
                 ("L key", "e.key === 'l' || e.key === 'L'"))
def missing_pointer_lines(name: str, html: str) -> list[str]   # f"{name}: missing {part}" per absent marker, in POINTER_PARTS order
```

`name` is the file stem (`roadmap-one-pager`). The L key marker must appear outside the deck-pointer block (the
block never contains it), so removing the block reports `missing pointer` only.

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `templates/bootstrap/slides-empty.html` | modify: deck-pointer block (source), `#btn-pointer`, L line | FR-NEW-001 to FR-NEW-004, FR-NEW-009, FR-NEW-014 | US-0102 |
| `templates/bootstrap/slides-empty.html` | modify: block gains the ring and box finding | FR-NEW-005 to FR-NEW-009, FR-NEW-013 | US-0103 |
| `tests/pointer_support.py` | create: Deck P, Deck O, module pages, measure scripts | test support | US-0102, US-0103, US-0104 |
| `tests/test_pointer_dot_e2e.py` | create: opened directly, dot, L, deck control | FR-NEW-001 to FR-NEW-004 | US-0102 |
| `tests/test_pointer_ring_e2e.py` | create: opened directly, ring, touch, reduced motion, print | FR-NEW-005 to FR-NEW-009, FR-NEW-013 | US-0103 |
| `tests/test_pointer_served_e2e.py` | create (US-0103), extend (US-0104): served tests | FR-NEW-005, FR-NEW-001, FR-NEW-002, FR-NEW-010 to FR-NEW-012 | US-0103, US-0104 |
| `src/mcp_htmleditor/static/editor.html` | modify: `#pointer-btn` | FR-NEW-002 | US-0104 |
| `src/mcp_htmleditor/static/editor.js` | modify: `presentDeck`, visibility, relay L | FR-NEW-001, FR-NEW-002, FR-NEW-011 | US-0104 |
| `src/mcp_htmleditor/static/editor-edit.js` | modify: `syncPointerAllowed` | FR-NEW-012 | US-0104 |
| `src/mcp_htmleditor/static/editor-save.js` | modify: strip pointer state | FR-NEW-010 | US-0104 |
| `tools/sync_deck_pointer.py` | create (5.5) | FR-NEW-014 | US-0105 |
| `Makefile` | modify: `sync-deck-pointer`, `check-generated` | FR-NEW-014 | US-0105 |
| `tests/test_sync_deck_pointer.py` | create: tool behavior on a `tmp_path` copy | FR-NEW-014 | US-0105 |
| `tests/test_presentation_templates_fullscreen.py` | modify: pointer guard (5.6), `PENDING_POINTER` | FR-NEW-014 | US-0105, emptied US-0106 to US-0109 |
| `templates/reference/slides/ibm-carbon.html`, `example-carbon-complete.html` | modify: button, L line, block | FR-NEW-014 | US-0106 |
| `templates/reference/slides/euro-information.html`, `example-ei-complete.html` | modify: same | FR-NEW-014 | US-0107 |
| `templates/bootstrap/slides-ei-empty.html` | regenerate (`make bootstrap-ei`) | FR-NEW-014 | US-0107 |
| `tests/test_pointer_templates_e2e.py` | create (US-0107: E2E-036), extend (US-0109: E2E-029, E2E-032) | FR-NEW-005, FR-NEW-013, FR-NEW-014 | US-0107, US-0109 |
| `templates/bootstrap/slides-medical-empty.html`, `reference/slides/medical.html`, `example-medical-complete.html` | modify: button, L line, block | FR-NEW-014 | US-0108 |
| `templates/reference/slides/presentation-standard.html`, `roadmap-one-pager.html` | modify: controls wrapper, button, L line, block | FR-NEW-002, FR-NEW-014 | US-0109 |
| `README.md` | modify: new `### Presenting` section with the sentence | NFR 7.6, E2E-034 | US-0110 |
| `skill/topics/slides-carbon.md` | modify: one sentence (7533 bytes today, budget 8000) | NFR 7.6, E2E-034 | US-0110 |
| `tests/test_skill_shipped.py` | modify: E2E-034 | FR-NEW-014 | US-0110 |
| `AGENTS.md`, `.agent_docs/html-conventions.md`, `.agent_docs/testing.md`, `.agent_docs/architecture.md`, `sdlc/constitution.md` | modify: pointer rule, sync target, test files, guard row | n/a (docs) | US-0110 |

Affected existing tests: all kept. `tests/test_export_golden.py` and its two fixtures are the PPTX baseline of
E2E-029 and are never regenerated; `tests/test_reference_decks_present_e2e.py` and `tests/test_fullscreen_e2e.py`
keep their assertions (FR-NEW-011 non regression); `tests/test_strip_idempotent.py` keeps proving the server's
cleaning is idempotent on templates holding the block; `tests/test_medical_template.py` keeps the medical CSS sync
(the block's `<style>` carries an `id`, so the `^<style>\n` anchor of `tools/sync_medical_css.py:31` never matches it).

Affected documentation: `README.md` (no presenting section exists today: `rg -n -i "present" README.md` finds only
the multi presentation section), `AGENTS.md`, `.agent_docs/*`, `skill/topics/slides-carbon.md`, `sdlc/constitution.md`.

## 7. Compatibility and risks

- R1, PPTX hashes (FR-NEW-013): any class selector in the block, or anything added inside a slide, would change the
  slide XML. Mitigation DEC-012; detection: the golden tests over all 11 templates (`pptx_slide_hashes.json` for ten,
  `example_carbon_complete_slide_hashes.json` for the eleventh), never regenerated.
- R2, saved runtime state (FR-NEW-010): the editor serializes the live framed DOM. The layer and the attribute exist
  only while the pointer is on, which edit mode forbids; the clone strip removes them anyway (DEC-014).
- R3, double toggle (E2E-003): an L typed in the deck never reaches the editor page's listener (separate documents,
  `editor.js:149`), and an L dispatched on the editor page never reaches the deck. Tests dispatch on the parent
  `document` (SPEC-0016 DEC-002), since headless Chromium keeps the focus in the iframe.
- R4, the fallback presentation (iframe element full screen): the deck's `document.fullscreenElement` stays null, so
  `togglePointer` does nothing and an armed pointer is disarmed by `presentDeck`'s fallback branch (DEC-013).
- R5, run time: the last closing run measured a 320.14 s test step at load 20 to 33 (`.agent_docs/testing.md`), with
  235 to 270 s on a quiet machine. The spec's browser tests get at most 40 s together (DEC-018), so a quiet run stays
  near 310 s; a loaded machine can pass 330 s, as before this spec.
- R6, guard order: the guard lands in US-0105 with a pending set naming the ten templates not yet carrying the
  pointer; each template story removes its files; US-0109 deletes the set. No story leaves `make check` red.
- R7, spec readings of FR-NEW-005 (gate note above): decided in DEC-008.
- Ordering: US-0102, US-0103, US-0104 on the Carbon starting point and the editor; US-0105 tool and guard; US-0106
  to US-0109 the other templates (snippet final before the first sync); US-0110 docs and converge.
- Rollback: `git revert` of a story commit; nothing persisted changes.
- Dependencies added or removed: none.

## 8. Security design

n/a (`Security: n/a`: the pointer reads and writes nothing, no new route, no server call).

## 9. Test strategy

Every acceptance test is functional e2e in real Chromium at 1600 × 900 unless stated, observed through
`tests/browser_wait.py` (`wait_until`, `wait_for_js`), never a fixed wait without `# pacing:`.

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| E2E-001, E2E-005, E2E-017, E2E-020, E2E-021, E2E-022, E2E-023, E2E-039 | functional e2e | Playwright, Deck P `file://`, module page | `tests/test_pointer_dot_e2e.py` | US-0102 |
| E2E-007, E2E-009, E2E-010, E2E-011, E2E-012, E2E-013, E2E-015, E2E-016, E2E-019, E2E-025, E2E-030, E2E-037 | functional e2e | Playwright, Deck P `file://`, module page | `tests/test_pointer_ring_e2e.py` | US-0103 |
| E2E-026 | functional e2e | Playwright context `has_touch=True`, `page.touchscreen.tap` | `tests/test_pointer_ring_e2e.py` | US-0103 |
| E2E-027 | functional e2e | Playwright context `reduced_motion="reduce"` | `tests/test_pointer_ring_e2e.py` | US-0103 |
| E2E-006, E2E-008, E2E-014, E2E-024 | functional e2e | Playwright, editor page, Deck P served | `tests/test_pointer_served_e2e.py` | US-0103 |
| E2E-002, E2E-003, E2E-004, E2E-018, E2E-028, E2E-031, E2E-035, E2E-038 | functional e2e | Playwright, editor page (E2E-031 also `file://`) | `tests/test_pointer_served_e2e.py` | US-0104 |
| E2E-033 | integration | guard functions on a `tmp_path` copy of `templates/` | `tests/test_presentation_templates_fullscreen.py` | US-0105 |
| E2E-036 | functional e2e | Playwright, editor page, deck from the `ei` starting point | `tests/test_pointer_templates_e2e.py` | US-0107 |
| E2E-029 | functional e2e plus integration | one served page over the 11 templates (file switched with `start_http_server`), then in process `to_pptx` hashes against the golden fixtures | `tests/test_pointer_templates_e2e.py` | US-0109 |
| E2E-032 | functional e2e | Playwright, Deck S `file://` and the three starting points served | `tests/test_pointer_templates_e2e.py` | US-0109 |
| E2E-034 | functional | README read, child process `mcp-htmleditor skill --type slides-carbon` | `tests/test_skill_shipped.py` | US-0110 |

Test data: generated. Deck P is built by `tests/pointer_support.py` from `templates/bootstrap/slides-empty.html`
(spec 9.0 contents); Deck O is Deck P with the deck-pointer block, the `#btn-pointer` element and the L line removed
(the three guard markers, DEC-016); Deck S is a copy of `presentation-standard.html`; the `ei` deck of E2E-036 is
built from `templates/bootstrap/slides-ei-empty.html` plus one content slide. Nothing user provided.

## 10. Decisions log

- **DEC-001:** The pointer is carried by each template, as one block synced from
  `templates/bootstrap/slides-empty.html` by `tools/sync_deck_pointer.py` (5.5) and checked by `make check-generated`;
  per template parts (button, L line) are hand edits checked by the guard. **Obliged by:** SPEC-0017/FR-NEW-014,
  FR-NEW-001 to FR-NEW-009 (same behavior opened directly and served). **Rationale:** decks must stay single file and
  work from `file://` (spec 3.3); one source avoids 11 hand copies. **Alternatives considered:** hand duplication with
  a byte equality test; `<script src>`; server injection; inserting the pointer at `new` time (misses the reference
  decks and decks opened directly). **Source:** existing pattern `tools/sync_medical_css.py`, `Makefile:259`.
  **Evidence:** `tools/gen_ei_bootstrap.py:1` to `:16`, spec 14.3 I2.
- **DEC-002:** Block shape: `<!-- deck-pointer:begin -->`, `<style id="deck-pointer-style">` (5.3),
  `<script id="deck-pointer-script">` holding one IIFE that assigns the four functions of 5.1 to `window`,
  `<!-- deck-pointer:end -->`, placed immediately before `</body>`. **Obliged by:** FR-NEW-001 to FR-NEW-009.
  **Rationale:** an IIFE cannot collide with each deck's own globals (`current`, `render`); `window` functions are
  what the editor already calls (`win.navigate`, `editor.js:156`); ids on the tags keep the medical CSS sync anchor
  off the block. **Alternatives considered:** top level `function` declarations (collision risk). **Source:** design.
  **Evidence:** `tools/sync_medical_css.py:31`.
- **DEC-003:** The L key is one line in each deck's own `keydown` table (5.2), under its existing focus exception, and
  `togglePointer()` itself checks full screen and `allowed`. **Obliged by:** FR-NEW-001, FR-NEW-012, FR-NEW-014.
  **Rationale:** reuses the focus exception (`slides-empty.html:397`); keeps the three guard parts independent so the
  failure lines of FR-NEW-014 are exact. **Alternatives considered:** a second `keydown` listener inside the block
  (then removing the block also removes the L key, two failure lines for one loss). **Source:** design.
  **Evidence:** `templates/bootstrap/slides-empty.html:396` to `:405`.
- **DEC-004:** Runtime overlay: when the pointer turns on, the block appends `#deck-pointer-layer` to `<body>` and sets
  `data-deck-pointer` on `<html>`; one `requestAnimationFrame` loop runs while on. Each frame it finds the current
  slide (`[data-type="slide"].active, [data-type="slide"][data-fs-current]`, else the first slide), places the layer at
  the slide's `getBoundingClientRect()`, computes `s = rect.width / slide.offsetWidth`, redraws the ring around its box
  and, when the current slide element differs from the previous frame's, removes the ring and redraws the dot at the
  last mouse point. The dot is placed at `lastPoint - layer origin - 9 * s`, shown only while `lastPoint` lies inside
  the slide rect. Pointer off removes the layer, the attribute and the loop. **Obliged by:** FR-NEW-004, FR-NEW-005
  (scaling, moving box, clipping), FR-NEW-007, FR-NEW-009. **Rationale:** one generic rule for both deck families and
  every scale (960 or 1280 slide pixels, spec glossary); clipping by `overflow:hidden` on a box equal to the slide;
  slide change detection without hooking 11 different `navigate` functions. **Alternatives considered:** elements
  inside the slide (section 2); a MutationObserver on `class` (misses the stacked marker semantics, more code).
  **Source:** design, spec 14.3 I11. **Evidence:** `templates/bootstrap/slides-empty.html:254` to `:258`.
- **DEC-005:** The system cursor is hidden by the block's first rule (5.3), active only while `data-deck-pointer` is on
  `<html>` and the document is full screen; the black margins keep the default cursor. **Obliged by:** FR-NEW-004.
  **Rationale:** no inline style is ever written on a slide (BL-0034: the clone strip rewrites a `style` holding
  `cursor`). **Alternatives considered:** inline `cursor:none` on the slide. **Source:** spec 14.3 I4.
  **Evidence:** `src/mcp_htmleditor/static/editor-save.js:26` to `:29`.
- **DEC-006:** State machine of 5.1: `allowed` (default true), `armed`, `on`; `fullscreenchange` entering sets
  `on = armed`, then `armed = false`; leaving sets `on = false`. `presentWithPointer()` arms then requests full screen
  and disarms on rejection or error. **Obliged by:** FR-NEW-002, FR-NEW-003, FR-NEW-009, FR-NEW-012. **Rationale:** the
  F key, the deck's present control and the editor's present control never arm, so they start off; a refused full
  screen leaves nothing armed for a later F (E2E-039). **Alternatives considered:** turning the pointer on right after
  `requestFullscreen()` resolves (races with `fullscreenchange`, and the editor's request comes from the parent page).
  **Source:** design. **Evidence:** `src/mcp_htmleditor/static/editor.js:114` to `:135`.
- **DEC-007:** Inputs. `pointermove` with `pointerType === 'mouse'` records `lastPoint` (always, pointer on or off,
  from page load) and moves the dot. `pointerdown` with another `pointerType` hides the dot. `mouseout` on `document`
  with `relatedTarget === null` hides the dot. `click` on `document` (bubble phase): ignored unless the pointer is on
  and the target is inside the current slide; ignored when `target.closest('a[href], button, input, select,
  textarea')` is inside the slide (FR-NEW-008: no `preventDefault`, ring unchanged); otherwise `findBox(target)`
  (DEC-008) and the one ring rule: same box removes the ring, another box moves it, no box removes it. A tap produces
  a `click`, so it rings like a click. **Obliged by:** FR-NEW-004, FR-NEW-005, FR-NEW-006, FR-NEW-008.
  **Rationale:** pointer events tell mouse from touch and pen; compatibility mouse events after a tap are not pointer
  events, so they never show the dot. **Alternatives considered:** `mousemove` (cannot tell a tap's compatibility
  events from a mouse). **Source:** spec FR-NEW-004 business rules. **Evidence:** n/a.
- **DEC-008:** `findBox(target)` implements FR-NEW-005 with these readings. Notation: `slide` the current slide,
  `area(e)` the product of `getBoundingClientRect()` width and height, `big(e)` is `area(e) >= 0.85 * area(slide)`,
  `layout(e)` is `e.matches(LAYOUT_AREAS)` (DEC-009), `inline(e)` is a computed `display` starting with `inline`
  for an element other than `img`, `svg`, `video`, `canvas`.
  1. start = `target`; if it has an ancestor or self `svg` inside the slide, start = the outermost such `svg`.
  2. if start has an ancestor or self `table` inside the slide, return the nearest one.
  3. walk e from start up to, excluding, `slide`: skip e when `layout(e)`, `inline(e)` or `big(e)`; return e when it is
     `candidate(e)` and fewer than two of its element children are `candidate`. `candidate(e)`: not `layout`, not
     `inline`, not `big`, and (computed `background-image` is not `none`, or `background-color` has alpha above 0 and
     differs from the slide's computed `background-color`, or `box-shadow` is not `none`, or each of the four sides
     has `border-*-style` other than `none` and `hidden`, width above 0 and colour alpha above 0).
  4. walk e again from start up to, excluding, `slide`: skip `layout`, `inline` and `big` elements; return the first e
     that is `img` or `svg`, or has a child text node with non whitespace text.
  5. return null (the slide itself is never a box).
  Readings decided: rule 4 never returns a layout area, and the page number is part of its footer area (E2E-036 forces
  it: the EI page number is a flex item, so a block holding text, and must not be ringed); the container test counts
  children by `candidate`, not recursively (no fixture differs); "set inside a line" is every inline level display,
  so an `inline-block` pill is not a box, replaced elements excepted so rule 4's image applies. **Obliged by:**
  FR-NEW-005, FR-NEW-006. **Rationale:** each reading is the one an acceptance test forces, or the literal text where
  none differs; recorded here so the implementer does not re-decide (spec leak, see the gate note). **Alternatives
  considered:** layout areas excluded from rule 3 only (rings the EI page number, fails E2E-036); recursive container
  test (same results on every fixture, more code); `display: inline` only (rings pills). **Source:** design, spec
  FR-NEW-005, E2E-007, E2E-036. **Evidence:** spec 14.3 I12.
- **DEC-009:** `LAYOUT_AREAS` is one selector in the block, the union over the 11 templates (measured by listing each
  slide's children): header `.slide-header, .slide-title-area, .med-head`; body `.slide-body`; footer and page number
  `.slide-footer, .slide-footer-right, .slide-foot, .slide-foot-page, .med-foot, .med-cover-foot`; top band
  `.med-band`; inner frame `.slide-inner`. Class names are unique to their charter, so the union is safe in every file.
  **Obliged by:** FR-NEW-005 (layout areas "in every template"). **Rationale:** keeps the block byte identical (DEC-001).
  **Alternatives considered:** a per template constant (breaks the shared block). **Source:** design.
  **Evidence:** templates listed in spec E6b; Carbon `slide-empty` children `.slide-header`, `.slide-body`,
  `.slide-footer`; EI `.slide-inner`, `.slide-foot`; medical `.med-band`, `.med-head`, `.med-foot`; roadmap
  `.slide-title-area`; presentation-standard `.slide-header`.
- **DEC-010:** Ring geometry: with the box rect `b` and layer origin `o`, the ring is at `left = b.left - o.left - 6 * s`,
  `top = b.top - o.top - 6 * s`, size `b.width + 12 * s` by `b.height + 12 * s`, `border-width = 3 * s`; radius: each
  corner of the box's computed `border-*-radius`, a percentage kept as is (a circle stays a circle), a length grown by
  `6 * s` after scaling by `s`. Appearance: `ring.animate([{opacity: 0, scale: 0.92}, {opacity: 1, scale: 1}],
  {duration: 150, easing: 'ease-out'})` unless `matchMedia('(prefers-reduced-motion: reduce)').matches`, in which case
  no animation is created. **Obliged by:** FR-NEW-005, NFR 7.4. **Rationale:** the layer is unscaled, so sizes are
  multiplied by `s`; the Web Animations API needs no `@keyframes` rule in the block. **Alternatives considered:** a
  CSS `@keyframes` (an at rule in every template's CSS). **Source:** design. **Evidence:** n/a.
- **DEC-011:** Printing: `@media print { #deck-pointer-layer { display:none !important; } }` in the block; the
  `data-deck-pointer` attribute only hides the cursor. **Obliged by:** FR-NEW-013. **Rationale:** the layer is the only
  visible pointer element. **Alternatives considered:** a `beforeprint` handler (needs a matching `afterprint`
  restore). **Source:** design. **Evidence:** n/a.
- **DEC-012:** PPTX invariance: the block holds no class selector (every rule targets an id, an attribute or starts
  with `:fullscreen`), so `_selector_target` returns `None` for each (its last compound never starts with `.`); the
  layer and the dot and ring live outside every slide and only at run time; the button, the key line and the block
  lie outside every slide and are `<button>`, `<script>` and `<style>`. The baseline of E2E-029 is the existing golden
  data, recorded before this spec: `tests/testdata/pptx_slide_hashes.json` (ten templates) and
  `tests/testdata/example_carbon_complete_slide_hashes.json`. Equal slide XML implies the same slides, shapes,
  positions, sizes and texts. **Obliged by:** FR-NEW-013. **Rationale:** invariance by construction, checked by the
  existing gate. **Alternatives considered:** a new shape level baseline (weaker than byte equality, new fixture).
  **Source:** existing code `src/mcp_htmleditor/export/pptx_style.py:558` to `:596`, SPEC-0016 DEC-007.
  **Evidence:** `tests/test_export_golden.py:28` to `:41`.
- **DEC-013:** Editor (5.4): `#pointer-btn` after `#present-btn`; `presentDeck(withPointer)` shares today's present
  path, arming before the request and disarming in each fallback branch; visibility rule; relay branch for L that
  skips edit mode and modifiers; `syncPointerAllowed()` on edit toggle and frame load. **Obliged by:** FR-NEW-001,
  FR-NEW-002, FR-NEW-011, FR-NEW-012. **Rationale:** the deck decides presenting; the editor only pushes the edit
  mode and forwards L like the other keys; a deck without the API (Deck O) shows no control and ignores L.
  **Alternatives considered:** the editor injecting a capture listener that stops L in edit mode (a deck clicked
  Pointeur button in edit mode would still present with the pointer). **Source:** existing code
  `src/mcp_htmleditor/static/editor.js:114` to `:171`, `:261`. **Evidence:** spec 14.3 I1, I3, I10.
- **DEC-014:** Save: `stripPresentingState(root)` (`editor-save.js:63`) also removes `#deck-pointer-layer` from the
  clone and `data-deck-pointer` from the clone's root; the server strip is unchanged. **Obliged by:** FR-NEW-010.
  **Rationale:** the editor page is the only writer of browser state; the elements cannot exist in edit mode, the strip
  covers a save called while presenting (as SPEC-0016 tests do). **Alternatives considered:** adding the id to
  `_EDITOR_ARTIFACTS` in `http_server.py` too (no path writes it; one more file). **Source:** existing code.
  **Evidence:** `src/mcp_htmleditor/static/editor-save.js:26` to `:34`, `:63`.
- **DEC-015:** Stacked decks: `#btn-present` moves into a new first child of `<body>`,
  `<div id="deck-controls" style="position:fixed;top:16px;right:16px;z-index:10;display:flex;gap:8px;align-items:flex-start">`,
  holding `#btn-pointer` then `#btn-present`; both buttons carry the same inline look (none today beyond the browser
  default) and `#btn-present` loses only its positioning declarations. The deck's own CSS gains
  `:fullscreen #deck-controls { display:none; }` and keeps `:fullscreen #btn-present { display:none; }`.
  **Obliged by:** FR-NEW-002 (left of `Présenter`, 8 page pixels apart, tops aligned, hidden while presenting).
  **Rationale:** a flex row gives the gap and the alignment whatever the label widths. **Alternatives considered:**
  `right: calc(...)` from a measured width (fragile). **Source:** design. **Evidence:**
  `templates/reference/slides/presentation-standard.html:195`, `:199`.
- **DEC-016:** Guard (5.6): three markers per discovered presentation file, one failure line per missing part,
  `f"{stem}: missing {part}"`. US-0105 adds `PENDING_POINTER`, the set of stems not yet carrying the pointer (ten),
  skipped by the pointer check; each template story removes its stems; US-0109 deletes the set and the skip. E2E-033
  runs `missing_pointer_lines` on a `tmp_path` copy of `templates/` with `roadmap-one-pager.html` edited three ways
  (deck-pointer block removed; `#btn-pointer` element removed; L line removed). **Obliged by:** FR-NEW-014.
  **Rationale:** the guard never makes `make check` red mid spec; the failure lines are the spec's exact text.
  **Alternatives considered:** landing the guard last (E2E-033 then shares a story with every template).
  **Source:** existing guard `tests/test_presentation_templates_fullscreen.py:13`, `:51`. **Evidence:** BL-0036
  (substring markers, kept).
- **DEC-017:** Test architecture, few browser sessions. `tests/pointer_support.py` holds Deck P and Deck O builders,
  `POINTER_STATE` (one JS function returning, for a document: pointer on, dot rect and diameter or null, ring rect and
  border width or null, ring count, current slide index, `fullscreenElement` tag, the slide's computed `cursor`), and
  module scoped page fixtures in the SPEC-0015 style (`width_support.width_page`): `pointer_file_page` (1600 × 900,
  Deck P `file://` reloaded per test with `page.goto`), `pointer_touch_page` (`has_touch=True`),
  `pointer_reduced_page` (`reduced_motion="reduce"`), `pointer_served_page`. Served tests start one editor server per
  test through `serve_deck`; the template sweep keeps one server and switches the file with a second
  `start_http_server(path)` call (idempotent switch, `http_server.py:1051`). Relay tests dispatch keys on the parent
  `document` (SPEC-0016 DEC-002). The mouse leaving the window is the event Chromium sends for it, dispatched on the
  element under the mouse: `mouseout` with `relatedTarget: null`. Pixels (E2E-023, E2E-037) come from
  `page.screenshot(clip=...)` read with Pillow. Printing (E2E-030, E2E-039) is `page.pdf()`; two prints compare equal
  after removing `/CreationDate (...)` and `/ModDate (...)`; each test first prints the unchanged page twice and
  asserts those two equal, so a non deterministic print fails loudly instead of passing. "Without a further move"
  (E2E-001) means no `page.mouse` call between the L press and the read. E2E-028's 3 seconds are 3 status polls
  (`wait_polls`, `tests/width_support.py:277`), not a fixed wait. E2E-032's decks created from a starting point
  (one slide each) get a second slide in their copy so Right has a next slide. E2E-037's left side check runs at
  1800 × 900, where the slide has black side bands (at 1600 × 900 the slide fills the width). **Obliged by:** n/a (no code impact): test
  harness for FR-NEW-001 to FR-NEW-014 within DEC-018. **Rationale:** one page load serves several assertions, as
  SPEC-0015 and SPEC-0016 did. **Alternatives considered:** one test per E2E with a fresh page (about 39 page loads).
  **Source:** user instruction (few sessions), spec 14.3 I8. **Evidence:** `tests/width_support.py:160`.
- **DEC-018:** Run time budget: the SPEC-0017 browser tests take at most 40 s in total (`test_pointer_dot_e2e.py` about
  6 s, `test_pointer_ring_e2e.py` about 10 s, `test_pointer_served_e2e.py` about 12 s, `test_pointer_templates_e2e.py`
  about 12 s); each story reports `make test ARGS='-k pointer --durations=0'`; the closing story proves the
  `make check` test step stays at most 330 s (SPEC-0014/BT-022), re running once above 330 s at a load above 30
  before trimming. **Obliged by:** n/a (no code impact): keeps SPEC-0014/BT-022 true. **Rationale:** quiet machine
  235 to 270 s today plus 40 s stays under 330 s. **Alternatives considered:** marking pointer tests slow (leaves
  FR-NEW-014 out of the gate). **Source:** user instruction, SPEC-0016 DEC-014. **Evidence:** `.agent_docs/testing.md:225`.
- **DEC-019:** E2E-018 compares bytes against the file as the editor saves it before any pointer use (SPEC-0015
  pattern): edit mode on, `saveContent()`, baseline read, edit mode off, then the pointer session, Escape, edit mode
  on, `l` typed at the end of the paragraph, save; the saved file equals the baseline with exactly the paragraph's
  serialized markup replaced once by its new serialized markup (read from the live DOM after typing), and holds none
  of `deck-pointer-layer`, `data-deck-pointer`, `cursor:none`. **Obliged by:** FR-NEW-010. **Rationale:** a whole file
  save reformats the bootstrap (indentation, attribute order), so "before" is the editor's own serialization.
  **Alternatives considered:** comparing to the fixture text (fails for reasons unrelated to the pointer).
  **Source:** existing test `tests/test_width_drag_e2e.py:139` to `:159`. **Evidence:** same.
- **DEC-020:** Documentation: `README.md` gains a `### Presenting` section (presenting, F, Escape, keys, and the
  pointer sentence of NFR 7.6); `skill/topics/slides-carbon.md` gains one French sentence of at most 300 bytes (467
  bytes free under the 8000 byte topic budget); the sentence names L, `Pointeur`, the click that rings a box, the
  pointer starting off, and that nothing of it reaches the file. **Obliged by:** NFR 7.6, FR-NEW-014 (E2E-034).
  **Rationale:** slides-carbon is the slides guidance topic of the Carbon starting point; no other topic needs a
  line. **Alternatives considered:** a line in `create` (13 bytes free). **Source:** `skill_content.py:47`.
  **Evidence:** `wc -c skill/topics/slides-carbon.md` gives 7533.
- **DEC-021:** Slicing: nine stories. US-0102 dot, L and the deck's control on the Carbon starting point (`min_tier` 1:
  full screen arming, scale geometry, PPTX invariance of the block); US-0103 ring and box rules (`min_tier` 1: the
  FR-NEW-005 readings of DEC-008); US-0104 editor control, relay, edit mode and save (`min_tier` 1: focus pitfall of
  relay tests, save byte identity); US-0105 sync tool and guard (`min_tier` 2); US-0106 Carbon reference decks,
  US-0107 EI decks, US-0108 medical decks (`min_tier` 2, mechanical); US-0109 stacked decks, every template
  (`min_tier` 1: controls placement and scale 1.25); US-0110 documentation and converge (closing, `min_tier` 2).
  **Obliged by:** n/a (no code impact): partition; every requirement is covered in section 11. **Rationale:** files
  touched is the binding budget; behavior first on one template, then the editor, then the other templates by
  family. **Alternatives considered:** one story for the ten other templates (14 files). **Source:** design, user
  instruction.

## 11. Stories

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0102 | pointer dot, L key and the deck's Pointeur control | P1 | FR-NEW-001 (partial), FR-NEW-002 (partial), FR-NEW-003, FR-NEW-004, FR-NEW-009 (partial), FR-NEW-013 (partial), FR-NEW-014 (partial) | main | 1 | no |
| US-0103 | ring and the box choice rules | P1 | FR-NEW-005, FR-NEW-006, FR-NEW-007, FR-NEW-008, FR-NEW-009, FR-NEW-012 (partial), FR-NEW-013 (partial) | US-0102 | 1 | no |
| US-0104 | editor Pointeur control, relay, edit mode and save | P1 | FR-NEW-001, FR-NEW-002 (partial), FR-NEW-003, FR-NEW-010, FR-NEW-011, FR-NEW-012 | US-0103 | 1 | no |
| US-0105 | pointer sync tool and template guard | P2 | FR-NEW-014 (partial) | US-0102 | 2 | no |
| US-0106 | pointer in the Carbon reference decks | P2 | FR-NEW-014 (partial), FR-NEW-013 (partial) | US-0103, US-0105 | 2 | no |
| US-0107 | pointer in the EI decks | P2 | FR-NEW-014 (partial), FR-NEW-005 (partial), FR-NEW-013 (partial) | US-0106 | 2 | no |
| US-0108 | pointer in the medical decks | P2 | FR-NEW-014 (partial), FR-NEW-013 (partial) | US-0107 | 2 | no |
| US-0109 | stacked decks and every template | P2 | FR-NEW-002, FR-NEW-004, FR-NEW-007, FR-NEW-013, FR-NEW-014 | US-0104, US-0108 | 1 | no |
| US-0110 | pointer documentation and converge | P3 | FR-NEW-014 | US-0109 | 2 | yes |
