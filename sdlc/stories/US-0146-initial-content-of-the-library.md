# US-0146: Create the initial content on the first start

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0145
> min_tier: 1
> Files touched: 8
> Closes spec: no

## Objective

On the first start of a new library the product creates the folder `WCBIP Melbourne Décembre 2026` with the two conference decks `From Challenges to Change` and `Bridging the Gap` unchanged (modified times carried over) and `lamya.chrif@gmail.com` as RW, and remembers it so that no later start adds or resets anything, even when every folder was deleted.

## Requirements covered

- SPEC-0025/FR-NEW-054: WHEN the web library mode starts for the first time, with no library yet, THE web library mode SHALL create the folder "WCBIP Melbourne Décembre 2026" holding the presentations "From Challenges to Change" and "Bridging the Gap", unchanged, with lamya.chrif@gmail.com as RW.
  - Business rules: The initial content is created once, when the library is first created, and that fact is remembered: later starts neither add nor reset anything, even when every folder was deleted. The two presentations keep the modified time of the supplied files (15 Nov 2026 19:57 UTC). The existing public static site for these two decks is not touched.
- SPEC-0025/FR-NEW-062 (partial: the seeded content, its modified times and its absence of re creation survive restarts): The web library mode SHALL keep every folder, presentation, history, member, activity line and signed in session after the product is restarted.
  - Business rules: A person signed in before a restart is still signed in after it, for the rest of the 30 days counted from their sign in.

## Independent Test

Run `make test ARGS='-k library_seed'`. The assertion that is not a mock: the stored files hash to `85dd0f464c068eb8fb784627d1f2f4beeaabf7162f7381e334007cb8a15155dd` and `011a91e9d03995fb0efe30d5f794f77706ba42c76d18d388f89b2ddb1a5e4eb2`, their `st_mtime` read back as `2026-11-15T19:57:19Z` and `19:57:18Z`, the `activity` table is empty and after deleting the folder and restarting, `folders` is empty.

## Design excerpt

### Decisions

- DEC-005 (SPEC-0025): Settings fields `library_origin`, `library_content_origin`, `library_dir_override` (property `library_dir`), `google_credentials_override` (property `google_credentials_file`), `library_seed_dir_override` (property `library_seed_dir`), env prefix `HTMLEDITOR_`, names added to `_SIGNIFICANT_ENV_VARS` and the path fields to `_PATH_FIELDS`. Obliged by: SPEC-0025/FR-NEW-057, SPEC-0025/FR-NEW-059, SPEC-0025/FR-NEW-062, spec section 3.3 (credentials supplied by the operator).
- DEC-025 (SPEC-0025): Metadata in one SQLite file (`<library_dir>/library.db`, WAL, `foreign_keys=ON`, `busy_timeout` 30 s, one connection per thread, `BEGIN IMMEDIATE` for writes, migrations numbered by `PRAGMA user_version`); presentation bytes in files named by two random 32 hex ids (`files/<folder id>/<presentation id>.html`); ids validated against `^[0-9a-f]{32}$` before a path is built; names exist only as column values. Obliged by: SPEC-0025/FR-NEW-032, SPEC-0025/FR-NEW-041, SPEC-0025/FR-NEW-021, SPEC-0025/FR-NEW-062, SPEC-0025/FR-NEW-063, SPEC-0025/FR-NEW-060.
- DEC-036 (SPEC-0025): The initial content is a manifest `library-seed/manifest.json` (folder name, members, per presentation: name, file, byte count, sha256, UTC modified time) and the two decks copied unchanged from the paths in the spec into `library-seed/`; `seed.py` runs in the first start inside one transaction guarded by `meta('seeded')`: it verifies each sha256, creates the folder and the member, copies the files and sets their `st_mtime` with `os.utime`, then writes the flag; it records no activity line; packaging uses `[tool.hatch.build.targets.wheel.force-include]` and `COPY library-seed/` in the Dockerfile. Obliged by: SPEC-0025/FR-NEW-054, SPEC-0025/FR-NEW-062.
- DEC-047 (SPEC-0025): The image runs `webserve` through compose (`command`), keeps `ENTRYPOINT ["mcp-htmleditor"]`, the uid 10001 user, the exec form and the `/health` `HEALTHCHECK`; the builder stage adds `COPY library-seed/ ./library-seed/` before `uv sync` (the wheel force-includes it); no Chromium is added; a `.dockerignore` is added. Obliged by: SPEC-0025/FR-NEW-054, SPEC-0025/FR-NEW-062.

