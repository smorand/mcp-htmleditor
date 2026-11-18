# US-0147: The operator can list the stored library and find a file's history

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P3
> Depends on: US-0146
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective

Stored presentations have opaque file names, so an operator needs a way to go from a folder and a presentation name to the file whose history `mcp-htmleditor history` and `restore` operate on: `mcp-htmleditor library-list` prints one line per presentation with the stored path.

## Requirements covered

- SPEC-0025/FR-NEW-026 (partial: the previous version is kept in the history of the presentation; an operator finds the stored file of a presentation to list or restore it through the existing history commands): WHEN a person with RW leaves a field they changed THE web library mode SHALL store the edited version in its folder at once and keep the previous version in the history of the presentation.
  - Business rules: The same storing happens 0.8 seconds after typing stops (FR-NEW-066). Stored changes are not recorded in the activity list (FR-NEW-051).

## Independent Test

Run `make test ARGS='-k library_oplist'`. The assertion that is not a mock: after the builder creates two folders, `library-list` through `CliRunner` prints one tab separated line per presentation and the path of the first line passed to `list_versions` returns the versions written by a save.

## Design excerpt

### Decisions

- DEC-025 (SPEC-0025): Metadata in one SQLite file (`<library_dir>/library.db`, WAL, `foreign_keys=ON`, `busy_timeout` 30 s, one connection per thread, `BEGIN IMMEDIATE` for writes, migrations numbered by `PRAGMA user_version`); presentation bytes in files named by two random 32 hex ids (`files/<folder id>/<presentation id>.html`); ids validated against `^[0-9a-f]{32}$` before a path is built; names exist only as column values. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-062, SPEC-0025/FR-NEW-063, SPEC-0025/FR-NEW-060.
- DEC-051 (SPEC-0025): `mcp-htmleditor library-list` prints one tab separated line per presentation (folder, presentation, stored path, bytes) so an operator can use `history` and `restore` on a library file. Obliged by: SPEC-0025/FR-NEW-026 (the previous version is kept in the history of the presentation), spec section 7.6 (an operator can list and restore through SPEC-0009).

### Data model

No change.

### Contracts

`mcp-htmleditor library-list` (`cli.py`, `click`, no argument): reads `get_settings().library_dir`, opens the database read only (`sqlite3.connect("file:...?mode=ro", uri=True)`), prints with `click.echo` one line per presentation `<folder name>\t<presentation name>\t<stored path>\t<byte count>` ordered by folder then presentation name, exits 0 with no output on an empty library and exits 1 with `No library at <path>` when `library.db` does not exist. `Library.inventory() -> list[InventoryRow]` (frozen dataclass `folder`, `presentation`, `path`, `bytes`) in `store.py` does the query and `os.stat`.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/cli.py` | modify | `library-list` |
| `src/mcp_htmleditor/library/store.py` | modify | `inventory`, `InventoryRow` |
| `tests/test_library_oplist.py` | create | CLI and inventory tests |

### Existing patterns

`cli.py:170-201` (a click command), `tests/test_history_tools.py` for CLI runner tests of history commands, `history.py:156-182` for `list_versions` and `restore_version`.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

This story maps no test of the spec; its tests are the story tests below.

### Story tests (not spec tests)

`tests/test_library_oplist.py` (story tests, no spec test is mapped here): (1) Given a library built with two folders and three presentations, When `library-list` runs through `CliRunner`, Then exit code 0 and exactly three lines of four tab separated fields, the stored path of each line exists and its size equals the fourth field; (2) Given a save of the first presentation through the library, When `list_versions(Path(<path of line 1>))` is called, Then it returns one version; (3) Given an empty library directory, Then exit code 1 and `No library at <path>`; (4) Given the command ran, Then the database file and every presentation file have unchanged `st_mtime` (read only).

## Constraints

- Read only: the command never writes the database or the files.
- The command prints stored paths and names for the operator; it is not a route and is never reachable over the network.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `README.md` and `.agent_docs/library.md` (the command and the history workflow for the operator).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] One commit `US-0147: The operator can list the stored library and find a file's history` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
