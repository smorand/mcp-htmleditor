# SPEC-0023 visual evidence (2026-11-14)

Deck: `templates/reference/slides/breathe.html` (23 slides) as shipped on `feat/breathe-template`.

| Folder or file | What |
|---|---|
| `reference/html/slide-NN.png` | `mcp-htmleditor render <deck> --slide slide-N --scale 1` (Chromium, 960 x 540) |
| `reference/pptx/slide-NN.png` | `mcp-htmleditor export pptx`, saved as PDF by Microsoft PowerPoint (AppleScript), `pdftoppm -r 72` |
| `reference/compare-N.png` | HTML render (left) and PPTX render (right), four slides per sheet |
| `reference/source-vs-new-N.png` | PPTX render of the source template finished by `breathe_pptx.py` (left, `_template/breathe/renders/pptx`, 2026-11-13) and of the integrated export (right) |

Results, all looked at sheet by sheet:

- 23 of 23 PPTX renders are byte identical (same md5) to the renders of the source template's PPTX produced by
  `breathe_pptx.py` on 2026-11-13: the integrated painter reproduces the source finish exactly.
- The PPTX renders match the HTML renders (composition, faces, line breaks, icons, pictures, page numbers).
- A copy of the WCBIP 2026 deck switched to `data-doc-template="breathe"`: `lint: OK (0 errors, 0 warnings)`,
  `report: OK`, 14 of 14 PPTX renders byte identical to the talk's current PPTX renders. Those pictures hold clinical
  images and stay outside this repository (constraint 3.3).
- Defect found by looking (fixed before this evidence, tested): measured slide after slide, the second slide
  inherited an inline `display:block` from the render's show script, so bottom pushed and centred content moved up
  (page numbers, divider band). `.agent_docs/breathe.md` § Gotchas.

Reproduce: export, then open the PPTX in PowerPoint (or `soffice --headless --convert-to pdf`, substitute fonts)
and compare with `mcp-htmleditor render` of each slide.
