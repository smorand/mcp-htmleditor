# US-0051: `history` and `restore` tools, patch snapshots, docs and deployment

> Spec: SPEC-0009 (sdlc/specs/SPEC-0009-reliable-saves/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0050, US-0025, US-0041
> min_tier: 2
> Files touched: 4
> Closes spec: yes

## Objective

Expose `history` and `restore` as MCP tools, make SPEC-0007's `patch` snapshot the previous content, and ship
the deployment and documentation updates so the container image can save. Closes SPEC-0009.

## Requirements covered

- SPEC-0009/FR-NEW-005 (partial: the tools): WHEN a user runs `mcp-htmleditor history <file>` or `mcp-htmleditor restore <file> <id>` THE Editor SHALL list the versions or put the chosen version back. Tool part: the tools `history(file)` and `restore(file, id)` return `{"file","versions":[{"id","bytes","reason"}]}` and `{"ok":true,"file","id"}`, `file` is the absolute path; the tools return, for an unknown id, a missing file, a template or a write failure, an error whose message is the command line line without its `error: ` prefix.
- SPEC-0009/FR-NEW-004 (partial: `patch`): WHEN a browser save, a `patch` or a `restore` is about to change a file's bytes THE Editor SHALL first keep the previous content in the history. A version is `{id, bytes, reason}` with `reason` one of `browser-save`, `keep-mine`, `patch`, `restore`.
- SPEC-0009/FR-NEW-001 (partial: `patch` writes atomically through the shared writer with the snapshot): WHEN the editor server writes a file THE Editor SHALL leave on disk either the complete old content or the complete new content, and no other file next to it.

## Independent Test

`make check`: `tests/test_history_tools.py` passes and `mcp-htmleditor skill-audit` stays green. By hand: apply a
`set_text` patch to a deck, then `mcp-htmleditor history deck.html` lists a first line with reason `patch`.

## Design excerpt

### Decisions

- DEC-001 (SPEC-0009): SPEC-0007's call changes by one line: `atomic_write(path, data)` becomes `atomic_write(path, data, reason="patch")` in `src/mcp_htmleditor/deck/patch.py` (the only caller of `atomic_write` there).
- DEC-017 (SPEC-0009): Tool errors raise `ToolError(message)` (`fastmcp.exceptions.ToolError`) where the message is the CLI message without `error: `.
- DEC-021 (SPEC-0009): Error text is `exc.strerror or str(exc)`.
- DEC-019 (SPEC-0009): Deployment files and documentation are updated in the closing story and are not counted in the 3 to 5 file rule. Without `HTMLEDITOR_STATE_DIR` the image answers 500 on every save (no writable home, `Dockerfile:51-53`); do not release the images of earlier stories before this one.

### Data model

None new (history layout from US-0050).

### Contracts

```python
# mcp_server.py
history(file: str) -> {"file": <abs>, "versions": [{"id", "bytes", "reason"}]}      # span mcp.history
restore(file: str, id: str) -> {"ok": True, "file": <abs>, "id": <id>}             # span mcp.restore
```

- Errors raise `ToolError(message)`: `File not found: <file>`; `Unknown history id "<id>". Valid ids: <id1>, <id2>` (`Valid ids: none`); `Refusing to modify a template: <file>`; write failure: the strerror. `<file>` as typed.
- Docstring `mcp_server.py:3` ("Exposes N tools") updated.
- Lines added at the end of the `## Tools` section of `skill/core.md` (SPEC-0006 design: `- <name>: <description>`, one line per tool, section ends at the next `## ` heading):
  - `- history: list the saved previous versions of a file, newest first (id, bytes, reason).`
  - `- restore: put a previous version of a file back by id; the replaced content is kept in the history.`
- `mcp-htmleditor skill-audit` stays green (listed tool names equal the registered tools; core at most 6 000 bytes).
- Unit tests to add: tool errors (unknown id, missing file, template, write failure) carry the CLI message without `error: `.

Deployment and documentation (listed in Paths under Docs, not counted in Files touched, DEC-019):
- `Dockerfile`: `ENV HTMLEDITOR_STATE_DIR=/var/lib/mcp-htmleditor`, `mkdir` and `chown` for `appuser` (the image has no home directory).
- `docker-compose.yml`: a volume for the state directory.
- `.env.example`: `HTMLEDITOR_STATE_DIR`.
- `README.md`: conflict behaviour, `history` and `restore` usage, update flag expiry (120 s), state location; replace the `.mcp_state.json` mention (`README.md:361`); state that the check and the replace are serialized per process, not against an agent writing the file directly or another process.
- `AGENTS.md`: line 82 `.mcp_state.json` replaced by the state directory.
- `.agent_docs/architecture.md`: diagram line 11, `state.py` row line 24, new modules `fileio.py`, `history.py`, save path section.
- `.agent_docs/testing.md`: new test files (`test_save_safety_e2e.py`, `test_save_ui_e2e.py`, `test_history_e2e.py`, `test_history_tools.py`), fixtures `isolate_state_dir`, `served_deck`, `FakeClock`, `needs_chromium`.
- `.agent_docs/observability.md`: spans `history.snapshot`, `history.restore`, `mcp.history`, `mcp.restore`, `file.write`.
- `.gitignore` keeps `.mcp_state.json` (files left by older versions).

### Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/mcp_server.py` | edit: tools `history`, `restore`, module docstring |
| `src/mcp_htmleditor/deck/patch.py` | edit: one line, add `reason="patch"` |
| `skill/core.md` | edit: two lines at the end of `## Tools` |
| `tests/test_history_tools.py` | create |
| Docs: `Dockerfile` | edit |
| Docs: `docker-compose.yml` | edit |
| Docs: `.env.example` | edit |
| Docs: `README.md` | edit |
| Docs: `AGENTS.md` | edit |
| Docs: `.agent_docs/architecture.md` | edit |
| Docs: `.agent_docs/testing.md` | edit |
| Docs: `.agent_docs/observability.md` | edit |

### Existing patterns

- In process tool tests with `fastmcp.Client(mcp)` (`asyncio_mode = auto`), as in `tests/test_state.py` E2E-005 (US-0047).
- Tool with span: `@mcp.tool()` with `trace_span("mcp.<name>")` in `src/mcp_htmleditor/mcp_server.py` (`get_status`).
- Core tool list and audit: SPEC-0006 `## Tools` section of `skill/core.md`, `mcp-htmleditor skill-audit`.
- SPEC-0007 patch test style: `tests/test_deck_patch.py`, helpers in `tests/deck_support.py`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures: DECK is an Euro-Information presentation `deck.html` of 8 slides, served by the editor. Saves at different seconds use `FakeClock`.

### SPEC-0009/E2E-006: Tools history and restore
- Level tool; Driver `fastmcp.Client`; Location `tests/test_history_tools.py`
- Given DECK saved twice
- When an agent calls `history` with `file` DECK, then `restore` with the oldest id
- Then `history` returns `{"file":"<DECK>","versions":[...]}` with 2 versions each holding `id`, `bytes`, `reason`; `restore` returns `{"ok":true,"file":"<DECK>","id":"<id>"}`

### SPEC-0009/E2E-026: Patch snapshots
- Level tool + CLI; Driver `patch` then `history`; Location `tests/test_history_tools.py`
- Given DECK and a `set_text` patch (SPEC-0007) changing a title
- When it is applied, then `history deck.html` is run
- Then the first line has reason `patch` and its bytes equal the size of DECK before the patch

## Constraints

- Docs row group: the `Docs:` rows are listed in Paths but not counted in Files touched (4 = non doc rows: `mcp_server.py`, `deck/patch.py`, `skill/core.md`, `tests/test_history_tools.py`), per DEC-019.
- Files not to touch: `history.py`, `fileio.py` signature, `http_server.py`, `static/*`.
- Dependencies not to add: none.
- Patterns to avoid: returning `{"ok": false, ...}` instead of raising `ToolError`; listing a tool in the core without registering it (or the reverse).
- Scope boundary: no cleaning of history for deleted files; no authentication (BL-0019).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: `tests/test_deck_patch*.py` (patch results identical, plus one snapshot), `tests/test_skill_audit*.py`, `tests/test_state.py`, `tests/test_history_e2e.py`, `tests/test_save_safety_e2e.py`, `tests/test_save_ui_e2e.py` unchanged and green; no test asserts `.mcp_state.json` (per design section 6, the three modified `test_state.py` tests landed in US-0047).
- [ ] Docs updated: `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`, `.agent_docs/testing.md`, `.agent_docs/observability.md` as listed in the design excerpt.
- [ ] Self review: full (tool names and core lines match, error text equals the CLI line, patch snapshot only on a real change, image can write its state directory, docs match behaviour).
- [ ] If the story registers an MCP tool: the lines `- history: ...` and `- restore: ...` are added to the `## Tools` section of `skill/core.md` in the same story and `mcp-htmleditor skill-audit` stays green.
- [ ] (Closing story only) the spec's full acceptance set green (every E2E-001 to E2E-032), and every requirement of SPEC-0009 (FR-NEW-001 to FR-NEW-009) cited by at least one story with status done or landed (US-0047 to US-0051).
- [ ] One commit `US-0051: history and restore tools, patch snapshots, docs and deployment`, body `Spec: SPEC-0009` and `FR-NEW-005, FR-NEW-004, FR-NEW-001`.
