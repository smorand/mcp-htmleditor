# BL-0037: Presenter view with audience window

Nature: FEAT
Origin: deferred from SPEC-0017 (pointer in presentation mode).

## What

Present on two screens: the window the presenter keeps becomes a presenter view (elapsed time and
clock, the notes of the current slide, the previous, current and next slides), and a second window,
the audience window, shows only the slide full screen and follows every slide change. The pointer of
SPEC-0017 shows in both windows, whichever one the mouse is over.

## Why

html-editor presents in one window only (SPEC-0001/FR-026 to FR-028): the presenter sees exactly what
the room sees, with no notes and no view of the next slide.

## Evidence

- snxt-deck-builder (read only, branch develop), `README.md` section "Present on two screens".
- `src/mcp_htmleditor/static/editor.js:114` (one window: the deck's own document put full screen).

## Notes

Needs a place for presenter notes in the deck format, which does not exist today.
