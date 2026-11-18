# Web library mode: the test support and the suite map (SPEC-0025)

Complements `library.md` (module map, flows) and `testing.md` (project wide rules).

## Support (`tests/library_support.py`)

`tests/library_support.py`: `library_server(**overrides)` fixture (free port, origins `http://slides.test:<port>`
and `http://slides-content.test:<port>`, temporary `library_dir` and `state_dir`, stopped at teardown),
`HttpClient(port, host)` (sets `Host`, keyword headers `x_forwarded_proto=` become `X-Forwarded-Proto`),
`FakeClock`. Use it in a test module with `library_server = library_support.library_server`.
Sign in support (US-0126): `start(google=fake, google_registered=True)` writes a credentials file pointing at the
`FakeGoogle` (fixture `fake_google`: `choose(email)`, `cancel()`, `accounts[email]` claim overrides,
`registered_redirects` = the console, `exchange_failure` `close`/`unavailable`/`bad_json`, `received`);
`running.browser(resolver)` is a `Browser` (cookies, redirects across hosts, `visited`, `replies`, `sign_in`,
`sign_out` with `Origin`); `LibraryReply.folder_rows()` (id, escaped name, role label of each home row);
`running.builder` (`folder` with `names.name_key`, `folders(*names)`, `member`, `standard()`) and `running.stored` (`sessions`,
`logins`, `folder_names`, `activity`, `rows`); fixture `evil_listener` counts visits to evil.example; US-0128:
`running.restart()`, `running.unreadable_database()`, `Browser.reopened()` (only cookies with `Max-Age` survive).
Folder page (US-0129): `builder.presentation(folder_id, name, *, size, modified, slides=1, title=None)` (a generated
deck padded with an HTML comment to exactly `size` bytes, below the smallest deck the start of one; `os.utime`),
`builder.standard_presentations(ids)` (the five decks of spec section 9, about 11 MB: only where a test needs them),
`builder.numbered_folders(count, email=None, role="RW")` (`Folder 001`...), `LibraryReply.presentation_rows()`,
`launch_chromium(playwright, *other_hosts)`, `person_context(chromium, running, session, zone=)`, `EVIL_HOST` and
`RecordingListener.page` (a hostile HTML page served from loopback).
US-0131: `StoredLibrary(library_dir, state_dir).entries()` (every path under both directories as `library/...` and
`state/...`), `LibraryBuilder(database, clock, state_dir).records(presentation)` (two history versions, two requests, one
AI suggestion through `HistoryStore`, `RequestService`; returns `<state_dir>/files/<key>`).
US-0132: `Browser.add_member(fid, email, role)`, `Browser.remove_member(fid, email)`, `LibraryReply.member_rows(fid)`
(address, role label; asserts the folder's `Members` section exists), `StoredLibrary.members()`, `signed_in`, `visible_texts`.
US-0130: `Browser.post_json(path, payload, headers=None)` (default `page_post_headers()`: `Origin`, `Sec-Fetch-Site:
same-origin`, JSON type), `LibraryReply.activity_lines()` (unescaped `(UTC ISO, actor, text)`).
US-0133: `start(scheme="https")`, `Browser.deck_cookies` (content origin, by path; `X-Forwarded-Proto` sent when the
origins are https), `open_presentation(pid)`, `deck(pid, route, follow=, x_editor="1")`, `grant(pid)`, `copied()`;
`sign_out` posts to the library origin wherever the browser is; `StoredLibrary.tickets()`, `grants()`.
Modules: `tests/test_library_<area>_http.py` (HTTP) and `_e2e.py` (Chromium) for the areas `visitor`, `auth`, `home`,
`sessions`, `gate`, `folders`, `admin`, `foldel`, `members`, `open`, plus `test_library_names.py` (units); each module docstring lists its spec ids.

## The later stories

- Editing and downloads (US-0136, US-0140): `Browser.save(pid, html, base_mtime=, force=)`, `post_deck(pid, route, payload)`,
  `send_save_length`, `running.versions(presentation)` and `version_text`, `EditorLibrary` (a running library, the standard
  presentations and `open(email, name, edit=)`), `turn_edit_on`, `type_in_title`, `leave_field`, `stored_title`, `with_title`,
  `deck_with_notes`; the fixture sets `HTMLEDITOR_STATE_DIR` as production does.
- Uploads (US-0141 to US-0145): `Browser.upload(fid, name, data, replace=)`, `upload_declaring`, `upload_streaming(fid, name, body,
  UploadPlan(declared, cut_at, pause_at, paused, resume, bytes_per_second, chunked, replace))`, `delete_presentation(pid,
  method=)`, `valid_deck(slides, size)`, `disk_full()`, `CountingReader`; `start(seed=True)` creates the initial content.
- Operator (US-0147): the command is run through `tests.deck_support.run_cli` (it keeps the process wide tracer untouched).
- Journeys (US-0149): `test_library_journeys_http.py` and `_e2e.py`; the classes of exploit tests are `test_exploit_*` or
  `test_e2e_sec_*` in the file of their area.

## Budget

The whole library suite (`make test ARGS='-k library'`) is 656 tests and runs in about 225 s on a quiet machine, above the 90 s
of DEC-049: the browser tests, the 10 Mbit/s upload (E2E-071, about 21 s) and the two 25 MB bodies weigh most. The real time bound
of E2E-076 (`test_library_limits_slow.py`, about 25 s) is `slow`: `make test ARGS='-m slow -k library'`. Some tests of the local
shell (`test_shell_shortcuts_e2e.py`, `test_help_shortcuts_e2e.py`) and `test_library_shell_e2e.py` flake under load during
`make check` and pass alone.
