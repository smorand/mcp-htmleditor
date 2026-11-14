# HTML conventions

The full authoring rules live in the skill (`mcp-htmleditor skill`, sources in `skill/`). This file keeps the
invariants the Python side depends on: break one of them and an export or the editor silently degrades.

## Document level

| Attribute | Effect |
|-----------|--------|
| `data-doc-type="presentation"` on `<html>` | Slide navigation active |
| `data-doc-type="document"` | Word like mode, the block picker appears in edit mode |
| `data-doc-template="perso"` / `"ei"` on the document `<article>` | Selects the charter, for the HTML rendering and for the DOCX export |
| `data-editable="text"` | Marks an editable text element |

## Slides

* `data-type="slide"` requires a unique `data-id` and a `data-title`; `article.slide` is the legacy fallback.
* EI slide footer markup is `.slide-foot-logo > .logo-disc > img`. The template only sizes
  `.slide-foot-logo .logo-disc img` (16px): without `.logo-disc` the chevrons render at 41x37 over the blue ring.
* Slide counters: eyebrow `Catégorie · Slide 0N / TT` in every charter, plus `.slide-footer-right` ("Slide N / TT",
  Carbon) or `.slide-foot-page` ("N", EI and medical); `renumberSlides()` in `editor-slides.js` rewrites only those.
* `<html data-asset-chevrons="data:image/png;base64,...">` in the EI bootstrap is the fallback source for
  `{{CHEVRONS}}` in inserted slides (`resolveTemplateAssets`), needed because a fresh file has no
  `.slide-foot-logo img` to copy from. Same pattern is available for `data-asset-cover`, `-cm`, `-cic`, `-ei`.
* Slide layouts may use `{{N}}` / `{{TT}}`: not substituted at insertion, `renumberSlides()` resolves them next pass.

### Medical charter, two invariants (2026-08-21)

* **Explicit width class on every child of a flex row.** `medical` states its side by side layouts with `w-25` to
  `w-70` (`flex:0 0 X%`) on each child of `.med-strip`, `.med-split`, `.med-cols`, `.med-compare`, `.med-steps`,
  `.med-stats`, `.med-timeline`, `.med-section-figs`. `pptx_flow.py` only splits a `display:flex` row into column
  regions when at least one child declares a width, so a bare `flex:1` everywhere exports as a cropped vertical
  stack. Same reason `.med-grid` is a vertical flex container of `.med-strip` rows, never a `display:grid` (the
  exporter does not read `grid-template-columns`). Authoring rules: `skill/topics/medical.md`.
* **CSS source direction is the opposite of EI.** For `ei` the reference deck is the source and `make bootstrap-ei`
  generates the bootstrap. For `medical`, `templates/bootstrap/slides-medical-empty.html` is the source and
  `make sync-medical-css` copies its `<style>` block into `reference/slides/medical.html` and
  `reference/slides/example-medical-complete.html` (both standalone); a reference `<style>` edited by hand diverges.
* **Breathe** shares the `med-` vocabulary with its own charter: `.agent_docs/breathe.md` (SPEC-0023).

## Fullscreen presentation mode (mandatory on every slide template)

Every presentation template (bootstrap or reference, current or future, any `new <key>`) ships the same three
blocks, otherwise the "Présenter" button opens a fullscreen with no scaling, or no button at all:

1. **CSS** (in the document `<style>`): `:fullscreen` rules hide `.shell-header`, `.toolbar`, `.nav-arrow`,
   `.status-bar` (`display:none !important`), paint `.stage` and `body` `#000`, set `.slide-frame` `padding:0` and
   give `.slide` `scale: var(--fs-scale, 1)` with `transform-origin: center center` (no border, no shadow). A
   selector absent from a template's shell (EI has no `.shell-header`) is omitted from that rule only.
2. **Toolbar button** `#btn-present` (`onclick="enterPresentation()"`), after the last `toolbar-sep`.
3. **JS** in the navigation `<script>`: `updateFullscreenScale()` at the end of `render()`, `fullscreenchange` /
   `resize` listeners calling it, `enterPresentation()` / `exitPresentation()`, `f`/`F` and `Escape` in `keydown`.

`--fs-scale` is a uniform `transform: scale()` from the slide's natural `getBoundingClientRect()` vs. the viewport
(PowerPoint style zoom, not CSS stretch); without it the slide keeps its native px size, fonts tiny. Reference
implementation: `templates/bootstrap/slides-empty.html` (Carbon) and `templates/bootstrap/slides-ei-empty.html`
(EI), both greppable with `:fullscreen`. A new slide template copies the block verbatim and adapts only the
selector list; verify with `grep -c fullscreen <file>` (> 0) and a headless screenshot showing `#btn-present`. A
template (or an old file) without `:fullscreen` is a bug to patch, not a variant.

