# US-0069: Render the checklist in the arch-qa topic output

> Spec: SPEC-0006 (sdlc/specs/SPEC-0006-progressive-skill/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0033
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective

Make `SkillLibrary.topic_output("arch-qa")` return `# Skill topic: arch-qa\n\n` + topic file stripped
+ `\n\n` + checklist stripped (from the injected `read_checklist`) + `\n`, as DEC-019 and design 3 state,
and let `mcp-htmleditor skill --type arch-qa` print the shipped checklist when the user location holds an
empty file or a directory, and a larger user checklist unchanged. An empty checklist raises `NotInstalledError`
(design: "An empty result makes `topic_output("arch-qa")` raise `NotInstalledError`").

## Requirements covered

- SPEC-0006/FR-NEW-002 (partial: the `arch-qa` output contains the checklist read at the time of the call).
- SPEC-0006/FR-NEW-007 (partial: `arch-qa` size measured with the shipped checklist, at most 8 000 bytes).

## Evidence (drift found in US-0033)

- `src/mcp_htmleditor/skill_content.py:92-100`: `topic_output` ignores `self.read_checklist`; `skill --type arch-qa` prints 2 697 bytes, no checklist.
- `sdlc/specs/SPEC-0006-progressive-skill/design.md:101,114-115,251-252` state the injection and the `NotInstalledError`.
- Frozen tests that encode the old behaviour and must be updated as declared here: `tests/test_skill_content.py:67` (`"checklist item" not in --all output`; with the injection the `--all` output of a fixture tree with a checklist includes it, adapt the assertion to the new contract) and `tests/test_skill_shipped.py:60` (`SkillLibrary(SKILL_DIR, lambda: "")` must use `read_shipped_checklist`).

## Acceptance tests

Level: unit plus CLI through `CliRunner`; Driver: pytest; Location: `tests/test_skill_content.py`, `tests/test_arch_checks.py`, `tests/test_skill_shipped.py`.
- `topic_output("arch-qa")` with a fake reader returns topic, one empty line, checklist, one final newline.
- Empty checklist reader: `NotInstalledError`; CLI exit status is the NotInstalled one.
- `skill --type arch-qa` with the user location an empty file, then a directory: output contains the shipped checklist (`2 passes`, `arch-col`), exit 0.
- User checklist non empty and larger than the shipped one: printed unchanged in the output.
- Real shipped tree: `len(topic_output("arch-qa").encode()) <= 8000` via `read_shipped_checklist` (replace the hand built rendering in `tests/test_arch_checks.py`); `skill-audit` item line for `arch-qa` ends with `OK`.

## Constraints

- Files not to touch: `skill/core.md`, other topics, `skill/topics/arch-qa.md`, the shipped checklist.
- Dependencies not to add: none. Other topics' rendering is unchanged.
- Keep `skill/` size gates, mypy strict, files under size caps.

## Definition of done

- [ ] RED evidence before the production change; `make check` green.
- [ ] One commit `US-0069: Render the checklist in the arch-qa topic output`, body `Spec: SPEC-0006`, `FR-NEW-002, FR-NEW-007`.
