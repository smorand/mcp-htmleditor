# US-0107: Pointer in the EI decks

> Spec: SPEC-0017 (sdlc/specs/SPEC-0017-presentation-pointer/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0106
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

The Euro-Information decks (the `ei` starting point, generated from `euro-information.html`, and
`example-ei-complete.html`) have no pointer. After this story they carry it, and on an EI content slide the white
inner frame and the footer with its page number are never ringed while a paragraph is. Work order inside SPEC-0017:
the three parts as in the Carbon decks, the starting point regenerated, one browser test.

## Requirements covered

- SPEC-0017/FR-NEW-014 (partial: `euro-information`, `slides-ei-empty`, `example-ei-complete`): The deck presentation SHALL offer the pointer in every presentation template, the same way opened directly and in the editor.
- SPEC-0017/FR-NEW-005 (partial: the EI layout areas): WHEN the presenter clicks or taps the current slide while the pointer is on THE deck presentation SHALL ring the box the click lands in.
- SPEC-0017/FR-NEW-013 (partial: the three EI files' PPTX export): The deck presentation SHALL NOT change the PPTX export of a deck, nor show the dot or the ring when the deck is printed.

Business rule (spec FR-NEW-005, verbatim): "The slide's own layout areas, never a box by rule 3, are, in every
template: the area holding the eyebrow, headline, rule and subtitle; the body area; the footer or foot band with its
page number; the grey top band; and the inner frame surrounding the content. Whatever sits inside these areas is
judged on its own by rules 1 to 6."

## Independent Test

`make check-generated` reports the three EI files fresh (`gen_ei_bootstrap --check` and `sync_deck_pointer --check`);
`make test ARGS='-k "pointer_templates or presentation_templates_fullscreen or golden"'`: E2E-036 red before (the
`ei` deck has no pointer), green after; golden hashes of the three EI files unchanged.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0017): block written by `make sync-deck-pointer`; then `make bootstrap-ei` regenerates `slides-ei-empty.html` from the reference, which copies the block unchanged; both checks agree.
- DEC-003 (SPEC-0017): the L line `if ((e.key === 'l' || e.key === 'L') && !e.ctrlKey && !e.metaKey && !e.altKey) togglePointer();` in each deck's own key table.
- DEC-008, DEC-009 (SPEC-0017): `.slide-inner`, `.slide-foot`, `.slide-foot-page` are in `LAYOUT_AREAS`; rule 4 never returns a layout area, the page number being part of its footer.
- DEC-012 (SPEC-0017): nothing added inside a slide; golden data never regenerated.
- DEC-016 (SPEC-0017): remove `euro-information`, `slides-ei-empty`, `example-ei-complete` from `PENDING_POINTER`.
- DEC-017 (SPEC-0017): `tests/test_pointer_templates_e2e.py`, one module page at 1600 × 900; served through `serve_deck`.

### Contracts
Shell deck button (5.2), immediately after `#btn-present`, same `class`:
`<button class="<class of #btn-present>" id="btn-pointer" onclick="presentWithPointer()" title="Présenter avec le pointeur (L)" aria-label="Présenter avec le pointeur (L)" style="width:auto;padding:0 12px">Pointeur</button>`
Order: edit `euro-information.html` and `example-ei-complete.html` (button, L line, markers), `make sync-deck-pointer`,
`make bootstrap-ei`; never edit `slides-ei-empty.html` by hand.

### Paths
| Path | Action |
|---|---|
| `templates/reference/slides/euro-information.html` | modify: button, L line, block |
| `templates/reference/slides/example-ei-complete.html` | modify: same |
| `templates/bootstrap/slides-ei-empty.html` | regenerate (`make bootstrap-ei`) |
| `tests/test_presentation_templates_fullscreen.py` | modify: three stems out of `PENDING_POINTER` |
| `tests/test_pointer_templates_e2e.py` | create: E2E-036, module page |

### Existing patterns
- EI generation: `tools/gen_ei_bootstrap.py`, `Makefile:251`.
- An EI deck built from the bootstrap with extra slides: `tests/deck_support.py` (`deck_ei`).
- Served deck test with the editor's present control: `tests/test_pointer_served_e2e.py` (US-0103, US-0104).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0017/E2E-036: Layout areas of the EI starting point are not boxes
- Level / Driver / Location: functional e2e; Playwright, editor page; `tests/test_pointer_templates_e2e.py`
- Given a deck created from the `ei` starting point with one content slide holding a paragraph `EI paragraph` and no tile, served, presented, pointer on
- When the presenter clicks an empty spot of the white inner frame, then the footer's page number, then `EI paragraph`
- Then no ring shows after the first two clicks; after the third only `EI paragraph` is ringed

## Constraints

- Files not to touch: Carbon, medical and stacked templates; golden fixtures; `src/`.
- Dependencies not to add: none.
- Patterns to avoid: hand editing the block or the generated bootstrap; changing `LAYOUT_AREAS` (it is shared; a needed change goes back to the source block and a re-sync, and must keep E2E-007 and E2E-010 green).
- Scope boundary: medical and stacked decks are US-0108 and US-0109.

## Definition of done

- [ ] RED evidence for E2E-036 and the guard on the three EI stems, in `.implement/US-0107-red.log`.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: golden hashes of the three EI files unchanged; SPEC-0016 presenting tests of `example-ei-complete` green; `tools/check_ei_insert.py` behavior unchanged.
- [ ] Durations reported (`make test ARGS='-k pointer_templates --durations=0'`).
- [ ] Self review: full.
- [ ] One commit `US-0107: Pointer in the EI decks`, body `Spec: SPEC-0017` and FR-NEW-005, FR-NEW-013, FR-NEW-014.
