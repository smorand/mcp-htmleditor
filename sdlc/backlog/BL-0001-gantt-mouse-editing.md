---
Id: BL-0001
Title: Edit existing Gantt charts with the mouse in the browser
Nature: FEAT
Source: legacy specs/BACKLOG.md BACKLOG-001 (user suggestion, session 2026-08-10)
Created: 2026-08-10
Severity: Medium
Fingerprint: legacy:specs/BACKLOG.md:BACKLOG-001
---

## What

Today a Gantt block can be inserted and exported as native deck shapes, but any change to an
existing Gantt (move a task, change its dates, add or remove a task, change its color) requires
the agent to rewrite the HTML. Idea: horizontal drag handles on each task bar (move and resize by
updating `data-start`/`data-end` or inline percentages), a `+` button to add a task, a context
menu for color and label, on the model of the arch node drag already shipped.

## Why

Reinforced on 2026-08-14 by a real client deck (`Agentic_Platform_Deck.html`, roadmap Gantt
slide): the user wants the same mouse editing level as arch nodes, plus an explicit check of the
deck export fidelity of the Gantt after each interaction.

## Evidence

Original entry: `specs/BACKLOG.md` BACKLOG-001 (moved in commit 5e22a15). Deferred because it needs
a dedicated interview: absolute dates versus inline percentages, snap granularity, task overlap,
export revalidation. Related: SPEC-0001/FR-013, SPEC-0002/FR-017, `skill/types/gantt.md`.

## Notes

Original text was in French. Next command: `/sdlc-spec BL-0001`.
