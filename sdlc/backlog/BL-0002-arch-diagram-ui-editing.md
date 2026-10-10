---
Id: BL-0002
Title: Add, remove, resize and restyle architecture nodes and edges from the browser
Nature: FEAT
Source: legacy specs/BACKLOG.md BACKLOG-002 (user suggestion, session 2026-08-10)
Created: 2026-08-10
Severity: Low
Fingerprint: legacy:specs/BACKLOG.md:BACKLOG-002
---

## What

Node position drag exists in the browser. Missing: add or remove a node or an edge from the UI,
resize a node, pick its shape (`data-shape`) or the edge style (`data-style`: solid, dashed,
dotted) without going through the agent. Idea: extend the existing context menu on `data-type`
elements with node and edge actions, corner resize handles, and a "connect two nodes" click mode.

## Why

The diagram is the hardest component to edit visually; today every structural change goes through
the agent.

## Evidence

Original entry: `specs/BACKLOG.md` BACKLOG-002 (moved in commit 5e22a15). Deferred: needs an
interview on the interaction model (edges must stay attached, native deck export must survive).
Related: SPEC-0002/FR-017, SPEC-0003 (declarative layout now computes positions, which changes the
premise of hand placed nodes), `skill/types/arch-diagram.md`.

## Notes

Original text was in French. Next command: `/sdlc-spec BL-0002`.
