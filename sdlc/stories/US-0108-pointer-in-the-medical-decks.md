# US-0108: Pointer in the medical decks

> Spec: SPEC-0017 (sdlc/specs/SPEC-0017-presentation-pointer/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0107
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

The medical decks (the `medical` starting point, `medical.html`, `example-medical-complete.html`) have no pointer.
After this story they carry the three parts, with the medical CSS sync and the PPTX export untouched. Work order
inside SPEC-0017: mechanical, as the Carbon decks.

## Requirements covered

- SPEC-0017/FR-NEW-014 (partial: `slides-medical-empty`, `medical`, `example-medical-complete`): The deck presentation SHALL offer the pointer in every presentation template, the same way opened directly and in the editor.
- SPEC-0017/FR-NEW-013 (partial: the three medical files' PPTX export): The deck presentation SHALL NOT change the PPTX export of a deck, nor show the dot or the ring when the deck is printed.

## Independent Test

`make check-generated` green (`sync_medical_css --check` and `sync_deck_pointer --check`);
`make test ARGS='-k "presentation_templates_fullscreen or golden or medical"'`: the guard checks the three medical
files (out of `PENDING_POINTER`) and passes; golden hashes of the three files unchanged; `tests/test_medical_template.py`
green.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0017): block written by `make sync-deck-pointer`. The block's `<style id="deck-pointer-style">` carries an id, so `tools/sync_medical_css.py` (anchored on a line `<style>` alone, `:31`) keeps copying only the head style.
- DEC-003 (SPEC-0017): the L line `if ((e.key === 'l' || e.key === 'L') && !e.ctrlKey && !e.metaKey && !e.altKey) togglePointer();` in each deck's own key table.
- DEC-009 (SPEC-0017): `.med-band`, `.med-head`, `.med-foot`, `.med-cover-foot`, `.slide-body`, `.slide-foot-page` are in `LAYOUT_AREAS` already.
- DEC-012, DEC-016 (SPEC-0017): nothing inside a slide; remove the three stems from `PENDING_POINTER`.

### Contracts
Shell deck button (5.2), immediately after `#btn-present`, same `class`:
`<button class="<class of #btn-present>" id="btn-pointer" onclick="presentWithPointer()" title="Présenter avec le pointeur (L)" aria-label="Présenter avec le pointeur (L)" style="width:auto;padding:0 12px">Pointeur</button>`
Order: edit the three files (button, L line, markers), `make sync-deck-pointer`, then `make check-generated` must
report every file fresh (the medical CSS check included).

### Paths
| Path | Action |
|---|---|
| `templates/bootstrap/slides-medical-empty.html` | modify: button, L line, block |
| `templates/reference/slides/medical.html` | modify: same |
| `templates/reference/slides/example-medical-complete.html` | modify: same |
| `tests/test_presentation_templates_fullscreen.py` | modify: three stems out of `PENDING_POINTER` |

### Existing patterns
- The three parts in `templates/bootstrap/slides-empty.html` and the Carbon reference decks (US-0106).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

No spec acceptance test is owned here; the medical starting point joins E2E-032 and the three files E2E-029
(US-0109). This story's checks: the guard, `make check-generated`, the golden hashes, `tests/test_medical_template.py`.

## Constraints

- Files not to touch: other templates, golden fixtures, `tools/sync_medical_css.py`, `src/`.
- Dependencies not to add: none.
- Patterns to avoid: putting the block inside the head `<style>`; hand editing the block.
- Scope boundary: stacked decks and the full template sweep are US-0109.

## Definition of done

- [ ] RED evidence: the guard failing on the three stems before the edits, in `.implement/US-0108-red.log`.
- [ ] `make check` green; main stays green after the squash.
- [ ] Non regression: golden hashes, medical CSS sync, `tests/test_medical_template.py` green.
- [ ] Self review: full.
- [ ] One commit `US-0108: Pointer in the medical decks`, body `Spec: SPEC-0017` and FR-NEW-013, FR-NEW-014.