**Stacked variant (SPEC-0016):** a deck of stacked `section[data-type="slide"]` in the body
(`presentation-standard.html`, `roadmap-one-pager.html`) has no `.stage`. Its CSS shows only the slide carrying
`data-fs-current`, which exists only while presenting (`enterPresentation()` only requests fullscreen; the deck's
`fullscreenchange` handler calls `render()`, which sets the marker and `--fs-scale` on entering and removes both on
leaving, so printing and PPTX see every slide). Save rule (US-0101): an editor save while presenting never writes
`data-fs-current` nor `--fs-scale`: `stripPresentingState()` in `editor-save.js` removes them from the save's
detached clone (as text on <html>'s style, other declarations byte-exact; an emptied `style` is dropped), never
from the live document. `#btn-present` sits outside every slide, and every selector starts with `:fullscreen` so
the PPTX resolver ignores them. Editor relay of the keys: `architecture.md` § Fullscreen presentation mode.
`tests/test_presentation_templates_fullscreen.py` is the guard for all of the above.

## Speaker notes and presenter block (SPEC-0022, 2026-05)

* **Notes:** `<aside data-role="speaker-notes">` as a direct child of the slide, plain text, newlines kept. Hidden by
  `[data-role="speaker-notes"]{display:none !important}` in the deck block: an attribute selector, never a class, because the
  PPTX resolver only reads class rules. The PPTX exporter skips the aside in the flow (`NOTES_ROLE`, `_is_notes` in
  `export/pptx_model.py`) and writes its text to `slide.notes_slide` (`_write_notes` in `to_pptx.py`); a whitespace only
  aside or no aside means no notes slide; a nested aside is not a note but is never exported as a shape either.
  `deck/` services (outline, get-slide, lint, patch `replace_slide`) keep the aside untouched (`tests/test_pptx_speaker_notes.py`).
* **deck-presenter block:** second synced block in `templates/bootstrap/slides-empty.html`, markers
  `<!-- deck-presenter:begin -->` / `<!-- deck-presenter:end -->`. `tools/sync_deck_pointer.py` copies both blocks and
  `make check-generated` checks both. It defines `togglePresenter`, `openPresenter`, `closePresenter`, `isPresenterOpen` and owns the
  key handler for F P S E: the per template `f` line is gone, the `L` line stays, `P` calls `togglePointer()`. In a
  `deck-preview` window it installs nothing.
* **Help overlay** (`?`, 2026-11-14): the block toggles `#deck-help` (lazy, id CSS rules only since the PPTX exporter reads class rules,
  hidden in print, Esc or `?` closes); framed it posts `deck-key` `?` and shows nothing. Keep `HELP_ROWS` in step with the keys.
* **Messages** (`postMessage`, target `*`, sender checked by `event.source`): deck to presenter `deck-state`
  `{index,total,titles,notes}`; presenter to deck `deck-cmd` `next|prev|goto|close`; framed deck to editor shell `deck-key`
  `{key:'e'}`; preview iframes (`srcdoc`, name `deck-preview`) follow `preview-goto`.

## Presentation pointer (SPEC-0017)

Every presentation template carries the pointer: L (or the Pointeur control, fullscreen with the pointer armed) turns
the mouse into a red dot while presenting, a click rings the box under it; off at every start, never in the file.

* **One source, eleven copies.** The block lives in `templates/bootstrap/slides-empty.html` between
  `<!-- deck-pointer:begin -->` and `<!-- deck-pointer:end -->`; `make sync-deck-pointer`
  (`tools/sync_deck_pointer.py`) copies it into the 10 other presentation templates, `--check` runs inside
  `make check-generated`. Never edit a copy. A template without the begin marker is left alone.
* **Guard** `tests/test_presentation_templates_fullscreen.py`, one line per missing part: `<stem>: missing pointer`
  (`window.togglePointer = function`), `<stem>: missing Pointeur control` (`id="btn-pointer"`),
  `<stem>: missing L key` (`e.key === 'l' || e.key === 'L'`).
* **Not a box:** `LAYOUT_AREAS` (in the block) lists the layout classes of every template (`.slide-header`,
  `.slide-body`, `.med-head`, `.slide-footer`, `.slide-inner`...); a new template's area classes go there or the
  ring surrounds the whole area. The ring rules (inside a tile or table, else headline or paragraph) are FR-NEW-005.
  A headline, paragraph or list item whose text sits only in inline descendants (`<h1><strong>Cover</strong></h1>`,
  a span, an inline-block pill) is the box (`holdsText`); the inline element never is.
* **L in a field:** each deck's own key table returns first when `document.activeElement` is an input, textarea,
  select or contenteditable (not the shared block); a deck written by hand must keep that line.
* **Fullscreenchange race:** entering fullscreen never turns the pointer off (the event arrives a frame after
  `fullscreenElement`; an L typed between must stay); leaving does. `armed` (Pointeur control) is consumed by it.
* **Stacked decks:** `#btn-pointer` and `#btn-present` sit in `#deck-controls` (DEC-015), whose inline `display:flex`
  needs `:fullscreen #deck-controls { display:none !important; }` (DEC-015 says `display:none`; needs `!important`).
* **Editor side** (`#pointer-btn`, `deckCarriesPointer()`, L relay, `setPointerAllowed(!editMode)`, the save strip of
  `#deck-pointer-layer` and `data-deck-pointer`): `architecture.md` § Presentation pointer.

## Documents

* Headings are semantic `<h1>` to `<h5>` (classes `doc-title`, `doc-subtitle`, `doc-h1` to `doc-h5`): Word Headings.
* Figures use `<figure>` plus `<figcaption>` (CaptionedFigure plus ImageCaption). PNG only: pandoc cannot size an
  SVG and old Word does not display it.
* Tables need a `<colgroup>` with `style="width:X%"` on each `<col>` for the DOCX widths; `data-col-width` alone is
  ignored. Templates carry a `@media print` block (`@page` margins, no shadow, no break in figures or rows, `thead`).
* The Word `Title` style comes from the document metadata, so the exporter lifts `.doc-title` / `.doc-subtitle` out
  of the body: a template must not duplicate the title by hand. Letterhead blocks (`.ei-doc-head`, `.ei-doc-foot`)
  become a real repeated Word header and footer for the charters that declare one (`export/docx_header_footer.py`).

## data-type values understood by the exporters

| `data-type` | Meaning |
|-------------|---------|
| `slide` | Presentation slide section |
| `gantt` / `gantt-task` | Gantt chart container / one task bar |
| `arch-diagram` / `arch-node` | Architecture diagram container / node |
| `arch-row` / `arch-lane` | Declarative layout input, consumed by `arch_layout.py`; inert to every exporter (no `data-type` branch matches them, `div` is not in `SKIP_TAGS`, so the recursive `find_all(True)` walk skips them) |
| `annotation` / `annotated-image` | Image callout / image plus annotations |
| `table` | HTML table |
| `document` | Word like document article |

## Declarative arch-diagram layout (`arch_layout.py`)

A diagram with at least one `arch-row` child is declarative (rows, nodes, edges, optional lanes; the LLM never
writes `data-x`/`data-y`); `mcp-htmleditor arch-layout` / the `layout_arch_diagram` MCP tool write the percentages.
A diagram with no `arch-row` is legacy (hand authored `data-x`/`data-y`) and left untouched; both coexist in a file.

**Hard invariant (`export/pptx_arch.py::_render_arch`):** `arch-row` and `arch-lane` never carry
`position:relative`. `_render_arch` walks with `element.find_all(True)` and resolves every node and edge percentage
against the top level `arch-diagram` box; a positioned wrapper would make the browser resolve child percentages
differently from the PPTX export, a silent divergence. Wrappers stay structural (no `position`, no `display`).

`arch-lane`'s dashed box and label are pure CSS (`[data-type="arch-lane"]` + `::before { content: attr(data-label) }`,
see the two bootstraps): the label is invisible to every exporter, like any CSS pseudo-element. A node flagged
`data-layout="manual"` (set by `editor-drag.js`'s `makeArchNodeDraggable` on the first pointer drag) is never
repositioned by a later `arch-layout` run: its box is read back from its own attributes, and it still reserves its
column slot so siblings do not overlap it.

**V2 primitives** (narrative diagrams): `arch-col` is a nested vertical stack used as one row slot (children resolved
against its slot box via `_compute_col_boxes`, one recursion level); `arch-spacer` reserves a slot's width without a
node box (aligns a node under a column of a wider row); `data-step` on `arch-edge` renders a numbered circle
(`.arch-edge-badge`) at the edge's true on-segment midpoint, independent of the text label; `data-color` on
`arch-edge` overrides the single accent colour on segment, tip and label (one colour per flow). `arch-col` and
`arch-spacer` add no `data-type` branch to `export/pptx_arch.py` (inert like `arch-row`/`arch-lane`); `arch-col`'s
CHILDREN do need one, see below. `.arch-edge-badge` exports through `_render_arch_children` -> `_render_arch_badge`: a
filled `MSO_SHAPE.OVAL` with the number centered, matching the browser's 14px circle.

**Hard invariant of `arch-col` (read before touching its CSS or `_resolve_row_slots`):** `arch-col` is
`position:absolute` so its own box resolves against the diagram, and therefore it is also the containing block of
its children: the browser resolves their `left`/`top`/`width`/`height` against the **col's** box. `arch_layout.py`
keeps every box diagram-relative internally (routing, lanes, collisions, `node_boxes`) and converts only the values
written to a nested node's attributes to col-relative percent at the last moment (`_to_local`, from the `arch-col`
branch of `_resolve_row_slots`). A manual-locked nested node's stored attributes are col-relative too and are
converted back when read (`_resolve_locked_box(..., container=slot_box)`). Getting it wrong crashes nothing: every
nested node silently shrinks to about col-width² / 100. One write path per node: `_write_node_box` is called once
(plain slot or `arch-col` branch of `_resolve_row_slots`); `_layout_diagram`'s node loop only does bookkeeping
(`node_boxes`, `node_row`) and must never call `_write_node_box` again.

