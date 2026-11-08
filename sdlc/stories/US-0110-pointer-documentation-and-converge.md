# US-0110: Pointer documentation and converge

> Spec: SPEC-0017 (sdlc/specs/SPEC-0017-presentation-pointer/)
> Nature: FEAT
> Priority: P3
> Depends on: US-0109
> min_tier: 2
> Files touched: 5
> Closes spec: yes

## Objective

Neither the person (README) nor the agent (skill) can learn that the pointer exists. This story writes one sentence
in each, records the conventions and the new make target for maintainers, then proves the whole SPEC-0017
acceptance set and the gate's run time.

## Requirements covered

- SPEC-0017/FR-NEW-014 (documentation, NFR 7.6): The deck presentation SHALL offer the pointer in every presentation template, the same way opened directly and in the editor.

NFR 7.6 (spec, verbatim): "The README section on presenting and the agent guidance topic on slides each state, in
one sentence, the L key, the Pointeur control, the click that rings a box, that the pointer starts off and that it
never reaches the file."

## Independent Test

`make test ARGS='-k skill_shipped'`: E2E-034 red before the two sentences, green after; `mcp-htmleditor skill-audit`
exits 0 (topic budget 8000 bytes); then `make check` green with the test step at most 330 s.

## Design excerpt

### Decisions
- DEC-020 (SPEC-0017): "`README.md` gains a `### Presenting` section (presenting, F, Escape, keys, and the pointer sentence of NFR 7.6); `skill/topics/slides-carbon.md` gains one French sentence of at most 300 bytes (467 bytes free under the 8000 byte topic budget); the sentence names L, `Pointeur`, the click that rings a box, the pointer starting off, and that nothing of it reaches the file."
- DEC-018 (SPEC-0017): "the SPEC-0017 browser tests take at most 40 s in total ... the closing story proves the `make check` test step stays at most 330 s (SPEC-0014/BT-022), re running once above 330 s at a load above 30 before trimming."

### Contracts
README sentence (English, no dash), for example: "While presenting full screen, press L or start with the
**Pointeur** button beside the present button to turn the mouse into a red dot; a click rings the box under it
(a tile, a table, else the headline or paragraph); the pointer starts off at every presentation and nothing of it
is ever written to the file."
Skill sentence (French, no dash), for example: "En présentation plein écran, L (ou le bouton Pointeur à côté de
Présenter) remplace le curseur par un point rouge et un clic entoure le bloc visé; le pointeur démarre éteint et
rien n'est écrit dans le fichier."
The test checks words, not the exact sentence: in one sentence (split on `. ` and line ends) of each text,
`L`, `Pointeur`, a click word (`click`/`clic`), a ring word (`ring`/`entoure`), a start off word (`starts off`/`démarre éteint`)
and a file word (`file`/`fichier`).

### Paths
| Path | Action |
|---|---|
| `README.md` | modify: new `### Presenting` section under the usage part |
| `skill/topics/slides-carbon.md` | modify: one sentence |
| `tests/test_skill_shipped.py` | modify: E2E-034 |
| `AGENTS.md` | modify: the fullscreen convention bullet gains the pointer (three parts per presentation template, `make sync-deck-pointer`, the guard) |
| `.agent_docs/html-conventions.md`, `.agent_docs/testing.md`, `.agent_docs/architecture.md`, `sdlc/constitution.md` | modify: pointer block and its sync, `LAYOUT_AREAS`, the editor relay and save strip, the four `test_pointer_*` modules and their budget, the guard row, dated entry with the measured test step |

Files touched counts the four code or test files plus the documentation group as one.

### Existing patterns
- Skill output in a child process with `HTMLEDITOR_SKILL_DIR` on the repository `skill/`: `tests/test_skill_shipped.py`.
- `tests/data/skill_anchors.json` lists strings that must stay in each topic: add the sentence's `Pointeur` anchor to `slides-carbon`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0017/E2E-034: Documentation states the pointer
- Level / Driver / Location: functional; README read and child process `mcp-htmleditor skill --type slides-carbon`; `tests/test_skill_shipped.py`
- Given the README and the agent guidance topic on slides as shipped
- When the operator reads the presenting section of each
- Then each holds one sentence naming the L key, the `Pointeur` control, the click that rings a box, the pointer starting off, and that nothing of it reaches the file

## Constraints

- Files not to touch: templates, `src/`, other skill topics (the `create` topic has 13 bytes free).
- Dependencies not to add: none.
- Patterns to avoid: em or en dashes in any text; growing `slides-carbon.md` past 8000 bytes.
- Scope boundary: none left after this story.

## Definition of done

- [ ] RED evidence for E2E-034, in `.implement/US-0110-red.log`.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Closes spec: the full SPEC-0017 acceptance set green (E2E-001 to E2E-039, by `make test ARGS='-k "pointer or presentation_templates_fullscreen or skill_shipped"'`), and every requirement FR-NEW-001 to FR-NEW-014 cited by at least one story with status done or landed.
- [ ] Run time: the SPEC-0017 browser tests at most 40 s together, the `make check` test step at most 330 s (load average recorded).
- [ ] Docs updated: the files above; `mcp-htmleditor skill-audit` exits 0.
- [ ] Self review: full.
- [ ] One commit `US-0110: Pointer documentation and converge`, body `Spec: SPEC-0017` and FR-NEW-014.
