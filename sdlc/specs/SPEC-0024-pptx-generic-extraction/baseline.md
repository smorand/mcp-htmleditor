# SPEC-0024 baseline: PPTX fidelity before any exporter change

Measured with `make pptx-fidelity` (`tools/pptx_fidelity.py`, see `.agent_docs/pptx-fidelity.md`), phase 1: the exporter
is untouched. 13 presentation files, 93 slides, 2026-11 run on macOS, LibreOffice (soffice) then pdftoppm.
Full run: 46 s wall clock (3 templates in parallel). Raw reports: `<tmp>/pptx-fidelity/report.{md,json}` and one
`NN-<slide>-side.png` (HTML left, PPTX right) per slide.

Score = 0.7 x SSIM (grayscale 480x270, 8x8 blocks) + 0.3 x colour histogram similarity. Recall = HTML words found in
the PPTX shapes. Editable = shapes that are not pictures over all shapes (mean over the slides).

## Scores

`mean` uses the whole slide box scaled to 960x540 (default `--reference slide`). `canvas mean` is the product render
clip (`--reference canvas`, a 960x540 window at the slide corner: it crops a larger slide, pads a smaller one).

| template | slides | mean | canvas mean | worst slide | recall | editable | pictures |
|---|---|---|---|---|---|---|---|
| slides-breathe-empty | 1 | 0.889 | 0.889 | slide-0 0.89 | 1.00 | 0.67 | 5 |
| slides-ei-empty | 1 | 0.940 | 0.940 | slide-0 0.94 | 1.00 | 0.33 | 4 |
| slides-empty (carbon) | 1 | 0.895 | 0.895 | slide-0 0.89 | 1.00 | 1.00 | 0 |
| slides-medical-empty | 1 | 0.889 | 0.889 | slide-0 0.89 | 1.00 | 1.00 | 0 |
| breathe | 23 | 0.915 | 0.915 | slide-4 0.86 | 1.00 | 0.80 | 79 |
| euro-information | 3 | 0.901 | 0.901 | slide-2 0.87 | 1.00 | 0.73 | 6 |
| example-carbon-complete | 9 | 0.678 | 0.680 | slide-6 0.60 | 1.00 | 0.99 | 1 |
| example-ei-complete | 9 | 0.794 | 0.794 | slide-3 0.66 | 1.00 | 0.88 | 12 |
| example-medical-complete | 15 | 0.737 | 0.737 | slide-9 0.62 | 0.98 | 0.96 | 7 |
| ibm-carbon | 9 | 0.586 | 0.600 | slide-8 0.30 | 0.95 | 1.00 | 0 |
| medical | 16 | 0.726 | 0.726 | slide-4 0.59 | 0.97 | 0.95 | 12 |
| presentation-standard | 4 | 0.533 | 0.518 | slide-cover 0.15 | 1.00 | 1.00 | 0 |
| roadmap-one-pager | 1 | 0.797 | 0.781 | slide-roadmap 0.80 | 0.59 | 1.00 | 0 |

Mean over all 93 slides: 0.769; 6 slides under 0.6, 32 under 0.7. Worst 6 slides: presentation-standard cover 0.15 and closing
0.24, ibm-carbon slide-8 0.30, ibm-carbon slide-6 0.54, ibm-carbon slide-2 0.57, medical slide-4 0.59.
The harness flags 0 overflowing slides and 0 empty slides; "flattened" (a picture over 90 % of the slide) fires on
the 23 Breathe slides and the Breathe bootstrap, which is the painted background by design, not a defect.

## Reading the numbers: harness limits

These bias every score and must be fixed or accounted for before a gate.

- H1 Font substitution. The PPTX names the real fonts (`IBM Plex Sans`, `Segoe UI`, `Trebuchet MS`) but
  LibreOffice here embeds a serif (`Linux Libertine`, `Frank Ruhl Hofshi`) in the PDF for all of them, even for the
  installed Trebuchet MS and Georgia. Every slide is affected (93): line wraps and glyph shapes differ, so the SSIM is
  capped around 0.9 even for a perfect shape layout. Mitigation to build in phase 2: a fontconfig alias or a font
  directory for soffice, or a PDF font check in the harness.
- H2 The overflow flag measures the shape box, not the text. It saw nothing, yet several slides visibly spill text out
  of its box (see D4, D5). Phase 2 needs a text height estimate or a rendered overlap test.
