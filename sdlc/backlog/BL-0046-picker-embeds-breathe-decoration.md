# BL-0046: The layout picker embeds the decoration of an inserted Breathe layout

Nature: FEAT
Origin: deferred from SPEC-0023 (scope 3.2, EXC-002a).

## What

When the editor inserts a Breathe layout whose background or icon classes have no rule in the deck's
decoration block, add the missing rules (from the catalogue, inline or linked like the rest of the deck) so the
slide shows its decoration without running `mcp-htmleditor breathe-inline`.

## Why

Today (SPEC-0023 E2E-052) the inserted slide shows no background until the author runs the command and reloads.

## Evidence

- `src/mcp_htmleditor/static/editor-slides.js` `insertSlide` (inserts the layout HTML only).
- `src/mcp_htmleditor/breathe/inline.py` (the embedding rules to reuse).
