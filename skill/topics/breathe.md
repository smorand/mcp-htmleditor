Charter `breathe`: congress template of Dr Lamya CHRIF MORAND, direction B "Editorial, airway as a story line". 16:9, 960 x 540, English. Ice `#E7F7FF` and navy `#194757` panels, teal `#0C7B70` titles and counts, aqua `#A2EAF7` highlights on navy, pink `#CD8684` only for alarm numbers on navy. Georgia titles, Trebuchet MS body (web safe, never a downloaded font).

```bash
mcp-htmleditor new breathe talk.html          # one cover slide, decoration inline
mcp-htmleditor breathe-inline talk.html       # after any new layout, picture, background or icon class
mcp-htmleditor breathe-inline talk.html --link   # refer to assets/<file> next to the deck instead
mcp-htmleditor lint talk.html                 # 0 error before export
mcp-htmleditor render talk.html --report-only # no overflow
mcp-htmleditor export pptx talk.html talk.pptx   # painted from the rendered slides, notes included
```

Detection: `data-doc-template="breathe"` on `<html>`, or the token `--breathe-ice` in the `<style>` when the page does not declare `medical`. A deck declaring `medical` stays medical (older Breathe decks keep working as before); switch one by changing the declaration to `breathe`. Classes and tokens keep the `med-` prefix of the layouts.

## Build a deck

Copy slides from the reference deck (23 slides, one per layout) or insert them with the editor's layout picker (`Cover`, `Disclosure`, `Pathway`, `Part 2: Diagnose`, `Key figures`, `Key figures, deep`, `Statement`, `Content with picture`, `Content with card`, `Table`, `Clinical image`, `Compare`, `Statement, deep`, `Clinical case`, `Annotated image`, `Timeline`, `Paper highlight`, `Video poster`, `Survey`, `Priorities`, `References`, `Thanks, collage`, `Thanks, message`). Then run `breathe-inline`: an inserted layout shows no background until then. Keep `data-type`, `data-id`, `data-title`, `data-slide-type` and the inline `background-color` of each `<article>`; `.slide-foot-page` holds the slide position.

## Airway stages

The `<article>` class `med-bg-<preset>-s<N>` picks the background picture: panels, ice facets and the airway line across the top. `s0` before the pathway (cover, disclosure, outline), `s1` to `s4` the current stage (solid up to station N, ring at N), `s5` pathway complete (conclusion, references, thanks). Stations at x 190, 397, 603, 810; rail at y 34.

| Preset | Panels | Use |
|---|---|---|
| `cover` | navy 0..600, ice right | cover (s0) |
| `side` | navy 0..300, ice | disclosure, survey, priorities |
| `split` | ice left half, navy right half | key figures (count on ice, alarm on navy) |
| `deep` / `ice` / `white` | navy / ice / white | deep statement, light statement, table, card, references |
| `image` | white, navy panel 540..960 x 0..430 | content with picture, clinical case |
| `compare` | white band, ice left, navy right | compare |
| `dark` | deep navy | clinical image, annotated image, video |
| `divider` | navy band with the watermark (s1 to s4) | section dividers |
| `track` | ice, airway zoomed at y 300 (s0, s5) | outline, timeline |
| `thanks` | navy, airway ending in a bronchial fan (s5) | thanks |

Rail label (a metro stop on the line): `<span class="med-rail-label med-on-ice" style="left:206px" aria-hidden="true"><b>01</b>Stage</span>`, `left` = station x + 16; stage 4 uses `style="right:166px"`; `med-on-ice`, `med-on-white`, `med-on-navy`, or `med-on-navy med-on-dark` on dark slides. The botanical logo (cover, thanks) and the stethoscope watermark (dividers) never share a slide.

## Icons

`<i class="med-ico med-ico-<glyph>-<variant> med-s52"></i>`, sizes `med-s22` to `med-s88`. Glyphs: `lungs scope microscope coins people clock map cap check hospital mail pin search chart doc shield`. Variants: `ring` (light), `solid` (light), `dark` (navy), `done` / `now` / `todo` (tracker stations, 88 px). New glyph: `tools/breathe_assets.py`, then `make breathe-assets`; `make breathe-assets ARGS=--list` prints the catalogue.

## Sizing (1 px = 1 pt in the PPTX)

Title `.med-title` 34 px, 2 lines max, it states the message. Cover key phrase 62 px, about 16 characters. Divider number, title, question 140 / 54 / 22 px. Statement 40 px, 3 lines. Big number `.med-num` 128 px (`.med-md` 104), 5 to 6 characters. Check item 20 px, 4 items of 2 lines. Takeaway `.med-take` 22 px, 2 lines. Table cell 19 px (`.med-compact` 17), 4 rows by 4 columns. Picture on the navy panel 372 px wide. Shorten the text before reducing a size.

## Lint rules

Rows `.med-bleed`, `.med-figs-deep`, `.med-prio-row` (and the medical rows) give every child a `w-*` class (L008). A slide with an `<img>`, other than `title` and `thanks`, has a non empty `.med-source` (L009). Foreign: `cds-*`, `tag-*`, `stat-*`, `ei-*`, and the medical structure `med-band`, `med-rule`, `med-head`, `med-foot`, `slide-body`, `slide-h1`, `slide-eyebrow` (L007). No hex colour in `style=""` outside the palette (L011); `#FFFFFF` surfaces are fine.

## Pictures and notes

A real picture is `<img data-asset="photo.jpg" src="" alt="...">` with its `.med-source`; decoration is a class. `breathe-inline` searches the deck's `assets/` folder, then the catalogue shipped with the editor; names are plain file names. Linked files (`--link`) are served by the editor next to the deck. Speech goes in `<aside data-role="speaker-notes">`, direct child of the slide, blank lines between paragraphs; open items as `TO CONFIRM` lines, never on the slide. Patient pictures follow `mcp-htmleditor skill --type medical-sources`.

## Export

The PPTX is painted from the rendered slides: background picture full bleed, boxes and icons at their place, every text an editable text box with the browser's line breaks, notes on the notes pages. It needs Chromium (`make install-browser`); without it the export still completes, flowed over the background pictures, with the warning `Deck exported without the rendered finish (...)`. Text boxes do not rewrap in PowerPoint: edit the HTML and export again. Tables become native PowerPoint tables. Insert a video over its poster in PowerPoint. Check the PPTX itself: `soffice --headless --convert-to pdf talk.pptx` then look at every page (LibreOffice substitutes Georgia and Trebuchet MS; PowerPoint is the reference).

Reference: templates/reference/slides/breathe.html