## Editor artifacts

The browser injects helper nodes and attributes into the iframe DOM (`_mcp_format_bar`, `_mcp_insert_bar`,
`_mcp_editor_styles`, `_editor_ctx_host`, `_mcp_drop_indicator`, `_mcp_drag_handle`, `_mcp_editable`,
`contenteditable`, Google Translate and Grammarly attributes); `_strip_editor_artifacts` removes them before writing.
A new artifact goes into `_EDITOR_ARTIFACTS` (`http_server.py`) with its `editor-*.js`, or it leaks into the file.

* The client save (`saveContent` in `editor-save.js`, SPEC-0004) strips the artifacts on a detached clone and never
  mutates the live DOM: removing `contenteditable` from the focused zone would move focus to `<body>` and drop the
  keystrokes typed after the save. A new client artifact is stripped on the clone too.
* The text width bar (`#width-bar`, `#width-readout`, SPEC-0015) belongs to the shell page, never the framed
  document, so it needs no `_EDITOR_ARTIFACTS` entry. The drag preview goes through `el.style`, which rewrites the
  whole style attribute (hex to `rgb(...)`, quotes in `url(...)`): never write a saved style through `el.style`,
  rebuild the text from the attribute as it was before the drag and use `setAttribute('style', text)`. The preview is
  suspended around every serialization (`withWidthPreviewSuspended` in `editor-width.js`): a new serialization path
  (save, snapshot, export of the document) runs inside it.

