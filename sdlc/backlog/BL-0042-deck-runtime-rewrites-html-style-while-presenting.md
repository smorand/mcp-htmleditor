# BL-0042: The deck runtime rewrites `<html>`'s style while presenting

Nature: BUG (hint)
Origin: deferred from SPEC-0020 (class sweep, section 1bis).
Decision: deferred by the 2026-11-09 run under the instruction "take recommended defaults"; not a security
finding.

## Evidence

Class: inline style text written by a person or an agent reaches a style object write that does not preserve
its text. Every presentation template sets the scale with `root.style.setProperty('--fs-scale', ...)` and
clears it with `root.style.removeProperty('--fs-scale')` (33 hits in 11 files,
`rg -n "setProperty\('--fs-scale'|removeProperty\('--fs-scale'" templates`, for example
`templates/bootstrap/slides-empty.html`, function `updateFullscreenScale`). While presenting, a `style` written
on `<html>` is reserialized by Chromium (hex colours to `rgb(...)`, comments dropped), and a save made during or
after presenting writes that form: the editor's presenting strip (SPEC-0020/BR-004) removes `--fs-scale` only.

## Proposal

Write the scale on `<html>` as text, or as a custom property on a node the deck owns, so `<html>`'s own style
keeps its bytes; sync the pointer and presenting blocks with `make sync-deck-pointer` where relevant. Test: a
deck with `<html style="color:#161616">`, present, save, leave: the file holds `style="color:#161616"`.