- H3 SSIM is block based and pessimistic on thin lines and text. Use the score for ranking and regression, not as an
  absolute quality number.
- H4 `presentation-standard` cover and closing: the HTML itself is white. `section[data-type="slide"]` (specificity
  0,1,1) sets `background: white` and beats `.slide-cover` and `.slide-closing` (0,1,0), whose gradient and white text
  therefore never show. The PPTX paints the intended dark gradient, so the 0.15 and 0.24 are a template CSS bug, not an
  exporter defect. To fix in the template, outside this phase.

## Defect catalogue

Ranked by slides affected. "Counted" means computed from the HTML structure of the 93 slides; "seen" means visible in
the side by side pictures I read (worst 6 plus 11 more), extrapolated by the same structure.

| rank | defect | slides | how counted |
|---|---|---|---|
| D1 | Font fallback and no letter spacing: eyebrow labels (`CONTEXTE · SLIDE 04 / 09`) lose their tracking, headings lose their sans weight, text widths change | all 93 (H1 for the font) | seen, every picture |
| D2 | Rounded and framed containers lost: EI blue frame with the rounded white page, rounded chips, pills, badge capsules become flat | 13 EI (euro 3, example-ei 9, ei-empty 1) for the frame; 15 slides with chip, badge, pill or tag classes | counted (chip classes), seen (EI) |
| D3 | Bullets become `•` characters in the text: the hanging indent is gone, wrapped lines return under the bullet, the bullet colour is the text colour (HTML bullets are teal discs and dashes) | 21 slides with lists | counted (`<li`) |
| D4 | Text spills out of its box or collides with the next block: a six row table runs under the callout and the footer (ibm-carbon slide-2, 0.57); stat column spills out of the grey panel and onto the source line (medical slide-12 and example-medical slide-11, 0.64); bullets overlapped by images (medical slide-4, 0.59) | 16 slides with tables plus the medical figure and stat slides; seen on 6 | seen, tables counted |
| D5 | Flex and grid rows flattened or re-gridded: stat cards (3 across) become a vertical list of loose numbers, the card background and the top accent border disappear; the `@mention` chip row (flex wrap) becomes a 3 column grid of grey boxes with plain text (ibm-carbon slide-3, example-carbon slide-6) | at least 8 seen (medical stats x4, mention rows x2, mode columns), more likely | seen |
| D6 | Image crop lost: HTML shows 3 or 4 wide `object-fit` cropped strips with a letter badge (A to D) and a caption; the PPTX places the whole image, taller, over the caption text; captions truncated, badges missing (recall 0.82 to 0.85) | 4 seen (medical 4, 6; example-medical 5, 9); 33 slides hold an `<img>` | seen, img counted |
| D7 | Inline code and tag styling lost in tables: the monospace chips `read grep`, the coloured pill cells (`Développeur`, `Fonctionnel`) become coloured bold text; row separator rules and header cell padding are gone | all slides with chip tables: ibm-carbon 2, 6; example-carbon 5; example-medical (tables) | seen, chip counted |
| D8 | Inline SVG and vector figures dropped: the Bob IDE screenshot reconstruction is replaced by a stray text line `SVG reconstruction fidèle...`; the exporter already warns (1 warning) | 1 (ibm-carbon slide-8, score 0.30) | counted (svg) |
| D9 | Generated and decorative text missing: month and quarter header row of the Gantt (recall 0.59: `jan`, `q1`, ...), the footnote `Image synthétique de démonstration`, A to D badges | 1 roadmap, 2 medical (slide-3, slide-5) | counted (recall) |
| D10 | Vertical rhythm: subtitle jammed under the title (presentation-standard cover: title wraps to two lines with a large line gap and the subtitle touches it; ibm-carbon and carbon decks: subtitle sits 3 px under the title instead of its own block) | 4 title blocks seen (presentation-standard cover, ibm-carbon 2, 3, 8) | seen |
| D11 | Header or footer bars approximated: footer band and blue rule are close but a few pixels off, the slide number moves | seen on about 8 slides, not measured | seen |
| D12 | Breathe painted export is the reference: only small text offsets, the diagonal light gradient background is a bitmap, so not editable | 0 defects of shape, 23 slides at 0.86 to 0.94 | seen |

