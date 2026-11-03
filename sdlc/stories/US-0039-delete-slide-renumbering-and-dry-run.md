# US-0039: `delete_slide`, renumbering, dry run

> Spec: SPEC-0007 (sdlc/specs/SPEC-0007-agent-editing-tools/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0038
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Adds `delete_slide` to `patch`, the one pass renumbering of ids, total, names and counters, the last slide protection, and proves the dry run writes nothing.

## Requirements covered

- SPEC-0007/FR-NEW-007: WHEN a patch holds `{"op":"delete_slide","id":<id>}` THE Editor SHALL remove that slide.
- SPEC-0007/FR-NEW-009 (partial: renumbering engine and its trigger by `delete_slide`; insert, move and replace reuse it in US-0040): WHEN a patch inserts, deletes, moves or replaces a slide THE Editor SHALL renumber the whole presentation once, after all operations.
- SPEC-0007/FR-NEW-010: WHEN a patch is run with `--dry-run` (or `dry_run` true) THE Editor SHALL validate and compute the result and SHALL write nothing.

## Independent Test

`make test ARGS='-k deck_patch_delete'`: `patch DECK-CARBON --ops -` with `[{"op":"delete_slide","id":"slide-1"}]` leaves 4 slides titled `Intro`, `Chiffres`, `Plan`, `Fin`, ids `slide-0` to `slide-3` and footers `Slide 1 / 4` to `Slide 4 / 4`; the same patch with `--dry-run` prints `"dry_run":true` and the file bytes and mtime are unchanged. Counters are checked by a regex helper in the test, independent of the renumber code.

## Design excerpt

### Decisions
- DEC-005 (SPEC-0007): "Renumbering is one pass: scan the assembled text, enumerate slides with `find_slides`, compute an edit list, drop edits whose replacement equals the current bytes, apply from the end. `id` and `data-id` are always set (added when missing), the `active` class is toggled as `editor.js` does, counters follow the charter..., the eyebrow keeps its text and only the pattern `Slide <n> / <total>` is replaced, `TOTAL` only changes its digits, `slideNames` is rewritten one entry per line with the first entry's indentation and a trailing comma, titles escaped for quotes, backslashes and newlines."
- DEC-004 (SPEC-0007) (delete part): "delete removes `pre` and the slide (the preceding line break goes, so after deleting the last slide `…</article>\n  </div>` is intact)".
- DEC-003 (SPEC-0007): atoms with `pre`; deleting an atom drops its `pre` too.
- Approach 2.2 A: edits computed on the assembled text with one scan; renumber after all operations, not after each (operations designate original ids).
- DEC-010 / DEC-011: single atomic write, flag only around the write.

### Data model
No new JSON shape. Internal frozen dataclass `Edit(start, end, text)`.

### Contracts
```python
# deck/renumber.py
@dataclass(frozen=True, slots=True)
class Edit: start: int; end: int; text: str
def renumber_edits(text: str) -> list[Edit]      # non overlapping edits, applied from the end backwards
```
`delete_slide` in `deck/patch.py`: `{"op":"delete_slide","id":<id>}` removes the slide's byte range from its opening `<article` tag to its closing tag, together with its line break and leading whitespace (`pre`). Reasons: `unknown slide id "<id>"` (also for an id deleted earlier in the same patch) and `cannot delete the last slide` (when the working copy has exactly one slide). Result keys as in US-0038; `changed` true; `slides` = count after.
Dry run (FR-NEW-010): validate and compute the full result, write nothing; the result is the one a real run gives plus `"dry_run":true`; errors identical to a real run. The dry run of a patch that would only fail still fails identically.
The `--dry-run` command line flag and `dry_run` parameter exist since US-0038; this story adds the tests on structural operations.

Renumbering rules (FR-NEW-009 business rules, all of them):
- A slide is an element with `data-type="slide"`, otherwise an `article.slide` or `section.slide` (outermost only), enumerated with `find_slides` on the assembled text.
- Slide ids and `data-id` become `slide-0`, `slide-1`, ... in order; both attributes are set unconditionally (added when missing, inserted right after the tag name's first attribute run, i.e. appended before the closing `>` of the start tag, `id` first then `data-id`).
- The class `active` is removed from every slide and added once to the first slide, keeping the other classes and their order (a slide with no `class` attribute gets none unless it is the first, which gets `class="active"`).
- Slide total constant `const TOTAL = <integer>;` in a script: only the numeric literal is replaced by the number of slides. Slide names list `const slideNames = [ ... ];`: rewritten with one entry per line, indented like the first existing entry, a trailing comma after each entry, the closing `];` on its own line with the indentation of the `const` line; each entry is the `data-title` of the slide in order (entities decoded) as a double quoted string with `\` and `"` escaped (and a newline written `\n`), accents kept. If the script holds no total constant or no slide names list, nothing is created. `slideNames.forEach` and other uses are not matched.
- In every slide eyebrow (the first `.slide-eyebrow` of the slide) the pattern `Slide <n> / <total>` becomes `Slide 0N / TT` (two digits each, `%02d`); text around the pattern is kept; an eyebrow without the pattern is left as is.
- In a Carbon deck the first `.slide-footer-right` pattern `Slide <n> / <total>` becomes `Slide N / TT` (no zero padding). In an Euro-Information or medical deck the first `.slide-foot-page` content becomes N. N is the 1 based position, TT the total. Only these elements are read or rewritten; an absent element is not created.
- Charter for the counter kind: from `deck.charter` (`carbon` footer; `ei` and `medical` page element).
- Idempotence: an edit whose replacement equals the current bytes is dropped, so an already consistent file yields no edit and stays byte identical.
- A `set_text` alone triggers no renumbering; renumbering runs once on the assembled text after all operations, only if the patch contained a structural operation (insert, delete, move, replace).

### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck/renumber.py` | create: `Edit`, `renumber_edits` |
| `src/mcp_htmleditor/deck/patch.py` | modify: `delete_slide`, renumber pass, atoms removal |
| `tests/test_deck_patch_delete.py` | create |
| `.agent_docs/agent-editing.md` | modify: renumbering rules and idempotence |

### Existing patterns
- `src/mcp_htmleditor/static/editor.js:1562-1603` browser renumbering (sets `slide.id` and `data-id` unconditionally, toggles `active`): this story reproduces its observable rules.
- `templates/bootstrap/slides-empty.html:336-338` slideNames layout (two space indent, trailing comma).
- `src/mcp_htmleditor/deck/patch.py` (US-0038) `Working` list and `apply_patch` flow.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures (generated by `tests/deck_support.py` from the real `templates/bootstrap/*.html`, never committed; no clock, `os.utime(path, (1_000_000_000, 1_000_000_000))` to force modification times):
- DECK-EI: an Euro-Information presentation (real EI bootstrap CSS and cover), no inline colour outside the Euro-Information palette, no remote image, no template text, consistent counters, 8 slides titled `Couverture`, `Sommaire`, `Contexte`, `Besoins`, `Architecture`, `Planning`, `Risques`, `Merci`, ids `slide-0` to `slide-7`; slide 3 holds a 1 500 character `data:image/png;base64` image; slides 1 to 6 carry eyebrow `Cat · Slide 0N / 08` (N = index + 1) and page element N (`.slide-foot-page`, so slides 1 to 6 hold 2 to 7); slide 7 is a section slide without foot; `const TOTAL = 8;` and `const slideNames = [ ... ];` consistent.
- DECK-CARBON: a Carbon presentation of 5 slides titled `Intro`, `Offre`, `Chiffres`, `Plan`, `Fin`, eyebrow `Section · Slide 0N / 05`, footers `Slide 1 / 5` to `Slide 5 / 5` (`.slide-footer-right`), TOTAL 5, slideNames 5 entries.
- DECK-MED: a medical presentation of 6 slides: cover (`data-slide-type="title"`) then content slides with `.med-strip` children carrying `w-50`, a tiny PNG, a non empty `.med-source`, `.slide-foot-page`.
- DOC-PERSO: `document-perso-empty.html` with the article body replaced by `h1.doc-title` "Rapport", `h1.doc-h1` "Contexte", `h2.doc-h2` "Périmètre", `h1.doc-h1` "Risques".

Test helper note: counters are verified with plain regexes written in the test (`Slide 0(\d) / 0(\d)` etc.), never with product code.

### SPEC-0007/E2E-006: Delete on a Carbon deck
- Level E2E; Driver CLI; Location `tests/test_deck_patch_delete.py`
- Given DECK-CARBON
- When the agent patches `[{"op":"delete_slide","id":"slide-1"}]`
- Then the file has 4 slides titled `Intro`, `Chiffres`, `Plan`, `Fin` with ids `slide-0` to `slide-3`
- And the footers read `Slide 1 / 4` to `Slide 4 / 4` and eyebrow counters use `Slide 0N / 04`

### SPEC-0007/E2E-013: Unknown id writes nothing
- Level E2E; Driver service + CLI; Location `tests/test_deck_patch_delete.py`
- Given DECK-EI, saved copy kept
- When the agent patches `[{"op":"set_text","id":"slide-1","selector":".slide-h1","text":"A"},{"op":"delete_slide","id":"slide-9"}]`, and again with `dry_run` true
- Then both calls fail with `patch failed at operation 2: unknown slide id "slide-9" (nothing written)`
- And the file equals the saved copy, and `set_text` with the selector `.nope` on `slide-1` fails with `patch failed at operation 1: selector ".nope" matches no element in slide "slide-1" (nothing written)`
- (The "again with dry_run true" is driven through `apply_patch(..., dry_run=True)`; the CLI path uses `--dry-run`.)

### SPEC-0007/E2E-019: Last slide
- Level E2E; Driver CLI; Location `tests/test_deck_patch_delete.py`
- Given a presentation of one slide (`build_deck("carbon", ["Seul"])`)
- When the agent patches `delete_slide` on `slide-0`
- Then it fails with `patch failed at operation 1: cannot delete the last slide (nothing written)`

### SPEC-0007/E2E-032: Dry run
- Level E2E; Driver CLI; Location `tests/test_deck_patch_delete.py`
- Given DECK-CARBON, saved copy kept
- When the agent patches `[{"op":"delete_slide","id":"slide-1"}]` with `dry_run` true
- Then the result is `{"ok":true,"changed":true,"slides":4,"problems":[],"dry_run":true}` and the file equals the saved copy, modification time unchanged (forced with `os.utime` before)

### Additional tests (same file)
- Renumber table, Carbon: deleting `slide-1` of DECK-CARBON gives `Section · Slide 02 / 04` on the second slide and footer `Slide 2 / 4`; `const TOTAL = 4;`; `slideNames` has four entries, one per line, same indent as the first original entry, trailing commas.
- Renumber table, EI: deleting `slide-1` of DECK-EI gives 7 slides, old `Contexte` becomes `slide-1` with eyebrow `Cat · Slide 02 / 07` and page element `2`; `TOTAL` 7. The section slide without foot gets no page element created.
- Renumber table, medical: deleting `slide-2` of DECK-MED renumbers `.slide-foot-page` to the new positions and eyebrow to `Slide 0N / 05`.
- `active`: a file whose slide 0 has `class="slide active"` and slide 2 has `class="slide active extra"` ends with `active` only on the first slide and `extra` kept on the other.
- `data-id` and `id` missing on a slide are added by the renumber pass.
- Escaping: a slide with `data-title="A &quot;b&quot; \ c"` yields the entry `"A \"b\" \\ c"` in `slideNames`.
- A deck whose script has no `TOTAL` and no `slideNames`: the patch succeeds and no constant is created.
- Idempotence: `renumber_edits(text)` returns `[]` on DECK-EI, DECK-CARBON and DECK-MED as generated; a delete followed by `renumber_edits` of the result returns `[]`.
- Bytes outside the removed slide and the counters are identical (prefix/suffix check around the touched regions, comment between slides kept in place).
- `delete_slide` of an id already deleted earlier in the same patch: `patch failed at operation 2: unknown slide id "slide-1" (nothing written)`.
- Deleting the last slide of the list (`slide-7` of DECK-EI) keeps `…</article>\n  </div>` intact (the text following the removed slide is unchanged).

## Constraints

- Files not to touch: `src/mcp_htmleditor/static/*`, `src/mcp_htmleditor/http_server.py`, `src/mcp_htmleditor/mcp_server.py`.
- Dependencies not to add: none.
- Patterns to avoid: renumbering after each operation; serializing with BeautifulSoup; creating counters or constants that do not exist; stdout in `deck/`.
- Scope boundary: no insert, move or replace (US-0040); `cli.py` is not touched (the `--dry-run` flag exists since US-0038).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: US-0035, US-0036 and US-0038 tests unchanged; the browser renumbering in `editor.js` untouched.
- [ ] Docs updated: `.agent_docs/agent-editing.md` renumbering rules, idempotence, engine rules.
- [ ] Self review: full at tier 2.
- [ ] This story registers no MCP tool; `skill/core.md` is not touched.
- [ ] One commit `US-0039: `delete_slide`, renumbering, dry run`, body `Spec: SPEC-0007` and the requirement ids FR-NEW-007, FR-NEW-009, FR-NEW-010.
