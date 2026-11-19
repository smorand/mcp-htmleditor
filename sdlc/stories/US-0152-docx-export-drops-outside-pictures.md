# US-0152: DOCX export drops outside pictures

> Spec: SPEC-0026 (sdlc/specs/SPEC-0026-pictures-outside-deck-folder/)
> Nature: BUG
> Priority: P1
> Depends on: US-0150
> min_tier: 2
> Files touched: 2
> Closes spec: no

## Objective
The DOCX export no longer embeds a picture that lies outside the deck's folder: pandoc embeds whatever the staged HTML names, so the export removes each outside `<img>` itself, before pandoc runs, and warns.

## Requirements covered
- SPEC-0026/BR-004 [EARS-U]: The DOCX export SHALL NOT embed a local picture named by an image `src` when that picture is outside the deck's folder. It judges the address written in the `src` of each image tag, before conversion.
- SPEC-0026/BR-005 (partial: the DOCX export) [EARS-O]: IF an export refuses a picture because it is outside the deck's folder, THEN THE export SHALL continue without it and SHALL add to its warnings the text `Image hors du dossier du deck, ignoree: <src>`. The DOCX export removes the `<img>` from the document it converts and puts nothing in its place.
- SPEC-0026/BR-006 (partial: the DOCX export) [EARS-U]: The product SHALL judge a picture by its resolved real path.

## Independent Test
`make test ARGS='tests/test_export_docx_outside.py'` is green (skips like the other DOCX tests when pandoc is absent). BT-013 reads `word/media/` of the DOCX: no entry equals the bytes of `secret.png`.

## Design excerpt
### Decisions
- DEC-006: `_drop_outside_pictures(html, root)` parses the prepared HTML with BeautifulSoup, judges the `src` of each `<img>` (skips empty, `data:`, `http(s)://`, `//`; a `file://` goes through `url_to_path`; anything else is a path relative to `root`, an absolute path being judged as is), removes each outside `<img>` (`decompose()`), returns the new HTML and one `outside_warning(src)` per removal. Pandoc was checked on 2026-11-18: it embeds `../secret.png`, an absolute path and a `file://` address.
### Contracts
In `src/mcp_htmleditor/export/to_docx.py`, function `to_docx` (line 97): after `prepared = preprocess_html(...)` and `warnings = list(prepared.warnings)`, replace `prepared.html` use by the cleaned HTML (`html, dropped = _drop_outside_pictures(prepared.html, input_path.parent)`; `warnings.extend(dropped)`; write `html` to the staged file at `staging.write_text(...)`, line 135). `PreprocessedHtml` is a dataclass: do not mutate it if frozen, use the local `html`. Import `is_inside`, `outside_warning`, `url_to_path` from `..deck_folder`.
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/export/to_docx.py` | modify |
| `tests/test_export_docx_outside.py` | create |
### Existing patterns
DOCX tests: `tests/test_export_docx.py:223-228` (deck with `figure.png` in the folder), pandoc skip logic in that file; CLI driver `run_cli` (`tests/deck_support.py:244`). The existing `src` pre pass reads `soup.find_all("img")` at `to_docx.py:263-264`.

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.

### SPEC-0026/BT-013: DOCX export (occurrence `to_docx.py:143-144`)
- Level / Driver / Location: exploit / CLI `export docx` / `tests/test_export_docx_outside.py`
- Red before the fix because: `word/media/` of the DOCX holds a file equal to `secret.png` (pandoc embeds it).
- Given `tmp/deck/doc.html` (a `doc` template file) with `<img src="../secret.png">`, `<img src="<tmp>/secret.png">` and `<img src="file://<tmp>/secret.png">`; `tmp/secret.png` a red 2x2 PNG
- When the user runs `export docx tmp/deck/doc.html tmp/out.docx`
- Then exit status 0, no `word/media/` entry of `out.docx` equals `secret.png`, and the error stream holds three lines starting `Attention: Image hors du dossier du deck, ignoree: `

## Constraints
- Files not to touch: PPTX modules, `render/`, existing tests.
- Dependencies not to add: none (BeautifulSoup is already imported by `to_docx.py`).
- Patterns to avoid: pandoc `--sandbox` (blocks the reference document); leaving an empty paragraph or the `alt` text where the picture was.
- Scope boundary: pandoc's own fetch of `http(s)` pictures stays as is (out of class, spec 1bis).

## Definition of done
- [ ] RED evidence recorded for the new test before the production code.
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_export_docx.py` (`:223-228`, `:475`) unchanged and green.
- [ ] Self review: `data:`, remote and `//` addresses are never judged; an inside picture keeps its `<img>`; the staged file is written from the cleaned HTML.
- [ ] One commit `US-0152: DOCX export drops outside pictures` on the work branch, body with `Summary:`, `Spec: SPEC-0026` and the requirement ids.
