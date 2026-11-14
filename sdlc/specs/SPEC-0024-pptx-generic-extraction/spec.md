# SPEC-0024: Generic PPTX extraction (one painter for every charter)

> Id: SPEC-0024 | Nature: FEAT | Status: specified (user request 2026-11-14) | Baseline: `baseline.md` (mean 0.769 over 93 slides)
> Depends on: SPEC-0023 (Breathe painted export, `export/pptx_paint.py`), `tools/pptx_fidelity.py`

## Why

The flow engine of `to_pptx.py` re-interprets CSS per charter (selectors, estimated heights); every charter is a
separate approximation (scores 0.53 to 0.79). The Breathe painted export measures the deck in Chromium (geometry,
computed style, browser line breaks) and writes editable shapes: it scores 0.915 and needs no per template code.
Decision (DEC-1): generalise that painter to every presentation, whatever the charter. The flow build stays as the
degraded result when Chromium or the render extra is missing (warning, as for Breathe today).

## Requirements

- FR-1 `export pptx` paints every presentation (all charters, generic, unknown charters too) from the browser
  measure. No per charter extraction code is added. Charter specific code may only remain for the degraded flow path.
- FR-2 Text stays editable text: browser line breaks, face, size, weight, italic, colour, letter spacing, alignment,
  inline runs (bold, colour, code spans), real paragraph bullets and numbers with hanging indent and the bullet colour.
- FR-3 Boxes: fill, border (per side), border radius (rounded rectangle with the right adjustment, ellipse for 50 %),
  linear gradient (native gradient fill, angle and stops), opacity, box shadow (native outer shadow when simple).
- FR-4 Pictures: `<img>` and CSS background images at their rendered box with the `object-fit` crop; inline `<svg>`
  and `<canvas>` become a picture rasterised from the browser (2x) instead of being dropped; the background of the slide
  full bleed (colour, gradient or picture).
- FR-5 Tables: `<table>` becomes a native PPTX table from measured column widths and row heights, cell fill, borders,
  text styles, colspan and rowspan; a table that cannot be mapped falls back to painted boxes and text.
- FR-6 Structures the flow engine exported natively (Gantt, arch diagram, annotated image) are painted from the
  rendered DOM like everything else; no native object is required there.
- FR-7 Notes pages, slide order, slide size 13.333 x 7.5 in (the 960 x 540 reference scaled by the slide box) and
  the report/warnings contract of the exporter are kept. Remote images stay refused. Slides never show editor chrome.
- FR-8 Failure isolation: a slide measured longer than the bound, a rendering error or a missing Chromium degrades to
  the flow slide with one warning naming the reason (as `pptx_paint.py` does).
- FR-9 Fidelity gate: `make pptx-fidelity` reports per template; target after the work (same harness, same machine):
  every template mean >= 0.85 (empty bootstraps >= 0.90), no slide < 0.70, text recall >= 0.98 (roadmap included),
  editable ratio >= 0.80. Scores are compared with the baseline run, not with 1.0 (the LibreOffice font substitution caps
  them near 0.9 until the harness font problem is fixed).
- FR-10 The `presentation-standard` template CSS bug (specificity of `section[data-type="slide"]` over
  `.slide-cover` / `.slide-closing`) is fixed in the template.

## Acceptance

Unit tests for the pure mapping functions (radius to adjustment, gradient parse, bullets, table spans, colour and
opacity parse); an integration test per charter family exporting a template deck and checking shapes, runs, tables
and editable ratio; the existing exporter tests keep passing or are rewritten where they asserted flow output of a
charter now painted; `make pptx-fidelity` table in the report; `make check` green; skill and docs maintained
(`skill/topics/export.md`, `.agent_docs`, README).
