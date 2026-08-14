# HTML conventions

The full authoring rules live in the skill (`mcp-htmleditor skill`, sources in `skill/`).
This file keeps the invariants the Python side depends on: break one of them and an
export or the editor silently degrades.

## Document level

| Attribute | Effect |
|-----------|--------|
| `data-doc-type="presentation"` on `<html>` | Slide navigation active |
| `data-doc-type="document"` | Word like mode, the block picker appears in edit mode |
| `data-doc-template="perso"` / `"ei"` on the document `<article>` | Selects the charter, for the HTML rendering and for the DOCX export |
| `data-editable="text"` | Marks an editable text element |

## Slides

* `data-type="slide"` requires a unique `data-id` and a `data-title`. `article.slide` is
  the legacy fallback still honoured by the exporter.
* EI slide footer markup is `.slide-foot-logo > .logo-disc > img`. The template only
  sizes `.slide-foot-logo .logo-disc img` (16px), so a missing `.logo-disc` lets the
  chevrons render at 41x37 and spill over the blue ring.
* Slide counters: eyebrow `Catégorie · Slide 0N / TT` in both charters, plus
  `.slide-footer-right` ("Slide N / TT", Carbon) or `.slide-foot-page` ("N", EI).
  `renumberSlides()` in `editor.js` rewrites exactly those three, anything else goes stale.
* `<html data-asset-chevrons="data:image/png;base64,...">` in the EI bootstrap is the
  fallback source for `{{CHEVRONS}}` in inserted slides (`resolveTemplateAssets`), needed
  because a fresh file has no `.slide-foot-logo img` to copy from. Same pattern is
  available for `data-asset-cover`, `-cm`, `-cic`, `-ei`.
* Slide layouts may use `{{N}}` / `{{TT}}`: they are not substituted at insertion, the
  eyebrow regex in `renumberSlides()` resolves them on the following pass.

## Fullscreen presentation mode (mandatory on every slide template)

Every presentation template (bootstrap or reference, current or future) must ship the
same three fullscreen building blocks. This is not charter specific: Carbon and EI carry
it today, and any new template key (`new <key>`) must carry it too, otherwise the
"Présenter" button opens a fullscreen with no scaling, or no button at all.

1. **CSS** (in the document `<style>`):
   ```css
   :fullscreen .shell-header, :fullscreen .toolbar, :fullscreen .nav-arrow,
   :fullscreen .status-bar { display:none !important; }
   :fullscreen .stage { background:#000; }
   :fullscreen .slide-frame { padding:0; }
   :fullscreen .slide { border:none; box-shadow:none; scale: var(--fs-scale, 1); transform-origin: center center; }
   :fullscreen body { background:#000; }
   ```
   Selectors that do not exist in a given template's shell (e.g. EI has no
   `.shell-header`) are simply omitted from that rule, never dropped from the whole
   block.
2. **Toolbar button** `#btn-present` (`onclick="enterPresentation()"`), placed after the
   last `toolbar-sep`.
3. **JS** in the navigation `<script>`: `updateFullscreenScale()` called at the end of
   `render()`, `fullscreenchange` / `resize` listeners calling it, `enterPresentation()` /
   `exitPresentation()`, and the `f`/`F` and `Escape` key bindings in the `keydown`
   handler.

`--fs-scale` is a uniform `transform: scale()` computed from the slide's natural
`getBoundingClientRect()` vs. the viewport (PowerPoint style zoom, not CSS stretch):
without it the slide fills the fullscreen container at native px size with the fonts
staying tiny and empty space around them.

Reference implementation: `templates/bootstrap/slides-empty.html` (Carbon) and
`templates/bootstrap/slides-ei-empty.html` (EI), both greppable with `:fullscreen`.

**When adding a new slide template:** copy this block verbatim from one of the two
bootstraps, adapt only the selector list to the new shell's class names. Verify with
`grep -c fullscreen <file>` (must be > 0) and a headless screenshot showing `#btn-present`
in the toolbar. A template missing this block is a bug, not a variant: old files created
before this convention existed (no `:fullscreen` at all) must be patched the same way
when noticed, not left as is.

## Documents

* Headings are semantic `<h1>` to `<h5>` (classes `doc-title`, `doc-subtitle`,
  `doc-h1` to `doc-h5`) so pandoc maps them to the Word Heading styles.
* Figures use `<figure>` plus `<figcaption>` (pandoc maps them to CaptionedFigure plus
  ImageCaption). PNG only: pandoc cannot size an SVG and old Word does not display it.
* Tables need a `<colgroup>` with `style="width:X%"` on each `<col>`: pandoc reads that
  for the DOCX column widths, `data-col-width` alone is ignored.
* Document templates carry a `@media print` block (`@page` margins, no shadow, no break
  inside figures or rows, repeated `thead`).
