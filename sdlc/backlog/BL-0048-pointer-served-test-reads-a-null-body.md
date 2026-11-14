# BL-0048: test_pointer_served_pointeur_control reads a null body while the frame reloads

Nature: BUG (test only)
Origin: SPEC-0023 run, make check of 2026-11-14 (US-0123 commit 4b059a8).

## Evidence

- `make check` failed once: `tests/test_pointer_served_e2e.py::test_pointer_served_pointeur_control`,
  `playwright._impl._errors.Error: Page.evaluate: TypeError: Cannot read properties of null (reading 'textContent')`
  at `tests/test_pointer_served_e2e.py:287` (the observer `({FRAME_DOC}).body.textContent.includes('Changed paragraph')`).
- The same test passed 5 of 5 runs alone right after, and in the two previous full runs of the day.
- Cause: the agent write reloads the frame; between the old document and the new one the frame document has no
  `body`, and the observer raises instead of returning false, so `wait_until` fails on the first exception.

## Proposal

Guard the observer: `(d => !!d && !!d.body && d.body.textContent.includes('Changed paragraph'))(<FRAME_DOC>)`, and
look for the same unguarded pattern in the other `*_e2e.py` observers that read a reloading frame.