Not a defect: the 16:9 slide of `ibm-carbon` and `example-carbon-complete` has a 900 x 430 box that is stretched to
960 x 540, as the PPTX slide is; the two aspects differ by 4 percent, accepted in the reference picture.

## Per template

- slides-empty, slides-ei-empty, slides-medical-empty, slides-breathe-empty (1 slide each, 0.89 to 0.94): empty
  templates, only D1 and D2 (EI frame). Breathe empty has 5 pictures (painted background and decoration), 15 shapes.
- breathe (23 slides, 0.915, recall 1.00): painted export, 79 pictures and 432 shapes, 80 % editable. Best result;
  D12 only. Worst slide-4 (0.86, big number slide), mostly because of the font (H1).
- euro-information (3, 0.90): D1, D2 (blue frame and rounded page lost), card bullets D3.
- example-ei-complete (9, 0.79): worst slide-3 0.66, three cards (D2, D3), the callout is kept, the card height is
  right but bottom space is empty; footer logo disc kept but offset.
- example-carbon-complete (9, 0.68): worst slide-6 0.60 (mention chip rows as grey boxes D5, D7), slide-5 0.61 table
  (D7, pills), slide-2 dark section slide is close (D1 only, subtitle one line instead of two).
- ibm-carbon (9, 0.59, recall 0.95): worst deck after presentation-standard. slide-8 0.30 SVG dropped (D8), slide-6 0.54
  table and callout (D4, D7), slide-2 0.57 table overflowing the callout (D4), slide-3 0.60 chip rows (D5).
- medical (16, 0.73) and example-medical-complete (15, 0.74): worst slide-4 0.59 and slide-9 0.62 image grids with
  overlapped captions (D6), slide-12 and slide-11 stat cards (D4, D5), slide-6 0.62 same as slide-9. Bullet lists D3.
- presentation-standard (4, 0.53): cover 0.15 and closing 0.24 are the HTML specificity bug (H4); the other two slides
  are text only.
- roadmap-one-pager (1, 0.80, recall 0.59): the PPTX redraws the bars from the data and loses the header row and the
  lane backgrounds; the HTML bars run past the right edge in the canvas clip (reason the whole slide reference is used).

## Success criteria proposed for the next phase

Not decided here. Measured starting point: slide mean 0.77, worst 0.15 (0.30 once H4 is out), recall 0.95 or more on
every deck but roadmap (0.59). A first gate could be `--min-score 0.6` per template mean once H1 is addressed, then
raise.

## Baseline after font fix

H1 fixed inside `tools/pptx_fidelity.py` (2026-11-14): LibreOffice here ran with an empty fontconfig, so it embedded a
serif for every face. The harness now gives soffice its own `fonts.conf` (system font dirs, a cache dir and aliases
inside the temp work dir, `FONTCONFIG_FILE`). Installed on this machine: Trebuchet MS, Georgia, Arial, Helvetica Neue,
Brush Script MT. Not installed: IBM Plex Sans, Segoe UI (aliased to Helvetica Neue in the harness only, and only when
missing). `pdffonts` shows real fonts now. Exporter untouched; same 13 files, 93 slides.

| template | slides | mean | worst slide | recall |
|---|---|---|---|---|
| slides-breathe-empty | 1 | 0.941 | slide-0 0.94 | 1.00 |
| slides-ei-empty | 1 | 0.940 | slide-0 0.94 | 1.00 |
| slides-empty (carbon) | 1 | 0.895 | slide-0 0.89 | 1.00 |
| slides-medical-empty | 1 | 0.890 | slide-0 0.89 | 1.00 |
| breathe | 23 | 0.954 | slide-4 0.91 | 1.00 |
| euro-information | 3 | 0.900 | slide-2 0.87 | 1.00 |
| example-carbon-complete | 9 | 0.675 | slide-6 0.60 | 1.00 |
| example-ei-complete | 9 | 0.791 | slide-3 0.65 | 1.00 |
| example-medical-complete | 15 | 0.734 | slide-13 0.63 | 0.98 |
| ibm-carbon | 9 | 0.580 | slide-8 0.30 | 0.95 |
| medical | 16 | 0.720 | slide-4 0.59 | 0.97 |
| presentation-standard | 4 | 0.531 | slide-cover 0.15 | 1.00 |
| roadmap-one-pager | 1 | 0.796 | slide-roadmap 0.80 | 0.59 |

