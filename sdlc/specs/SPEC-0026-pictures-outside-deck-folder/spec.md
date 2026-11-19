# Pictures outside the deck folder: Bug Specification

> Generated on: 2026-11-18
> Id: SPEC-0026
> Nature: BUG
> Depth: M
> Depth evidence: 2 contexts (export, render), 8 requirements, no public contract change, no persisted data change
> Status: implemented
> Verdict: no authority
> Defect class: absent
> Severity: Medium
> From backlog: BL-0047
> Security: internal finding
> CVSS: not scored
> Affected: every commit with the PPTX flow export, the painted export, the DOCX export and `render` (local mode)
> Fixed in: unreleased

## 1. Defect

### BUG-001: a deck makes the exports and the render read pictures outside its own folder
- **Observed behavior:** a picture address in a deck (`src` of an image, `url()` of a Breathe background class) that is an absolute path, climbs out with `../`, is a `file://` address, or goes through a symlink to another folder, is read from disk and ends up in the PPTX, the DOCX or the rendered PNG. No warning is given.
- **Expected per authority:** none: no authority (SPEC-0025 refuses such pictures only in the web library mode, FR-NEW-052, which is unchanged here).
- **Reproduction:** folder `work/` holds `deck/deck.html` with slide 1 `<img src="../secret.png">` and `work/secret.png` (a real 1x1 PNG). `mcp-htmleditor export pptx work/deck/deck.html out.pptx`. Expected: `out.pptx` holds no picture equal to `secret.png`. Actual: it holds it.
- **Root cause:** five read sites take the address as is, with no check that its resolved path stays under the deck's folder:
  - flow export `src/mcp_htmleditor/export/pptx_images.py:117-125` (absolute path used as is, `../` joined and not normalised);
  - painted export, bytes `src/mcp_htmleditor/export/pptx_paint_shapes.py:199-204` (`file://` read directly, absolute path replaces the base, `../` not rejected);
  - painted export, Chromium `src/mcp_htmleditor/export/pptx_paint.py:155-157` (only `^https?://` is aborted, so any `file://` request is served);
  - DOCX `src/mcp_htmleditor/export/to_docx.py:143-144` (pandoc given `--resource-path <deck folder>`, no `--sandbox`; checked on 2026-11-18: pandoc embeds `../secret.png`, an absolute path and a `file://` address in the DOCX);
  - render `src/mcp_htmleditor/render/service.py:211` (`goto` of the deck as `file://`, no request interception).
- **Contributing factors:** the library mode flag `embedded_pictures_only` (`src/mcp_htmleditor/export/pptx_images.py:112`, `src/mcp_htmleditor/export/pptx_paint_shapes.py:193`) was added for the web library only and is off in local mode (`src/mcp_htmleditor/export/to_pptx.py:67`).
- **Impact:** a deck received from someone else, opened and exported (or rendered by an agent) on the author's machine, puts any local picture file of the machine into a file or an image the author then sends back. Local only: no network request reaches these paths (BL-0047).
- **Rollback posture:** a deck whose pictures all sit in its folder (or are `data:`) exports exactly as before; a revert restores the previous reading.

## 1bis. Class Sweep

