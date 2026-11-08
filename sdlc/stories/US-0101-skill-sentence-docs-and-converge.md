# US-0101: Skill sentence, documentation and converge

> Spec: SPEC-0016 (sdlc/specs/SPEC-0016-reference-decks-and-editor-residues/)
> Nature: BUG
> Priority: P2
> Depends on: US-0095, US-0096, US-0099, US-0100
> min_tier: 2
> Files touched: 5
> Closes spec: yes

## Objective

The skill still tells agents that `ibm-carbon.html` has no fullscreen CSS, which becomes false once the decks are
fixed. This story corrects that sentence, documents the relay, the vector warnings' place in the conventions, the
stacked deck variant and the guard, then proves the whole SPEC-0016 acceptance set and the gate's run time.

## Requirements covered

- SPEC-0016/BR-021: The shipped skill text SHALL NOT state that `ibm-carbon.html` or any of the five decks lacks fullscreen support or `:fullscreen` CSS.

Business rule (spec, verbatim): "the statement about the 540 px height budget of `ibm-carbon.html` in the same
sentence is true and stays."

## Independent Test

`make test ARGS='-k skill_shipped'`: BT-024 red before the sentence edit, green after; `mcp-htmleditor skill-audit`
exits 0; then `make check` green with the test step at most 330 s.

## Design excerpt

### Decisions
- DEC-013 (SPEC-0016): "BR-021 is one sentence edit and a test in `tests/test_skill_shipped.py` that reads every `skill/topics/*.md`, splits sentences on `. `, `: ` and line ends, and asserts no sentence holding `ibm-carbon` contains `:fullscreen` or `plein écran`, and that `skill --type slides-carbon` output still holds `dépassent 540 px`."
- DEC-014 (SPEC-0016): "the SPEC-0016 browser tests take at most 40 s in total; ... the closing story proves the `make check` test step stays at most 330 s (SPEC-0014/BT-022)."

### Contracts
`skill/topics/slides-carbon.md:96`, before:
``La référence `ibm-carbon.html` est un catalogue autonome, sans CSS `:fullscreen`, dont les slides dépassent 540 px: copier ses composants en respectant le budget 540 px, jamais sa densité ni son modèle de hauteur variable.``
After:
``La référence `ibm-carbon.html` est un catalogue autonome dont les slides dépassent 540 px: copier ses composants en respectant le budget 540 px, jamais sa densité ni son modèle de hauteur variable.``
The topic shrinks; its 8000 byte budget holds.

### Paths
| Path | Action |
|---|---|
| `skill/topics/slides-carbon.md` | modify: the sentence above, nothing else |
| `tests/test_skill_shipped.py` | modify: add BT-024 |
| `AGENTS.md` | modify: the fullscreen convention bullet says the five reference decks comply and `tests/test_presentation_templates_fullscreen.py` enforces it on every presentation file under `templates/` |
| `.agent_docs/html-conventions.md` | modify: § Fullscreen gains the stacked variant (`data-fs-current` only while presenting, `#btn-present` outside every slide, selectors starting with `:fullscreen` so the PPTX resolver ignores them) and the editor relay's `End` |
| `.agent_docs/testing.md` | modify: test file map (`test_reference_decks_present_e2e.py`, `test_presentation_templates_fullscreen.py`, `test_export_pptx_vectors.py`, `test_legacy_arbitrations.py`, relay tests in `test_fullscreen_e2e.py`, the BT-032 fixture), dated entry with the measured test step |

### Existing patterns
- Skill output in a child process with `HTMLEDITOR_SKILL_DIR` on the repository `skill/`: `tests/test_skill_shipped.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0016/BT-024: Skill text no longer states the gap
- Level / Driver / Location: functional; file scan of `skill/topics/*.md` and child process `skill --type slides-carbon` / `tests/test_skill_shipped.py`
- When the shipped skill topics are searched for `ibm-carbon` together with `:fullscreen` or `plein écran` in one sentence
- Then no sentence holds both, and the `skill --type slides-carbon` output still contains `dépassent 540 px` next to `ibm-carbon.html`
- Red before the edit because: `slides-carbon.md:96` holds `ibm-carbon.html` and `sans CSS :fullscreen` in one sentence.

### SPEC-0016/BT-036: Clean save and template scans
- When `tests/test_strip_idempotent.py` and `tests/test_deck_get_slide.py::test_deck_scan_agrees_with_beautifulsoup_on_every_template` run over the fixed templates
- Then they pass unchanged

## Constraints

- Files not to touch: `skill/core.md`, every other topic, every template, every product module.
- Dependencies not to add: none.
- Patterns to avoid: em or en dashes in any documentation; rewording the 540 px clause.
- Scope boundary: BL-0009 (`EditorState.load()`) and BL-0035 stay open.

## Definition of done

- [ ] RED evidence for BT-024 recorded in `.implement/US-0101-red.log`.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Closes spec: the full acceptance set of SPEC-0016 green: BT-001 to BT-004 (BT-004 as the recorded evidence of US-0099), BT-010 to BT-024, BT-030 to BT-036, listed by test name with their file in `.implement/US-0101-converge.md`; and every requirement BR-001 to BR-021 cited by at least one story with status done or landed in `sdlc/stories/_queue.md`.
- [ ] Run time (SPEC-0014/BT-022): the `make check` test step lasts at most 330 s; the SPEC-0016 browser tests at most 40 s in total (DEC-014); both recorded in `.implement/US-0101-converge.md`.
- [ ] `mcp-htmleditor skill-audit` exits 0 (run through `make run ARGS='skill-audit'`).
- [ ] Docs updated: `AGENTS.md`, `.agent_docs/html-conventions.md`, `.agent_docs/testing.md`.
- [ ] Self review: full (tier 2).
- [ ] One commit `US-0101: Skill sentence, documentation and converge`, body `Spec: SPEC-0016` and BR-021.
