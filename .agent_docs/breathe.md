# Breathe template (SPEC-0023)

Congress template of Dr Lamya CHRIF MORAND, direction B "Editorial, airway as a story line". Authoring rules for
agents: `skill/topics/breathe.md`. Spec and design: `sdlc/specs/SPEC-0023-breathe-template/`.

## Map

| Piece | Where |
|---|---|
| Key, marker, detection rule `is_breathe(declared, css)` | `src/mcp_htmleditor/export/charters.py` |
| Deck charter, export theme | `deck/__init__.py` `_presentation_charter`, `export/pptx_style.py` `detect_theme`, `THEME_BREATHE` |
| Picker detection and set | `static/slide-layouts.js` `detectTemplate`, generated block `breathe-layouts:begin/end` |
| Lint tables | `deck/charter_rules.py` (`BREATHE` in `FOREIGN_CLASSES`, `PALETTES`, `CHARTER_FLEX_ROWS`, `SOURCE_CHARTERS`) |
| Embedding command | `breathe/inline.py`, CLI `breathe-inline` |
| Painted PPTX | `export/pptx_paint.py`, called at the end of `to_pptx._build_pptx`; degraded chrome `pptx_chrome._chrome_breathe` |
| Files next to the deck | `deck_files.py`, `http_server._serve_deck_file` |
| Catalogue and generator | `templates/assets/breathe/` (git LFS), `tools/breathe_assets.py` (`make breathe-assets`) |
| Shipped decks | `templates/bootstrap/slides-breathe-empty.html`, `templates/reference/slides/breathe.html` |
| Sync | `tools/sync_breathe_layouts.py` (`make sync-breathe-layouts`, in `make check-generated`) |

## Rules

- The page declaration wins: `breathe` is Breathe, `medical` is medical whatever the styles hold; otherwise the
  marker `--breathe-ice` in the `<style>` outside comments. Never write the marker in a comment of a shipped file
  (2026-11-14: a comment made a medical deck Breathe; `is_breathe` now strips comments).
- Breathe keeps the `med-*` classes and `--med-*` tokens of the layouts (DEC-002): a deck switches with one attribute.
- Decoration is pictures set by class (`med-bg-<preset>-s<N>`, `med-ico-<glyph>-<variant>`), rules between
  `/* breathe:assets:begin */` and `/* breathe:assets:end */`; a real picture is `<img data-asset="name">`.
- Edit the reference deck, never `LAYOUT_SETS.breathe`; then `make sync-breathe-layouts`. It also re-embeds the
  shipped decks from the catalogue (through a temporary copy: `breathe-inline` refuses template files).
- The catalogue is stored with git LFS: clone with `git lfs install`, else its files are pointers and `make install`
  copies pointers.
- The generator is byte for byte the source one (2026-11-14: all 158 files equal `_template/breathe/assets`).

## Gotchas (2026-11-14)

- `SHOW_SLIDE_JS` (render) hides the other slides with an inline `display:none !important`, then gives the target an
  inline `display:block` when it computes `none`. Run slide after slide in one page, the next slide keeps that inline
  block instead of its own `flex`: pushed (`margin-top:auto`) and centred content moves up. The painter clears the
  inline `display` before each show (`UNHIDE_JS`); the reference geometry test fails without it. The render's
  `--report-only` measures slides the same way: its overflow numbers on flex slides may be off (not fixed here).
- Playwright's sync API refuses a thread holding an asyncio loop: the painter measures in its own worker thread,
  tests that open their own browser next to a `page` fixture do the same.
- A data URI holds `;` (`data:image/png;base64,`): the declaration parser splits on it, so `_chrome_breathe` reads the
  background `url()` with its own pattern from `StyleResolver.stylesheet`.
- The painter keeps the browser's line breaks (no wrap) and widens text boxes by 8 % (centred boxes on both sides):
  editing a long line in PowerPoint does not rewrap it.
- Painted geometry is checked against an independent Chromium measure of the picture content boxes (borders are
  painted as rectangles), within 1 point.
- LibreOffice previews substitute Georgia and Trebuchet MS; PowerPoint (AppleScript, sandboxed container folder
  `~/Library/Containers/com.microsoft.Powerpoint/Data/`) is the reference renderer for evidence.
