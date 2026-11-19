# US-0150: folder rule and the PPTX flow export

> Spec: SPEC-0026 (sdlc/specs/SPEC-0026-pictures-outside-deck-folder/)
> Nature: BUG
> Priority: P1
> Depends on: main
> min_tier: 2
> Files touched: 4
> Closes spec: no

## Objective
A deck that names a picture outside its own folder (absolute path, `../`, symlink to elsewhere) no longer gets that picture embedded by the PPTX flow export. The export continues, names the picture in a warning, and creates the shared folder rule that the later stories reuse.

## Requirements covered
- SPEC-0026/BR-001 [EARS-U]: The PPTX export SHALL NOT read, whatever its finish, a local picture named by an image `src` or by the `url()` of a background class of the deck when that picture is outside the deck's folder. (this story: the flow export, `paint=False`)
- SPEC-0026/BR-005 (partial: the flow export and the library precedence) [EARS-O]: IF an export refuses a picture because it is outside the deck's folder, THEN THE export SHALL continue without it and SHALL add to its warnings the text `Image hors du dossier du deck, ignoree: <src>`, where `<src>` is the address as written in the deck, cut at its first 60 characters.
- SPEC-0026/BR-006 (partial: the flow export) [EARS-U]: The product SHALL judge a picture by its resolved real path: a symlink inside the deck's folder that leads outside is refused, and a symlink that leads to a place inside the folder is accepted.

## Independent Test
`make test ARGS='tests/test_deck_folder.py tests/test_export_pptx_outside.py'` is green; the same files fail before the change (RED evidence). BT-010 reads the zip of the produced PPTX: no `ppt/media/` entry equals the bytes of `secret.png`.

## Design excerpt
### Decisions
- DEC-001: one shared containment module applied at each read site. DEC-002: `resolve()` (not strict) then `is_relative_to(root.resolve())`. DEC-003: each site builds its path as today and adds only the check; the flow export keeps ignoring `file://` (joined to the folder, not found, existing warning `Image introuvable, ignoree`). DEC-005: one `outside_warning(src)`. DEC-007: in the library mode `embedded_pictures_only` is checked first.
### Contracts
Create `src/mcp_htmleditor/deck_folder.py`:
```python
OUTSIDE_PREFIX: Final = "Image hors du dossier du deck, ignoree: "
SOURCE_CHARS: Final = 60


def is_inside(root: Path, path: Path) -> bool: ...  # path.resolve().is_relative_to(root.resolve())
def url_to_path(url: str) -> Path | None: ...  # file:// -> Path(url2pathname(unquote(urlparse(url).path))), else None
def outside_warning(src: str) -> str: ...  # OUTSIDE_PREFIX + src[:SOURCE_CHARS]
def guard_browser(target: Any, root: Path) -> None: ...  # added by US-0151
```
Only the first three are written here; `guard_browser` is added by US-0151.
Edit `_image_source` in `src/mcp_htmleditor/export/pptx_images.py` (lines 117-125 today): after the `embedded_pictures_only` and remote checks, build `path` exactly as today, then:
```python
if not is_inside(self.ctx.base_dir, path):
    self.ctx.report.warn(outside_warning(src))
    return None
```
before the `path.exists()` check. `self.ctx.base_dir` is `source.resolve().parent` (`export/to_pptx.py:123`). The `url()` of a Breathe `med-bg-*` class reaches this method through `_add_picture` (`pptx_chrome.py:334`), so BT-015 is fixed by the same edit.
### Paths
| Path | Action |
|---|---|
| `src/mcp_htmleditor/deck_folder.py` | create |
| `src/mcp_htmleditor/export/pptx_images.py` | modify |
| `tests/test_deck_folder.py` | create (unit tests of `is_inside`, `url_to_path`, `outside_warning`) |
| `tests/test_export_pptx_outside.py` | create |
### Existing patterns
Test helpers: `tests/deck_support.py` (`build_deck`, `write_deck`, `deck_ei`, `run_cli`); PPTX media listing and deck fixture: `tests/test_export_pptx_library.py:40-47` (`media(output)`, `hostile(tmp_path)`, `deck(tmp_path, sources)`).

## Acceptance tests
> 100% must pass, run through `make check`. Never run test files ad hoc.
All in `tests/test_export_pptx_outside.py`, functional level, driver: direct call `to_pptx(path, out, paint=False)`; `secret.png` is a red 2x2 PNG written by the test in `tmp_path` (outside the deck folder `tmp_path / "deck"`).

### SPEC-0026/BT-010: absolute path, `../` and symlink (occurrence `pptx_images.py:117-125`)
- Red before the fix because: `assert [m for m in media(out) if m == SECRET] == []` fails, the list holds the secret picture.
- Given deck folder `tmp/deck/` with three slides naming `../secret.png`, `<tmp>/secret.png` (absolute) and `link.png` (a symlink in `tmp/deck/` to `<tmp>/secret.png`)
- When the export runs
- Then the report holds a warning starting `Image hors du dossier du deck, ignoree: ` for each of the three, and the zip holds no `ppt/media/` entry equal to the bytes of `secret.png` (re-read from the archive)

### SPEC-0026/BT-015: Breathe background class `url()` (occurrence `pptx_chrome.py:334`)
- Red before the fix because: the same assertion fails, the flow export embeds `../secret.png` through the background class.
- Given a Breathe deck (`data-doc-template="breathe"`) whose style holds `.med-bg-x{background-image:url(../secret.png)}` and whose slide 1 uses the class `med-bg-x`; `<tmp>/secret.png` a red PNG
- When the export runs
- Then the zip holds no `ppt/media/` entry equal to `secret.png`, and the report holds a warning starting `Image hors du dossier du deck, ignoree: ../secret.png`

### SPEC-0026/BT-020: warning text and exit status
- Given the deck of BT-010 with an address longer than 60 characters (`../` followed by 70 `a` and `.png`)
- When exported with the call `to_pptx(paint=False)`
- Then the warning is `Image hors du dossier du deck, ignoree: ` followed by the first 60 characters of the address and the call returns normally (the exit status 0 of the command line is asserted by BT-001 in US-0151)

### SPEC-0026/BT-021: symlink accepted when it stays inside
- Given `tmp/deck/real/a.png` and `tmp/deck/link.png` (symlink to `real/a.png`), a slide naming `link.png`
- When exported (flow)
- Then the archive holds the bytes of `a.png` and the report holds no warning starting `Image hors du dossier`

### SPEC-0026/BT-023: library mode keeps its text
- Given `embedded_pictures_only=True` and `../secret.png`
- When exported
- Then the warning is exactly `Image non incluse dans le fichier, ignoree.` and nothing starting `Image hors du dossier` appears

## Constraints
- Files not to touch: `pptx_paint*.py`, `to_docx.py`, `render/`, existing tests.
- Dependencies not to add: none.
- Patterns to avoid: a second copy of the folder rule; any setting or CLI option (BR-008).
- Scope boundary: the painted export, DOCX and render belong to US-0151 to US-0153; `guard_browser` is US-0151.

## Definition of done
- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit.
- [ ] Non regression: `tests/test_export_pptx_library.py`, `tests/test_export_pptx.py` (`:351`, `:368`, `:389`) unchanged and green.
- [ ] Docs: none in this story (US-0154).
- [ ] Self review: the check runs before `exists()`; a `data:` address and a remote address never reach it; no test modified.
- [ ] One commit `US-0150: folder rule and the PPTX flow export` on the work branch, body with `Summary:`, `Spec: SPEC-0026` and the requirement ids.
