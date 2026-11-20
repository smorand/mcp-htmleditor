# US-0160: the decoration rules route

> Spec: SPEC-0029 (sdlc/specs/SPEC-0029-picker-embeds-decoration/)
> Nature: FEAT
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 3
> Closes spec: no

## Objective
The editor server can give the page the decoration rules (embedded or linked, files copied) for a list of Breathe classes, with the command's messages on refusal. No page change yet.

## Requirements covered
- SPEC-0029/FR-NEW-001 (partial: the rules the page will add): WHEN the author inserts a layout in a Breathe deck THE Editing context SHALL, for every background and icon class of the new slide that has no rule in the deck's decoration block, add its rule to the block. The rules are those `breathe-inline` writes for the same classes.
- SPEC-0029/FR-NEW-003 (partial: the linked form on the server): linked rules refer to `assets/<file>` and the missing files are copied there; otherwise the pictures are embedded.
- SPEC-0029/FR-NEW-004 (partial: the reasons): the reason is the message `breathe-inline` gives for the same failure.

## Independent Test
`make test ARGS='tests/test_breathe_assets_route.py'` green, `make check` green.

## Design excerpt
### Decisions
DEC-002 one function reusing the command's blocks. DEC-007 route on the local handler only. DEC-008 body via `_read_json_object`, at most 64 classes.
### Contracts
`src/mcp_htmleditor/breathe/inline.py` (after `embed_assets`):
```
@dataclass(frozen=True, slots=True)
class RulesOutcome:
    rules: list[str]
    copied: int
def decoration_rules(deck: Path, classes: Sequence[str], *, link: bool) -> RulesOutcome: ...
```
For each class: prefix `med-bg-` maps to file `bg-<suffix>.png`, `med-ico-` to `icon-<suffix>.png` (`CLASS_FILES`), any other class: `DeckError(f"class {name} is not a decoration class")`. Build `_Need(suffix, file_name, 0)` per class, then `_check_names`, `_check_links(needs, folder)`, `sources = _locate(needs, folder, catalogue)`, rules via `_rule(cls, need.file_name, sources, link)` in the order given, `copied = _copy_missing(sources, folder, created)` only when `link` (undo with `_undo_copies` on `DeckError`). `folder = deck.resolve().parent / "assets"`. Classes repeated in the list are built once. Empty list: empty outcome, no I/O.
`src/mcp_htmleditor/http_server.py`: in `do_POST` add `elif path == "/breathe-assets": self._breathe_assets()` and the handler:
```
def _breathe_assets(self) -> None:
    served = self._served_file()
    if not served: -> 404 {"error": "No file loaded"}
    body = self._read_json_object(); None -> return (refusal already sent)
    classes = body.get("classes"); link = body.get("link", False)
    invalid (not a list of str, more than 64, link not bool) -> self._refuse_request(400, "Invalid request body")
    with trace_span("mcp.breathe_assets", {"file.path": served, "breathe.link": link, "breathe.classes": len(classes)}):
        try: outcome = decoration_rules(Path(served), classes, link=link)
        except DeckError as exc: self._refuse_request(422, str(exc)); return
    self._send_json({"rules": outcome.rules, "copied": outcome.copied})
```
Import `decoration_rules` and `DeckError` where `http_server.py` already imports its siblings (lazy import inside the handler is fine, as `_run_arch_layout` does).
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/breathe/inline.py` | modify |
| `src/mcp_htmleditor/http_server.py` | modify |
| `tests/test_breathe_assets_route.py` | create |
### Existing patterns
HTTP route tests with a real server: `tests/test_http_*` files and the `served_deck` / `ServedDeck.request(method, route, body, ...)` helper (`tests/conftest.py:203-230`); the command tests in `tests/test_breathe_inline.py` for deck fixtures (`deck_with`, `breathe_slide`).

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.
Level: integration, driver: HTTP through `ServedDeck.request("POST", "/breathe-assets", json_bytes)` (JSON content type) on a served Breathe deck copy; location `tests/test_breathe_assets_route.py`.
### T-1: embedded rules equal the command's
- Given a served Breathe deck whose block is empty / When classes `med-bg-cover-s0` and `med-ico-lungs-dark` are posted with `link: false` / Then 200, `rules` has 2 entries that start `  .med-bg-cover-s0 { background-image:url(data:image/` and `  .med-ico-lungs-dark {`, equal to the rules `breathe-inline` writes for a copy of the deck using the same classes, and `copied` is 0
### T-2: linked rules copy the files
- Given the same deck / When posted with `link: true` / Then 200, the rules read `url(assets/bg-cover-s0.png)` and `url(assets/icon-lungs-dark.png)`, `copied` is 2, and the two files exist in `assets` next to the deck
### T-3: refused names change nothing
- When classes `med-bg-../../secret`, `med-bg-/etc/passwd`, `not-a-class` are posted (one request each) / Then 422 with `asset name ../../secret is not a plain file name` (for the traversal), or `class not-a-class is not a decoration class`, no file created, deck bytes unchanged
### T-4: a missing catalogue file
- Given `catalogue_dir` monkeypatched to an empty folder / When `med-bg-cover-s0` is posted / Then 422 `asset bg-cover-s0.png not found in: <deck folder>/assets, <empty folder>`
### T-5: an unwritable folder, linked
- Given the deck folder made read only / When posted with `link: true` / Then 422 starting `Cannot write ` and no `assets` folder left (skipped when running as root)
### T-6: request shape
- Posting a body that is not an object, `classes` not a list of strings, 65 classes, `link` not a boolean / Then 400 `Invalid request body`; a request without the JSON content type gets 415; with no file loaded 404 `No file loaded` (use a server started on no file if the fixture allows, else assert through the handler's gate test)
### T-7: the library keeps refusing
- No new test (the library route table is unchanged: `tests/test_library_*` stay green).

## Constraints
- Files not to touch: `static/*`, the library modules, `cli.py`, the other tests.
- Dependencies not to add: none.
- Scope boundary: the page is US-0161.

## Definition of done
- [ ] RED evidence for the new tests before the production code (an unknown route answers 404).
- [ ] Every test above green; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_breathe_inline.py`, `tests/test_http_*`, library tests unchanged.
- [ ] One commit `US-0160: the decoration rules route`, body with `Summary:`, `Spec: SPEC-0029` and the requirement ids.
