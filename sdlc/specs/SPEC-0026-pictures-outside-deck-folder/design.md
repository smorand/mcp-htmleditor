# SPEC-0026: Pictures outside the deck folder, design

> Spec: sdlc/specs/SPEC-0026-pictures-outside-deck-folder/spec.md
> Nature: BUG
> Depth: M
> Security: internal finding
> Designed on: 2026-11-18
> Target tier: 2 (default: no `--tier`, no `Tier:` in `sdlc/constitution.md`, no `.spec.json`)

## 1. Stack and skills
| Element | Choice | Version | DEC |
|---|---|---|---|
| Language, tooling | Python 3.13, uv, ruff, mypy strict, pytest (`make check`) | as in `pyproject.toml` | none, existing |
| Browser interception | Playwright (`render` extra, already used by `render/service.py` and `export/pptx_paint.py`) | as in `pyproject.toml`, no new dependency | DEC-004 |
| HTML edit for DOCX | BeautifulSoup4 (already used by `to_docx.py`) | as in `pyproject.toml` | DEC-006 |

Skills loaded: python. Effect: `make` only, settings only through `Settings` (no setting added, DEC-008), `trace_span` stays on the export calls, no new dependency so no context7 lookup.

## 2. Approaches
### Chosen: one containment helper, applied at each read site (boundary at the read)
Summary: a neutral module holds the folder rule; each of the five sites calls it where it turns an address into a read or a browser load. Pros: the rule is written once, each site keeps its own wording of the refusal, no behavior moves for in folder pictures. Cons: five call sites to keep in step (the exploit tests pin each one). Affected scope: export, render, one new top level module.

### Rejected: sanitise the deck first (rewrite every outside `src` to nothing before any export)
A pre pass over the HTML would hide the problem from Chromium and pandoc at once. Rejected (DEC-001): the painted export and the render load the deck from its path, not from a rewritten copy; rewriting the copy changes what the measure sees for in folder pictures too, and `url()` in style sheets, fonts and frames cannot be rewritten reliably.

### Rejected: pandoc `--sandbox` and Chromium `--allow-file-access-from-files=false`
`--sandbox` also blocks the reference document and the staged file; the Chromium flag does not stop a `file://` page loading sub resources. Rejected (DEC-004, DEC-006): neither gives the warning BR-005 requires.

## 3. Architecture
```
deck_folder.py   is_inside(root, path)   url_to_path(url)   outside_warning(src)   guard_browser(target, root)
   ^ used by
export/pptx_images.py  (flow read)         export/pptx_paint_shapes.py (painted bytes)
export/pptx_paint.py   (measure page)      export/to_docx.py (staged HTML)
render/service.py      (render page)
```
`deck_folder.py` sits next to `deck_files.py` (`src/mcp_htmleditor/deck_files.py:55-77`, the same rule for the HTTP server), imports nothing from export or render, so both depend on it without a cycle. The deck's folder (`root`) is `deck_file.resolve().parent`, already how each site gets its base: `src/mcp_htmleditor/export/to_pptx.py:123` (`source.resolve().parent`), `pptx_paint.py:77` (`html_path.resolve().parent`), `to_docx.py` (`input_path.parent` of the resolved path), `render/service.py:211` (`Path(file).resolve()`).

## 4. Data model
None. No persisted data, no schema.

