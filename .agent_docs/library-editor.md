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

## Hostile deck script

A deck script runs on the content origin with no library cookie (the session cookie is on the library origin, the grant
cookie is `HttpOnly`) and an empty storage: `tests/test_library_viewer_e2e.py` E2E-SEC-013 reads `stored:  | {} | {}`.
No server code exists for it, the test is the guard. Positive control: the same message does toggle edit mode for RW.

## Tests

`tests/test_library_viewer_e2e.py`; helpers in `tests/library_support.py`: `deck_with_notes` (real "ei" deck, notes on slide 1,
optional probe script), `open_presenter` (key S, returns the popup page).
