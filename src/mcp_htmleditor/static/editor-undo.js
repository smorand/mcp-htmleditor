/* ============================================================
   Undo / redo (structural mutations only)
   ============================================================
   Scope: DOM-mutating structural operations that have no native undo —
   arch-node reposition/add/remove/rename/reshape, arch-edge create, image
   insert, table row/col add/remove, table delete, gantt task add/resize/
   rename/delete, slide insert/delete, document block insert/reorder/delete.

   Deliberately OUT of scope: plain contenteditable text edits (bold, typing,
   caret-level changes) and native in-place image resize/reposition when the
   image lives inside a contenteditable zone — both already have a working
   native undo stack via the browser's own Ctrl+Z on contenteditable. Pushing
   our own snapshot on every keystroke would fight that native stack instead
   of complementing it (see .agent_docs/html-conventions.md § Undo/redo for
   the exact interaction observed when the two are interleaved).

   Snapshot granularity: the whole iframe document's outerHTML. Simpler and
   always structurally correct; a document is a single slide deck or article,
   never large enough (parsed HTML string, not a live tree) for this to be a
   real perf concern. Capped at UNDO_MAX_DEPTH entries.

   Push BEFORE the mutation runs (pre-mutation state), so undo restores what
   was there before. Call snapshotForUndo() at the top of every structural
   mutation handler, synchronously, before touching the DOM. ============================================================ */
/** Serialize the iframe's current DOM state the same way saveContent() does,
 *  but WITHOUT writing to disk: used as a snapshot payload for undo/redo. */
function captureDomSnapshot(doc) {
  const editables = [...doc.querySelectorAll('[contenteditable]')];
  const backup = editables.map(el => ({
    el, ce: el.contentEditable,
    outline: el.style.outline, cursor: el.style.cursor,
  }));
  editables.forEach(el => {
    el.removeAttribute('contenteditable');
    el.style.outline = ''; el.style.cursor = '';
  });

  const fb = doc.getElementById('_mcp_format_bar');
  const ib = doc.getElementById('_mcp_insert_bar');
  const fbDisplay = fb?.style.display; const ibDisplay = ib?.style.display;
  if (fb) fb.style.display = 'none';
  if (ib) ib.style.display = 'none';

  const detachedDrag = detachDragArtifacts(doc);

  const html = doc.documentElement.outerHTML;

  backup.forEach(({ el, ce, outline, cursor }) => {
    el.contentEditable = ce; el.style.outline = outline; el.style.cursor = cursor;
  });
  if (fb) fb.style.display = fbDisplay;
  if (ib) ib.style.display = ibDisplay;
  reattachDragArtifacts(detachedDrag);

  return html;
}

/** Record the CURRENT (pre-mutation) DOM state on the undo stack. Call this
 *  synchronously right before mutating the DOM for any structural op. Clears
 *  the redo stack: a fresh mutation invalidates whatever was undone before. */
function snapshotForUndo() {
  if (!editMode) return;
  const doc = frame.contentDocument;
  if (!doc) return;
  undoStack.push(captureDomSnapshot(doc));
  if (undoStack.length > UNDO_MAX_DEPTH) undoStack.shift();
  redoStack = [];
  updateUndoRedoButtons();
}

/** Replace the iframe document's full markup with a previously captured
 *  snapshot, then re-wire interactivity and persist via the existing save
 *  path (same POST /content saveContent() already uses for every other
 *  mutation: no second save mechanism).
 *
 *  Rewiring itself (editable zones, drag handles, arch-node drag, context
 *  menus) is NOT duplicated here: doc.write() makes Chromium (verified,
 *  see onFrameLoad()'s restoringFromUndo guard) fire the iframe's own
 *  'load' event exactly like a real navigation, so onFrameLoad() runs and
 *  does it — the same single rewiring path every other document load goes
 *  through, deliberately not a second parallel implementation. */
async function restoreDomSnapshot(html) {
  const doc = frame.contentDocument;
  if (!doc) return;
  const activeTag = doc.activeElement && doc.activeElement.tagName;
  if (activeTag) doc.activeElement.blur();

  restoringFromUndo = true;
  const loaded = new Promise(resolve => frame.addEventListener('load', resolve, { once: true }));

  doc.open();
  doc.write(html);
  doc.close();

  await loaded;
  restoringFromUndo = false;

  markPending();
  await saveContent();
}

