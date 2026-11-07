# US-0093: Agent side, guidance lines and documentation

> Spec: SPEC-0015 (sdlc/specs/SPEC-0015-text-max-width-handle/)
> Nature: FEAT
> Priority: P2
> Depends on: US-0092
> min_tier: 2
> Files touched: 4 (plus 5 documentation files)
> Closes spec: yes

## Objective

The agent reads a width the author set as a plain `max-width:Npx` declaration, its lint reports exactly the same
problems as before, and its guidance tells it the bar exists, what it writes and that the exports ignore it. This
story also documents the feature, proves the whole acceptance set and checks that the gate stays under its run time.

## Requirements covered

- SPEC-0015/FR-NEW-014: The agent tools SHALL show a width set by the author as the `max-width:Npx` declaration in the text's inline style, and the lint SHALL report the same problems before and after a width change.
- SPEC-0015/FR-NEW-015: The agent guidance SHALL hold, in the creating and editing topic under "Ce que l'humain peut faire", line L1, and in the export topic under "Perdu", line L2, both spelled exactly as below.

```text
L1: - Largeur d'un texte: barre sur son bord droit (glisser par pas de 10px, Alt au pixel, flèches; double clic: largeur du modèle). Écrit `max-width:Npx` dans son `style`.
L2: - Le `max-width` d'un texte (barre de largeur de l'éditeur): la zone de texte garde la largeur de son bloc.
```

Business rules (spec, verbatim): "the `L1: ` and `L2: ` prefixes are labels of this spec, not part of the lines. Each
topic stays within its 8000 byte budget and the size audit reports no problem. The core is unchanged: its rule 8
already tells the agent that a human change found in the file is deliberate."

## Independent Test

`make test ARGS='-k width_agent'`: the five tests below pass; `mcp-htmleditor skill --type create` prints L1 verbatim
under `## Ce que l'humain peut faire`, `skill-audit` exits 0, and `get_slide` on slide 2 after a browser drag shows
`color:#123456; max-width:650px`. Then `make check` green with the test step at most 330 s.

## Design excerpt

### Decisions
- DEC-010 (SPEC-0015): "The two guidance lines are added as the last item of their lists; no other topic text changes. Measured budgets leave 13 bytes in `create` after the line, so nothing else may grow that topic in the same story." Measured this run (`skill-audit --json`, rendered topic): `create` 7815 bytes, L1 adds 172 (UTF-8, newline included), 7987 of 8000; `export` 7261, L2 adds 109, 7370.
- Core unchanged: `skill/core.md` sha256 `171b191f41e9b11f0d608caf0255b6f37d07f89e7025a450f61839106660d4dd` (E2E-035 compares it).
- DEC-011 (SPEC-0015): shared module page; the 43 tests of the spec take at most 25 s together; the closing story proves the gate's test step stays at most 330 s (SPEC-0014/BT-022).

### Contracts
Agent side, unchanged and called in process: `mcp_htmleditor.deck.read.get_slide(file, slide_id)` (`deck/read.py:33`,
returns the slide markup), `mcp_htmleditor.deck.lint.lint_file(file)` (`deck/lint.py:96`, returns a report dict whose
problems include the L011 message `colour #123456 is not in the carbon palette`). Command line in a child process:
`[sys.executable, "-m", "mcp_htmleditor", "skill", "--type", "create"]`, `... "export"`, `... "skill-audit"`, with
`HTMLEDITOR_SKILL_DIR` pointing at the repository `skill/` (same driver as `tests/test_skill_shipped.py`).

### Paths
| Path | Action |
|---|---|
| `skill/topics/create.md` | modify: L1 as last item under `## Ce que l'humain peut faire` (after the `Clic droit:` line) |
| `skill/topics/export.md` | modify: L2 as last item under `### Perdu` (after the `Images distantes` line) |
| `tests/width_support.py` | modify only if a helper is shared (the drag helper of US-0089 is reused) |
| `tests/test_width_agent_e2e.py` | create |
| `README.md` | modify: "Visual editor" list, one bullet on the width bar (drag, Alt, arrows, double click, `max-width:Npx`, exports ignore it) |
| `AGENTS.md` | modify: "The editor is twelve classic scripts" becomes thirteen |
| `.agent_docs/html-conventions.md` | modify: "Editor artifacts": the width bar lives in the shell page and never in the framed document, the live preview is suspended around every serialization (`withWidthPreviewSuspended`), a new serialization path must use it; "Undo / redo": a width change is one covered structural step |
| `.agent_docs/architecture.md` | modify: browser side, `editor-width.js` role and its hooks in `editor-edit.js`, `editor-save.js`, `editor-undo.js`, `editor.js` |
| `.agent_docs/testing.md` | modify: the five `tests/test_width_*_e2e.py` files and `tests/width_support.py` (shared module page, `__widthSaves` counter) in the test file map, dated entry |

