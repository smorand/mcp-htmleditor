# US-0060: Optional render extra, install-browser and fixtures

> Spec: SPEC-0008 (sdlc/specs/SPEC-0008-visual-render/)
> Nature: FEAT
> Priority: P1
> Depends on: US-0059
> min_tier: 2
> Files touched: 5
> Closes spec: no

## Objective

Make Playwright an optional runtime extra named `render`, give the maintainer `make install-browser`, make `make install` ship the extra, and create the shared test support (`needs_chromium`, deck builders, defect injectors, 40 slide generator, PNG helpers) that every later story uses. No command exists yet; this story is the install step of FR-NEW-001 and the fixtures.

## Requirements covered

- SPEC-0008/FR-NEW-001 (partial: the install step named in the error message `error: Rendering needs Chromium. Install it with: make install-browser`; the command itself arrives in US-0061): WHEN a user runs `mcp-htmleditor render <file>` THE Editor SHALL write a PNG picture of one slide of the presentation and print one line giving its slide, path and size.

## Independent Test

`make test ARGS='-k render_install'`: `pyproject.toml` declares `render = ["playwright>=1.62,<2"]` and no core dependency on Playwright; `make -n install-browser` shows both install branches; `make -n install` shows `.[render]`; the fixture self tests pass.

## Design excerpt

### Decisions

- DEC-002 (SPEC-0008): "Playwright is declared as `[project.optional-dependencies] render = ["playwright>=1.62,<2"]`; the lock keeps 1.62.0 through the dev group."
- DEC-023 (SPEC-0008): "`make install` installs the tool with `.[render]` and `make install-browser` installs Chromium with the Python of the installed tool when it exists, else with `uv run --extra render`."
- DEC-025 (SPEC-0008): "Pure modules are tested with no browser; browser tests are skipped without Chromium; `cli.py` and `mcp_server.py` stay in the coverage omit list."
- DEC-026 (SPEC-0008): "Test decks come from `build_deck`/`deck_med`/`doc_perso` (SPEC-0007) plus string injectors; the 1 500 character image of `deck_ei()` is avoided; PNG data is generated with `zlib` and `struct`."

### Data model

No product data. Test support API (`tests/render_support.py`):
```python
needs_chromium: pytest.MarkDecorator          # skipif no chromium-* in the Playwright cache dir (tests/test_tab_title_e2e.py:29-40 pattern)
EI_TITLES: Final[tuple[str, ...]]              # 8 titles, ids slide-0 .. slide-7
def ei_deck_html() -> str                      # build_deck("ei", EI_TITLES), no big image
def med_deck_html(dark_slide: str = "slide-2") -> str   # deck_med() with class "slide dark" on that slide
def inject_in_body(html: str, slide_id: str, snippet: str) -> str     # first child of .slide-body
def append_to_slide(html: str, slide_id: str, snippet: str) -> str    # after the inner frame, before </article>
def set_slide_class(html: str, slide_id: str, cls: str) -> str
def add_script(html: str, js: str) -> str
def big_deck(count: int = 40, *, with_images: bool = False) -> str    # build_deck("ei", [f"Slide {i}" ...]); images: valid 1x1 PNG data address, half also file based pics/ok.png
def tiny_png_bytes() -> bytes                  # zlib + struct, valid 1x1 PNG
def png_size(path: Path) -> tuple[int, int]    # IHDR, no Pillow
def png_pixel(path: Path, x: int, y: int) -> tuple[int, int, int]    # Pillow (present through python-pptx)
```

### Contracts

pyproject.toml:
```toml
[project.optional-dependencies]
render = ["playwright>=1.62,<2"]
# [tool.ruff.lint.per-file-ignores]
"src/mcp_htmleditor/render/service.py" = ["PLC0415"]   # the optional render extra is imported on demand
```
`uv.lock` regenerated with `make` has no target for it: run `uv lock` once (generated file); the locked playwright stays 1.62.0 because the dev group already pins it.

Makefile (names exact):
```make
## install-browser: Install the Chromium that `render` uses (needs the render extra)
install-browser:
ifeq ($(HAS_UV),yes)
	@TOOL_PY="$$(uv tool dir)/$(PROJECT_NAME)/bin/python"; \
	  if [ -x "$$TOOL_PY" ]; then echo "==> Installing Chromium for the installed tool"; "$$TOOL_PY" -m playwright install chromium; \
	  else echo "==> Installing Chromium for the project environment"; uv run --extra render python -m playwright install chromium; fi
else
	@echo "Error: uv not found. Install it from https://docs.astral.sh/uv/"
	@exit 1
endif
```
`install` runs `uv tool install ".[render]" --reinstall --force`. `install-browser` is added to `.PHONY` and to `help` (section "Build & Install").