**Class:** a picture address carried by a document's markup reaches a local file read, or a browser load that lands in an output, with no confinement to the document's folder (CWE-22, CWE-73).
**Searches run** (literal, from `src/mcp_htmleditor`):
1. `rg -n "base_dir|resolve\(|is_absolute|Path\(|open\(|add_picture|Image\.open|resource-path|read_bytes|read_text|relative_to|is_relative_to|copy" export breathe deck` (path building and reads in the exporters and loaders).
2. `rg -n "url\(|\bsrc\b|href|background|file://|data-" export breathe deck` (markup values entering those modules).
3. `rg -n "playwright|chromium|goto\(|file://|route\(|set_content"` (every browser load, whole package).
4. `rg -n "Path\(|open\(|read_bytes|read_text|resolve\(|is_relative_to|commonpath|\.\./" src Makefile` minus export, render, breathe, deck (everything else: library, MCP tools, CLI, state).
5. `rg -n "httpx|requests|urlopen|urllib.request|srcset|poster|add_style_tag|add_script_tag|subprocess" src/mcp_htmleditor` (outbound fetch and other tag idioms): no outbound fetch and no `srcset` reader; `add_style_tag` at `pptx_paint.py:158` takes the fixed `FREEZE_CSS`; `subprocess.run` appears at `export/to_docx.py:154` (the vulnerable DOCX row) and `export/reference_docx.py:408,714` (fixed argument lists, no deck value); `deck/tools.py:109` only catches the error; `poster` is a layout name only.
6. `rg -n "read_bytes|add_picture|Image\.open|exists\(\)|is_file\(\)" src/mcp_htmleditor/export src/mcp_htmleditor/render src/mcp_htmleditor/deck src/mcp_htmleditor/breathe` (sink idiom): no reader beyond the rows below.
Out of class, unchanged: pandoc itself fetches `http(s)` picture addresses of a DOCX (`export/to_docx.py:143-154`, no guard); that is a network read, not a local file read, and no requirement here covers it.
Idioms not searched: SVG `<image href>` parsing in Python (the browser loads it, see BT-012).

| Occurrence | Verdict | Disposition |
|---|---|---|
| `src/mcp_htmleditor/export/pptx_images.py:117-125` | vulnerable | BR-001, BR-005, BR-006, BT-010 |
| `src/mcp_htmleditor/export/pptx_paint_shapes.py:199-204` | vulnerable | BR-002, BR-005, BR-006, BT-011 |
| `src/mcp_htmleditor/export/pptx_paint.py:155-157` | vulnerable | BR-003, BR-006, BT-012, BT-016 |
| `src/mcp_htmleditor/export/to_docx.py:143-144` | vulnerable | BR-004, BR-005, BR-006, BT-013 |
| `src/mcp_htmleditor/render/service.py:211` | vulnerable | BR-003, BR-006, BR-007, BT-014, BT-017 |
| `src/mcp_htmleditor/export/pptx_chrome.py:334` (`url()` of `med-bg-*`, feeds the flow `_image_source`) | vulnerable (same sink `_image_source` as the first row, a second entry: the payload is the `url()` of a background class, so the test is a separate payload, not a separate fix) | BR-001, BR-005, BT-015 |
| `src/mcp_htmleditor/breathe/inline.py:150-167` | safe: `PLAIN_NAME` (`:36`) rejects `/`, `\` and a leading `.`; `_check_links` rejects a symlinked assets folder or candidate resolving outside | none |
| `src/mcp_htmleditor/breathe/inline.py:170-182` (reads the shipped catalogue too; symlinks there are not checked) | safe: the catalogue is a file of the product, not a value from a deck | none (user decision 2026-11-18, no entry written) |
| `src/mcp_htmleditor/deck_files.py:55-77` | safe: rejects `..`, hidden segments, then `resolve()` and `is_relative_to(base)`; tests `tests/test_http_deck_files_e2e.py:105,170,182,200` | none |
| `src/mcp_htmleditor/library/server.py:407` (flag on) | safe: `embedded_pictures_only` refuses every non `data:` address (`pptx_images.py:112`, `pptx_paint_shapes.py:193`); tests `tests/test_export_pptx_library.py:56-100` | none |
| `src/mcp_htmleditor/library/uploads.py:60-67`, `store.py:196,573` | safe: the upload name is metadata only, stored paths use generated ids | none |
| `src/mcp_htmleditor/library/seed.py:58-80`, `src/mcp_htmleditor/skill_content.py:99-101` | out of class: the manifest and the topic name are not deck markup; `skill_content.py:99` restricts the topic to `TOPIC_NAMES` | none |
| `mcp_server.py:77,142,205,224`, `cli.py:260,457,571`, `history.py:140,170`, `request_service.py:305` | out of class: the file argument is the deck chosen by its caller, not a value read from a deck | none |

## 2. Expected Behavior

"The deck's folder" is the directory holding the deck file, after resolving symlinks, with every subfolder below it. A picture is "inside" when its address, resolved to a real path (symlinks followed), lies in that folder or below it. Every other local address is "outside": an absolute path, a path climbing with `../`, a `file://` address, or a path that goes through a symlink to somewhere outside. A `data:` address is never outside.

