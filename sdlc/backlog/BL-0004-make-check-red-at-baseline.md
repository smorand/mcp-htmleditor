---
Id: BL-0004
Title: Make the quality gate green again (format check and port range test)
Nature: BUG
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: High
Fingerprint: red-test-suite:tests/test_tab_title_e2e.py:make check
---

## What

`make check` exits 2 at base commit 2521c33. Two independent causes:
1. format-check fails: `tests/test_tab_title_e2e.py` would be reformatted (lines 53 and 131,
   quote style).
2. `tests/test_port_range.py::test_raises_a_clear_error_when_the_whole_range_is_taken` fails with
   `OSError: [Errno 48] Address already in use` when any process already listens on a port of
   7840 to 7849 (a running editor held 7842). The test binds every port itself
   (`tests/test_port_range.py:52`) and does not tolerate a busy machine.

## Why

The gate is the only quality barrier (no CI, SPEC-0001 DEC-009); a red gate hides new failures.

## Evidence

Gate run: lint pass, format-check fail, typecheck pass, security pass, tests 245 passed 1 failed,
coverage 95.44 %. `node --check src/mcp_htmleditor/static/*.js` pass.
`tests/test_tab_title_e2e.py:53`: `"<head><meta charset=\"UTF-8\"><title>" + title + "</title></head>\n"`.

## Notes

Cause 1 is a `make format` away. Cause 2 makes SPEC-0001/E2E-044 machine dependent. Next:
`/sdlc-spec --debt BL-0004` or a direct fix.