Mean over 93 slides 0.776, worst 0.15, 33 slides under 0.7, 55 under 0.85. Only Breathe moved (0.915 to 0.954): the
flow decks were limited by their layout, not by the font.

## Result of phase 2a (generic painter, FR-1 to FR-4, FR-7, FR-8, FR-10, FR-5 where mappable)

Same harness, same machine, after the generic painter and the template fix (FR-10).

| template | slides | mean before | mean after | worst before | worst after | recall after | editable after | pictures | tables |
|---|---|---|---|---|---|---|---|---|---|
| slides-breathe-empty | 1 | 0.941 | 0.941 | slide-0 0.94 | slide-0 0.94 | 1.00 | 0.67 | 5 | 0 |
| slides-ei-empty | 1 | 0.940 | 0.968 | slide-0 0.94 | slide-0 0.97 | 1.00 | 0.33 | 4 | 0 |
| slides-empty | 1 | 0.895 | 0.957 | slide-0 0.89 | slide-0 0.96 | 1.00 | 1.00 | 0 | 0 |
| slides-medical-empty | 1 | 0.890 | 0.964 | slide-0 0.89 | slide-0 0.96 | 1.00 | 1.00 | 0 | 0 |
| breathe | 23 | 0.954 | 0.952 | slide-4 0.91 | slide-4 0.91 | 1.00 | 0.79 | 79 | 2 |
| euro-information | 3 | 0.900 | 0.982 | slide-2 0.87 | slide-0 0.97 | 1.00 | 0.73 | 6 | 1 |
| example-carbon-complete | 9 | 0.675 | 0.878 | slide-6 0.60 | slide-2 0.86 | 1.00 | 0.99 | 1 | 1 |
| example-ei-complete | 9 | 0.791 | 0.954 | slide-3 0.65 | slide-5 0.91 | 1.00 | 0.89 | 12 | 1 |
| example-medical-complete | 15 | 0.734 | 0.915 | slide-13 0.63 | slide-3 0.85 | 1.00 | 0.98 | 7 | 2 |
| ibm-carbon | 9 | 0.580 | 0.850 | slide-8 0.30 | slide-6 0.81 | 0.93 | 1.00 | 1 | 0 |
| medical | 16 | 0.720 | 0.927 | slide-4 0.59 | slide-14 0.88 | 1.00 | 0.98 | 12 | 2 |
| presentation-standard | 4 | 0.531 | 0.979 | slide-cover 0.15 | slide-content 0.96 | 1.00 | 1.00 | 0 | 0 |
| roadmap-one-pager | 1 | 0.796 | 0.989 | slide-roadmap 0.80 | slide-roadmap 0.99 | 1.00 | 1.00 | 0 | 0 |

Mean over 93 slides 0.928 (before 0.776), worst slide 0.81 (before 0.15), 0 slides under 0.7 (before 33), 6 under 0.85.

Against FR-9: template mean >= 0.85 met on all 13 (ibm-carbon 0.850 is the tightest); empty bootstraps >= 0.90 met;
no slide under 0.70 met; text recall >= 0.98: met on 12 of 13, not on ibm-carbon (0.93); editable ratio >= 0.80: met on
all decks except the picture heavy ones (breathe 0.79, euro-information 0.73) and the bootstraps that hold logos and
a background picture by design (ei-empty 0.33, breathe-empty 0.67).

What remains:

- ibm-carbon recall 0.93: slide-8 is a rasterised `<svg>` (about half of its words live in the picture, kept as alt text only);
  slide-2 and slide-6 have the footer pushed out of the scrolling slide box (`overflow-y:auto`), so it is not visible in
  the HTML slide box and not exported. Not a painter defect.
- Tables stay painted boxes and text when a cell holds a block, a picture or a pill (ibm-carbon, 0 native table in 9
  slides); native tables: 9 over the 13 files. Next step: map pills to run highlights, or draw them over the table.
- Editable ratio of Breathe and EI: decorations are pictures (backgrounds, logos), as designed.
- CSS `counter()` markers (medical reference lists), radial gradients, shadows with spread, `object-position` on
  backgrounds other than cover and contain are not mapped.
- Remaining visual gap is the font (PowerPoint and LibreOffice draw Helvetica Neue or Arial where the HTML used an
  unavailable condensed face) and exact line spacing in LibreOffice (about 3 px lower text).
- Breathe lost 0.002 (0.954 to 0.952): the 2x raster and the generic bullets, within noise.
