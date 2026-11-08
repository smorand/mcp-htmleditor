# US-0115: Presentation guards and span privacy

> Spec: SPEC-0019 (sdlc/specs/SPEC-0019-code-and-test-debts/)
> Nature: DEBT
> Priority: P2
> Depends on: US-0112, US-0113, US-0114
> min_tier: 2
> Files touched: 4
> Closes spec: yes

## Objective

The presentation guard passes on markers that sit in a comment, the skill can lose the fact that the Carbon catalogue presents, and no test asserts that spans carry no document content (SPEC-0001 E2E-036 untested). This story adds a structural guard, a positive skill statement and a span privacy test beside the existing tests, records the five new test files in the test map, and closes SPEC-0019.

## Requirements covered

- SPEC-0019/DR-004: The test suite SHALL check, for every presentation file found by `presentation_files(TEMPLATES_ROOT)` (`tests/test_presentation_templates_fullscreen.py:51`), after removing HTML comments: a `<style>` block whose text, CSS comments removed, contains `:fullscreen`; an element start tag carrying `id="btn-present"`; and, inside `<script>` blocks, a line matching `^\s*(?:async\s+)?function (enterPresentation|exitPresentation|updateFullscreenScale)\s*\(` for each of the three names.
- SPEC-0019/DR-005: The `slides-carbon` skill topic SHALL contain the sentence `Le catalogue \`ibm-carbon.html\` a le mode présentation (bouton Présenter).`
- SPEC-0019/DR-008: The test suite SHALL assert that a traced save and export of a deck write none of the deck's text into span names or attributes (SPEC-0001 FR-023, E2E-036), through DT-030.
- SPEC-0019/DR-006 (partial: this story's edits and the converge): The system SHALL produce, for every input covered by the existing test suite, byte identical observable output before and after this change, the undo snapshot string and the HTML posted by a save included; the only text change is the sentence of DR-005 in the `slides-carbon` topic output.

## Independent Test

`make test ARGS='-k "markers_structural or no_content"'`: DT-021 red before the sentence, green after; DT-020 and DT-030 green. `make run ARGS='skill-audit'`: `slides-carbon` about 7874 bytes of 8000, OK. `make test ARGS='--durations=0 -k "state_record or serve_poll or artifact_strip or markers_structural or no_content"'` total at most 6 s (DEC-007), pasted. `make check` green with the test step at most 330 s.

## Design excerpt

### Decisions

- DEC-004 (SPEC-0019): Harden with new tests beside the existing ones, never by editing them (`missing_markers` message is asserted at `tests/test_presentation_templates_fullscreen.py:113-116`; BT-024 at `tests/test_skill_shipped.py:330-343` guards a different fact).
- DEC-005 (SPEC-0019): the positive statement goes into `slides-carbon` (202 bytes of budget left), appended at the end of `skill/topics/slides-carbon.md:96` after one space; not `create` (13 bytes left), not `core` (sha256 pinned).
- DEC-007 (SPEC-0019): the new SPEC-0019 tests at most 6 s together; DT-030 is the only child process.
- DEC-009 (SPEC-0019): US-0112 has landed, so `tests/test_agent_docs_size.py` exists: the five rows keep `.agent_docs/testing.md` at most 220 lines.
- DEC-010 (SPEC-0019): new files follow SPEC-0018 DT-010 and DT-012.
- DEC-011 (SPEC-0019): measure; a step above 330 s at load above 30 is re run once; above 330 s at normal load, stop and open a backlog entry for a trim.

### Paths

| Path | Action |
|---|---|
| `skill/topics/slides-carbon.md` | append the DR-005 sentence to `:96` |
| `tests/test_presentation_markers_structural.py` | create: DT-020, DT-021 |
| `tests/test_tracing_no_content.py` | create: DT-030 |
| `.agent_docs/testing.md` | § Files: one row each for `test_state_record.py`, `test_serve_poll.py`, `test_editor_artifact_strip.py`, `test_presentation_markers_structural.py`, `test_tracing_no_content.py` |

### Existing patterns

- Template discovery: `presentation_files` (`tests/test_presentation_templates_fullscreen.py:50`), `TEMPLATES_ROOT`.
- In process skill CLI: `tests/test_skill_shipped.py:91-99` (`real_tree`), `:341`.
- Traced child server: `run_traced_server` (`tests/trace_support.py:115`), raw requests as in `tests/test_tracing_unencodable.py:134-150`; EI deck from `tests/deck_support.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0019/DT-020: Presentation markers are real code
- Level / Driver / Location: structural / regex, parametrized by relative path / `tests/test_presentation_markers_structural.py`
- Given each of the 11 discovered presentation files, text with `<!--.*?-->` removed
- Then `<style\b[^>]*>(.*?)</style>` (CSS `/\*.*?\*/` removed) contains `:fullscreen`; `<[a-zA-Z][^>]*\bid="btn-present"` matches; inside `<script\b[^>]*>(.*?)</script>` the line pattern of DR-004 (`re.MULTILINE`) matches each of the three names (`re.DOTALL` elsewhere); failure message `<relative path>: missing <marker>` with markers `:fullscreen rule`, `#btn-present element`, `function enterPresentation`, `function exitPresentation`, `function updateFullscreenScale`. No BeautifulSoup.
- Negative cases in the same file: a deck whose five markers appear only inside one HTML comment reports all five missing; a deck with `function enterPresentationLater(` and no `enterPresentation(` reports `function enterPresentation`; a deck with `:fullscreen` only in a `<script>` string reports `:fullscreen rule`.
- Green on today's 11 files.

### SPEC-0019/DT-021: The skill states that the Carbon catalogue presents
- Level / Driver / Location: functional, in process / `CliRunner` / `tests/test_presentation_markers_structural.py`
- Given `HTMLEDITOR_SKILL_DIR` set to the repository `skill/` folder (as `real_tree`)
- When `CliRunner().invoke(main, ["skill", "--type", "slides-carbon"])`
- Then exit code 0 and stdout contains `Le catalogue \`ibm-carbon.html\` a le mode présentation (bouton Présenter).`; `skill-audit` stays OK (existing budget test in `tests/test_skill_shipped.py`)
- Red before the fix because: the sentence is absent.

### SPEC-0019/DT-030: Spans carry no document content
- Level / Driver / Location: functional e2e / child traced server / `tests/test_tracing_no_content.py`
- Given `served` a copy of the EI deck of `tests/deck_support.py`, and two raw requests built as in `tests/test_tracing_unencodable.py:134-150`: `POST /content` (`Host: 127.0.0.1:%PORT%`, `Content-Type: application/json`, `Content-Length`) whose HTML holds `<p>SECRET-7f3a9c</p>` and the title `SECRET-TITLE-7f3a9c`, then `GET /export/pptx`
- When `run_traced_server(tmp_path, served, [save, export])`
- Then `run.data == [200, 200]`, and neither `SECRET-7f3a9c` nor `SECRET-TITLE-7f3a9c` appears in any line of `run.trace_lines`; the application log is not asserted
- Expected green before and after (a guard). If red on its first run, the leak is a real finding: stop, write a `Nature: BUG` backlog entry naming the leaking attribute, never weaken the assertion.

### Spec converge (closing story)
- The full SPEC-0019 acceptance set green under `make check`: DT-001, DT-002, DT-003, DT-010, DT-011 (US-0113), DT-012 (US-0114), DT-020, DT-021, DT-030 (this story); Section 8.1 criterion.
- Requirement coverage audit: DR-001, DR-002, DR-007 by US-0113; DR-003 by US-0114; DR-004, DR-005, DR-008 by this story; DR-006 by all three.

## Constraints

- Files not to touch: `tests/test_presentation_templates_fullscreen.py`, `tests/test_skill_shipped.py`, `tests/test_tracing_unencodable.py`, every other existing test.
- `.agent_docs/testing.md` stays at most 220 lines (SPEC-0018 DT-013); one line per new file, nothing else moved.
- The skill sentence is appended to `slides-carbon.md:96` only; it holds neither `:fullscreen` nor `plein écran` (BT-024 stays green).
- Dependencies not to add: any (no BeautifulSoup in DT-020).
- Scope boundary: browser rows of BL-0010 and BL-0017 stay in the backlog (DEC-006).

## Definition of done

- [ ] RED evidence recorded for DT-021 before the sentence; DT-020 negative cases red on their fixtures.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Durations pasted: the five SPEC-0019 files at most 6 s; `make check` test step at most 330 s (DEC-011).
- [ ] Non regression: `tests/test_presentation_templates_fullscreen.py`, `tests/test_skill_shipped.py` unchanged and green.
- [ ] DEBT: the existing suite passes unmodified, exceptions: the 4 removed tests of `tests/test_state.py` (US-0113), none in this story.
- [ ] Docs updated: `.agent_docs/testing.md` § Files (five rows), `skill/topics/slides-carbon.md:96`.
- [ ] Self review: full.
- [ ] Closes spec: the full SPEC-0019 acceptance set green, every requirement of SPEC-0019 cited by a landed or done story.
- [ ] One commit `US-0115: Presentation guards and span privacy`, body `Spec: SPEC-0019` and `DR-004, DR-005, DR-006, DR-008`.
