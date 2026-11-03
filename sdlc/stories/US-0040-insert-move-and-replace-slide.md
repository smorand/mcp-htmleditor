# US-0040: `insert_slide`, `move_slide`, `replace_slide`

> Spec: SPEC-0007 (sdlc/specs/SPEC-0007-agent-editing-tools/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0039
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Completes the five operations of `patch`: insert a slide, move a slide, replace a slide (restoring `data:ref:img-N` images), always with the one pass renumbering of US-0039 and atomic behavior.

## Requirements covered

- SPEC-0007/FR-NEW-005: WHEN a patch holds `{"op":"replace_slide","id":<id>,"html":<html>}` THE Editor SHALL replace that slide by the given HTML after restoring each `data:ref:img-N` to the Nth large image of the replaced slide.
- SPEC-0007/FR-NEW-006: WHEN a patch holds `{"op":"insert_slide","after":<id or "start">,"html":<html>}` THE Editor SHALL insert the given slide after that slide, or first when `after` is `"start"`.
- SPEC-0007/FR-NEW-008: WHEN a patch holds `{"op":"move_slide","id":<id>,"after":<id or "start">}` THE Editor SHALL move that slide after the given slide, or first when `after` is `"start"`.
- SPEC-0007/FR-NEW-009 (partial: triggered by insert, move and replace; the engine is US-0039): WHEN a patch inserts, deletes, moves or replaces a slide THE Editor SHALL renumber the whole presentation once, after all operations.

## Independent Test

`make test ARGS='-k deck_patch_structure'`: inserting the `Budget` slide after `slide-4` of DECK-EI gives 9 slides, the new slide id `slide-5`, eyebrow `Slide 06 / 09`, page element `6`, former `Planning` `slide-6` with page `7`, `TOTAL` 9, `slideNames` 9 entries with `"Budget"` at index 5; a replace round trip of `get-slide` output keeps the 1 500 character image byte for byte (compared with the original file text, not with the product output).

## Design excerpt

### Decisions
- DEC-004 (SPEC-0007): "Placement details the spec leaves open: delete removes `pre` and the slide...; insert after writes `"\n" + lead + html` right after the reference atom (CRLF if the reference's `pre` is CRLF); insert at `start` writes `html + "\n" + lead` before the first atom, reusing the first atom's `pre` for the new slide (symmetric result, no blank line); move to `start` does the same."
- DEC-003 (SPEC-0007): atoms and the id map: "Each id designates a slide of the original file, and that id stays valid for as long as the slide is in the working copy, including after it is moved or replaced."
- DEC-019 (SPEC-0007): "`replace_slide` restores [image references] by the same ordering on the replaced slide's current text."
- DEC-005 (SPEC-0007): one renumber pass after all operations (US-0039).
- DEC-016 (SPEC-0007): a file with zero slides gives the reason `operation "<op>" needs a presentation`.

### Data model
No new JSON shape. Operations as in US-0038. An `Atom` gains `touched = True` for replaced or inserted slides (used by US-0044).

### Contracts
Operations (FR-NEW-005, 006, 008 business rules):
- `{"op":"replace_slide","id":<id>,"html":<html>}`: the `html` is one slide element carrying `data-type="slide"` and a `data-id` (non empty). Reasons in check order: `unknown slide id "<id>"`, `slide html must have data-type="slide" and a data-id`, `unknown image reference "data:ref:img-3"`. Each token `data:ref:img-N` found in the html (regex `data:ref:img-(\d+)`) is replaced by the full `src` value of the Nth large image (data address longer than 1 000 characters, N from 1, document order) of the replaced slide's current text in the working copy; if N exceeds the count (or N is 0) the reason names the token as written. The result is written verbatim (only renumbering edits it afterwards): `replace_slide` substitutes exactly the slide's byte range, leading whitespace untouched.
- `{"op":"insert_slide","after":<id or "start">,"html":<html>}`: same html rule; `data:ref:img-N` is not allowed (reason `unknown image reference "data:ref:img-1"` naming the first token found). Reasons in check order: `unknown slide id "<id>"` (for `after`), html shape, image reference. After the closing tag of the reference slide it writes a newline, the leading whitespace of the reference slide (`lead`, i.e. its `pre` without the leading line break; `\r\n` when the reference's `pre` uses CRLF), then the html. For `start`: before the first slide, the new slide takes the first slide's `pre`, then the html is followed by a newline and the first slide's `lead` (no blank line, symmetric result). The inserted slide cannot be designated by later operations of the same patch; a `data-id` inside the html is ignored for designation.
- `{"op":"move_slide","id":<id>,"after":<id or "start">}`: reason `unknown slide id "<id>"` (for `id` first, then `after`). The range moves with its leading whitespace (`pre`) to right after the closing tag of the reference slide; `start` follows the insert at `start` placement (moved slide takes the first slide's `pre`, the old first slide gets `"\n" + lead`). Comments and other raw segments between slides stay where they are. `after` equal to its own `id` leaves the slide unchanged.
- HTML validity check: parse the fragment with BeautifulSoup `html.parser`; exactly one top level element (whitespace and comments ignored around it) with attribute `data-type="slide"` and a non empty `data-id`.
- Any operation may designate by an original id a slide moved or replaced earlier in the same patch; a slide deleted earlier gives `unknown slide id "<id>"`.
- After all operations the renumbering pass of US-0039 runs once; `slides` in the result is the count after.
- US-0038's reason `operation "<op>" is not supported yet` no longer exists for any operation after this story.

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck/patch.py` | modify: add the three operations, html validation, image reference restore |
| `tests/deck_support.py` | modify: add `slide_html` |
| `tests/test_deck_patch_structure.py` | create |
| `AGENTS.md` | modify: index entry for the `deck/` package and the agent editing doc |
| `.agent_docs/testing.md` | modify: files table rows and the fixtures and byte identity helper description |

### Existing patterns
- `src/mcp_htmleditor/deck/patch.py` (US-0038 and US-0039): `Working` list, atoms, `renumber_edits` call.
- `src/mcp_htmleditor/deck/scan.py` (US-0036): `large_images`, `hide_images`, `slide_range`.
- Browser insertion: `src/mcp_htmleditor/static/slide-layouts.js` and `editor.js:1490-1603` (observable renumber rules only).
- Test layout: `tests/test_deck_patch.py` (US-0038) for CLI invocation style.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures (generated by `tests/deck_support.py` from the real `templates/bootstrap/*.html`, never committed; no clock, `os.utime(path, (1_000_000_000, 1_000_000_000))` to force modification times):
- DECK-EI: an Euro-Information presentation (real EI bootstrap CSS and cover), no inline colour outside the Euro-Information palette, no remote image, no template text, consistent counters, 8 slides titled `Couverture`, `Sommaire`, `Contexte`, `Besoins`, `Architecture`, `Planning`, `Risques`, `Merci`, ids `slide-0` to `slide-7`; slide 3 holds a 1 500 character `data:image/png;base64` image; slides 1 to 6 carry eyebrow `Cat · Slide 0N / 08` (N = index + 1) and page element N (`.slide-foot-page`, so slides 1 to 6 hold 2 to 7); slide 7 is a section slide without foot; `const TOTAL = 8;` and `const slideNames = [ ... ];` consistent.
- DECK-CARBON: a Carbon presentation of 5 slides titled `Intro`, `Offre`, `Chiffres`, `Plan`, `Fin`, eyebrow `Section · Slide 0N / 05`, footers `Slide 1 / 5` to `Slide 5 / 5` (`.slide-footer-right`), TOTAL 5, slideNames 5 entries.
- DECK-MED: a medical presentation of 6 slides: cover (`data-slide-type="title"`) then content slides with `.med-strip` children carrying `w-50`, a tiny PNG, a non empty `.med-source`, `.slide-foot-page`.
- DOC-PERSO: `document-perso-empty.html` with the article body replaced by `h1.doc-title` "Rapport", `h1.doc-h1` "Contexte", `h2.doc-h2` "Périmètre", `h1.doc-h1` "Risques".

Fixture helper added to `tests/deck_support.py`: `slide_html(charter, title, *, eyebrow="Slide 01 / 01", page="1", data_title=None, extra="") -> str` returns one valid, lint clean slide element for `ei` (`<article class="slide" data-type="slide" data-id="x" data-slide-type="content" data-title=...>` with `.slide-inner`, `.slide-eyebrow`, `.slide-h1`, `.slide-foot` with `.slide-foot-page`) or for `carbon` (`.slide-header`, `.slide-eyebrow`, `.slide-h1`, `.slide-footer` with `.slide-footer-right`), no inline colour, no foreign class, no template text.

### SPEC-0007/E2E-005: Insert in the middle
- Level E2E; Driver CLI; Location `tests/test_deck_patch_structure.py`
- Given DECK-EI and an HTML slide with `data-type="slide"`, `data-id="x"`, `data-title="Budget"`, eyebrow `Slide 01 / 01` and a page element holding `1`
- When the agent patches `[{"op":"insert_slide","after":"slide-4","html":<that slide>}]`
- Then the file has 9 slides; the new slide has id and `data-id` `slide-5`, eyebrow `Slide 06 / 09` and page element `6`
- And the former `Planning` is `slide-6` with page element `7`; the total constant is 9; the slide names list has 9 entries with `"Budget"` at index 5
- And the result `slides` is 9

### SPEC-0007/E2E-007: Move
- Level E2E; Driver CLI; Location `tests/test_deck_patch_structure.py`
- Given DECK-CARBON
- When the agent patches `[{"op":"move_slide","id":"slide-4","after":"slide-0"}]`
- Then the order is `Intro`, `Fin`, `Offre`, `Chiffres`, `Plan` with ids `slide-0` to `slide-4` and footers `Slide 1 / 5` to `Slide 5 / 5`

### SPEC-0007/E2E-008: Replace keeping the image
- Level E2E; Driver CLI; Location `tests/test_deck_patch_structure.py`
- Given DECK-EI and the HTML returned by `get_slide` for `slide-3`, where the title is changed to `Architecture cible`
- When the agent patches `[{"op":"replace_slide","id":"slide-3","html":<that html>}]`
- Then slide 3 shows `Architecture cible` and still holds the original 1 500 character image, byte for byte

### SPEC-0007/E2E-014: Mixed operations are atomic
- Level E2E; Driver CLI; Location `tests/test_deck_patch_structure.py`
- Given DECK-CARBON, saved copy kept
- When the agent patches `[{"op":"delete_slide","id":"slide-1"},{"op":"move_slide","id":"slide-2","after":"slide-7"}]`
- Then it fails with `patch failed at operation 2: unknown slide id "slide-7" (nothing written)` and the file equals the saved copy

### SPEC-0007/E2E-017: Replacement without required attributes
- Level E2E; Driver CLI; Location `tests/test_deck_patch_structure.py`
- Given DECK-EI
- When the agent patches `replace_slide` on `slide-2` with `<article><h1>x</h1></article>`, and `insert_slide` after `slide-2` with the same HTML
- Then each fails with `patch failed at operation 1: slide html must have data-type="slide" and a data-id (nothing written)`

### SPEC-0007/E2E-018: Unknown image reference
- Level E2E; Driver CLI; Location `tests/test_deck_patch_structure.py`
- Given DECK-EI (slide 3 has one large image)
- When the agent patches `replace_slide` on `slide-3` with a valid slide holding `data:ref:img-3`, and `insert_slide` with a valid slide holding `data:ref:img-1`
- Then the first fails with `patch failed at operation 1: unknown image reference "data:ref:img-3" (nothing written)` and the second with `patch failed at operation 1: unknown image reference "data:ref:img-1" (nothing written)`

### SPEC-0007/E2E-029: Insert at both ends and move to the ends
- Level E2E; Driver CLI; Location `tests/test_deck_patch_structure.py`
- Given DECK-CARBON
- When the agent, each time on a fresh copy of DECK-CARBON, inserts a valid slide titled `Début` with `after` `"start"`, then inserts `Fin 2` after `slide-4`, then moves `slide-2` with `after` `"start"`
- Then after the first run the order starts `Début`, `Intro` with footers `Slide 1 / 6`, `Slide 2 / 6`; after the second the last slide is `Fin 2` with footer `Slide 6 / 6`; after the third `Chiffres` is first

### SPEC-0007/E2E-030: Titles with special characters
- Level E2E; Driver CLI; Location `tests/test_deck_patch_structure.py`
- Given DECK-EI and a valid slide whose attribute is `data-title="Café &amp; &quot;Co&quot; &lt;1&gt;"`
- When the agent inserts it after `slide-1`
- Then the slide names list holds the entry `"Café & \"Co\" <1>"`, the attribute in the HTML is unchanged
- And the file has no problem that `lint` would report for L001 to L006: asserted here with independent checks written in the test (all nine slides carry `data-type`, `data-id`, `data-title`; ids `slide-0` to `slide-8` in order; `TOTAL` 9; `slideNames` has 9 entries; every eyebrow and page counter equals its expected value). The literal `lint` command is not available before US-0042; US-0042 re-asserts this clause through `lint` (test `test_lint_clean_after_special_title_insert` in `tests/test_deck_lint.py`).

### Additional tests (same file)
- Byte splice per operation on a hand built file with 3 slides indented by 4 spaces and an HTML comment between slide 1 and slide 2: insert after slide 0 yields `</article>\n    <article` (indentation of the reference); the comment stays where it was; delete (US-0039) unaffected; move of slide 2 to after slide 0 moves the slide range with its indentation and leaves the comment in place.
- Same file with CRLF line ends: inserted text uses `\r\n` and the lead of the reference.
- Insert at `start` of a file: the result has exactly one line break between the new slide and the old first slide, no blank line, and the new slide has the old first slide's indentation.
- `move_slide` with `after` equal to its own id: result `changed` false, file untouched, mtime unchanged.
- An operation naming a slide deleted earlier: `delete_slide` slide-1 then `replace_slide` slide-1 gives `patch failed at operation 2: unknown slide id "slide-1" (nothing written)`.
- Moved then referenced by original id: `move_slide` slide-4 after slide-0, then `set_text` on `slide-4` `.slide-h1` edits `Fin`, not the slide now at index 4.
- Replace with a slide holding two references `data:ref:img-1` in one slide restores both; a replacement without images on a slide that had a large image removes the image (no error).
- `get_slide` then `replace_slide` without editing yields `changed` false for a consistent file (idempotent: html identical after restore, renumber edits empty).
- Operations on DOC-PERSO still give `needs a presentation` for the five names.

## Constraints

- Files not to touch: `src/mcp_htmleditor/deck/renumber.py` (read only), `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/mcp_server.py`, `src/mcp_htmleditor/cli.py`.
- Dependencies not to add: none.
- Patterns to avoid: serializing with BeautifulSoup (parse only to validate the fragment); renumbering the inserted html before the final pass; stdout in `deck/`.
- Scope boundary: lint problems in the patch result (US-0044); tool (US-0041).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: US-0035 to US-0039 tests unchanged.
- [ ] Docs updated: `AGENTS.md` index (deck package, `.agent_docs/agent-editing.md`); `.agent_docs/testing.md` (new test files, fixtures, `assert_only_region_changed`, `slide_html`, `os.utime` rule).
- [ ] Self review: full at tier 2.
- [ ] This story registers no MCP tool; `skill/core.md` is not touched.
- [ ] One commit `US-0040: `insert_slide`, `move_slide`, `replace_slide``, body `Spec: SPEC-0007` and the requirement ids FR-NEW-005, FR-NEW-006, FR-NEW-008, FR-NEW-009.