* The Word `Title` style comes from the document metadata, so the exporter lifts
  `.doc-title` / `.doc-subtitle` out of the body: a template must not duplicate the title
  by hand.
* Letterhead blocks (`.ei-doc-head`, `.ei-doc-foot`) become a real repeated Word header
  and footer for the charters that declare one (see `export/docx_header_footer.py`).

## data-type values understood by the exporters

| `data-type` | Meaning |
|-------------|---------|
| `slide` | Presentation slide section |
| `gantt` / `gantt-task` | Gantt chart container / one task bar |
| `arch-diagram` / `arch-node` | Architecture diagram container / node |
| `arch-row` / `arch-lane` | Declarative layout input, consumed by `arch_layout.py`; inert to every exporter (no `data-type` branch matches them, `div` is not in `SKIP_TAGS`, so they are simply skipped during the recursive `find_all(True)` walk) |
| `annotation` / `annotated-image` | Image callout / image plus annotations |
| `table` | HTML table |
| `document` | Word like document article |

## Declarative arch-diagram layout (`arch_layout.py`)

A diagram with at least one `arch-row` child is authored declaratively (rows, nodes,
edges, optional lanes — the LLM never writes `data-x`/`data-y`); `mcp-htmleditor
arch-layout` / the `layout_arch_diagram` MCP tool compute and write the final
percentages. A diagram with no `arch-row` is legacy (hand authored `data-x`/`data-y`)
and is left untouched — both formats coexist in the same file.

**Hard invariant, verified against `export/to_pptx.py::_render_arch`**: `arch-row` and
`arch-lane` must never carry `position:relative`. `_render_arch` walks the diagram with
`element.find_all(True)` (recursive) and always resolves every node/edge percentage
against the top level `arch-diagram` box, never against an intermediate wrapper. Giving
a wrapper its own positioning context would make the browser resolve child percentages
differently from the PPTX export, a silent divergence between the live render and the
exported deck. Keep wrappers purely structural (no `position`, no `display` beyond the
default block flow that CSS never reads for percentage resolution here).

`arch-lane`'s dashed box and its label are pure CSS (`[data-type="arch-lane"]` +
`::before { content: attr(data-label) }`, see the two bootstraps): the label is
therefore invisible to every exporter, consistent with the existing "lost at PPTX
export" bucket for CSS pseudo-elements — no extra DOM node needed, no risk of double
rendering.

A node flagged `data-layout="manual"` (set by `editor.js`'s `makeArchNodeDraggable` on
the first pointer drag) is never repositioned by a later `arch-layout` run: its box is
read back from its own attributes instead of being recomputed, but it still reserves its
column slot so siblings do not overlap it.

**V2 primitives** (added to cover narrative diagrams: numbered flow steps, icon cards
with sub-descriptions, mixed row heights) live in the same recursive-safe model: `arch-col`
is a nested vertical stack usable as one row slot (its own children get resolved against
its slot box via `_compute_col_boxes`, one recursion level, no arbitrary nesting depth);
`arch-spacer` reserves a row slot's width without producing a node box, used to align a
node in one row under a specific column of a wider row; `data-step` on `arch-edge` renders
a numbered circle (`.arch-edge-badge`) at the edge's true on-segment midpoint, independent
of the optional text label's offset position; `data-color` on `arch-edge` overrides the
bootstrap's single fixed accent colour on the segment, tip and label (needed the moment a
diagram has more than one flow, each with its own colour, like a legend). `arch-col` and
`arch-spacer` add no new `data-type` branch to `export/to_pptx.py` (stay inert to it exactly
like `arch-row`/`arch-lane`); `arch-col`'s CHILDREN do need one, see the invariant below.
`.arch-edge-badge` (the `data-step` circle) has its own render branch
(`_render_arch_children` -> `_render_arch_badge`): a filled `MSO_SHAPE.OVAL` with the
number centered, matching the browser's 14px circle.

**Hard invariant discovered building this (read before touching `arch-col`'s CSS or
`_resolve_row_slots`)**: `arch-col` must be `position:absolute` for ITS OWN box to resolve
against the diagram — but per CSS, any `position:absolute` element is *also* the containing
block for its own absolutely positioned descendants. A col's children therefore have their
`left`/`top`/`width`/`height` percentages resolved by the browser against the **col's** box,
not the diagram's, no matter what the Python side intended. `arch_layout.py` handles this by
keeping every box diagram-relative internally (edge routing, lanes, collisions all reason in
diagram-relative percent, via `node_boxes`) and converting only the *values written to a
nested node's own attributes* to col-relative percent at the last moment (`_to_local`, called
from `_resolve_row_slots`'s `arch-col` branch). A manual-locked (`data-layout="manual"`)
nested node's *stored* attributes are therefore col-relative too, and must be converted back
to diagram-relative when read (`_resolve_locked_box(..., container=slot_box)`) before being
used for routing. Getting this wrong doesn't crash anything: it silently shrinks and misplaces
every node nested in a col (a node meant to be half the col's width renders at roughly
col-width² / 100, since the percentage compounds), the exact bug this note exists to prevent
someone from reintroducing. There is exactly one write path per node (`_write_node_box` is
called once, either directly in `_resolve_row_slots` for a plain slot or its `arch-col`
branch for a nested one) — `_layout_diagram`'s own node loop only does bookkeeping
(`node_boxes`, `node_row`), it must never call `_write_node_box` again.