#### BR-001 [EARS-U]: the PPTX flow export reads no outside picture
> The PPTX export SHALL NOT read, whatever its finish, a local picture named by an image `src` or by the `url()` of a background class of the deck when that picture is outside the deck's folder.

- **Source:** decided here: BL-0047 Proposal, confirmed by the user on 2026-11-18 ("defaults").
- **Inputs:** a deck file, any `src` or `url()` address.
- **Outputs:** the PPTX holds no picture whose bytes come from an outside file.
- **Business Rules:** the check applies to the address as written, resolved against the deck's folder, symlinks followed.
- **Exact names:** none.

#### BR-002 [EARS-U]: the painted export reads no outside picture
> The painted PPTX export SHALL NOT read a measured picture whose address, a `file://` address or a path, resolves outside the deck's folder.

- **Source:** decided here: same decision.
- **Business Rules:** an address that resolves inside the folder, as a `file://` address or as an absolute path, is read as today.

#### BR-003 [EARS-E]: the browser loads of the export and of the render stop at the folder
> WHEN the browser used to measure a deck for the PPTX export, or to render a deck, requests a `file://` resource whose resolved path is outside the deck's folder, THE product SHALL abort that request, for every resource type (picture, font, style sheet, frame).

- **Source:** decided here: user answer to question 4, "defaults" (abort every outside `file://` request, not only pictures).
- **Business Rules:** the deck file itself and every resource inside the folder load as today. `https?://` requests stay aborted by the export (`pptx_paint.py:51`) and are not changed by this spec.

#### BR-004 [EARS-U]: the DOCX export embeds no outside picture
> The DOCX export SHALL NOT embed a local picture named by an image `src` when that picture is outside the deck's folder.

- **Source:** decided here: same decision.
- **Business Rules:** the DOCX export names each refused picture itself before the document is built, so BR-005 holds for it; the check does not rely on a signal from the converter. It judges the address written in the `src` of each image tag, before conversion.

#### BR-005 [EARS-O]: a refused picture does not stop the export and is named
> IF an export refuses a picture because it is outside the deck's folder, THEN THE export SHALL continue without it and SHALL add to its warnings the text `Image hors du dossier du deck, ignoree: <src>`, where `<src>` is the address as written in the deck, cut at its first 60 characters.

- **Source:** decided here: user answer to question 2, "defaults" (warn, no failure).
- **Outputs:** the command line prints each warning on its own line as `Attention: <warning>` on the error stream (`src/mcp_htmleditor/cli.py:626-627`), the exit status stays 0.
- **Business Rules:** the same address may be named more than once (the flow export reads an address for its ratio and again to place it, as for a missing file); at least one warning names it. The wording keeps the style of the existing warnings (French, no accents). In the library mode (`embedded_pictures_only`), the existing text `Image non incluse dans le fichier, ignoree.` keeps precedence and nothing changes.
- **Exact names:** warning prefix `Image hors du dossier du deck, ignoree: `.
- **Painted export:** the `<src>` is the address the browser reports (the absolute `file://` form), cut at 60 characters; BT-011 and BT-012 assert only the prefix. A refused picture adds no shape; the other shapes of the slide are unchanged.
- **Refused picture in the files:** the flow export skips it; the DOCX export removes the `<img>` from the document it converts and puts nothing in its place.

#### BR-006 [EARS-U]: a symlink is judged by where it leads
> The product SHALL judge a picture by its resolved real path: a symlink inside the deck's folder that leads outside is refused, and a symlink that leads to a place inside the folder is accepted.

- **Source:** decided here: user answer to question 1, "defaults".

#### BR-007 [EARS-E]: a picture refused by the render is reported by the existing report
> WHEN `render` aborts a picture request under BR-003, THE render SHALL report it through the existing image problem line `<src> did not load` (kind `image`), and SHALL NOT add any new message.

- **Source:** decided here: user answer to question 5, "defaults". Existing line: `src/mcp_htmleditor/render/service.py:232`.

