# SPEC-0004: Background autosave takes focus away from the zone being typed in, design

> Spec: sdlc/specs/SPEC-0004-autosave-focus-loss/spec.md
> Nature: BUG
> Depth: S
> Security: n/a
> Designed on: 2026-10-10
> Target tier: 2 (default: no `--tier`, no `Tier:` in `sdlc/constitution.md`, no `.spec.json`)

## 1. Stack and skills

| Element | Choice | Version | DEC |
|---|---|---|---|
| Browser code | vanilla JS, no build step (existing) | n/a | existing code `src/mcp_htmleditor/static/editor.js` |
| Browser tests | pytest + pytest-playwright, Chromium (existing) | `pytest-playwright>=0.6` (`pyproject.toml:35`) | DEC-003 |

Skills loaded: python. Effect: tests run only through `make test` / `make check`; coverage gate 80 %;
no new dependency.

## 2. Approaches

### Chosen: serialize a detached clone (fix at the root cause site)
`saveContent` builds the saved HTML from a deep clone of the document element and strips every
editor artifact on the clone. The live DOM is never mutated by a save, so focus, caret, selection and
keystrokes cannot be affected. Pros: removes the cause, not the symptom; no focus or blur events fire,
so `onEditableBlur` cannot re-enter `saveContent`; serialized output is identical to today. Cons: one
extra in-memory copy of the document per save (same order as the `outerHTML` string already built).
Scope: `saveContent` only. Best suited when the live DOM must stay untouched.

### Rejected: strip in place, then restore focus and selection
Record `activeElement` and the selection ranges, strip, serialize, restore, refocus. Rejected
(DEC-002): removing `contenteditable` from the focused node fires `blur`, whose handler
(`src/mcp_htmleditor/static/editor.js:1395`) calls `saveContent` again; refocusing fires `focus`, which
re-shows the insert bar (`src/mcp_htmleditor/static/editor.js:576`); IME composition in progress would
be cancelled. Treats the symptom.

## 3. Architecture

One function changes: `saveContent` (`src/mcp_htmleditor/static/editor.js:1398`). Its stripping block
(`:1403` to `:1433`) is replaced by a clone based serialization. Everything after the HTML string is
built (`selfSaving`, `POST /content`, mtime adoption, `markSaved`) is unchanged. Server side cleaning
(`src/mcp_htmleditor/http_server.py:294`) is unchanged and still runs. `captureDomSnapshot`
(`src/mcp_htmleditor/static/editor.js:370`) is out of scope (spec Assumption; BL-0014).

## 4. Data model

None. Saved file format unchanged (BR-004).

## 5. Contracts and interfaces

- `POST /content` body `{"html": "<!DOCTYPE html>\n<html ...>...</html>"}`: unchanged.
- Clone stripping, applied to `clone = doc.documentElement.cloneNode(true)` (DEC-001):
  - every `[contenteditable]`: attribute removed, inline `outline` and `cursor` cleared;
  - `#_mcp_format_bar`, `#_mcp_insert_bar`: `style.display = 'none'` (same output as today);
  - `._mcp_drag_handle`, `._mcp_drop_indicator`: removed;
  - class `_mcp_drag_host`: removed.
- Serialized string: `'<!DOCTYPE html>\n' + clone.outerHTML`.

## 6. File structure impact

| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/static/editor.js` | modify `saveContent` | BR-001, BR-002, BR-003, BR-004 | US-0001 |
| `tests/test_autosave_focus_e2e.py` | create | BT-001, BT-010..BT-014, BT-020..BT-022 | US-0001 |
| `.agent_docs/html-conventions.md` | modify § Editor artifacts: saves serialize a clone, never mutate the live DOM | DEC-001 | US-0001 |
| `.agent_docs/testing.md` | modify test file map: new e2e file | DEC-003 | US-0001 |

Affected existing tests: all kept (`tests/test_undo_redo_e2e.py`, `tests/test_website_template_e2e.py`,
`tests/test_tab_title_e2e.py`, `tests/test_fullscreen_e2e.py`, `tests/test_http_helpers.py`).
Affected documentation: the two `.agent_docs` files above. README and AGENTS.md unchanged.

## 7. Compatibility and risks

- No consumer change: file format and HTTP contract identical.
- Risk: an artifact added later to `editor.js` but not to the clone stripping leaks into the client
  payload; the server strip (`http_server.py:443`) still removes it. Accepted.
- Baseline gate is red (BL-0004: format check on `tests/test_tab_title_e2e.py`, port range test
  machine dependent). The story cannot land with `make check` green unless BL-0004 is fixed first or
  the run happens with ports 7840 to 7849 free and the format issue fixed. Recorded as a story
  constraint.
- Rollback: revert the story commit.

## 9. Test strategy

| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| BT-001 | functional e2e | Playwright Chromium + real HTTP server | `tests/test_autosave_focus_e2e.py::test_typing_after_autosave_stays_in_the_zone` | US-0001 |
| BT-010 | functional e2e | same | `::test_caret_offset_survives_a_save` | US-0001 |
| BT-011 | functional e2e | same | `::test_selection_survives_a_save` | US-0001 |
| BT-012 | functional e2e | same | `::test_leaving_a_zone_keeps_focus_in_the_next_zone` | US-0001 |
| BT-013 | functional e2e | same | `::test_several_saves_lose_nothing` | US-0001 |
| BT-014 | functional e2e | same, `page.route("**/content", abort)` on POST | `::test_failed_save_keeps_focus` | US-0001 |
| BT-020 | functional e2e | same, file read from disk | `::test_saved_file_has_no_editing_markers` | US-0001 |
| BT-021 | functional e2e | same | `::test_self_save_does_not_reload_the_preview` | US-0001 |
| BT-022 | functional e2e | same | `::test_status_dot_returns_to_saved` | US-0001 |
| BT-023 | regression suite | `make test` | existing e2e files | US-0001 |

Test data: generated, copy of the `doc` bootstrap (`templates/bootstrap/document-empty.html`, title
`Titre du document` at line 61, `h2` `Introduction` at line 67) into `tmp_path`, as in
`tests/test_undo_redo_e2e.py::_plain_document`. BT-001 is red today: focus moves to `BODY` and `BBB`
is missing (observed 2026-10-10).

## 10. Decisions log

- **DEC-001:** `saveContent` serializes a deep clone of `doc.documentElement` and strips editor
  artifacts on the clone only; the live DOM is never mutated by a save. **Obliged by:**
  SPEC-0004/BR-001, BR-002, BR-003, BR-004. **Rationale:** removes the root cause
  (`editor.js:1410`) with identical output. **Alternatives considered:** strip in place then restore
  focus and selection (DEC-002). **Source:** design. **Evidence:** `src/mcp_htmleditor/static/editor.js:1398`.
- **DEC-002:** Do not save and restore focus or selection around an in place strip. **Obliged by:**
  SPEC-0004/BR-001. **Rationale:** the strip fires `blur`, which re-enters `saveContent`
  (`editor.js:1395`), and `focus`, which re-shows the insert bar (`editor.js:576`). **Alternatives
  considered:** none further. **Source:** existing code. **Evidence:** `editor.js:1395`, `editor.js:576`.
- **DEC-003:** New tests live in a new file `tests/test_autosave_focus_e2e.py`, reusing the harness
  pattern of `tests/test_undo_redo_e2e.py` (`_start`, `_inner`, `_enable_edit_mode`, `needs_chromium`)
  copied locally, not imported across test modules. **Obliged by:** SPEC-0004/BT-001 (end to end
  reproduction). **Rationale:** existing e2e files are self contained (each defines its own harness).
  **Alternatives considered:** add to `tests/test_undo_redo_e2e.py` (different subject); move the
  harness to `conftest.py` (touches every e2e file, out of scope). **Source:** existing code.
  **Evidence:** `tests/test_undo_redo_e2e.py:108`, `tests/test_tab_title_e2e.py:29`.
- **DEC-004:** `captureDomSnapshot` is not changed. **Obliged by:** n/a (no code impact): spec
  Assumption excludes structural actions; BL-0014 tracks the duplication. **Rationale:** keep the fix
  inside the spec. **Alternatives considered:** share one clone based helper. **Source:** spec
  constraint. **Evidence:** `editor.js:370`.

## 11. Stories

| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0001 | Autosave serializes a clone and never moves focus | P1 | BR-001, BR-002, BR-003, BR-004 | main | 2 | yes |
