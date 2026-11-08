---
Id: BL-0010
Title: Cover the update window reload of SPEC-0001 in a browser
Nature: DEBT
Source: retro-spec 20261010-123424; re-verified 2026-11-08 by SPEC-0019
Created: 2026-10-10
Severity: Low
Fingerprint: untested-requirement:sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md:E2E
---

## What

Of the 11 `untested` rows of SPEC-0001 § 8, one gap remains on 2026-11-08: E2E-004 and E2E-005 (FR-004) have
their agent half covered (`tests/test_state.py::test_state_shared_between_processes` uses a real `fastmcp.Client`;
`tests/test_state.py::test_status_with_expiry`, `::test_update_end_after_expiry`), but no test asserts the browser
half: no reload while the update window is open, then exactly one reload after `update_end`.

Closed since: E2E-002 and E2E-045 (`tests/test_deck_tools.py::test_new_unknown_template_then_create_then_refuse_overwrite`),
E2E-009 (superseded by SPEC-0009: `tests/test_save_safety_e2e.py:152`), E2E-014 (superseded by the deck tools:
`tests/test_deck_tools.py::test_export_pptx_of_a_document_without_slide_fails`), E2E-023, E2E-024, E2E-025
(`tests/test_server_lifecycle_stdio.py:112`, `:122`, `:140`), E2E-046 (`tests/test_legacy_arbitrations.py:86`,
`tests/test_deck_tools.py:202`, `:211`), E2E-036 (taken by SPEC-0019 DT-030).

## Why

The reload contract is what keeps a human from editing a stale page during an agent write.

## Evidence

`sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md:151-152`; the overlay alone is seen in `tests/test_width_visibility_e2e.py:53`, `:124`.

## Notes

A browser test costs about 3 s and the `make check` test step runs at 320 to 325 s against a 330 s hard cap
(`.agent_docs/testing.md` § SPEC-0016 closing run, § SPEC-0017 pointer tests). Specify together with BL-0017 and
a trim of the test step. Next: `/sdlc-spec --debt BL-0010`.