/** Ctrl+Z / Cmd+Z → undo, Ctrl+Shift+Z / Cmd+Shift+Z / Ctrl+Y → redo.
 *  Only active in edit mode. Never intercepts a keystroke while the user is
 *  actively typing in a contenteditable region: that keeps the browser's own
 *  native undo stack in sole control of plain text edits (see module header
 *  comment). Structural ops fire regardless of where focus is otherwise
 *  (toolbar buttons, context-menu prompts, arch-node drag handles, …). */
async function handleUndoRedoKeydown(e) {
  if (!editMode) return;
  const isZ = e.key === 'z' || e.key === 'Z';
  const isY = e.key === 'y' || e.key === 'Y';
  const mod = e.metaKey || e.ctrlKey;
  if (!mod || (!isZ && !isY)) return;

  const doc = frame.contentDocument;
  const active = doc && doc.activeElement;
  const inLiveTextEdit = !!(active && active.isContentEditable);
  // Let the browser's native undo run inside an actively-edited text zone —
  // EXCEPT when it has nothing left to undo natively (queryCommandEnabled
  // returns false once its own history is exhausted): at that point Ctrl+Z
  // would otherwise do nothing, so fall through to our structural stack.
  if (inLiveTextEdit) {
    try {
      const nativeHasUndo = isZ && !e.shiftKey && doc.queryCommandEnabled('undo');
      const nativeHasRedo = (isZ && e.shiftKey) || isY;
      if (isZ && !e.shiftKey && nativeHasUndo) return;
      if (nativeHasRedo && doc.queryCommandEnabled('redo')) return;
    } catch (err) {
      // queryCommandEnabled is not implemented consistently everywhere;
      // if it throws, be conservative and let the native handler have it.
      return;
    }
  }

  if (isZ && !e.shiftKey) {
    if (!undoStack.length) return;
    e.preventDefault();
    await performUndo();
  } else if ((isZ && e.shiftKey) || isY) {
    if (!redoStack.length) return;
    e.preventDefault();
    await performRedo();
  }
}

async function performUndo() {
  const doc = frame.contentDocument;
  if (!doc || !undoStack.length) return;
  const current = captureDomSnapshot(doc);
  const previous = undoStack.pop();
  redoStack.push(current);
  if (redoStack.length > UNDO_MAX_DEPTH) redoStack.shift();
  updateUndoRedoButtons();
  await restoreDomSnapshot(previous);
}

async function performRedo() {
  const doc = frame.contentDocument;
  if (!doc || !redoStack.length) return;
  const current = captureDomSnapshot(doc);
  const next = redoStack.pop();
  undoStack.push(current);
  if (undoStack.length > UNDO_MAX_DEPTH) undoStack.shift();
  updateUndoRedoButtons();
  await restoreDomSnapshot(next);
}

function updateUndoRedoButtons() {
  if (undoBtn) undoBtn.disabled = undoStack.length === 0;
  if (redoBtn) redoBtn.disabled = redoStack.length === 0;
}

/** The undo/redo buttons are only meaningful in edit mode (same gating as
 *  handleUndoRedoKeydown): hide them the rest of the time instead of leaving
 *  a permanently disabled pair in the toolbar. */
function updateUndoRedoVisibility() {
  const display = editMode ? 'inline-flex' : 'none';
  if (undoBtn) undoBtn.style.display = display;
  if (redoBtn) redoBtn.style.display = display;
}

/** Reset both stacks: called whenever the iframe loads a genuinely different
 *  document (initial load, external agent write, navigating to another
 *  file). A snapshot captured against a PREVIOUS document's DOM would not
 *  correspond to anything restorable once that document is gone, so it must
 *  never survive past this boundary. Toggling edit mode off/on within the
 *  SAME loaded document deliberately does NOT reset the stacks: closing the
 *  edit toolbar to preview the render and reopening it should not throw away
 *  undo history. */
function resetUndoStacks() {
  undoStack = [];
  redoStack = [];
  updateUndoRedoButtons();
}

