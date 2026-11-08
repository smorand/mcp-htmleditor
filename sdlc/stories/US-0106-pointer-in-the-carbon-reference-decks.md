# US-0106: Pointer in the Carbon reference decks

> Spec: SPEC-0017 (sdlc/specs/SPEC-0017-presentation-pointer/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0103, US-0105
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective

The two IBM Carbon reference decks (`ibm-carbon.html`, `example-carbon-complete.html`) present but have no pointer.
After this story each carries the pointer block (written by `make sync-deck-pointer`), a `Pointeur` button right
after its `Présenter` button and the L line in its key table, with a PPTX export byte identical to before. Work order
inside SPEC-0017: mechanical, same three parts as the Carbon starting point.

## Requirements covered

- SPEC-0017/FR-NEW-014 (partial: `ibm-carbon`, `example-carbon-complete`): The deck presentation SHALL offer the pointer in every presentation template, the same way opened directly and in the editor.
- SPEC-0017/FR-NEW-013 (partial: these two decks' PPTX export): The deck presentation SHALL NOT change the PPTX export of a deck, nor show the dot or the ring when the deck is printed.

## Independent Test

`make check-generated` reports both decks fresh; `make test ARGS='-k "presentation_templates_fullscreen or golden or reference_decks_present"'`:
the guard checks both decks (removed from `PENDING_POINTER`) and passes, the golden hashes of `ibm-carbon.html` and the
BT-032 fixture of `example-carbon-complete.html` are unchanged, the SPEC-0016 presenting tests of both decks pass.

## Design excerpt

### Decisions
- DEC-001 (SPEC-0017): the block is written by `make sync-deck-pointer` once the begin and end markers are in the file; never edited by hand.
- DEC-003 (SPEC-0017): the L line in the deck's own key table, under its focus exception: `if ((e.key === 'l' || e.key === 'L') && !e.ctrlKey && !e.metaKey && !e.altKey) togglePointer();`.
- DEC-012 (SPEC-0017): nothing added inside a slide; the golden data is the baseline, never regenerated.
- DEC-016 (SPEC-0017): remove `ibm-carbon` and `example-carbon-complete` from `PENDING_POINTER`.

### Contracts
Shell deck button (5.2), immediately after `#btn-present`, same `class` as `#btn-present`:
`<button class="<class of #btn-present>" id="btn-pointer" onclick="presentWithPointer()" title="Présenter avec le pointeur (L)" aria-label="Présenter avec le pointeur (L)" style="width:auto;padding:0 12px">Pointeur</button>`

Procedure: add `<!-- deck-pointer:begin -->` and `<!-- deck-pointer:end -->` on their own lines right before
`</body>`, run `make sync-deck-pointer`, check `git diff` shows only the three parts.

### Paths
| Path | Action |
|---|---|
| `templates/reference/slides/ibm-carbon.html` | modify: button, L line, block |
| `templates/reference/slides/example-carbon-complete.html` | modify: same |
| `tests/test_presentation_templates_fullscreen.py` | modify: two stems out of `PENDING_POINTER` |

### Existing patterns
- The three parts in `templates/bootstrap/slides-empty.html` (US-0102, US-0103).
- These decks' key table and `#btn-present`: added by SPEC-0016 US-0097.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

No spec acceptance test is owned here; the decks join E2E-029 (US-0109). This story's checks: the guard over both
decks, `make check-generated`, `tests/test_export_golden.py` (`ibm-carbon.html` hashes, `example-carbon-complete`
fixture), `tests/test_reference_decks_present_e2e.py` for both decks.

## Constraints

- Files not to touch: other templates, the golden fixtures, `src/`.
- Dependencies not to add: none.
- Patterns to avoid: hand editing the block; a class added to the button that a CSS class rule targets inside slides.
- Scope boundary: EI, medical and stacked decks are US-0107 to US-0109.

## Definition of done

- [ ] RED evidence: the guard run with the two stems removed from `PENDING_POINTER` before the deck edits, failing with `ibm-carbon: missing pointer`, `ibm-carbon: missing Pointeur control`, `ibm-carbon: missing L key` (and the same for `example-carbon-complete`), in `.implement/US-0106-red.log`.
- [ ] `make check` green; main stays green after the squash.
- [ ] Non regression: golden hashes and the BT-032 fixture unchanged; SPEC-0016 presenting tests green.
- [ ] Self review: full.
- [ ] One commit `US-0106: Pointer in the Carbon reference decks`, body `Spec: SPEC-0017` and FR-NEW-013, FR-NEW-014.
