---
Id: BL-0024
Title: Two autosave e2e tests fail intermittently when the full suite runs under load
Nature: BUG
Source: implement US-0018 (SPEC-0012)
Created: 2026-11-03
Severity: Low
Fingerprint: bug:tests/test_autosave_focus_e2e.py:flaky-timing
---

## What

During `make check` on a docs only change (US-0018), two tests failed once and passed on the rerun and when run alone (`9 passed`):
`tests/test_autosave_focus_e2e.py::test_several_saves_lose_nothing[chromium]` (`assert 'Titre du document123' in ''`, l.193) and `::test_status_dot_returns_to_saved[chromium]` (`rgb(194, 150, 62) == rgb(66, 190, 101)`, l.255).

## Why

A gate that fails at random trains people to rerun it. The expected state is read before the autosave round trip completed.

## Evidence

`make check` log of the run: `2 failed, 356 passed in 127.94s`, then `358 passed in 105.56s` on the next run without any change.

## Notes

Likely a fixed wait versus the poll or save latency under CPU load. Reproduce with the suite under parallel load first. Next: `/sdlc-analysis BL-0024`.

## Update 2026-11-03 (implement US-0026)

A third flaky e2e test showed up once during `make check` and passed on rerun without change: `tests/test_undo_redo_e2e.py::test_undo_redo_document_block_insert[chromium]`. Same family (Chromium e2e timing under load).
