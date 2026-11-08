# US-0105: Pointer sync tool and template guard

> Spec: SPEC-0017 (sdlc/specs/SPEC-0017-presentation-pointer/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0102
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Eleven templates must carry the same pointer code, and an operator must learn from the test suite when one lacks
it. This story adds the tool that copies the pointer block from the Carbon starting point into every presentation
template holding the block's markers (its `--check` mode joins `make check-generated`), and extends the template
guard with the three pointer parts and their exact failure lines. Ten templates do not carry the pointer yet: they
sit in a pending set that the next four stories empty.

## Requirements covered

- SPEC-0017/FR-NEW-014 (partial: the guard and its failure lines; the templates follow in US-0106 to US-0109): The deck presentation SHALL offer the pointer in every presentation template, the same way opened directly and in the editor.

Business rule (spec, verbatim): "When a presentation template lacks one of them, the test suite fails and names the
file and what is missing." User visible text: "one failure line per missing part, exactly `<template>: missing
pointer`, `<template>: missing Pointeur control` or `<template>: missing L key`, where `<template>` is the template's
file name without its folder and without `.html` (for example `roadmap-one-pager: missing pointer`, `slides-empty:
missing L key`)."

## Independent Test

`make test ARGS='-k "sync_deck_pointer or presentation_templates_fullscreen"'`: E2E-033 and the tool tests red
before (no function `missing_pointer_lines`, no tool), green after; `make check-generated` green (only the source
holds the block, so nothing is stale).

## Design excerpt

### Decisions
- DEC-001 (SPEC-0017): one block per template synced from `templates/bootstrap/slides-empty.html` by `tools/sync_deck_pointer.py`, checked by `make check-generated`.
- DEC-016 (SPEC-0017): "three markers per discovered presentation file, one failure line per missing part, `f\"{stem}: missing {part}\"`. US-0105 adds `PENDING_POINTER`, the set of stems not yet carrying the pointer (ten), skipped by the pointer check; each template story removes its stems; US-0109 deletes the set and the skip. E2E-033 runs `missing_pointer_lines` on a `tmp_path` copy of `templates/` with `roadmap-one-pager.html` edited three ways (deck-pointer block removed; `#btn-pointer` element removed; L line removed)."

### Contracts
Tool (5.5):
```
python tools/sync_deck_pointer.py           # rewrite the block in every target
python tools/sync_deck_pointer.py --check   # report freshness per target, write nothing, exit 1 when stale
```
Source `templates/bootstrap/slides-empty.html`; block from `<!-- deck-pointer:begin -->` to `<!-- deck-pointer:end -->`
inclusive. Targets: every `templates/**/*.html` whose opening `<html ...>` tag holds `data-doc-type="presentation"`,
holding the begin marker, other than the source. A source without the block: `SystemExit` naming it. A target with a
begin marker and no end marker: `SystemExit` naming it. Output lines through `tools/freshness.py` `report_line`.
A function `sync(root: Path, check: bool) -> int` (exit code) takes the templates root so tests run it on a copy.

Makefile:
```make
## sync-deck-pointer: Copy the presentation pointer block from the Carbon bootstrap to every presentation template
sync-deck-pointer:
	@uv run python tools/sync_deck_pointer.py
```
and `check-generated` gains `uv run python tools/sync_deck_pointer.py --check || rc=1;` before `exit $$rc`.

Guard (5.6), in `tests/test_presentation_templates_fullscreen.py`:
```python
POINTER_PARTS = (("pointer", "function togglePointer("),
                 ("Pointeur control", 'id="btn-pointer"'),
                 ("L key", "e.key === 'l' || e.key === 'L'"))
PENDING_POINTER = frozenset({"ibm-carbon", "example-carbon-complete", "euro-information", "slides-ei-empty",
                             "example-ei-complete", "slides-medical-empty", "medical", "example-medical-complete",
                             "presentation-standard", "roadmap-one-pager"})
def missing_pointer_lines(name: str, html: str) -> list[str]   # f"{name}: missing {part}" per absent marker, POINTER_PARTS order
```
A parametrized test over `presentation_files(TEMPLATES_ROOT)` (existing discovery) asserts
`missing_pointer_lines(path.stem, text) == []` for every stem not in `PENDING_POINTER`; a second test asserts every
stem of `PENDING_POINTER` is a discovered file (no stale name).

### Paths
| Path | Action |
|---|---|
| `tools/sync_deck_pointer.py` | create |
| `Makefile` | modify: `sync-deck-pointer`, `check-generated` |
| `tests/test_sync_deck_pointer.py` | create: tool on a `tmp_path` copy (stale target rewritten, `--check` exit 1 then 0, file without markers untouched, missing source block error) |
| `tests/test_presentation_templates_fullscreen.py` | modify: pointer guard and E2E-033 |

### Existing patterns
- Freshness tool with `--check`: `tools/sync_medical_css.py`, `tools/freshness.py`.
- Guard discovery and `tmp_path` copy: `tests/test_presentation_templates_fullscreen.py` (SPEC-0016 BT-021).
- Freshness tools under test: `tests/test_generated_freshness.py`; the new tool is called in process through `sync(root, check)`.
- The guard drops HTML comments before searching markers (`HTML_COMMENT`, `tests/test_presentation_templates_fullscreen.py:15`): the three pointer markers live in script and markup, never only in a comment.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0017/E2E-033: A template without the pointer fails the suite
- Level / Driver / Location: integration; guard functions on a `tmp_path` copy of `templates/`; `tests/test_presentation_templates_fullscreen.py`
- Given a copy of the templates where the reference deck `roadmap-one-pager` has lost the pointer (the test first writes the three parts into the copy's `roadmap-one-pager.html` when absent, by copying the block from `slides-empty.html` before `</body>`, a `#btn-pointer` button and the L line, so the case does not depend on US-0109; then removes the block)
- When the operator runs the template guard of the test suite on that copy
- Then it fails with the line `roadmap-one-pager: missing pointer`, and passes on the unmodified templates (every file of the real `templates/` outside `PENDING_POINTER` gives no line)
- And on a copy where `roadmap-one-pager` lost only the Pointeur control, it fails with exactly `roadmap-one-pager: missing Pointeur control`, and on one where it lost only the L key, with exactly `roadmap-one-pager: missing L key`

## Constraints

- Files not to touch: the templates (no sync is run in this story), `src/`.
- Dependencies not to add: none.
- Patterns to avoid: a hard coded target list in the tool; regenerating any golden fixture.
- Scope boundary: each template family gets the pointer in US-0106 to US-0109.

## Definition of done

- [ ] RED evidence recorded for E2E-033 and the tool tests, in `.implement/US-0105-red.log`.
- [ ] Every acceptance test above green; `make check` green (check-generated included); main stays green after the squash.
- [ ] Non regression: the five SPEC-0016 markers of the guard still checked unchanged; the EI and medical checks of `make check-generated` still pass.
- [ ] Docs updated: none in this story (US-0110 documents the make target).
- [ ] Self review: full.
- [ ] One commit `US-0105: Pointer sync tool and template guard`, body `Spec: SPEC-0017` and FR-NEW-014.
