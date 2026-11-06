# BL-0033: PPTX and DOCX exports honour a text's width

Nature: FEAT
Origin: deferred from SPEC-0015 (text width bar in the editor).

## What

A text whose inline style holds `max-width:Npx` (set by the editor's width bar, or by the agent) is
exported at that width: the PPTX text box is at most N pixels wide (one CSS pixel is one point), and
the DOCX paragraph gets a matching right indent or is left as is with a stated reason.

## Why

The author narrows a headline or a paragraph in the browser and the PPTX shows it full width again,
with different line breaks. SPEC-0015 documents the loss in the export guidance topic.

## Evidence

The PPTX exporter reads `max-width` for images and annotated images only:
`src/mcp_htmleditor/export/pptx_blocks.py:164,177-180`, `src/mcp_htmleditor/export/pptx_images.py:33`.
The DOCX export goes through pandoc, which ignores inline widths (to verify).

## Notes

Remove the "Perdu" line added by SPEC-0015 to the export topic once done.
