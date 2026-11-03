# US-0043: Charter rules L007 to L011

> Spec: SPEC-0007 (sdlc/specs/SPEC-0007-agent-editing-tools/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0042
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Adds the charter rules to `lint`: foreign classes, medical width classes, medical source lines, remote images (all file types) and palette warnings.

## Requirements covered

- SPEC-0007/FR-NEW-012 (partial: the exit status and report forms exercised on charter rules and warnings): WHEN an agent or a user runs `lint` on a file THE Editor SHALL report every problem found and a verdict, and exit with status 1 when at least one problem is an error.
- SPEC-0007/FR-NEW-014: WHEN `lint` runs on a presentation THE Editor SHALL apply these charter rules.

## Independent Test

`make test ARGS='-k deck_lint_charter'`: `lint` on DECK-MED with a `cds-tile` div in `slide-2` prints `error L007 slide-2 class "cds-tile" belongs to another charter than medical` and exits 1; DECK-EI with one remote image prints `warning L010 ...` and `lint: OK (0 errors, 1 warning)` with exit 0.

## Design excerpt

### Decisions
- DEC-008 (SPEC-0007): rule functions per scope, ordered by code. "L007: one problem per distinct foreign class per slide, first occurrence order. L008: one per offending child. L010: one per remote `img`."
- DEC-006 (SPEC-0007): rule groups key on the presentation charters `ei`, `carbon`, `medical` from `deck.charter`.
- DEC-017 (SPEC-0007): "E2E-009 holds on the generated deck with the real EI bootstrap CSS and cover (checked: the EI bootstrap slide has no inline hex colour and no foreign class)"; DECK-EI stays clean with these rules active.
- Interpretation chosen: the charter name in the L007 and L011 messages is the charter key (`medical`, `ei`, `carbon`).

### Data model
Same Problem shape as US-0042. L007/L008/L009 severity `error`; L010/L011 severity `warning`.

### Contracts
```python
# deck/charter_rules.py
def foreign_class_problems(slide: Tag, charter: str) -> list[tuple[str, str]]    # (code, message)
def charter_problems(slide: Tag, charter: str) -> list[tuple[str, str, str]]     # (code, severity, message)
def remote_image_problems(scope: Tag) -> list[str]                                # messages for L010
```
`lint_deck` (US-0042) gains: per slide of a presentation the charter rules L007 to L011 of its charter; for every file type the L010 rule (for a file that is not a presentation its slide column is `-` and lint emits no other code; in a presentation an image outside every slide is also reported with slide `-`).

| Code | Severity | Rule | Message |
|---|---|---|---|
| L007 | error | a class belongs to another charter | `class "cds-tile" belongs to another charter than medical` |
| L008 | error | a child of a medical flex row has no width class | `child of .med-strip has no w-* width class` |
| L009 | error | a medical slide other than `title` and `thanks` has an image and no non empty `.med-source` | `slide has an image and no source line` |
| L010 | warning | an image source starts with `http://` or `https://` (all file types) | `remote image <url> is not exported` |
| L011 | warning | a colour in a `style` attribute is outside the charter palette, white, black and pure greys excepted | `colour #123456 is not in the medical palette` (colour written as in the file; one problem per distinct colour per slide) |

Business rules:
- Foreign classes. Medical deck: any class starting `cds-`, `tag-`, `stat-`, `ei-`, or equal to `slide-inner`, `slide-header`, `slide-footer`, `slide-foot`, `slide-foot-logo`, `slide-foot-title`. Euro-Information deck: any class starting `med-`, `stat-`, `cw-`, `mention-`, or equal to `slide-header`, `slide-footer`. Carbon deck: any class starting `med-`, or equal to `slide-inner`, `slide-foot`, `slide-foot-logo`, `slide-foot-title`, `slide-foot-page`, `slide-title-rule`. Classes are read from the `class` attribute of every element of the slide (the slide itself included); one problem per distinct class per slide, in first occurrence order.
- Medical flex rows: elements with class `.med-strip`, `.med-split`, `.med-cols`, `.med-compare`, `.med-steps`, `.med-stats`, `.med-timeline`, `.med-section-figs`; accepted width classes `w-25`, `w-30`, `w-33`, `w-40`, `w-50`, `w-60`, `w-70`; every direct child element without one gives one L008 whose message names the row class (`.med-strip`, ...).
- L009: medical slides only; `data-slide-type` `title` and `thanks` are exempt; "an image" is any `img` in the slide; a source line is a `.med-source` element with non blank text.
- L010: `src` of `img` elements only, `http://` or `https://` (scheme compared case insensitively), the url shown as written.
- Palettes (hex, compared case insensitively after expanding a 3 digit colour to 6): Euro-Information `#003A8D #284AAA #285C99 #FBAE40 #EC6962 #50565B #262626 #F4F6F9`; Carbon `#0F62FE #0043CE #EDF5FF #161616 #F4F4F4 #E0E0E0 #525252 #198038 #DA1E28`; medical `#159984 #0F6F60 #EE5A02 #E9EDEE #F5F7F8 #D7DEE2 #252525 #3A3A3A #5D5D5D #3D85C6 #C81E3A #0F2E4C #0B0E11 #14181D #2A323B #E8EDF2 #9AA7B4 #4FC3D9 #F2A33C`. White (`#FFFFFF`), black (`#000000`) and pure greys (R=G=B) are always accepted. `rgb()`, `var(...)` and colour names are ignored. The check covers the `style` attribute of any element of a slide (not `<style>` blocks). The hex colours are found with the regex `#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])`.
- Ordering inside a slide: by code (L005 .. L011 after the structure rules), as DEC-008.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck/charter_rules.py` | create: foreign classes, flex rows, palettes, rules L007 to L011 |
| `src/mcp_htmleditor/deck/lint.py` | modify: register the charter rules and L010 for every file type |
| `tests/deck_support.py` | modify: add mutators `replace_in_slide`, `add_style` |
| `tests/test_deck_lint_charter.py` | create |

### Existing patterns
- `src/mcp_htmleditor/deck/lint.py` (US-0042) rule tables and `Problem`.
- `skill/types/slides.md` and `skill/types/medical.md` (prose source of the class tables and palettes).
- `templates/bootstrap/slides-medical-empty.html` and `templates/reference/slides/medical.html` (real class usage).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures (generated by `tests/deck_support.py` from the real `templates/bootstrap/*.html`, never committed; no clock, `os.utime(path, (1_000_000_000, 1_000_000_000))` to force modification times):
- DECK-EI: an Euro-Information presentation (real EI bootstrap CSS and cover), no inline colour outside the Euro-Information palette, no remote image, no template text, consistent counters, 8 slides titled `Couverture`, `Sommaire`, `Contexte`, `Besoins`, `Architecture`, `Planning`, `Risques`, `Merci`, ids `slide-0` to `slide-7`; slide 3 holds a 1 500 character `data:image/png;base64` image; slides 1 to 6 carry eyebrow `Cat · Slide 0N / 08` (N = index + 1) and page element N (`.slide-foot-page`, so slides 1 to 6 hold 2 to 7); slide 7 is a section slide without foot; `const TOTAL = 8;` and `const slideNames = [ ... ];` consistent.
- DECK-CARBON: a Carbon presentation of 5 slides titled `Intro`, `Offre`, `Chiffres`, `Plan`, `Fin`, eyebrow `Section · Slide 0N / 05`, footers `Slide 1 / 5` to `Slide 5 / 5` (`.slide-footer-right`), TOTAL 5, slideNames 5 entries.
- DECK-MED: a medical presentation of 6 slides: cover (`data-slide-type="title"`) then content slides with `.med-strip` children carrying `w-50`, a tiny PNG, a non empty `.med-source`, `.slide-foot-page`.
- DOC-PERSO: `document-perso-empty.html` with the article body replaced by `h1.doc-title` "Rapport", `h1.doc-h1` "Contexte", `h2.doc-h2` "Périmètre", `h1.doc-h1` "Risques".

Mutators added to `tests/deck_support.py`: `replace_in_slide(html, slide_index, old, new)`, `add_style(html, slide_index, style_fragment)`.

### SPEC-0007/E2E-021: Foreign class
- Level E2E; Driver CLI; Location `tests/test_deck_lint_charter.py`
- Given DECK-MED where slide `slide-2` holds `<div class="cds-tile">`
- When the user runs `lint`
- Then the output holds `error L007 slide-2 class "cds-tile" belongs to another charter than medical`

### SPEC-0007/E2E-022: Missing width class
- Level E2E; Driver CLI; Location `tests/test_deck_lint_charter.py`
- Given DECK-MED where `slide-3` has a `.med-strip` whose second child has no `w-*` class
- When the user runs `lint`
- Then the output holds `error L008 slide-3 child of .med-strip has no w-* width class`

### SPEC-0007/E2E-026: Exit status
- Level E2E; Driver CLI; Location `tests/test_deck_lint_charter.py`
- Given DECK-EI with one warning only (a remote image `https://example.com/a.png` in `slide-2`) and DECK-EI with one error (the TOTAL constant set to 7)
- When the user runs `lint` on each
- Then the first prints `lint: OK (0 errors, 1 warning)` and exits 0; the second ends with `lint: FAIL (1 error, 0 warnings)` and exits 1
- And `lint --json` on the second prints `{"problems":[...],"errors":1,"warnings":0}` with `slide` null for a whole file problem

### SPEC-0007/E2E-035: Image without source
- Level E2E; Driver CLI; Location `tests/test_deck_lint_charter.py`
- Given DECK-MED where `slide-1` of type `content` holds an image and an empty source element, and `slide-0` (type `title`) holds a logo image and no source
- When the user runs `lint`
- Then the output holds `error L009 slide-1 slide has an image and no source line` and no problem for `slide-0`

### SPEC-0007/E2E-037: Palette warning
- Level E2E; Driver CLI; Location `tests/test_deck_lint_charter.py`
- Given DECK-MED where `slide-2` holds `style="color:#123456"` and another element `style="color:#159984; background:#FFFFFF; border-color:#777777"`
- When the user runs `lint`
- Then the output holds exactly one palette warning: `warning L011 slide-2 colour #123456 is not in the medical palette`

### Additional tests (same file)
- Foreign class tables: for each charter, one class per prefix and per exact name is flagged (for example `stat-card`, `ei-doc-head` on medical; `med-list`, `cw-bar`, `mention-pill`, `slide-header` on ei; `med-band`, `slide-inner`, `slide-title-rule` on carbon) and classes of the charter itself are not (`slide-foot-page` on ei and medical, `slide-header` on carbon); two uses of the same foreign class in one slide give one problem.
- L008: three children without width in one `.med-strip` give three problems; a `.med-split` child with `w-60` passes; `w-45` is not an accepted class.
- L009: a `thanks` slide with an image and no source passes; `.med-source` with only whitespace fails; a slide without image passes.
- L010: `<img src="HTTP://x/a.png">` is flagged; `<img src="data:image/png;base64,AAAA">` and a relative path are not; on DOC-PERSO with a remote image: the report has one line `warning L010 - remote image https://example.com/a.png is not exported` and no other code, and `lint: OK (0 errors, 1 warning)`.
- L011: `#ABC` expands to `#AABBCC` (outside the ei palette, flagged and shown as written `#ABC`); `#fbae40` in an ei deck is accepted; `rgb(1,2,3)`, `var(--x)` and `red` are ignored; `#000`, `#fff` and `#808080` are accepted; the same colour on two elements of one slide gives one warning; a `<style>` block with a foreign colour gives none; the palette name in the message follows the charter (`ei`, `carbon`, `medical`).
- DECK-EI, DECK-CARBON and DECK-MED stay `lint: OK (0 errors, 0 warnings)` with all rules active (non regression of E2E-009).

## Constraints

- Files not to touch: `src/mcp_htmleditor/deck/patch.py`, `src/mcp_htmleditor/cli.py`, `src/mcp_htmleditor/mcp_server.py`.
- Dependencies not to add: none.
- Patterns to avoid: duplicating the palette in more than one module; scanning `<style>` blocks; one problem per occurrence for L007/L011 (it is per distinct value per slide).
- Scope boundary: no wiring into outline or patch (US-0044).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: US-0042 tests unchanged (including the clean DECK-EI report).
- [ ] Docs updated: none beyond code docstrings (consolidated in US-0046).
- [ ] Self review: full at tier 2.
- [ ] This story registers no MCP tool; `skill/core.md` is not touched.
- [ ] One commit `US-0043: Charter rules L007 to L011`, body `Spec: SPEC-0007` and the requirement ids FR-NEW-012, FR-NEW-014.