#### BR-008 [EARS-UB]: no way to allow an outside read
> The product SHALL NOT offer a setting, flag or option that lets an export or the render read a picture outside the deck's folder.

- **Source:** decided here: user answer to question 3, "defaults" (no opt in, YAGNI). No deck under `templates/` names an address outside its folder (`rg -n 'src="(/|\.\./|file:)|url\((\.\./|/|file:)' templates --glob '*.html'` returns no match).

## 3. Edge Cases

| Case | Expected behavior | Requirement |
|------|-------------------|-------------|
| Absolute path of a picture inside the folder | read as today | BR-001, BR-002 |
| `file://` address of a picture inside the folder | painted export and DOCX: read as today (the painted export gets such addresses from Chromium for every local picture, pandoc resolves them). PPTX flow export: unchanged, the address is not understood today (`pptx_images.py:117-120` joins it to the folder, the file is not found, existing warning `Image introuvable, ignoree`); this spec adds no `file://` support there | BR-002, BR-003 |
| Picture in a subfolder `media/a.png` | read as today | BR-001 |
| Symlink inside the folder to another file inside | read as today | BR-006 |
| Symlink inside the folder to an outside file | refused, warning | BR-006, BR-005 |
| `../secret.png` that stays inside after normalising (`media/../a.png`) | read as today | BR-001 |
| Outside address that does not exist | refused with the outside warning (the folder rule is checked first); no second "introuvable" warning is required | BR-005 |
| `data:` address | read as today | BR-001 |
| `https://` address | unchanged (existing remote warning) | BR-001 |
| Library mode flag on | unchanged, existing warning | BR-005 |
| Outside font, style sheet or frame in the browser | request aborted, nothing from it rendered | BR-003 |

## 4. Tests

Driver names: CLI = `mcp-htmleditor` through `tests/deck_support.py` `run_cli`; Chromium tests (BT-012, BT-014, BT-016, BT-017, BT-030, BT-031) carry the `needs_chromium` marker of `tests/render_support.py:39`. `secret.png` is a real PNG written by the test next to the deck folder, never inside it.

### 4.1 End to end reproduction (mandatory)
#### BT-001: the flow export of a deck naming `../secret.png`
- **Reproduces:** BUG-001
- **Driver:** CLI `export pptx`
- **Fails today because:** `pptx_images.py:117-125` joins `../secret.png` to the deck's folder and embeds the file.
- Given `tmp/deck/deck.html` (a real presentation file whose slide 1 holds `<img src="../secret.png" alt="x">`) and `tmp/secret.png` (a 2x2 red PNG)
- When the user runs `export pptx tmp/deck/deck.html tmp/out.pptx`
- Then exit status 0, and no file under `ppt/media/` of `out.pptx` has the bytes of `secret.png`, and the error stream holds the line `Attention: Image hors du dossier du deck, ignoree: ../secret.png`

### 4.1bis Exploit tests (MANDATORY)
Each carries its literal payload, asserts the rejection and reads the absence of the effect through the output artifact (zip media list, rendered pixels), not through the warning.

#### BT-010: flow export, absolute path, `../` and symlink (occurrence `pptx_images.py:117-125`)
- **Covers:** `src/mcp_htmleditor/export/pptx_images.py:117-125`
- **Driver:** direct call `to_pptx(path, out, paint=False)` (the flow output, per the project convention)
- **Red before the fix because:** `assert [m for m in media(out) if m == SECRET] == []` fails, the list holds the secret picture.
- Given deck folder `tmp/deck/` with three slides naming `../secret.png`, `<tmp>/secret.png` as an absolute path, and `link.png` (a symlink in `tmp/deck/` to `<tmp>/secret.png`); `<tmp>/secret.png` holds a red 2x2 PNG
- When the export runs
- Then the report holds a warning starting `Image hors du dossier du deck, ignoree: ` for each of the three, and the zip holds no `ppt/media/` entry equal to the bytes of `secret.png` (re-read from the archive)

