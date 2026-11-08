# BL-0040: SPEC-0017 wording mismatches found while implementing

Nature: FEAT
Origin: found while implementing and closing SPEC-0017 (US-0103, US-0105, US-0110). Amend the spec with /sdlc-spec.

## What

Four places where the spec text and the built behaviour differ, to settle in the spec (the code was built to the
tested reading):

1. E2E-008 contradicts FR-NEW-006: clicking a second cell of the ringed table moves the ring away (one ring, a
   table is one box), while E2E-008 reads as if the ring stays. The tests click the background between cells.
2. A click on a form field's label runs `findBox` and removes any ring; no test covers it (FR-NEW-008 names links,
   buttons and fields, not labels).
3. A click outside the slide is ignored (the ring stays); FR-NEW-006 does not say so.
4. FR-NEW-005 leaves reading choices that DEC-008 settled (which box wins when a tile contains a table, what a
   transparent box is); fold DEC-008 into the requirement text.

Also: design.md and US-0105 name the guard marker `function togglePointer(`, the template and the guard use
`window.togglePointer = function` (`tests/test_presentation_templates_fullscreen.py:17`). DEC-015 says
`:fullscreen #deck-controls { display:none; }`; the built decks need `display:none !important` because the
container's inline `display:flex` wins (`templates/reference/slides/presentation-standard.html:196`).

## Why

The next reader of the spec should not have to rediscover which reading the tests encode.

## Evidence

- `templates/bootstrap/slides-empty.html:574` to `:584` (click handler: `slide.contains(e.target)` guard, `CONTROLS`
  guard, `removeRing()` before `showRing`).
- `tests/test_pointer_served_e2e.py::test_pointer_served_table_is_one_box` (E2E-008 and E2E-009).
- `.agent_docs/html-conventions.md` § Presentation pointer records the `!important` fact.