## 5. Contracts and interfaces
`src/mcp_htmleditor/deck_folder.py`:
- `OUTSIDE_PREFIX: Final = "Image hors du dossier du deck, ignoree: "`
- `SOURCE_CHARS: Final = 60`
- `def is_inside(root: Path, path: Path) -> bool`: `path.resolve()` (not strict) `.is_relative_to(root.resolve())`.
- `def url_to_path(url: str) -> Path | None`: for a `file://` URL, `Path(url2pathname(unquote(urlparse(url).path)))`; any other scheme `None`.
- `def outside_warning(src: str) -> str`: `OUTSIDE_PREFIX + src[:SOURCE_CHARS]`.
- `def guard_browser(target: Page | BrowserContext, root: Path) -> None`: `target.route("file://**", handler)`; the handler computes `url_to_path(route.request.url)`, calls `route.continue_()` when `is_inside(root, path)`, else `route.abort()`. Typed with `Any` for the Playwright types so the module imports without the `render` extra.
Existing messages kept: `NOT_EMBEDDED` (`pptx_vectors.py:20`), `Image introuvable, ignoree: <path>`, render line `<src> did not load` (`render/service.py:232`). No CLI flag, no setting (DEC-008).

## 6. File structure impact
| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/deck_folder.py` | create | BR-001..BR-006 | US-0150 |
| `src/mcp_htmleditor/export/pptx_images.py` | modify `_image_source` | BR-001, BR-005, BR-006 | US-0150 |
| `src/mcp_htmleditor/export/pptx_paint_shapes.py` | modify `_bytes` | BR-002, BR-005, BR-006 | US-0151 |
| `src/mcp_htmleditor/export/pptx_paint.py` | modify `_measure_pages` | BR-003 | US-0151 |
| `src/mcp_htmleditor/export/to_docx.py` | modify `to_docx` (the function), add private `_drop_outside_pictures` | BR-004, BR-005 | US-0152 |
| `src/mcp_htmleditor/render/service.py` | modify `_open_page` | BR-003, BR-007 | US-0153 |
| `tests/test_deck_folder.py`, `tests/test_export_pptx_outside.py` | create | BR-001, BR-005, BR-006 | US-0150 |
| `tests/test_export_pptx_outside_painted.py` | create | BR-002, BR-003 | US-0151 |
| `tests/test_export_docx_outside.py` | create | BR-004 | US-0152 |
| `tests/test_render_outside.py` | create | BR-003, BR-007 | US-0153 |
| `tests/test_outside_nonregression.py` | create | BR-008 and non regression | US-0154 |
| `README.md`, `AGENTS.md`, `.agent_docs/architecture.md`, `skill/topics/export.md` if it states picture rules | modify | documentation | US-0154 |
Affected existing tests: none modified (spec 4.4, all Kept). Existing tests that must stay green: `tests/test_export_pptx_library.py`, `tests/test_export_pptx.py`, `tests/test_export_docx.py`, `tests/test_http_deck_files_e2e.py`, `tests/test_pptx_paint_generic.py`.

## 7. Compatibility and risks
- Consumers see the same output for decks whose pictures are inside the folder (BT-030). A deck that named a picture outside now exports without it and with a warning (the declared behavior, BR-005).
- Order: US-0150 creates the module; US-0151 to US-0153 depend on it; US-0154 depends on all of them. BT-001 (CLI PPTX, painted finish) is green only after US-0151.
- Risk: a Chromium upgrade that stops reporting a class of `file://` request (spec section 6): BT-012, BT-016, BT-017 would go red, which is the intended alarm.
- Risk: `route("file://**")` also sees the deck page itself and its in folder files; the handler continues them (BT-031).
- Rollback: revert the commits; no data to migrate. No dependency added or removed.

## 8. Security design
- Threat surface: trust boundary = the deck file (written by someone else); untrusted source = picture address (`src`, `url()`, `href`, CSS); dangerous sinks = the local file reads and the browser loads listed below.
- Per occurrence:

| Occurrence | Fix site | Mechanism | DEC |
|---|---|---|---|
| `pptx_images.py:117-125` (originating) and `pptx_chrome.py:334` | `_image_source` | `is_inside` on the built path before `exists()` | DEC-002, DEC-003 |
| `pptx_paint_shapes.py:199-204` | `_bytes` | `is_inside` on the path (relative, absolute or `file://`) before `is_file()` | DEC-002, DEC-003 |
| `pptx_paint.py:155-157` | `_measure_pages` | `guard_browser` on the measure page | DEC-004 |
| `to_docx.py:143-144` | before the staged HTML is written | remove each outside `<img>` | DEC-006 |
| `render/service.py:211` | `_open_page` | `guard_browser` on the context | DEC-004 |

