---
Id: BL-0003
Title: Harden the deck export (limits, fonts, gradients, z-order, visual regression)
Nature: unknown
Source: legacy specs/BACKLOG.md BACKLOG-003 (user suggestion, session 2026-08-10)
Created: 2026-08-10
Severity: Medium
Fingerprint: legacy:specs/BACKLOG.md:BACKLOG-003
---

## What

Strengthen deck export robustness and fidelity beyond the existing non blocking diagnostics:
tested limits on file size and slide count, behavior with fonts missing on the export host,
complex CSS gradients, z-index and overlaps, automated visual regression tests (today only a
manual procedure in `.agent_docs/testing.md`), and guards for reference decks that have none.

## Why

"Hardening" is a theme, not yet a set of testable requirements; each lead needs its own EARS
requirement and E2E test.

## Evidence

Original entry: `specs/BACKLOG.md` BACKLOG-003 (moved in commit 5e22a15). Related: SPEC-0001/FR-013,
FR-014, legacy TBD-011, `.agent_docs/testing.md`.

## Notes

Nature left `unknown`: the entry mixes new capability (FEAT) and test and robustness work (DEBT),
and carries no command hint. Split before `/sdlc-spec`.
