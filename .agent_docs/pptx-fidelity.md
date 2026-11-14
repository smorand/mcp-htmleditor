# PPTX fidelity harness (SPEC-0024)

`make pptx-fidelity` runs `tools/pptx_fidelity.py`: it measures how close the PPTX export is to the HTML slide, for
every presentation under `templates/` (found by `data-doc-type="presentation"`, keyed by file stem). It measures, it
does not gate: exit 0 unless a tool failed (1) or a prerequisite is missing or the template name is unknown (2).
`--min-score X` exits 1 when a template mean is below X (for a later gate).

## 2026-11-06 Pipeline and score

- Needs `soffice`, `pdftoppm` (poppler) and Chromium (`make install-browser`). No numpy: Pillow and the stdlib only.
- Per slide: HTML picture 960x540, `export_file(..., "pptx")` (same code as the CLI), `soffice --headless --convert-to pdf`
  with a private `-env:UserInstallation` profile, `pdftoppm -png -r 72 -scale-to-x 960 -scale-to-y 540`.
- `--reference slide` (default): whole slide box screenshot scaled to 960x540. `--reference canvas`: the product
  `render_deck` picture (a 960x540 clip at the slide corner, crops a 1280x720 slide). Slide mode is the fair one.
- `score = 0.7 x ssim + 0.3 x (1 - histogram_distance)`. SSIM: grayscale 480x270, 8x8 non overlapping blocks, mean.
  Histogram: 4 levels per channel, half L1 distance. Both in 0..1.
- Text recall: distinct HTML words (no script, style, hidden, speaker notes) found in the words of the PPTX text frames,
  table cells and groups. Editable ratio: non picture shapes over all shapes. Overflow: a text shape box leaving the
  slide by more than 1 %. Flattened: a picture over 90 % of the slide (Breathe backgrounds trigger it by design).
- Output `<tmp>/pptx-fidelity` (or `--out`): `report.md`, `report.json`, and per template a folder with the HTML png, the
  deck pptx and pdf, the PDF pages and `NN-<slide>-side.png` (HTML left, PPTX right). A template folder is deleted and
  rebuilt on each run; nothing else is touched. The product render directory `<tmp>/htmleditor-render` is only used in
  `canvas` mode.
- `--only a,b` restricts the templates, `--jobs N` (default 3) runs templates in parallel. Full run: about 45 s.

## Gotchas

- H1 (fixed 2026-11-14): the Homebrew soffice ran with an empty fontconfig (`no <cachedir> elements`) and embedded a
  serif for every face. `rasterize` now writes `<work>/fonts.conf` (system font dirs, a cache dir, aliases for faces the
  machine lacks: IBM Plex Sans and Segoe UI to Helvetica Neue, IBM Plex Mono to Menlo; an alias only applies when the
  face is missing) and runs soffice with `FONTCONFIG_FILE`. Everything stays in the work dir. Check with `pdffonts`.
- The painter measures in the product render viewport (1280 x 900); a deck whose slide size depends on the viewport
  (`max-height: 100%`) gets the same box as the reference picture only with that viewport.
- Slide content that scrolls out of the slide box (overflow auto) is not exported and counts as missing words.
- `render_deck` deletes the other pictures of the same file stem at each call, so canvas mode copies each picture at once.
- The overflow flag looks at shape boxes, not text height, and sees nothing on decks whose text visibly spills.
- Tests: `tests/test_pptx_fidelity.py` (pure functions in the gate, one end to end `slow` test).
