# US-0116: breathe decoration catalogue and generator

> Spec: SPEC-0023 (sdlc/specs/SPEC-0023-breathe-template/)
> Nature: FEAT
> Priority: P2
> Depends on: main
> min_tier: 1
> Files touched: 6
> Closes spec: no

## Objective
Ship the Breathe decoration catalogue (backgrounds, icons, logo disc, samples, the four source pictures) under large file storage, with the maintainer generator ported from the source template, so decks and exports never depend on files outside the product.

## Requirements covered
- SPEC-0023/FR-NEW-017: WHEN the maintainer types `make breathe-assets` THE Template catalogue SHALL redraw the backgrounds of every preset and stage, the icons of every glyph in every variant, the logo disc and the sample pictures into the catalogue folder and print `<N> files written to <folder> (<K> KB)`.
- SPEC-0023/FR-NEW-024: The Template catalogue SHALL ship, besides the 158 generated files of FR-NEW-017, the files `collage-sample-b.jpg`, `wiip-strong-logo.png`, `filigrane-stethoscope-poumons.png` and `logo-2026-botanical-transparent.png`.

## Independent Test
`make test ARGS='tests/test_breathe_assets_tool.py'`: a subset written with `--only` is byte identical to `templates/assets/breathe`; `git lfs ls-files` lists the 162 catalogue files.

## Design excerpt
### Decisions
- DEC-010 Pillow in the dev group (SPEC-0023 design.md)
- DEC-011 `.gitattributes` LFS before the first binary (SPEC-0023 design.md)
- DEC-014 `--only` subset, full run `slow` (SPEC-0023 design.md)
### Paths
| Path | Action |
|---|---|
| `.gitattributes` | create |
| `tools/breathe_assets.py` | create |
| `templates/assets/breathe/*` | create |
| `Makefile` | modify |
| `pyproject.toml`, `uv.lock` | modify |
| `tests/test_breathe_assets_tool.py` | create |

## Acceptance tests
> 100% must pass through `make check`. The Given/When/Then of each test is in the spec, Section 9.

- SPEC-0023/E2E-038 (slow): full catalogue, 158 files, byte identical
- SPEC-0023/E2E-039: `--list`, 56 + 16 lines, nothing written
- SPEC-0023/E2E-040: watermark source missing, exit 1, nothing written
- SPEC-0023/E2E-054: logo source missing, same shape

## Constraints
- Files not to touch: the medical, Carbon and Euro-Information templates and their exporter paths.
- Dependencies not to add: none beyond the design (Pillow dev only).
- Scope boundary: the other stories of SPEC-0023.

## Definition of done
- [ ] RED evidence recorded for every new test before the production code.
- [ ] Every acceptance test above green; `make check` green on the work branch after this commit.
- [ ] Non regression: the ten golden PPTX fingerprints (`tests/test_export_golden.py`), every medical, Carbon and
      Euro-Information lint and export test unchanged.
- [ ] Docs updated where the story changes usage.
- [ ] Self review: full (tier 1).
- [ ] One commit `US-0116: <title>` on `feat/breathe-template`, body with `Summary:`, `Spec: SPEC-0023` and the ids.
