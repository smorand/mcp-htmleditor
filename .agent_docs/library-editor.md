# Web library mode: the editor shell of a presentation (SPEC-0025)

Complements `library.md` (shell route, grant, `editor-library.js` fetch prefix).

## Read only form (US-0135, DEC-039)

- Role `RO` in the folder (`Role.RO` only, not `RW`, not `Admin`): `library_shell(..., role)` puts `"readOnly": true` in the
  `editor-config` meta and inserts `READ_ONLY_STYLE` (`display:none !important` on `#edit-mode-btn`, `#undo-btn`,
  `#redo-btn`, `#requests-toggle`, `#ask-ai-btn`, `#notes-btn`, `#toolbar-slide-actions`, `#toolbar-doc-actions`,
  `#export-docx-btn`, `#requests-side`, `#ask-ai-panel`, `#notes-panel`) right after the library script tag.
- Why a style block: the editor CSS gives some ids `display: inline-flex` and its scripts rewrite `style.display`, so neither
  `hidden` nor an inline style holds; no node is removed because `editor-requests.js` reads `#requests-side`.
- `editor-library.js` loads first, so with `readOnly` it registers capture listeners: `keydown` (key `e`, no modifier:
  `preventDefault` + `stopImmediatePropagation`) and `message` (`deck-key` with key `e`). The editor scripts are untouched.
- Kept for RO: full screen (F), pointer, presenter window (S, speaker notes), HTML and PPTX download, help.
- Hiding is usability only; the server refusal of writes (US-0136) is the control.

## Saving a change (US-0136, DEC-003, DEC-022, DEC-028)

- `POST /d/<pid>/content` (`routes_deck.py`: `EDIT`, `is_json`, answered as `EditorAnswer("save")`) is the inherited
  `_receive_content`: no save pipeline is copied. `check_conflict`, `write_save` and `atomic_write` are unchanged.
- Order on the content origin: route found, then `_refused_by_origin_rule` (a state changing method needs `Origin` equal to
  the content origin, `Sec-Fetch-Site` absent or `same-origin`/`none`, and `application/json`; refusal is the JSON
  `Access denied.`), then grant, presentation, role (`authorize(role, EDIT)`, a RO role is refused before the body is
  read), then the handler.
- `LibraryHandler._save_lock()` returns `LibraryServer.save_lock(pid)`: a `PresentationLock` (one `threading.Lock` per
  presentation id from `lock_for`, created on first use under one guard lock). After acquiring it re-reads the row and raises
  `SaveRefusal(403, DENIED_PAYLOAD)` when the presentation was deleted meanwhile, so a save that lost the race creates
  nothing. Uploads and deletions of later stories take the same lock.
- History: `atomic_write` keeps the previous version under `<state_dir>/files/<key>/history/` with the state directory of
  the environment (`HTMLEDITOR_STATE_DIR`), so `webserve` must run with the state directory of its settings; the
  `library_server` fixture sets it. Stored changes write nothing in the activity table (FR-NEW-051).
- Answers are those of the local mode: 200 `{ok, mtime}`, 409 conflict, 413 `Request too large`, 500 with the operating
  system reason (`_failure_reason`, never a path). The timers (0.8 s, at once on blur, 0.6 s after a slide action) are the
  editor's own.

## Session or right ends while a presentation is open (US-0137, DEC-037, DEC-040)

- Deck routes answer a request with `X-Editor: 1` with a `code`: `401 session_expired` (grant ended or absent) or
  `403 denied` (live grant, no right, presentation or folder gone). Without the header: `302 /open/<pid>` on navigation
  routes, `403 Access denied.` otherwise.
- `Accounts.grant_for` rebinds a grant whose session expired by time to the newest live session of the same address created
  after it, up to 24 hours after the expiry (`ENDED_SESSION_KEPT_SECONDS`); a session ended by sign out cascades its grants
  away, so that grant never revives. A second sign in in another window is what lets the first window store again.
- `editor-library.js` (on `DOMContentLoaded`, the editor scripts are untouched) reassigns the global functions
  `showSaveError` (the two English texts shown alone, no `Save failed:` prefix), `notePollFailure` (a poll answer with a
  `code` is a quiet pause: no count, no lost connection notice) and `window.alert` (a message ending with `Access denied.`
  is alerted as that alone); the click on `#download-btn` goes through `fetch` (200 saves the blob, `session_expired`
  navigates to the library unless text is unsaved, `denied` alerts `Access denied.`).
- Nothing unsaved means nothing shown (FR-NEW-074): saves only exist with pending text, and the poll stays quiet; moving
  between slides never calls the server.
- Tests: `test_library_access_e2e.py` (the clock of the server moves past 30 days with `running.clock.advance`),
  `test_library_grants_http.py`.

## Requests, Ask AI and arch layout (US-0138, DEC-003, DEC-044)

- `routes_deck.py` rows (all `EDIT`, the POST ones `is_json`, so the origin rule applies): `GET /d/<pid>/requests`,
  `POST /requests`, `POST /requests/delete`, `POST /review/apply`, `POST /arch-layout`. They are the inherited editor
  methods (`_list_requests`, `_queue_request`, `_delete_request`, `_apply_suggestion`, `_run_arch_layout`); the record is
  the presentation's own under `<state_dir>/files/<key>/requests/`. A RO role gets `403 denied` for each, the read included.
- `/export/docx` and every other path under `/d/<pid>/` stay `Access denied.` for every role; a test greps
  `library/routes_*.py` and `server.py` for `to_docx`, `deck.tools`, `render`, `new_file` imports.
- `/arch-layout` rewrites the stored file with its own atomic write and does not take the presentation lock (the local
  mode neither); a concurrent save then wins or loses whole, never a mix.

## Hostile deck script

A deck script runs on the content origin with no library cookie (the session cookie is on the library origin, the grant
cookie is `HttpOnly`) and an empty storage: `tests/test_library_viewer_e2e.py` E2E-SEC-013 reads `stored:  | {} | {}`.
No server code exists for it, the test is the guard. Positive control: the same message does toggle edit mode for RW.

## Tests

`tests/test_library_viewer_e2e.py`; helpers in `tests/library_support.py`: `deck_with_notes` (real "ei" deck, notes on slide 1,
optional probe script), `open_presenter` (key S, returns the popup page).