#### BT-011: painted export bytes (occurrence `pptx_paint_shapes.py:199-204`)
- **Covers:** `src/mcp_htmleditor/export/pptx_paint_shapes.py:199-204`
- **Driver:** direct call of `Painter._bytes` as in `tests/test_export_pptx_library.py:84-100`
- **Red before the fix because:** `painter._bytes("../secret.png")` returns the bytes of `secret.png` instead of `None`.
- Given a `Painter` on base folder `tmp/deck/`, `tmp/secret.png`
- When `_bytes` receives `../secret.png`, `<tmp>/secret.png`, `file://<tmp>/secret.png`
- Then each returns `None` and the report holds three warnings starting `Image hors du dossier du deck, ignoree: `; and `_bytes("local.png")` for a file in `tmp/deck/` still returns its bytes

#### BT-012: painted export, Chromium measure draws an outside picture (occurrence `pptx_paint.py:155-157`)
- **Covers:** `src/mcp_htmleditor/export/pptx_paint.py:155-157`
- **Driver:** CLI `export pptx` on a deck with Chromium available
- **Red before the fix because:** the raster picture of the figure holds the pixels of `secret.png` (the browser drew the file); `assert not any(pixel == (1, 2, 3) for pixel in raster_pixels)` fails. This payload does not go through the byte reader, so BT-011's fix cannot turn it green.
- Given `tmp/secret.png` a 4x4 PNG of the single colour (1, 2, 3), and a deck whose slide 1 holds `<svg width="80" height="80"><image href="file://<tmp>/secret.png" width="80" height="80"/></svg>`
- When the user exports it with the painted finish
- Then no pixel of colour (1, 2, 3) appears in any picture under `ppt/media/` of the PPTX (each decoded with an image library), and the export did not fall back to the degraded warning (`Deck exported without the rendered finish`)

#### BT-015: Breathe background class `url()` (occurrence `pptx_chrome.py:334`)
- **Covers:** `src/mcp_htmleditor/export/pptx_chrome.py:334`
- **Driver:** direct call `to_pptx(path, out, paint=False)`
- **Red before the fix because:** `assert [m for m in media(out) if m == SECRET] == []` fails, the flow export embeds `../secret.png` through the background class.
- Given a Breathe deck (`data-doc-template="breathe"`) whose style holds `.med-bg-x{background-image:url(../secret.png)}` and whose slide 1 uses the class `med-bg-x`; `<tmp>/secret.png` a red PNG
- When the export runs
- Then the zip holds no `ppt/media/` entry equal to `secret.png`, and the report holds a warning starting `Image hors du dossier du deck, ignoree: ../secret.png`

#### BT-016: painted export, an outside style sheet (BR-003, occurrence `pptx_paint.py:155-157`)
- **Covers:** `src/mcp_htmleditor/export/pptx_paint.py:155-157`
- **Driver:** CLI `export pptx` with Chromium
- **Red before the fix because:** slide 1 of the PPTX holds a fill of `0000FF` taken from the outside style sheet; `assert "0000FF" not in slide1_xml` fails.
- Given `tmp/out.css` holding `.slide{background:#0000FF}` and a deck whose head holds `<link rel="stylesheet" href="../out.css">`
- When the user exports it with the painted finish
- Then the XML of slide 1 holds no `0000FF`

#### BT-013: DOCX export (occurrence `to_docx.py:143-144`)
- **Covers:** `src/mcp_htmleditor/export/to_docx.py:143-144`
- **Driver:** CLI `export docx`
- **Red before the fix because:** `word/media/` of the DOCX holds a file equal to `secret.png` (pandoc embeds it, checked 2026-11-18).
- Given `tmp/deck/doc.html` (a `doc` template file) with `<img src="../secret.png">`, `<img src="<tmp>/secret.png">` and `<img src="file://<tmp>/secret.png">`
- When the user runs `export docx tmp/deck/doc.html tmp/out.docx`
- Then exit status 0, no `word/media/` entry of `out.docx` equals `secret.png`, and the error stream holds three lines starting `Attention: Image hors du dossier du deck, ignoree: `

