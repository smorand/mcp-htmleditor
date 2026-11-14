# BL-0047: The PPTX export reads pictures named outside the deck's folder

Nature: BUG
Origin: class sweep of SPEC-0023 (occurrence #6, section 14.2).
Decision: deferred by the implementing agent on 2026-11-14 under the user's standing instruction for the
SPEC-0023 run ("decide, record decisions and tradeoffs"); to be confirmed by the user. What stays possible until
fixed: a deck received from someone else can name any local picture (absolute path or `../`), and that picture
ends up in a PPTX exported from it. No request from the network reaches this path (the editor server only writes
the deck after its request gate).

## Evidence

- Class: a value carried by a deck's markup (`src`, `url()`) reaching a file read (CWE-22).
- `src/mcp_htmleditor/export/pptx_images.py:115` to `:121`: a relative `src` is joined to the deck's folder, an
  absolute one is used as is, with no containment.
- `src/mcp_htmleditor/render/service.py:211`: the render opens the deck through `file://`, so the browser loads
  any local picture it names.
- The painted export of SPEC-0023 reads the pictures the browser loaded (`file://` URLs), same rule.
- `src/mcp_htmleditor/export/to_docx.py:143` to `:144`: pandoc gets `--resource-path <deck folder>` and resolves
  every local `<img src>`, relative or absolute, embedding it in the DOCX.
- The degraded Breathe export of SPEC-0023 reads the `url()` of a slide's background class (a linked file).

## Proposal

Refuse, with a warning naming the picture, any local picture whose resolved path is outside the deck's folder,
in the flowed export, the painted export, the degraded export, the DOCX export and the render (route `file://` requests outside the folder to abort).