### Paths

| Path | Action |
|---|---|
| `pyproject.toml` | modify: extra `render`, ruff per file ignore |
| `uv.lock` | regenerate with `uv lock` (generated) |
| `Makefile` | modify: `install-browser`, `install` with the extra, `.PHONY`, `help` |
| `tests/render_support.py` | create |
| `tests/test_render_install.py` | create |

### Existing patterns

- `Makefile:51` (`uv run playwright install chromium` in `sync`), `Makefile:155-175` (`install`), `Makefile:292-` (`help`).
- `pyproject.toml:35` (dev group with `pytest-playwright`), `pyproject.toml:95-125` (per file ignores with a comment each).
- `tests/test_tab_title_e2e.py:29-40` (`needs_chromium`), `tests/deck_support.py` (SPEC-0007: `build_deck`, `deck_med`, `doc_perso`).

## Acceptance tests

> 100% must pass, run through `make check` (or the project target). Never run test files ad hoc.

Fixtures of the spec (verbatim):

DECK-EI: an Euro-Information presentation of 8 slides `slide-0` to `slide-7` with no layout problem. DECK-MED: a
medical presentation of 6 slides whose `slide-2` has class `slide dark`. DOC-PERSO: a document. The machine running the tests has Segoe UI or Calibri installed, so DECK-EI and DECK-MED report no font problem. Where a test needs a defect, it states the defect.

Fixtures are generated by `tests/render_support.py` (US-0060) from the SPEC-0007 helpers in `tests/deck_support.py` (`build_deck`, `deck_med`, `doc_perso`, `run_cli`, `call_tool`), never committed and never read from `~/.config`. DECK-EI is `build_deck("ei", EI_TITLES)` with 8 titles and no big image. DECK-MED is `deck_med()` with the article of `slide-2` given `class="slide dark"`. DOC-PERSO is `doc_perso()`. The output directory is redirected with `monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))`. Browser tests carry `@needs_chromium`. On a machine without Segoe UI and Calibri the EI font stack still ends with Arial (`templates/bootstrap/slides-ei-empty.html:31`), which keeps DECK-EI free of a `font` problem.

### Additional integration and unit tests (`tests/test_render_install.py`)

- `pyproject.toml` parsed with `tomllib`: `project.optional-dependencies.render == ["playwright>=1.62,<2"]` and no entry of `project.dependencies` starts with `playwright`.
- `uv.lock` parsed with `tomllib`: the package `mcp-htmleditor` lists `render` under `optional-dependencies` with a `playwright` requirement.
- `make -n install-browser` output contains `-m playwright install chromium` and `uv run --extra render python -m playwright install chromium`.
- `make -n install` output contains `.[render]`; the `.PHONY` line and `make help` both name `install-browser`.
- Fixture self tests: `ei_deck_html()` has the 8 ids `slide-0` to `slide-7`; `inject_in_body` changes only the target slide (the text outside it is identical); `append_to_slide` puts the snippet after the inner frame; `set_slide_class(html, "slide-2", "dark")` marks only that article; `big_deck(40)` has 40 `data-type="slide"` articles and `big_deck(40, with_images=True)` gives each an `img`; `tiny_png_bytes()` has `png_size == (1, 1)`; `needs_chromium` is a `skipif` mark.
- `pyproject.toml` ruff config: `ruff check tests/render_support.py` is clean (run by `make lint`).

## Constraints

- Files not to touch: `src/mcp_htmleditor/**` (no product code in this story), `Dockerfile` (the image ships no browser), `tests/test_fullscreen_e2e.py`, `tests/test_tab_title_e2e.py`, `tests/test_autosave_focus_e2e.py` (their own `needs_chromium` stay).
- Dependencies not to add: anything but the optional `playwright` extra; do not move Playwright to the core dependencies; do not drop `pytest-playwright` from the dev group.
- Patterns to avoid: running `uv`, `pytest` or `playwright` directly (use `make`), a committed deck fixture, reading templates from `~/.config`.
- Scope boundary: no `render` command, no `render/` package.

## Definition of done

- [ ] RED evidence recorded for every new test before the production code (the command and output of the failing run).
- [ ] Every acceptance test above green; `make check` green; main stays green after the squash.
- [ ] Non regression: existing tests pass unmodified (`tests/test_skill_content.py`, `tests/test_templates.py`, the three existing browser E2E files); the existing commands and tools behave as before.
- [ ] Docs updated: none required beyond the Makefile `help` text; the user documentation lands in US-0067.
- [ ] Self review: full at tier 2.
- [ ] One commit `US-0060: Optional render extra, install-browser and fixtures` with body `Spec: SPEC-0008` and requirement ids FR-NEW-001.
