# SPEC-0022 design: PPTX export of speaker notes (FR-6)

2026-05

* `export/pptx_model.py`: `NOTES_ROLE = "speaker-notes"` and `_is_notes(element)`.
* `export/pptx_flow.py`: `_collect` returns nothing for a notes aside and `_is_block_child` refuses it, so it is never a shape
  at any depth.
* `export/to_pptx.py`: `_SlideBuilder._write_notes` runs after the flow; the first direct child aside with non blank text is
  written to `slide.notes_slide.notes_text_frame.text`. python-pptx creates the notes slide lazily, so a slide without notes
  has none.
* `deck/` services are unchanged: they treat the aside as ordinary slide content (tested).
* Tests: `tests/test_pptx_speaker_notes.py`.
