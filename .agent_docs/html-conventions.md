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
| `annotation` / `annotated-image` | Image callout / image plus annotations |
| `table` | HTML table |
| `document` | Word like document article |

## Editor artifacts

The browser injects helper nodes and attributes into the iframe DOM (`_mcp_format_bar`,
`_mcp_insert_bar`, `_mcp_editor_styles`, `_editor_ctx_host`, `_mcp_drop_indicator`,
`_mcp_drag_handle`, `_mcp_editable`, `contenteditable`, plus Google Translate and
Grammarly attributes). `_strip_editor_artifacts` removes all of them before writing, so
a saved file never carries editor state. Add a new artifact to `_EDITOR_ARTIFACTS` in
`http_server.py` at the same time as you add it to `editor.js`, otherwise it leaks into
the file the next agent reads.
