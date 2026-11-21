# BL-0050: A diagram edit followed by the layout run cannot be undone

Nature: BUG
Origin: US-0165 (SPEC-0020 BT-018), found while writing the connect mode test.

## Evidence

- `src/mcp_htmleditor/static/editor-menus.js:36-47` (`saveThenLayout`): after a structural diagram edit (add or remove a node, create an edge:
  `:97`, `:113`, `:168`) the page saves, then `POST /arch-layout` makes the server rewrite the file with the recomputed positions.
- The poll sees the new modification time as an external change and reloads the frame (`src/mcp_htmleditor/static/editor.js:465-475`);
  `onFrameLoad` then empties the undo and redo stacks (`editor.js:351`, `editor-undo.js:169-170`).
- Observed 2026-11-20 in Chromium: after creating an edge in connect mode and waiting for the layout, `#undo-btn` is disabled and
  `undoStack.length` is 0, although `finishArchConnect` took a snapshot (`editor-menus.js:157`).

## Proposal

Keep the undo history across a reload the editor itself caused by its layout run. Undo of such an edit then removes the node or edge,
and Redo brings it back. Source of the expectation: SPEC-0002/FR-009 (Undo reverts the last structural action) and SC-002.
Test: create an edge, wait for the layout, press Undo: no `arch-edge` in the file; press Redo: it is back.