### Existing patterns
- Skill output in a child process: `tests/test_skill_shipped.py`.
- In process lint: `tests/test_deck_lint_charter.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Location `tests/test_width_agent_e2e.py`.

### SPEC-0015/E2E-028: The agent reads it and lint is unchanged
- Level / Driver: functional e2e; Playwright drag on the shared module page, then `get_slide` and `lint_file` in process
- Given D1, the agent's lint lists `colour #123456 is not in the carbon palette` for slide 2
- When the author drags J's bar 150 pixels left and lets go; the agent reads slide 2 and lints the file
- Then slide 2's markup shows J with style `color:#123456; max-width:650px`; the lint lists exactly the same problems as before, `colour #123456 is not in the carbon palette` included

### SPEC-0015/E2E-029: Creating topic line
- Level / Driver: functional; child process `skill --type create`
- Given the product installed / When the agent runs `mcp-htmleditor skill --type create`
- Then the output holds the FR-NEW-015 creating line verbatim under "Ce que l'humain peut faire" (the line appears after the `## Ce que l'humain peut faire` heading and before the next `## ` heading)

### SPEC-0015/E2E-034: Export topic line
- Level / Driver: functional; child process `skill --type export`
- When the agent runs `mcp-htmleditor skill --type export`
- Then the output holds the FR-NEW-015 export line verbatim under "Perdu" (after `### Perdu`, before the next heading)

### SPEC-0015/E2E-035: Budgets kept
- Level / Driver: functional; child process `skill-audit --json` and a sha256 of `skill/core.md`
- When the agent runs `mcp-htmleditor skill-audit`
- Then it exits 0, the creating and export topics are each at most 8000 bytes, and the core is byte identical to before this increment (sha256 `171b191f41e9b11f0d608caf0255b6f37d07f89e7025a450f61839106660d4dd`)

### SPEC-0015/E2E-041: A width written by the agent in percent
- Level / Driver: functional e2e; Playwright drag, then `get_slide` in process
- Given D1, paragraph P written by the agent with `max-width:50%` (400 pixels in its column)
- When the author drags P's bar 47 pixels right and lets go
- Then P's style reads `max-width:450px`; reading slide 2 the agent sees exactly that

## Constraints

- Files not to touch: `skill/core.md` (byte identical), every other skill topic, editor scripts (the feature is complete after US-0092), Python product modules.
- Dependencies not to add: none.
- Patterns to avoid: shortening another line of `create.md` (not needed: 13 bytes stay free); em or en dashes in any documentation.
- Scope boundary: PPTX and DOCX honouring the width stay deferred to BL-0033.

## Definition of done

- [ ] RED evidence recorded for every new test before the change (E2E-029 and E2E-034 red before the lines exist).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Closes spec: the full acceptance set of SPEC-0015 green (`make test ARGS='-k width'` lists the 43 tests E2E-001 to E2E-043 across the five files, all passed), and every requirement FR-NEW-001 to FR-NEW-015 and NFR-001 to NFR-003 cited by US-0089 to US-0093 with status landed.
- [ ] Run time (SPEC-0014/BT-022): the `make check` test step lasts at most 330 s on an unloaded machine; the summed durations of the five width files are at most 25 s; both recorded in `.implement/US-0093-runtime.log`. Over budget: stop and report, do not drop a test.
- [ ] `mcp-htmleditor skill-audit` exits 0.
- [ ] Docs updated: `README.md`, `AGENTS.md`, `.agent_docs/html-conventions.md`, `.agent_docs/architecture.md`, `.agent_docs/testing.md`.
- [ ] Self review: full (tier 2).
- [ ] One commit `US-0093: Agent side, guidance lines and documentation`, body `Spec: SPEC-0015` and FR-NEW-014, FR-NEW-015.