### Data model

No change. `meta('seeded')` holds the UTC time of the seeding.

### Contracts

**Dataset** (user provided data, present today, verified by the design on 2026-11-16): copy
`/Users/sebastien/projects/lamya/presentations/WCBIP_WIIP_2026-12_Melbourne/deck/wiip2026.html` (3 901 499 bytes, sha256 `85dd0f464c068eb8fb784627d1f2f4beeaabf7162f7381e334007cb8a15155dd`, 18 slides) to `library-seed/from-challenges-to-change.html` and
`/Users/sebastien/projects/lamya/presentations/WABIP_2026-12_Melbourne/deck/wcbip2026-v1.html` (3 278 888 bytes, sha256 `011a91e9d03995fb0efe30d5f794f77706ba42c76d18d388f89b2ddb1a5e4eb2`, 15 slides) to `library-seed/bridging-the-gap.html` (a plain `cp`; the files are read only sources, never modified). If a source is missing at implementation time the story is blocked, not worked around.

**Manifest** `library-seed/manifest.json`:

```json
{"folder": "WCBIP Melbourne Décembre 2026",
 "members": [{"email": "lamya.chrif@gmail.com", "role": "RW"}],
 "presentations": [
  {"name": "From Challenges to Change", "file": "from-challenges-to-change.html", "bytes": 3901499,
   "sha256": "85dd0f464c068eb8fb784627d1f2f4beeaabf7162f7381e334007cb8a15155dd", "modified": "2026-11-15T19:57:19Z"},
  {"name": "Bridging the Gap", "file": "bridging-the-gap.html", "bytes": 3278888,
   "sha256": "011a91e9d03995fb0efe30d5f794f77706ba42c76d18d388f89b2ddb1a5e4eb2", "modified": "2026-11-15T19:57:18Z"}]}
```

**`library/seed.py::seed_if_new(library: Library, seed_dir: Path, clock) -> bool`**: returns `False` when `meta('seeded')` exists; otherwise inside one `BEGIN IMMEDIATE` transaction: read the manifest, verify each file's size and sha256 (a mismatch raises `SeedError` and nothing is created), insert the folder (new id, `name_key`), the members, the presentation rows (new ids), copy each file to `presentation_path(fid, pid)` with `shutil.copyfile` then `os.utime(path, (modified, modified))`, insert `meta('seeded')`, commit; on any exception remove the copied files and roll back. No activity line. Wrapped in `trace_span("library.seed", {"presentations": 2})`. `LibraryServer.start()` calls it once (a flag `seed: bool = True` on the constructor, tests that use a builder pass `False`).

**Settings**: `library_seed_dir_override` (`HTMLEDITOR_LIBRARY_SEED_DIR`, `_PATH_FIELDS`, `_SIGNIFICANT_ENV_VARS`) with property `library_seed_dir` (override, else repo `library-seed/`, else package `library_seed/`, same rule as `skill_dir`, `config.py:192-201`).

**Packaging**: `pyproject.toml` `[tool.hatch.build.targets.wheel.force-include]` gains `"library-seed" = "mcp_htmleditor/library_seed"`.

### Paths

| Path | Action | Note |
|---|---|---|
| `src/mcp_htmleditor/library/seed.py` | create | `seed_if_new`, `SeedError` |
| `library-seed/manifest.json` | create | manifest above |
| `library-seed/from-challenges-to-change.html` | create | copy of the supplied deck (data) |
| `library-seed/bridging-the-gap.html` | create | copy of the supplied deck (data) |
| `src/mcp_htmleditor/library/server.py` | modify | call at start |
| `src/mcp_htmleditor/config.py` | modify | `library_seed_dir` |
| `pyproject.toml` | modify | force-include the seed directory |
| `tests/test_library_seed_http.py` | create | functional tests |

