# US-0154: no opt in, non regression and documentation

> Spec: SPEC-0026 (sdlc/specs/SPEC-0026-pictures-outside-deck-folder/)
> Nature: BUG
> Priority: P2
> Depends on: US-0151, US-0152, US-0153
> min_tier: 2
> Files touched: 4
> Closes spec: yes

## Objective
Prove that nothing allows an outside read, that pictures inside the folder export exactly as before on every path, and document the rule. This story closes SPEC-0026: its full acceptance set must be green.

## Requirements covered
- SPEC-0026/BR-008 [EARS-UB]: The product SHALL NOT offer a setting, flag or option that lets an export or the render read a picture outside the deck's folder.
- Every other requirement of SPEC-0026 is covered by US-0150 to US-0153; the closing audit checks them all (BR-001 to BR-007).

## Independent Test
`make test ARGS='tests/test_outside_nonregression.py'` is green, then `make check` is green, and every SPEC-0026 test id (BT-001, BT-010 to BT-017, BT-020 to BT-023, BT-030 to BT-032) is green.

## Design excerpt
### Decisions
- DEC-008: no setting, no CLI option; `Settings` and the `export` and `render` options stay as they are.
### Paths
| Path | Action |
|---|---|
| `tests/test_outside_nonregression.py` | create |
| `README.md` | modify (a short note under export and render: pictures outside the deck's folder are refused with the warning) |
| `AGENTS.md` | modify (one line in essential conventions) |
| `.agent_docs/architecture.md` | modify (module map: `deck_folder.py`; export pipeline and render: where the rule applies) |
Check `skill/topics/` for a topic that states picture rules for export (`rg -n "picture|image" skill/topics/*.md | rg -i export`) and update it only if it describes where pictures may live; `mcp-htmleditor skill-audit` must still pass.
### Existing patterns
`--help` of the click commands: `run_cli("export", "pptx", "--help")` (`tests/deck_support.py:244`).

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.
All in `tests/test_outside_nonregression.py`.

### SPEC-0026/BT-022: no setting to allow outside reads
- Level / Driver: functional / CLI `--help`
- Given the `export pptx`, `export docx` and `render` commands
- When their `--help` output is read
- Then the options lists equal the ones recorded in the test (written from today's `--help`) and none mentions picture folders or outside access; and `Settings` has no field whose name contains `picture` or `outside`

### SPEC-0026/BT-030: pictures inside the folder
- Level / Driver: functional / direct call and CLI, `needs_chromium` for the painted and render parts
- Given `tmp/deck/` with `local.png`, `media/a.png`, and slides naming `local.png`, `media/a.png`, `<tmp>/deck/local.png`, `file://<tmp>/deck/media/a.png`
- When exported to PPTX (flow, `paint=False`), to PPTX (painted) and to DOCX, and rendered
- Then the PPTX flow export embeds 3 pictures (the `file://` address is not understood by the flow export, as today, with the existing `Image introuvable, ignoree` warning), the painted PPTX embeds 4, the DOCX embeds 4, and the render has no `did not load` line

### SPEC-0026/BT-031: Chromium keeps loading in folder resources
- Level / Driver: functional / CLI `render`, `needs_chromium`
- Given a deck with `<link rel="stylesheet" href="theme.css">` (a rule setting the slide background to blue) and `<img src="media/a.png">` (a red PNG), both inside the deck folder
- When rendered
- Then the picture shows its pixels (red in its box) and the slide background is blue (pixel read)

### SPEC-0026/BT-032: the web library mode
- Level / Driver: non regression
- Then `tests/test_export_pptx_library.py` and the `tests/test_library_*` files, unchanged, pass

## Constraints
- Files not to touch: source files of US-0150 to US-0153 (this story changes no behavior).
- Dependencies not to add: none.
- Scope boundary: nothing new beyond tests and documentation.

## Definition of done
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit.
- [ ] Spec converge: every test of SPEC-0026 green (BT-001, BT-010 to BT-017, BT-020 to BT-023, BT-030 to BT-032), and every requirement BR-001 to BR-008 cited by at least one story with status done or landed.
- [ ] Docs updated: `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`; `mcp-htmleditor skill-audit` passes.
- [ ] Self review: no source behavior changed in this story.
- [ ] One commit `US-0154: no opt in, non regression and documentation` on the work branch, body with `Summary:`, `Spec: SPEC-0026` and the requirement ids.