#### BT-014: render, an outside picture (occurrence `render/service.py:211`)
- **Covers:** `src/mcp_htmleditor/render/service.py:211`
- **Driver:** CLI `render <deck> --slide slide-1 --report`
- **Red before the fix because:** the PNG shows the red picture (pixel at the picture centre is (255, 0, 0)) and the report has no `did not load`.
- Given `tmp/deck/deck.html` slide `slide-1` holding `<img src="../secret.png" style="width:200px;height:200px">`, `tmp/secret.png` a 200x200 red PNG
- When the user renders slide-1 with `--report`
- Then the output has the line `image slide-1: ../secret.png did not load`, and the PNG (re-read with an image library) has no pixel of (255, 0, 0) in the picture's box

#### BT-017: render, an outside style sheet and an outside frame (BR-003)
- **Covers:** `src/mcp_htmleditor/render/service.py:211`
- **Driver:** CLI `render <deck> --slide slide-1`
- **Red before the fix because:** the PNG slide background is (0, 0, 255) and the frame area is (255, 0, 0); `assert no pixel (0, 0, 255)` and `assert no pixel (255, 0, 0)` fail.
- Given `tmp/out.css` (`.slide{background:#0000FF}`), `tmp/frame.html` (a page with a red background), and a deck whose head holds `<link rel="stylesheet" href="../out.css">` and whose slide 1 holds `<iframe src="../frame.html" style="width:200px;height:200px"></iframe>`
- When the user renders slide-1
- Then the PNG holds no pixel of (0, 0, 255) and none of (255, 0, 0)

### 4.2 New behavior
#### BT-020: warning text and exit status
- **Validates:** BR-005
- Given the deck of BT-001 with an address longer than 60 characters (`../` followed by 70 `a` and `.png`)
- When exported to PPTX
- Then the warning is `Image hors du dossier du deck, ignoree: ` followed by the first 60 characters of the address, exit status 0

#### BT-021: symlink accepted when it stays inside
- **Validates:** BR-006
- Given `tmp/deck/real/a.png` and `tmp/deck/link.png` (symlink to `real/a.png`), slide naming `link.png`
- When exported to PPTX (flow)
- Then the archive holds the bytes of `a.png` and the report holds no `hors du dossier` warning

#### BT-022: no setting to allow outside reads
- **Validates:** BR-008
- Given the `export` commands and the `render` command
- When their `--help` output is read
- Then no option mentions picture folders or outside access (the options list equals the one before this change)

#### BT-023: library mode keeps its text
- **Validates:** BR-005 (precedence)
- Given the flag `embedded_pictures_only=True` and `../secret.png`
- When exported
- Then the warning is exactly `Image non incluse dans le fichier, ignoree.` and nothing starting `Image hors du dossier` appears

### 4.3 Non regression
#### BT-030: pictures inside the folder
- **Protects:** pictures next to the deck, in a subfolder, as an absolute path or `file://` address inside the folder, and `data:`
- Given `tmp/deck/` with `local.png`, `media/a.png`, and slides naming `local.png`, `media/a.png`, `<tmp>/deck/local.png`, `file://<tmp>/deck/media/a.png`
- When exported to PPTX (flow, `paint=False`), to PPTX (painted) and to DOCX, and rendered
- Then the PPTX flow export embeds 3 pictures (the `file://` address is not understood by the flow export, as today, with the existing `Image introuvable, ignoree` warning), the painted PPTX embeds 4, the DOCX embeds 4, and the render has no `did not load` line

#### BT-031: Chromium keeps loading in folder resources
- **Protects:** fonts, style sheets and images inside the folder under the measure and the render
- Given a deck with `<link rel="stylesheet" href="theme.css">` (a rule setting the slide background to blue) and `<img src="media/a.png">`
- When rendered
- Then the picture shows its pixels and the slide background is blue (pixel read)

#### BT-032: the web library mode
- **Protects:** SPEC-0025 FR-NEW-052
- The tests `tests/test_export_pptx_library.py` and `tests/test_library_*` are unchanged and pass