- Exploit tests (spec 4.1bis) and where they run: BT-010 and BT-015 in US-0150, BT-011, BT-012, BT-016 in US-0151, BT-013 in US-0152, BT-014 and BT-017 in US-0153. The absence of effect is read through the output artifact (zip media bytes, slide XML, decoded pixels), never through the warning. Each is red before its story for the reason the spec names, and each story's RED evidence records the failing assertion.
- Secrets: none handled. Never traced: a picture's content; the `file.path` span attribute stays the deck path (existing).

## 9. Test strategy
| Test | Level | Driver | Location | Story |
|---|---|---|---|---|
| BT-010, BT-015, BT-020, BT-021, BT-023 | exploit / functional | direct call `to_pptx(paint=False)` | `tests/test_export_pptx_outside.py` | US-0150 |
| BT-001 | functional e2e | CLI `run_cli("export", "pptx", ...)` | `tests/test_export_pptx_outside_painted.py` | US-0151 |
| BT-011 | exploit | direct call of `Painter._bytes` | `tests/test_export_pptx_outside_painted.py` | US-0151 |
| BT-012, BT-016 | exploit (Chromium) | CLI export, `needs_chromium` | `tests/test_export_pptx_outside_painted.py` | US-0151 |
| BT-013 | exploit | CLI `export docx` | `tests/test_export_docx_outside.py` | US-0152 |
| BT-014, BT-017 | exploit (Chromium) | CLI `render`, `needs_chromium` | `tests/test_render_outside.py` | US-0153 |
| BT-022, BT-030, BT-031, BT-032 | functional / non regression | CLI help, exports, render | `tests/test_outside_nonregression.py` | US-0154 |
Plus unit tests of `deck_folder.py` in `tests/test_deck_folder.py` (US-0150). Test data: generated by the tests (PNG written with Pillow, which python-pptx already requires); pandoc and Chromium availability follow the existing skips of `tests/render_support.py:39` and the DOCX tests.

