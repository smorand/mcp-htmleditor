# SPEC-0029: Layout picker brings the Breathe decoration, design

> Spec: sdlc/specs/SPEC-0029-picker-embeds-decoration/spec.md
> Nature: FEAT
> Depth: M
> Security: n/a
> Designed on: 2026-11-19
> Target tier: 2 (default)

## 1. Stack and skills
Existing stack, no new dependency: Python 3.13 (editor server `http_server.py`, `breathe/inline.py`), vanilla JS editor scripts, Playwright e2e tests. Skills loaded: python (`make` only, `trace_span` on external calls, no `os.environ` read, JSON routes through the existing gate).

## 2. Approaches
### Chosen: the page asks the server for the rules, adds them to its live style block, saves normally
The page (which knows the new slide and its classes) POSTs the missing class names; the server (which can read the catalogue and write `assets/`) returns the rules by reusing the command's functions; the page inserts them before the end marker of the block and saves. Pros: no reload, undo history intact, one rule builder shared with the command. Cons: one new route.
### Rejected: save, run `embed_assets` on the file, reload the frame
It rescans the file, reloads the preview and the page drops the undo stacks on a reload (DEC-001).
### Rejected: ship the catalogue to the page
Hundreds of KB of base64 in the page for rules most decks never need (DEC-001).

## 3. Architecture
Page: `editor-slides.js` `insertSlide` gets a follow up step `addBreatheDecoration(doc, slide)` after its `saveContent()`. Server: `POST /breathe-assets` in `http_server.py` next to `/arch-layout` (`http_server.py:322-336`), calling `decoration_rules` in `breathe/inline.py`. The web library handler refuses unregistered POSTs (`library/routes_deck.py:108-109`), and a library presentation is not a Breathe deck with the assets marker the page looks for, so the step does nothing there.

## 4. Data model
None.

## 5. Contracts and interfaces
Route `POST /breathe-assets`, JSON body `{"classes": ["med-bg-<x>", "med-ico-<x>", ...], "link": false}` (at most 64 classes; the body goes through the existing `_read_json_object` rules: JSON content type, at most 1 MiB). Answer 200 `{"rules": ["  .med-bg-x { background-image:url(...); }", ...], "copied": <int>}`; refusal 4xx `{"error": "<the breathe-inline message>"}`; no file loaded 404 `{"error": "No file loaded"}`. Same origin gate as `/content`.
`breathe/inline.py`: `decoration_rules(deck: Path, classes: Sequence[str], *, link: bool) -> RulesOutcome(rules: list[str], copied: int)`; classes that do not start with `med-bg-` or `med-ico-` are refused with `DeckError("class <name> is not a decoration class")`; names go through `_check_names`, `_check_links`, `_locate`, `_rule`, `_copy_missing` exactly as `embed_assets`; on a write error the copies are undone (`_undo_copies`) and `DeckError` raised.
Page: new notice element `#decoration-error` (`editor.html`, in `#notices`), text `Decoration not added: <reason>`; hidden at the start of each insertion, never cleared by a save. Reasons: the server message, or `the editor server did not answer` (network error, timeout, or a non 2xx answer without a message).

## 6. File structure impact
| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/breathe/inline.py` | modify: `RulesOutcome`, `decoration_rules` | FR-NEW-001, 003, 004 | US-0160 |
| `src/mcp_htmleditor/http_server.py` | modify: route `POST /breathe-assets`, handler, body bound | FR-NEW-001, 003, 004 | US-0160 |
| `tests/test_breathe_assets_route.py` | create | route and function behavior | US-0160 |
| `src/mcp_htmleditor/static/editor-slides.js` | modify: `addBreatheDecoration`, hide notice at insertion | FR-NEW-001..006, FR-MOD-001 | US-0161 |
| `src/mcp_htmleditor/static/editor.html` | modify: `#decoration-error` | FR-NEW-004 | US-0161 |
| `tests/test_picker_decoration_e2e.py` | create | E2E-001..007, 009..015 | US-0161 |
| `tests/test_breathe_reference.py` | modify: `test_inserted_layout_before_and_after_embedding` | E2E-008 (declared) | US-0161 |
| `README.md`, `skill/topics/breathe.md`, `.agent_docs/breathe.md`, `.agent_docs/architecture.md` | modify | documentation | US-0162 |
Affected existing tests: `tests/test_breathe_reference.py::test_inserted_layout_before_and_after_embedding` (declared modified by the spec, E2E-008).