### 4.4 Existing tests asserting the current behavior
| Test file | Test name | Action | Reason |
|-----------|-----------|--------|--------|
| `tests/test_export_pptx_library.py` | `test_the_default_still_embeds_a_relative_picture` | Kept | picture next to the deck stays embedded |
| `tests/test_export_pptx_library.py` | `test_a_refused_address_gives_no_picture_and_the_warning`, `test_with_the_flag_no_address_but_a_data_uri_is_read`, `test_the_painted_path_refuses_the_same_addresses` | Kept | flag on, library mode |
| `tests/test_export_pptx.py` | `test_relative_images_resolve_against_the_html_file` (`:368`), `test_base64_images_are_embedded` (`:351`), `test_missing_and_remote_images_are_reported` (`:389`) | Kept | inside the folder, `data:`, remote |
| `tests/test_export_docx.py` | tests using `figure.png`, `schema.svg` (`:223-228`, `:475`) | Kept | pictures in the deck folder |
| `tests/test_http_deck_files_e2e.py` | traversal and symlink tests (`:105,170,182,200`) | Kept | different site (HTTP serving) |
| `tests/test_pptx_paint_generic.py` | tests exporting from `templates/reference/slides` (`:26,246,263`) | Kept | the reference decks name no outside address (ripgrep above, no match) |

## 5. Existing Specs Affected
- SPEC-0025/FR-NEW-052 and E2E-SEC-022 (library mode refuses non `data:` pictures): unchanged, BR-005 states the precedence.
- SPEC-0023/FR-NEW-009 (files next to the open deck are served): unchanged, those are served by the editor server under `src/mcp_htmleditor/deck_files.py` containment; this spec brings the exporters and the render to the same rule.
- SPEC-0024 (painted export): BR-003 adds an interception to the measure page; the pictures it measures inside the folder are unchanged.

## 6. Assumptions
- **Assumption:** the folder rule is the same for all five sites (BR-001 to BR-004), as one product rule; shaped BR-001 to BR-004.
- **Assumption:** Playwright interception sees every `file://` request of the page, outside the folder included; checked 2026-11-18 on Chromium (a probe page naming `../out.png` and `file:///etc/hosts` had both requests reported). A requirement of BT-012 and BT-014 depends on it; if a later Chromium stops reporting a class of request, BT-012 or BT-014 goes red.
- **Assumption:** the exporters resolve the deck's folder from the deck file's real path; a deck opened through a symlinked folder is judged by its real folder; shaped BR-006.
- **Proposed backlog entries (not written):** none. The shipped catalogue point (`breathe/inline.py:170-182`) was cut by the user (no entry).

## 7. Implementability Checklist
Read back from disk on 2026-11-18.

| Item | Result |
|---|---|
| 1 No technical decision | PASS (only root cause `file:LINE`) |
| 2 No buried requirement | PASS (BR-005 warning text and BR-007 render text are their own requirements) |
| 3 Observable names spelled | PASS (warning text, `Attention:` prefix, `<src> did not load`, kind `image`) |
| 4 No forced choice | PASS (symlink, absolute inside, `file://` inside, repeated warning, exit status, opt in all stated) |
| 5 Every test specified | PASS (BT-001 to BT-032, 4.4 lists the touched suites) |
| 6 Reproduction is end to end | PASS (BT-001 drives the CLI and reads the archive) |
| 7ante Security misclassification | PASS (`Security: internal finding`, path traversal flaw) |
| 7bis Sweep real | PASS (6 searches, every hit disposed, safe verdicts cite controls; fresh auditor round 1 found F1 to F4 and A2, A3, all amended; round 2 below) |
| 8 No hidden prerequisite | PASS (Chromium needs are in the test drivers; pandoc presence is the existing prerequisite of the DOCX export) |
| 9 EARS clean | PASS |
| 10 Right tool | PASS (existing behavior changes, no new capability) |
| 11 Length | PASS (M) |
| 12 Claims cited | PASS (counts of sites: 5 vulnerable, recounted) |
| 13 Round trip read | PASS (writer: the deck address; reader: sites above; two implementations, flow and painted, each have an exploit test) |
| 14 Verdict consistent | PASS (`no authority`, class `absent`, every BR Source is `decided here`) |

| Verdict | IMPLEMENTABLE |
|---|---|
| Open F failures | 0 |
| A failures | amended in place: 0; proposed: none |
