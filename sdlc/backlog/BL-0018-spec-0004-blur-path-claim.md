---
Id: BL-0018
Title: Correct the SPEC-0004 claim that a save on leaving a zone strips the next zone
Nature: unknown
Source: US-0001 (SPEC-0004), /sdlc-implement 2026-10-10
Created: 2026-10-10
Severity: Low
Fingerprint: spec-claim:sdlc/specs/SPEC-0004-autosave-focus-loss/spec.md:at which point the focus has already reached the next zone
---

## What

SPEC-0004 BUG-001 "Contributing factors" says the immediate save on leaving a zone runs when "the
focus has already reached the next zone, which is then stripped too". On the pre-fix code, BT-012
(`tests/test_autosave_focus_e2e.py::test_leaving_a_zone_keeps_focus_in_the_next_zone`) passed:
the `blur` save runs before the next zone takes focus, so that path never lost focus.

## Why

A statement about the code in a spec is wrong; the requirement (BR-001) is unaffected.

## Evidence

`.implement/US-0001-red.log` on base 50969de:
`test_leaving_a_zone_keeps_focus_in_the_next_zone[chromium] PASSED` while BT-001, BT-010, BT-011,
BT-013 and BT-014 failed. `onEditableBlur` at `src/mcp_htmleditor/static/editor.js:1395`.

## Notes

Specs are never edited after the fact; next spec touching autosave can restate it. No code action.