## Editor artifacts

The browser injects helper nodes and attributes into the iframe DOM (`_mcp_format_bar`,
`_mcp_insert_bar`, `_mcp_editor_styles`, `_editor_ctx_host`, `_mcp_drop_indicator`,
`_mcp_drag_handle`, `_mcp_editable`, `contenteditable`, plus Google Translate and
Grammarly attributes). `_strip_editor_artifacts` removes all of them before writing, so
a saved file never carries editor state. Add a new artifact to `_EDITOR_ARTIFACTS` in
`http_server.py` at the same time as you add it to `editor.js`, otherwise it leaks into
the file the next agent reads.

## Undo / redo (structural mutations, `editor.js`)

Ctrl+Z / Cmd+Z (undo) and Ctrl+Shift+Z / Cmd+Shift+Z / Ctrl+Y (redo) are active only in
edit mode. Implementation: a pure in-memory JS stack of whole-document `outerHTML`
snapshots (`undoStack`/`redoStack`, capped at `UNDO_MAX_DEPTH = 50`), pushed via
`snapshotForUndo()` right BEFORE each structural mutation runs. No new DOM markers, no
new `_EDITOR_ARTIFACTS` entry needed: the stacks never touch disk or the saved file.

**Covered (has zero native undo without this feature):** arch-node drag reposition (one
snapshot per drag gesture, not per pointermove), arch-node add/remove/rename/reshape,
arch-edge create, image insert via drag-drop (`embedImageFile`'s `insertAdjacentHTML`
branch — unlike the file-picker's `execCommand('insertHTML', ...)`, this does NOT push a
native contenteditable undo step), table row/col add/remove/table delete, gantt task
add/resize/rename/delete, slide insert/delete, document block insert/reorder (drag
handle), annotation edit/delete.

**Deliberately NOT covered, on purpose:** plain contenteditable text edits (typing,
format-bar bold/italic/color/font-size, `insertTable`/`insertLink`/`insertHorizontalRule`
when invoked with caret focus inside a `[data-editable~="text"]` zone — all of these are
`execCommand`-based and already push a step onto the browser's OWN native undo stack) and
native image resize/reposition when the image sits inside a `contenteditable` region
(dragging the browser's own resize handles fires the `input` event, which is native
undo territory the same as typing). `handleUndoRedoKeydown()` checks
`document.activeElement.isContentEditable` and, if true, lets the keystroke fall through
to the browser's native handler UNLESS `doc.queryCommandEnabled('undo'|'redo')` reports
nothing left to undo/redo natively, in which case it falls back to the structural stack
so Ctrl+Z is never a silent no-op. Interaction observed when a text edit and a structural
op are interleaved (verified with a real Chromium E2E, `tests/test_undo_redo_e2e.py::
test_undo_does_not_fire_inside_active_text_editing`): a keystroke while focus is inside
an actively-edited text zone never touches the structural stack, so undoing a structural
operation always requires focus to be OUTSIDE a live text edit at the moment of Ctrl+Z
(clicking elsewhere in the iframe, or the caret having blurred). The two stacks do not
merge or interleave; each stays scoped to its own kind of change.

**Restore mechanism**: `restoreDomSnapshot()` calls `doc.open(); doc.write(html);
doc.close();` on the iframe's document. Verified experimentally: Chromium fires the
iframe's own `load` event on every `doc.write()`, exactly like a real navigation — so
`onFrameLoad()` runs again and re-wires everything a fresh load already re-wires
(editable zones, drag handles, arch-node drag, context menus): there is deliberately no
second parallel rewiring function. The `restoringFromUndo` flag lets `onFrameLoad()`
tell an undo/redo-triggered reload apart from a genuinely different document and skip
`resetUndoStacks()` in that one case — get this flag wrong and `performUndo()`/
`performRedo()` overwrite their own updated stacks with a wipe on every call (the actual
bug hit and fixed while building this: redo silently did nothing, one push short every
time). Persistence after a restore reuses `saveContent()` — the same `POST /content` path
every other mutation already uses, no second save mechanism.

Stacks reset (`resetUndoStacks()`) whenever the iframe loads a genuinely different
document (initial load, external agent write, navigating to another file): a snapshot
from a previous document does not correspond to anything restorable. Toggling edit mode
off/on within the SAME loaded document deliberately does NOT reset the stacks.
