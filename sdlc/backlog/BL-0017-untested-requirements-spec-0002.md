---
Id: BL-0017
Title: Cover the untested browser requirements of SPEC-0002
Nature: DEBT
Source: retro-spec 20261010-123424; re-verified 2026-11-08 by SPEC-0019
Created: 2026-10-10
Severity: Medium
Fingerprint: untested-requirement:sdlc/specs/SPEC-0002-browser-editing/spec.md:E2E
---

## What

The 7 `untested` rows of SPEC-0002 § 8, re-verified on 2026-11-08 against the current tests:

- E2E-013 (FR-002, FR-003): uncovered. No test shows the format bar on a selection, hides it on an outside click, or
  shows the insert bar (image, table, rule, link) on focus.
- E2E-014 (FR-004 to FR-006): partial. Saves are observed (`tests/test_autosave_focus_e2e.py`, `save_delay`), the
  800 ms and 600 ms delays and the save on blur are not asserted.
- E2E-015 (FR-007): partial. Green and orange are asserted (`tests/test_save_ui_e2e.py:28-29`, `:76`;
  `tests/test_autosave_focus_e2e.py:293`); the yellow dot during an agent update is not.
- E2E-016 (FR-008): partial. No reload on the page's own save is asserted (`tests/test_save_ui_e2e.py:243`,
  `tests/test_autosave_focus_e2e.py:279`); no reload while changes are pending is not.
- E2E-017 (FR-011): partial. Undo and redo are tested (`tests/test_undo_redo_e2e.py`), the depth of 50 and the redo
  cleared by a new action are not.
- E2E-018 (FR-018): uncovered. Space, arrows, Home, End and F typed in an editable zone must not move the slide.
- E2E-019 (FR-019): uncovered. No test clicks an export button and receives the download (`expect_download`).

## Why

Autosave, reload and keyboard isolation are the paths a human hits on every keystroke.

## Evidence

`sdlc/specs/SPEC-0002-browser-editing/spec.md:120-126`.

## Notes

All seven are browser tests. The `make check` test step runs at 320 to 325 s against a 330 s hard cap
(`.agent_docs/testing.md` § SPEC-0016 closing run, § SPEC-0017 pointer tests): a spec for this entry must first
decide the trim that pays for them (SPEC-0019 DEC-006). Next: `/sdlc-spec --debt BL-0017`.
