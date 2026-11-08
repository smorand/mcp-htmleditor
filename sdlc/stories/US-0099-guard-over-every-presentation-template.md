# US-0099: Guard over every presentation template

> Spec: SPEC-0016 (sdlc/specs/SPEC-0016-reference-decks-and-editor-residues/)
> Nature: BUG
> Priority: P2
> Depends on: US-0098
> min_tier: 2
> Files touched: 2
> Closes spec: no

## Objective

The fullscreen rule of `AGENTS.md` was enforced for the medical bootstrap only, so five decks broke it unnoticed.
After this story `make test` discovers every presentation file under `templates/` when it runs and fails, naming the
file and the missing marker, as soon as one lacks a building block, today's eleven files and any added later.

## Requirements covered

- SPEC-0016/BR-009: Each of the five decks SHALL contain a `:fullscreen` CSS rule, one element with `id="btn-present"` whose activation calls `enterPresentation()`, and script functions named `enterPresentation`, `exitPresentation` and `updateFullscreenScale`.
- SPEC-0016/BR-016: IF an HTML file under `templates/` has `data-doc-type="presentation"` on its `<html>` and lacks one of the five markers of BR-009 THEN `make test` and `make check` SHALL fail with a message naming the file's path and the missing marker.

Business rules (spec, verbatim): "the set of files is discovered when the tests run, so a file added later is checked
without editing the test; installed copies outside the repository are not checked."

## Independent Test

`make test ARGS='-k presentation_templates_fullscreen'`: eleven guard cases pass on the repository; the `tmp_path`
case fails the guard function for `reference/slides/x.html` with the five markers; the evidence run on c507194
(BT-004) fails naming the five decks.

## Design excerpt

### Decisions
- DEC-011 (SPEC-0016): "The guard is a parametrized test over `presentation_files(TEMPLATES_ROOT)` collected at import (one case per file, id = path relative to `templates/`), plus a test of the two pure functions on a `tmp_path` copy of `templates/` holding one more marker less file (BT-021), plus a BeautifulSoup check that each of the five decks' `#btn-present` has `onclick=\"enterPresentation()\"` (BT-016). The discovered set is asserted to contain the eleven files of E17, not to equal it, so a later template needs no test edit. BT-004 is gate evidence: the guard run in a worktree of c507194 (`git worktree add`), its failing output kept in `.implement/US-0099-red.log`."

### Contracts
`tests/test_presentation_templates_fullscreen.py` (new):

```python
TEMPLATES_ROOT = Path(__file__).resolve().parents[1] / "templates"
MARKERS = (":fullscreen", 'id="btn-present"', "enterPresentation", "exitPresentation", "updateFullscreenScale")
HTML_TAG = re.compile(r"<html\b[^>]*>", re.IGNORECASE)


def presentation_files(root: Path) -> list[Path]:
    """Every templates/**/*.html whose first <html ...> tag holds data-doc-type="presentation", sorted."""


def missing_markers(html: str) -> list[str]:
    """MARKERS absent from the text, in MARKERS order."""
```

Assertion message per file: `f"{path.relative_to(root)}: missing {', '.join(missing)}"`.

The eleven files of today (E17): bootstraps `slides-empty.html`, `slides-ei-empty.html`, `slides-medical-empty.html`;
reference decks `euro-information.html`, `medical.html`, `example-medical-complete.html`, `ibm-carbon.html`,
`example-ei-complete.html`, `example-carbon-complete.html`, `presentation-standard.html`, `roadmap-one-pager.html`
(all under `templates/bootstrap/` or `templates/reference/slides/`).

### Paths
| Path | Action |
|---|---|
| `tests/test_presentation_templates_fullscreen.py` | create |
| `sdlc/constitution.md` | modify: the fullscreen rule's "Enforced by" becomes `tests/test_presentation_templates_fullscreen.py` (every presentation file under `templates/`), the BL-0007 violation note removed |

### Existing patterns
- The medical only check this generalizes: `tests/test_medical_template.py:86` `test_medical_bootstrap_ships_fullscreen_support` (kept).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Location `tests/test_presentation_templates_fullscreen.py`.

### SPEC-0016/BT-004: The guard catches a deck without the building blocks
- Level / Driver: gate evidence; `make test` in a worktree of c507194 holding this story's test file
- Given `git worktree add /tmp/us0099-c507194 c507194`, the new test file copied in, the five decks left as they were
- When `make test ARGS='-k presentation_templates_fullscreen'` runs there
- Then it fails, and its output names each of `reference/slides/ibm-carbon.html`, `reference/slides/example-ei-complete.html`, `reference/slides/example-carbon-complete.html`, `reference/slides/presentation-standard.html`, `reference/slides/roadmap-one-pager.html` with the marker `:fullscreen`
- Recorded: the output in `.implement/US-0099-red.log`; the worktree removed afterwards (`git worktree remove`).

### SPEC-0016/BT-016: Building blocks of the five decks
- Given each of the five decks
- Then its text contains `:fullscreen`, `id="btn-present"`, `enterPresentation`, `exitPresentation` and `updateFullscreenScale`, and BeautifulSoup finds exactly one element with `id="btn-present"`, whose `onclick` is `enterPresentation()` (the click behavior is asserted by BT-003, US-0097 and US-0098)

### SPEC-0016/BT-021: Guard over every presentation template
- Given the repository's `templates/`
- Then the guard passes on every file with `data-doc-type="presentation"` (the discovered set contains the eleven files above) and skips the others (no `data-doc-type="document"` or `"website"` file is in the set)
- Given a copy of `templates/` under `tmp_path` with one more file `reference/slides/x.html` holding `<html data-doc-type="presentation">` and a single `<section data-type="slide">`, no marker
- Then `presentation_files` of the copy contains `x.html`, and `missing_markers` of it equals the five markers; the message built for it reads `reference/slides/x.html: missing :fullscreen, id="btn-present", enterPresentation, exitPresentation, updateFullscreenScale`

## Constraints

- Files not to touch: every template (they comply after US-0097 and US-0098), `tests/test_medical_template.py`.
- Dependencies not to add: none.
- Patterns to avoid: a fixed list of files to check; reading installed template copies.
- Scope boundary: documentation of the guard in `AGENTS.md` and `.agent_docs/` is US-0101.

## Definition of done

- [ ] RED evidence: BT-004 output recorded in `.implement/US-0099-red.log`; BT-021's second half red before `missing_markers` exists.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_medical_template.py::test_medical_bootstrap_ships_fullscreen_support` unchanged and green.
- [ ] Self review: full (tier 2).
- [ ] One commit `US-0099: Guard over every presentation template`, body `Spec: SPEC-0016` and BR-009, BR-016.
