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

## Hostile deck script

A deck script runs on the content origin with no library cookie (the session cookie is on the library origin, the grant
cookie is `HttpOnly`) and an empty storage: `tests/test_library_viewer_e2e.py` E2E-SEC-013 reads `stored:  | {} | {}`.
No server code exists for it, the test is the guard. Positive control: the same message does toggle edit mode for RW.

## Tests

`tests/test_library_viewer_e2e.py`; helpers in `tests/library_support.py`: `deck_with_notes` (real "ei" deck, notes on slide 1,
optional probe script), `open_presenter` (key S, returns the popup page).
