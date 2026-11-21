# SPEC-0033: Render limits, design

> Spec: sdlc/specs/SPEC-0033-render-limits/spec.md
> Nature: FEAT
> Depth: M
> Security: n/a
> Designed on: 2026-11-20
> Target tier: 2 (default)

## 1. Stack and skills
Existing stack (Python 3.13, Playwright sync API, `make check`). No dependency. Skill python: `make` only; no I/O added.

## 2. Approaches
### Chosen: four local fixes in the render module
One fix per behavior, at the site that produces it (DEC-001..DEC-004). Rejected: a post processing pass over the finished report (the picture failure cannot be fixed after the fact, and line level normalisation belongs where the line is built).

## 3. Architecture
`render/service.py` (`_shoot`, `PageSignals.record`, `_failed_images`) and `render/scripts.py` (`MEASURE_SLIDE_JS` generic list). `render/problems.py` is unchanged.

## 4. Data model
None.

## 5. Contracts and interfaces
- `scripts.py`: in `MEASURE_SLIDE_JS`, `const generic = [...]` becomes `['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui', 'ui-serif', 'ui-sans-serif', 'ui-monospace', 'ui-rounded', 'emoji', 'math', 'fangsong', '-apple-system', 'blinkmacsystemfont']` (compared after `toLowerCase()`, as today; `families` already unquotes names).
- `service.py` `_shoot`: `locator = page.locator(SLIDE_SELECTOR).nth(target.index)`; `locator.scroll_into_view_if_needed()`; then `box = locator.bounding_box()` and the clip as today. The scroll happens after `SHOW_SLIDE_JS` (the slide is displayed) and after the measure.
- `service.py` `PageSignals.record(name, message)`: `text = " ".join(f"{name}: {message}".split())`; the `(slide, text)` pair de duplication is unchanged.
- `service.py` `_failed_images`: keep the first item of each `(slide_index, src)` pair in page order (`dict.fromkeys`), then the message is `f"{shorten_source(src) or '(empty address)'} did not load"`.

## 6. File structure impact
| Path | Action | Caused by | Story |
|---|---|---|---|
| `src/mcp_htmleditor/render/scripts.py` | modify: generic list | FR-NEW-002, FR-MOD-001 | US-0171 |
| `src/mcp_htmleditor/render/service.py` | modify: scroll, record, `_failed_images` | FR-NEW-001, 003, 004, 005, FR-MOD-002 | US-0171 |
| `tests/test_render_limits_e2e.py` | create | E2E-001..009 | US-0171 |
| `.agent_docs/render.md` | modify: the rules of the four behaviors | docs | US-0171 |
Affected existing tests: none modified (`tests/test_render_report.py`, `tests/test_render_picture.py` keep passing).

## 7. Compatibility and risks
Report lines change only in the cases of the spec. Risk: `scroll_into_view_if_needed` on a slide that is already in view is a no op. Rollback: revert.

## 9. Test strategy
Browser tests through the command line in a worker thread as in `tests/test_render_report.py` (`run_cli` wrapper); fixtures built with `tests/render_support.py` helpers (`ei_deck_html`, `append_to_slide`, `add_script`) and string edits of the EI deck.

## 10. Decisions log
- **DEC-001:** scroll the target into view before reading its box. **Obliged by:** SPEC-0033/FR-NEW-001. **Alternatives considered:** a taller viewport (changes the layout the report measures). **Source:** SPEC-0008 DEC-008 follow up.
- **DEC-002:** extend the generic names list in the page script. **Obliged by:** SPEC-0033/FR-NEW-002, FR-MOD-001.
- **DEC-003:** normalise white space in `PageSignals.record`. **Obliged by:** SPEC-0033/FR-NEW-003.
- **DEC-004:** de duplicate failed images on `(slide, address)` in `_failed_images` and name the empty address. **Obliged by:** SPEC-0033/FR-NEW-004, FR-NEW-005, FR-MOD-002.

## 11. Stories
| Story | Title | Priority | Requirements | Depends on | min_tier | Closes spec |
|---|---|---|---|---|---|---|
| US-0171 | the four render limits | P1 | FR-NEW-001..005, FR-MOD-001, FR-MOD-002 | main | 2 | yes |
