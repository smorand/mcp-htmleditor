# BL-0041: Pointer clicks on a field's label and on the black margins

Nature: FEAT
Origin: SPEC-0017 amendment for BL-0040 (2026-11-08). Settle with /sdlc-spec, then a test per behavior.

## What

Two click cases of the presentation pointer that the spec does not state and no test covers:

1. A click on the text of a form field's label (fixture `<label>Note <input id="note"></label>`,
   `tests/pointer_support.py:55`). The built code does not count a label as a control: the `CONTROLS` guard is
   `a[href], button, input, select, textarea` (`templates/bootstrap/slides-empty.html:442`), so the label click
   runs `findBox` and moves or removes the ring (`:574` to `:584`), while the browser also forwards the click to
   the field. Proposed product behavior: a label belongs to its field, so its click keeps the ring unchanged like
   the field's (FR-NEW-008), with `label` added to the guard and an E2E test. This is a behavior change, hence
   not folded into the amendment.
2. A click on the black margins around the slide while presenting. The handler returns when the target is not
   inside the current slide (`:576`), so the ring stays; FR-NEW-006 does not say so and no test clicks there
   (E2E-021, `tests/test_pointer_dot_e2e.py::test_pointer_dot_over_the_black_margins`, only moves the mouse).
   Proposed: add the rule to FR-NEW-006, an edge case row, and a click step to E2E-021.

## Design corrections (design.md of SPEC-0017, not edited by the amendment)

- The guard marker is `window.togglePointer = function` (`tests/test_presentation_templates_fullscreen.py:17`),
  not `function togglePointer(` as design.md and US-0105 say.
- DEC-015 reads `:fullscreen #deck-controls { display:none; }`; the built decks need `display:none !important`
  because the container's inline `display:flex` wins (`templates/reference/slides/presentation-standard.html:196`).

## Why

A presenter clicking a label to fill a field would lose or move the ring; the margin behavior is right but
unprotected by any test.
