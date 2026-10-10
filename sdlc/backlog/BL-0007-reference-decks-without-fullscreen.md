---
Id: BL-0007
Title: Add fullscreen support to the five reference slide decks missing it
Nature: BUG
Source: retro-spec 20261010-123424
Created: 2026-10-10
Severity: Medium
Fingerprint: doc-contradicts-code:AGENTS.md:Every slide template (current and future) must ship fullscreen support
---

## What

Five reference decks have no `:fullscreen` CSS, no `#btn-present`, no
`enterPresentation`/`exitPresentation`/`updateFullscreenScale`:
`templates/reference/slides/ibm-carbon.html`, `example-ei-complete.html`,
`example-carbon-complete.html`, `presentation-standard.html`, `roadmap-one-pager.html`.

## Why

`AGENTS.md:67` states a presentation file missing fullscreen "is a bug to patch, not a valid
variant". A deck copied from one of these never gets presentation mode (legacy TBD-011).

## Evidence

grep counts (`:fullscreen` / `btn-present` / functions) are 0/0/0 for each of the five, against
6 to 8 / 1 / 10 for the three bootstraps and the EI and medical references.

## Notes

`ibm-carbon.html` also keeps the old Carbon height model (legacy DEC-015). Next: `/sdlc-analysis BL-0007`.