## 7. Compatibility and risks
Additive. A deck without the `breathe:assets` marker is never touched (FR-NEW-006). Library mode: the page's step requires the marker in the style and the local save path; the library's own pages keep their route table. Risk: the undo snapshot is taken before the insertion (`editor-slides.js:55`, `snapshotForUndo`), so Undo restores the document without the new rules (FR-NEW-002); the redo snapshot must hold them (taken by `performUndo` from the current DOM, after the rules were added). Rollback: revert.

## 8. Security design
Not flagged, but the new route takes names from the page: they are checked by `_check_names` (`PLAIN_NAME`) and the prefix test before any path is built, files only come from the deck's own `assets` folder or the shipped catalogue (`_locate`), links are refused by `_check_links`. Tests: a class `med-bg-../../x` and an absolute one are refused (route test), no file is copied.

## 9. Test strategy
| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| route and function: embedded rules, linked rules and copies, refused names, missing asset, unwritable folder, body bounds, no file | integration | HTTP client on the real server | `tests/test_breathe_assets_route.py` | US-0160 |
| E2E-001..007, 009..015 | functional e2e | Chromium, real editor server | `tests/test_picker_decoration_e2e.py` | US-0161 |
| E2E-008 | functional e2e (modified) | Chromium | `tests/test_breathe_reference.py` | US-0161 |
Test data: the Breathe bootstrap (`tests/breathe_support.py` `BOOTSTRAP`), `serve_deck`, the helpers of `tests/test_breathe_reference.py` (`open_picker`, `slides_on_disk`, `Serve`). E2E-004 monkeypatches `catalogue_dir` to a copy lacking one file (the server runs in the test process). E2E-009 aborts the POST with `page.route`.

## 10. Decisions log
- **DEC-001:** the page asks the server for rules and inserts them live (no reload). **Obliged by:** SPEC-0029/FR-NEW-001, FR-NEW-002. **Alternatives considered:** run the command on the file and reload (loses undo); ship the catalogue to the page. **Source:** design. **Evidence:** `static/editor-slides.js:50-80`, `breathe/inline.py:76`.
- **DEC-002:** one function `decoration_rules` reusing the command's building blocks so the rules are identical to the command's. **Obliged by:** SPEC-0029/FR-NEW-001 (same rules as `breathe-inline`), FR-NEW-004 (same messages). **Source:** existing code. **Evidence:** `breathe/inline.py:130-206`.
- **DEC-003:** the page decides the form: linked when any existing rule contains `url(assets/`, else embedded. **Obliged by:** SPEC-0029/FR-NEW-003. **Source:** spec.
- **DEC-004:** the page computes the missing classes from the new slide (tokens starting `med-bg-` or `med-ico-`, the slide element included) minus the classes with a rule in its block (regex `\.(med-(?:bg|ico)-[A-Za-z0-9_-]+)\s*\{`); no request when none is missing. **Obliged by:** SPEC-0029/FR-NEW-005. **Source:** design.
- **DEC-005:** the page adds the returned rules just before the `/* breathe:assets:end */` marker in the `<style>` that holds it, then calls the normal `saveContent()`. **Obliged by:** SPEC-0029/FR-NEW-001, FR-NEW-002. **Source:** design.
- **DEC-006:** a new notice element, not `#save-error`, because the save that follows an insertion clears `#save-error`. **Obliged by:** SPEC-0029/FR-NEW-004 (the notice stays through the save). **Evidence:** `static/editor-save.js:106,116,146`.
- **DEC-007:** the route lives on the local editor handler only; the library handler refuses it, so the page's step is inert there. **Obliged by:** spec scope 3.2 (library out of scope). **Evidence:** `library/routes_deck.py:108-109`.
- **DEC-008:** the body is read with `_read_json_object` (content type 415, 1 MiB bound) and the list is limited to 64 classes (a layout uses fewer than 10). **Obliged by:** SPEC-0029 NFR 7.5 (reliability). **Source:** existing code. **Evidence:** `http_server.py:612-640`.

## 11. Stories
| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0160 | the decoration rules route | P1 | FR-NEW-001, FR-NEW-003, FR-NEW-004 (server part) | main | 2 | no |
| US-0161 | the picker adds the decoration | P1 | FR-NEW-001..006, FR-MOD-001 | US-0160 | 2 | no |
| US-0162 | documentation of the picker decoration | P2 | FR-NEW-001 (docs) | US-0161 | 2 | yes |