## 10. Decisions log
- **DEC-001:** one shared containment module, applied at each read site (no pre pass over the deck). **Obliged by:** SPEC-0026/BR-001, BR-002, BR-003, BR-004. **Rationale:** one rule, five sites, no change to what the browser measures for in folder pictures. **Alternatives considered:** rewrite the deck before export; per module copies of the rule. **Source:** design. **Evidence:** `src/mcp_htmleditor/deck_files.py:55-77` (same rule for HTTP).
- **DEC-002:** the folder test is `resolve()` of the candidate (not strict) then `is_relative_to(root.resolve())`. **Obliged by:** SPEC-0026/BR-006, BR-001. **Rationale:** a symlink is judged by where it leads; an outside file that does not exist is refused before `exists()` (spec edge case). **Alternatives considered:** `os.path.commonpath` (same result, more code); `strict=True` (raises on a missing file and loses the outside warning). **Source:** existing code. **Evidence:** `deck_files.py:66-77`.
- **DEC-003:** each site builds its path as today and only adds the containment check; the flow export keeps ignoring `file://` (not understood, as today), the painted export keeps reading `file://` through `url_to_path`. **Obliged by:** SPEC-0026/BR-001, BR-002 and spec edge case on `file://`. **Rationale:** no new capability (user decision 2026-11-18). **Alternatives considered:** one address parser for both. **Source:** spec 3, user answer. **Evidence:** `pptx_images.py:117-120`, `pptx_paint_shapes.py:200-203`.
- **DEC-004:** `guard_browser` registers `route("file://**")` and aborts outside requests, for every resource type; on the measure page (`page.route`, next to the existing `REMOTE` route) and on the render context. **Obliged by:** SPEC-0026/BR-003. **Rationale:** the only point that sees pictures, fonts, style sheets and frames; probed on 2026-11-18: Playwright reports `file://` requests outside the folder. **Alternatives considered:** a Chromium flag (does not stop sub resources of a `file://` page); aborting only images (user answer 4: every type). **Source:** spec, user answer. **Evidence:** `export/pptx_paint.py:155-157`, `render/service.py:211`.
- **DEC-005:** one warning builder `outside_warning(src)` (prefix + first 60 characters of the address as the site holds it). **Obliged by:** SPEC-0026/BR-005. **Rationale:** same text at every site, the painted export holds the browser's `file://` form (spec). **Alternatives considered:** per site text. **Source:** spec. **Evidence:** `pptx_paint_shapes.py:197` (same cut at 60 for remote).
- **DEC-006:** DOCX: `_drop_outside_pictures(html, root)` parses the prepared HTML, judges the `src` of each `<img>` (skips empty, `data:`, `http(s)://`, `//`; a `file://` is converted by `url_to_path`, anything else is a path relative to `root`), removes each outside `<img>` and returns one warning per removal; its result replaces `prepared.html` before the staged file is written. **Obliged by:** SPEC-0026/BR-004, BR-005. **Rationale:** pandoc gives no per picture signal and `--sandbox` blocks the reference document. **Alternatives considered:** `--sandbox`; filter in a pandoc Lua filter (new moving part). **Source:** design. **Evidence:** `to_docx.py:130-146`, `to_docx.py:263-264` (existing `src` pre pass).
- **DEC-007:** in the library mode the existing `embedded_pictures_only` check stays first; the folder check follows it. **Obliged by:** SPEC-0026/BR-005 (precedence), SPEC-0025/FR-NEW-052. **Rationale:** BT-023 and the library tests stay green unchanged. **Alternatives considered:** folder check first (would change the library warning text). **Source:** spec. **Evidence:** `pptx_images.py:112-114`, `pptx_paint_shapes.py:193-195`.
- **DEC-008:** no setting, no CLI option. **Obliged by:** SPEC-0026/BR-008. **Rationale:** spec prohibition. **Alternatives considered:** `HTMLEDITOR_` allow list. **Source:** spec, user answer 3. **Evidence:** `src/mcp_htmleditor/config.py` (`Settings`) untouched.
- **DEC-009:** a refused picture in the painted export adds no shape: `_bytes` returns `None`, `picture()` returns at `if data is None`. **Obliged by:** SPEC-0026/BR-002, BR-005. **Rationale:** matches the existing handling of a missing file. **Alternatives considered:** a placeholder box (new visible behavior). **Source:** existing code. **Evidence:** `pptx_paint_shapes.py:208-210`.
- **DEC-010:** BR-007 needs no code: an aborted image request leaves the image incomplete, which the existing script reports; BT-014 pins it. **Obliged by:** SPEC-0026/BR-007. **Rationale:** reuse the existing report. **Alternatives considered:** a dedicated message (user answer 5: none). **Source:** existing code. **Evidence:** `render/service.py:232`, `render/scripts.py:25`.

## 11. Stories
| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0150 | folder rule and the PPTX flow export | P1 | BR-001, BR-005, BR-006 | main | 2 | no |
| US-0151 | painted PPTX export refuses outside pictures | P1 | BR-002, BR-003, BR-005, BR-006 | US-0150 | 2 | no |
| US-0152 | DOCX export drops outside pictures | P1 | BR-004, BR-005, BR-006 | US-0150 | 2 | no |
| US-0153 | render aborts outside file requests | P1 | BR-003, BR-006, BR-007 | US-0150, US-0151 | 2 | no |
| US-0154 | no opt in, non regression and documentation | P2 | BR-008 | US-0151, US-0152, US-0153 | 2 | yes |
