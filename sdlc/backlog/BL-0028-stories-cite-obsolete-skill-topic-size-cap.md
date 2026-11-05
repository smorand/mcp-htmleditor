# BL-0028: SPEC-0010 stories cite a 3 800 byte cap for skill/topics/create.md

Nature: DEBT
Origin: US-0054 (SPEC-0010), found by its implementer.

## Evidence

`sdlc/stories/US-0054-complete-from-the-command-line.md` (contract and UT-C03) says the shipped `skill/topics/create.md`
stays at or below 3 800 bytes. After SPEC-0006 the file is about 7 100 bytes (7 611 after this story); the real gate
is `topic_output <= 8000` enforced by `skill-audit`. The story's design predates the final topic sizes.

## Proposal

Correct the figure in the stories and the SPEC-0010 design (3 800 should read 7 900 for the file, 8 000 for the output)
through the spec amendment path (never edited by implementation). US-0058 and US-0059 may repeat the same cap: check
them before running.