## Undo / redo (structural mutations, `editor-undo.js`)

Ctrl+Z / Cmd+Z, Ctrl+Shift+Z / Cmd+Shift+Z / Ctrl+Y, edit mode only: in-memory whole-document `outerHTML` snapshots
(`undoStack`/`redoStack`, `UNDO_MAX_DEPTH = 50`) pushed by `snapshotForUndo()` right BEFORE each structural mutation;
nothing reaches disk (no DOM marker, no `_EDITOR_ARTIFACTS` entry).

**Covered** (no native undo otherwise): arch-node drag (one snapshot per gesture, not per pointermove),
add/remove/rename/reshape, arch-edge create, image insert by drag-drop (`embedImageFile`'s `insertAdjacentHTML`
branch, unlike the file picker's `execCommand('insertHTML', ...)` it pushes no native step), table row/col
add/remove/table delete, gantt task add/resize/rename/delete, text width change (one step each, SPEC-0015), slide
insert/delete, document block insert/reorder, annotation edit/delete.

**Not covered, on purpose:** contenteditable text edits (typing, format bar, `insertTable`/`insertLink`/
`insertHorizontalRule` with the caret in a `[data-editable~="text"]` zone: `execCommand` already pushes a native
step) and native image resize inside a `contenteditable` region (fires `input`). `handleUndoRedoKeydown()` lets
the key through to the browser when `document.activeElement.isContentEditable`, UNLESS
`doc.queryCommandEnabled('undo'|'redo')` reports nothing native left, then falls back to the structural stack so
Ctrl+Z is never a silent no-op. Undoing a structural operation needs focus OUTSIDE a live text edit; the two stacks
never merge (`tests/test_undo_redo_e2e.py::test_undo_does_not_fire_inside_active_text_editing`).

**Restore:** `restoreDomSnapshot()` runs `doc.open(); doc.write(html); doc.close();` on the iframe document.
Chromium fires the iframe `load` on every `doc.write()`, so `onFrameLoad()` re-wires everything (editable zones,
drag handles, arch-node drag, context menus): there is no second rewiring function. The `restoringFromUndo` flag
makes `onFrameLoad()` skip `resetUndoStacks()` for an undo/redo reload; get it wrong and `performUndo()`/
`performRedo()` wipe their own stacks (redo silently did nothing, the bug hit while building it). Persistence
reuses `saveContent()` (`POST /content`). `resetUndoStacks()` runs when the iframe loads a genuinely different
document (initial load, external agent write, another file); toggling edit mode within the same document does not.