### Existing patterns

`config.py:192-201` (`skill_dir` resolution); `templates.py:25-26` for locating packaged data; `tests/test_reference_decks_present_e2e.py` for tests that need real decks.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

### SPEC-0025/E2E-129: Other accounts see nothing of the initial content

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_seed_http.py`
- **Category:** failure
- **Scenario:** SC-020
- **Requirements:** FR-NEW-010, FR-NEW-020, FR-NEW-054
- **Given** The initial content is loaded; bob.nobody@gmail.com is in no list and carol.ro@example.org is RO in "Cardiology 2027" only.
- **When** Bob signs in; Carol opens the link to "Bridging the Gap".
- **Then** Bob sees "Access denied."; Carol sees "Access denied."
- **And** No title of the two decks appears to either.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-130: The seeded member is not an administrator

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_seed_http.py`
- **Category:** failure
- **Scenario:** SC-020
- **Requirements:** FR-NEW-013, FR-NEW-054
- **Given** lamya.chrif@gmail.com is signed in.
- **When** She opens the administration link.
- **Then** "Access denied." is shown.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-131: A restart does not reset or recreate the initial content

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_seed_http.py`
- **Category:** edge (side effect, state transition)
- **Scenario:** SC-020
- **Requirements:** FR-NEW-054, FR-NEW-062
- **Given** lamya.chrif@gmail.com deleted "Bridging the Gap" and changed the title of slide 1 of "From Challenges to Change"; the product restarts.
- **When** She opens her folder.
- **Then** Only "From Challenges to Change", with her changed title, is listed.
- **And** The administrator's activity list shows her deletion line, and no creation line from the restart.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-132: The seeded decks are unchanged and pass the upload checks

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_seed_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-020
- **Requirements:** FR-NEW-022, FR-NEW-031, FR-NEW-054
- **Given** "From Challenges to Change" and "Bridging the Gap" as seeded.
- **When** lamya.chrif@gmail.com downloads both HTML files, then the administrator uploads them into "Pneumo Été".
- **Then** The downloads are byte for byte the supplied decks (3 901 499 and 3 278 888 bytes); both uploads end with "Uploaded From Challenges to Change." and "Uploaded Bridging the Gap.", with no validation problem.
- **And** The public static site of these decks is still reachable without sign in and is unchanged.
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the last And (the public static site) is outside the product and outside this repository; it is checked by the runbook command `curl -sI https://lamya-slides.scm-platform.org/` of US-0148, not by an automated test.

### SPEC-0025/E2E-143: An empty activity list says so

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_seed_http.py`
- **Category:** edge
- **Scenario:** SC-022
- **Requirements:** FR-NEW-050, FR-NEW-054
- **Given** A library that holds only its initial content.
- **When** The administrator opens the activity list.
- **Then** "No activity yet." is shown.
- **Priority:** Low
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-159: A library whose every folder was deleted is not seeded again

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_seed_http.py`
- **Category:** edge (state transition)
- **Scenario:** SC-020
- **Requirements:** FR-NEW-016, FR-NEW-054, FR-NEW-062
- **Given** The initial content was created; the administrator then deleted "WCBIP Melbourne Décembre 2026", the only folder.
- **When** The product restarts and seb.morand@gmail.com opens the home page.
- **Then** "You have no access to any folder yet." is shown.
- **And** lamya.chrif@gmail.com signs in and sees "Access denied." (she holds no role anywhere).
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### Story tests (not spec tests)

`tests/test_library_seed_http.py` holds a unit test where a corrupted seed file (sha256 mismatch) creates nothing and a second start retries.

## Constraints

- The seed files are copied byte for byte; never re serialized, never edited.
- No activity line for the seeding.
- The seed directory is not under `templates/` (every presentation there is scanned by `tests/test_presentation_templates_fullscreen.py`).
- Do not touch the public static site (outside this repository).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: `.agent_docs/library.md` (seed), `README.md` (initial content).
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] Note: The two source decks are user data outside this repository; the story copies them, it does not alter them.
- [ ] One commit `US-0146: Create the initial content on the first start` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
