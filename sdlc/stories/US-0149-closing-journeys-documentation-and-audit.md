# US-0149: Closing journeys, documentation audit and acceptance of the whole spec

> Spec: SPEC-0025 (sdlc/specs/SPEC-0025-web-library-mode/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0148
> min_tier: 1
> Files touched: 2
> Closes spec: yes

## Objective

Close the spec: the journeys that cross several features and could not be green earlier are written and green, the documentation is audited against the final code, and the full acceptance set of SPEC-0025 is run (the whole library suite in `make check` and the slow real time bounds).

## Requirements covered

- SPEC-0025/FR-NEW-060 (partial: the 200 folder and 100 presentation bounds run in the closing audit): WHILE the library holds 200 folders, or a folder holds 100 presentations, THE web library mode SHALL display that list within 2 seconds on a 50 megabit per second connection.
  - Business rules: Every entry stays reachable. The 2 seconds are counted from the person's request until the whole list can be read and used.
- SPEC-0025/FR-NEW-061 (partial: the slow test of the 25 MB upload at 10 Mbit/s runs in the closing audit): WHEN a person uploads a valid file of 25 MB THE web library mode SHALL complete the upload within 2 minutes on a 10 megabit per second connection and finish with "Uploaded <name>."
  - Business rules: none beyond the statement.
- SPEC-0025/FR-NEW-062 (partial: folders, presentations, history, members, activity and sessions survive restarts, proven by journeys that cross every feature): The web library mode SHALL keep every folder, presentation, history, member, activity line and signed in session after the product is restarted.
  - Business rules: A person signed in before a restart is still signed in after it, for the rest of the 30 days counted from their sign in.

## Independent Test

Run `make check` then `make test ARGS='-m slow -k library'`. The assertion that is not a mock: every file listed in section 9 of the design exists, `make check` is green and `make test ARGS='-k library --collect-only -q'` collects at least the number of tests the design maps (one per spec test, 214), none skipped.

## Design excerpt

### Decisions

- DEC-036 (SPEC-0025): The initial content is a manifest `library-seed/manifest.json` (folder name, members, per presentation: name, file, byte count, sha256, UTC modified time) and the two decks copied unchanged from the paths in the spec into `library-seed/`; `seed.py` runs in the first start inside one transaction guarded by `meta('seeded')`: it verifies each sha256, creates the folder and the member, copies the files and sets their `st_mtime` with `os.utime`, then writes the flag; it records no activity line; packaging uses `[tool.hatch.build.targets.wheel.force-include]` and `COPY library-seed/` in the Dockerfile. Obliged by: SPEC-0025/FR-NEW-054, SPEC-0025/FR-NEW-062.
- DEC-049 (SPEC-0025): Test infrastructure is one module `tests/library_support.py`: an in process `LibraryServer` on a free port with a temporary `library_dir` and `state_dir`, a `FakeClock`, a `FakeGoogle` (a loopback HTTP server with `/authorize` and `/token`, scripted accounts and failures, a record of the requests it received), an HTTP client that sets `Host` and keeps cookies per person, a `LibraryBuilder` that creates folders, members and presentations of exact sizes through the repository, a `StoredLibrary` operator view, and Playwright launch arguments mapping `slides.test` and `slides-content.test` to 127.0.0.1. Browser tests are named `test_*_e2e.py` and use `tests/browser_wait.py`; an exploit test is a function named `test_exploit_<id>` inside the `_http.py` or `_e2e.py` file of its area, so `-k exploit` selects them all. The library suite stays under 90 s in `make check`; the test of 25 MB at 10 Mbit/s is marked `slow`. Obliged by: SPEC-0025/FR-NEW-060, SPEC-0025/FR-NEW-061, AGENTS.md testing rules.
- DEC-050 (SPEC-0025): Documentation: `.agent_docs/library.md` (new, the module map, flows, cookies, seams, gotchas), `AGENTS.md` (commands and index line), `README.md` (a "Web library mode" section and the VPS runbook), `.agent_docs/architecture.md` and `.agent_docs/testing.md` (pointers, counts), `.agent_docs/docker.md` (the new compose file), `.agent_docs/observability.md` (the new spans), `.agent_docs/html-conventions.md` (the editor seam); the skill `topics/editor.md` gets one paragraph (the editor in the web mode), `skill-audit` stays green. Obliged by: SPEC-0025/FR-NEW-057, SPEC-0025/FR-NEW-062 (operability), AGENTS.md documentation pattern.

### Data model

No change.

### Contracts

**Journeys** (tests only, through the finished product): the member sign in then an upload attributed in lower case; the administrator acting in a folder with no member entry (upload, edit, delete); the administrator adding a member who then sees the `Upload` control; the administrator listed RO who can still upload; every kind of successful action in the activity list (upload, replace, delete, folder, member); the initial content opened and its slide counts read from the editor. They use `FakeGoogle`, `LibraryBuilder`, `StoredLibrary` and the Playwright helpers of the earlier stories.

**Documentation audit** (DEC-050): `README.md` (section Web library mode, the settings table, the runbook of the deployment story), `AGENTS.md` (commands `webserve` and `library-list`, the index line of `.agent_docs/library.md`), `.agent_docs/library.md` (final, under about 200 lines: consolidate if it grew), `.agent_docs/architecture.md` (the hooks, the module map pointer), `.agent_docs/testing.md` (the library suite map, the 90 s budget, the seams, the `slow` file), `.agent_docs/observability.md` (the spans `auth.google_token`, `session.create`, `library.upload`, `library.replace`, `library.delete_presentation`, `library.delete_folder`, `library.seed`), `.agent_docs/html-conventions.md` (the library shell), `skill/topics/editor.md` (one paragraph: the editor in the library), `mcp-htmleditor skill-audit` stays green (`make check` runs it through its tests).

**Requirement audit**: `rg -o 'SPEC-0025/FR-NEW-[0-9]{3}' sdlc/stories/US-01[2-4]*.md | sed 's#.*/##' | sort -u | wc -l` prints 74, and every story row of SPEC-0025 in `sdlc/stories/_queue.md` is `done`.

### Paths

| Path | Action | Note |
|---|---|---|
| `tests/test_library_journeys_http.py` | create | E2E-001, E2E-108, E2E-114, E2E-138 |
| `tests/test_library_journeys_e2e.py` | create | E2E-085 and E2E-128 |

### Existing patterns

`tests/test_library_open_http.py`, `tests/test_library_upload_http.py` and `tests/test_library_seed_http.py` for the helpers the journeys reuse.

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Closing story: besides the tests below, the definition of done below carries the full acceptance set of the spec (all 214 tests, by command) and the requirement coverage audit.

### SPEC-0025/E2E-001: A member signs in and signs out

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_journeys_http.py`
- **Category:** happy (side effect, state transition)
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-008, FR-NEW-015, FR-NEW-024, FR-NEW-068, FR-NEW-071, FR-NEW-072
- **Given** lamya.chrif@gmail.com is RW in "WCBIP Melbourne Décembre 2026" and has no session; Google will return her account as "Lamya.Chrif@Gmail.COM".
- **When** She opens slides.scm-platform.org, chooses "Sign in with Google", completes the Google sign in, then chooses "Sign out".
- **Then** After the sign in the home page lists one folder, "WCBIP Melbourne Décembre 2026", with the role "Read and write", and shows "Sign out" but no "Administration". After "Sign out" the sign in page shows only "Sign in with Google".
- **And** The product asked for no password of its own.
- **And** Opening the address again in the same browser shows the sign in page and no folder name.
- **And** No "Access denied." and no "Sign-in is unavailable. Try again later." message appeared.
- **And** In another run she cancels the Google consent first: the sign in page is shown again with no message, and a second attempt succeeds.
- **And** The sign in answer belonged to the sign in this browser started, so no "Sign-in is unavailable. Try again later." appeared.
- **And** Lamya's own upload of "Quarterly Review.html", done in this session, appears in the administrator's activity list as attributed to lamya.chrif@gmail.com in lower case, not "Lamya.Chrif@Gmail.COM".
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-085: The administrator acts in a folder where they have no member entry

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_journeys_e2e.py`
- **Category:** happy (side effect)
- **Scenario:** SC-013
- **Requirements:** FR-NEW-014, FR-NEW-024, FR-NEW-025, FR-NEW-028, FR-NEW-039
- **Given** seb.morand@gmail.com is in no member list; "Pneumo Été" is empty; "Spirometry Basics.html" is valid.
- **When** He uploads it into "Pneumo Été", edits it (the change is stored by itself), then deletes "Statins Review" from "Cardiology 2027".
- **Then** "Uploaded Spirometry Basics." is shown, the edit is stored, and the deletion succeeds.
- **And** dan.rw@example.org sees 2 presentations in "Cardiology 2027".
- **Priority:** High
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-108: The administrator adds a member

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_journeys_http.py`
- **Category:** happy (side effect, state transition)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-024, FR-NEW-045, FR-NEW-046, FR-NEW-049
- **Given** "Pneumo Été" has no member; dan.rw@example.org holds no role there.
- **When** The administrator adds dan.rw@example.org with the role RW.
- **Then** Dan's next page shows "Pneumo Été" labelled "Read and write" with "Upload" available.
- **And** The activity list gains "Added dan.rw@example.org as RW to "Pneumo Été"".
- **And** Adding dan.rw@example.org again with RW leaves one entry in the member list of "Pneumo Été".
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-114: The administrator's own address can be listed

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_journeys_http.py`
- **Category:** edge (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-012, FR-NEW-014, FR-NEW-045
- **Given** The administrator.
- **When** He adds seb.morand@gmail.com as RO to "Pneumo Été".
- **Then** The entry is added; his label stays "Admin" and he can still upload there.
- **Priority:** Low
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

### SPEC-0025/E2E-128: The initial content is there

- Level / Driver / Location: functional e2e / Playwright / `tests/test_library_journeys_e2e.py`
- **Category:** happy (side effect)
- **Scenario:** SC-020
- **Requirements:** FR-NEW-015, FR-NEW-018, FR-NEW-024, FR-NEW-054
- **Given** The web library mode started for the first time.
- **When** seb.morand@gmail.com, then lamya.chrif@gmail.com, open the home page and the folder.
- **Then** Both see "WCBIP Melbourne Décembre 2026" (Lamya labelled "Read and write"); the folder lists "Bridging the Gap" (3.1 MB) before "From Challenges to Change" (3.7 MB), both with the modified time of the supplied files, 15 Nov 2026 19:57.
- **And** The activity list holds "No activity yet."
- **And** Opening "From Challenges to Change" shows 18 slides and "Bridging the Gap" 15.
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.
- Design note: the person's time zone is fixed to UTC in the browser context (`timezone_id="UTC"`); the slide counts are read from the stored files.

### SPEC-0025/E2E-138: The activity list records every kind of successful action

- Level / Driver / Location: functional e2e / HTTP client / `tests/test_library_journeys_http.py`
- **Category:** happy (side effect)
- **Scenario:** SC-022
- **Requirements:** FR-NEW-013, FR-NEW-049, FR-NEW-050
- **Given** A fresh library. dan.rw@example.org uploads "Quarterly Review", replaces it, deletes it; the administrator creates "Oncology 2030", adds dan.rw@example.org RW, changes him to RO, removes him, and deletes the folder.
- **When** The administrator opens the activity list.
- **Then** 8 lines are shown, newest first, each with its time and its email address in lower case: seb.morand@gmail.com for the 5 folder and member lines, dan.rw@example.org for the 3 presentation lines: Deleted folder "Oncology 2030"; Removed dan.rw@example.org from "Oncology 2030"; Changed dan.rw@example.org to RO in "Oncology 2030"; Added dan.rw@example.org as RW to "Oncology 2030"; Created folder "Oncology 2030"; Deleted "Quarterly Review" from "Cardiology 2027"; Replaced "Quarterly Review" in "Cardiology 2027"; Uploaded "Quarterly Review" in "Cardiology 2027".
- **Priority:** Critical
- Cleanup: the fixtures remove their temporary library and state directories and stop every server and fake provider at teardown.

## Constraints

- No product code is expected; a journey that fails reveals a defect of an earlier story, which is fixed in that story's module with a regression test here.
- Do not edit `sdlc/specs/SPEC-0025-web-library-mode/spec.md` (set `Status: implemented` only through the landing command).

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the failing assertion named; for E2E-SEC tests, the reason named in the test).
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit; main only receives the whole squash at landing.
- [ ] Non regression: every existing test of the local mode passes unmodified under `make check`; `git diff --stat` shows no change to `templates/`, `static/editor.html`, `static/editor*.js`, `static/slide-layouts.js`, `static/doc-blocks.js` unless this story lists them under Paths.
- [ ] Docs updated: Every file of the documentation audit above.
- [ ] Self review: why the code is correct and where it would break (failure modes walked through), stated in the commit body.
- [ ] Closes spec: the spec's full acceptance set green: `make check` (the whole library suite and every other suite) and `make test ARGS='-m slow -k library'` (the real time bounds), 214 tests of SPEC-0025 in total, none skipped, none marked xfail.
- [ ] Closes spec: every requirement of SPEC-0025 (74) cited by at least one story with status done: `rg -o 'SPEC-0025/FR-NEW-[0-9]{3}' sdlc/stories/US-01[2-4]*.md | sed 's#.*/##' | sort -u | wc -l` prints 74.
- [ ] The two deployment prerequisites are written in the final report: the redirect URI in the Google console, the second host name (certificate and route).
- [ ] Note: Needs you before the first deployment (not before implementation): the owner adds the redirect URI in the Google console and accepts the second host name.
- [ ] One commit `US-0149: Closing journeys, documentation audit and acceptance of the whole spec` on the work branch, body with `Summary:` (2 to 4 plain lines), `Spec: SPEC-0025` and the requirement ids.
