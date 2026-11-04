/**
 * editor.js — mcp-htmleditor
 *
 * iframe-based renderer + lightweight rich-text editing.
 *
 * Features:
 *  - Polling /status → reload iframe on external changes
 *  - Overlay "modification LLM en cours"
 *  - Edit mode: contenteditable on [data-editable~="text"]
 *  - Floating format toolbar on text selection (bold/italic/underline/strike/…)
 *  - Insert toolbar on editable focus (image, table)
 *  - Context menus on data-type elements (gantt, arch, annotation, table)
 */

/* ============================================================
   State
   ============================================================ */
let pollInterval = 1000;
let lastMtime     = null;
let wasUpdating   = false;
let editMode      = false;
let saveTimer     = null;
let hasPendingChanges = false; // local edits not yet written to disk
let selfSaving    = false;     // true while our own POST /content is in flight
let isPresentation = false;   // detected from data-doc-type
let isDocument     = false;   // detected from data-doc-type
let isWebsite      = false;   // detected from data-doc-type; reuses document block/drag editing, no export
let insertPosition = null;    // 'before' | 'after' when slide picker is open
let blockPosition  = null;    // 'before' | 'after' when block picker is open
let lastDocRange   = null;    // saved caret range in document mode
let archConnectSource = null; // {node, doc} while picking an edge's target node

const frame        = document.getElementById('content-frame');
const undoBtn       = document.getElementById('undo-btn');
const redoBtn       = document.getElementById('redo-btn');
const overlay      = document.getElementById('update-overlay');
const statusDot    = document.getElementById('toolbar-status');

/* Save-state dot colors: green = saved, orange = pending changes,
   yellow = LLM update in progress. */
const DOT_SAVED   = '#42be65';
const DOT_PENDING = '#ff832b';
const DOT_LLM     = '#f1c21b';

/** Mark the document as having unsaved changes (orange dot). */
function markPending() {
  hasPendingChanges = true;
  if (statusDot) {
    statusDot.style.color = DOT_PENDING;
    statusDot.title = 'Modifications non sauvegardees';
  }
}

/** Mark the document as saved (green dot). */
function markSaved() {
  hasPendingChanges = false;
  if (statusDot) {
    statusDot.style.color = DOT_SAVED;
    statusDot.title = 'Sauvegarde';
  }
}
const editBtn      = document.getElementById('edit-mode-btn');
const presentBtn   = document.getElementById('present-btn');
const exportPptxBtn = document.getElementById('export-pptx-btn');
const exportDocxBtn = document.getElementById('export-docx-btn');
const slideActions = document.getElementById('toolbar-slide-actions');
const docActions   = document.getElementById('toolbar-doc-actions');

/* ============================================================
   Bootstrap
   ============================================================ */
(async function init() {
  try {
    const st = await fetch('/status').then(r => r.json());
    pollInterval = st.poll_interval || 1000;
    lastMtime    = st.mtime;
    const name   = (st.filename || '').split('/').pop();
    document.getElementById('toolbar-filename').textContent = name;
    document.title = name || 'HTML Editor';
  } catch (e) {
    console.warn('Could not reach /status', e);
  }

  editBtn.addEventListener('click', () => {
    editMode = !editMode;
    editBtn.setAttribute('aria-pressed', editMode ? 'true' : 'false');
    applyEditMode();
    updateSlideActionsVisibility();
    updateDocActionsVisibility();
    updateUndoRedoVisibility();
  });

  undoBtn.addEventListener('click', () => { if (!undoBtn.disabled) performUndo(); });
  redoBtn.addEventListener('click', () => { if (!redoBtn.disabled) performRedo(); });
  updateUndoRedoVisibility();

  // Present button: fullscreen the inner document (not the iframe element)
  // so keyboard events stay inside the iframe's own document. Fullscreen
  // alone does NOT move keyboard focus there, so the click on this button
  // (which lives in the parent shell) would otherwise keep focus on the
  // button itself and the slide's own arrow-key navigation would never
  // fire: explicitly focus the iframe once fullscreen is granted.
  presentBtn.addEventListener('click', () => {
    try {
      const inner = frame.contentDocument && frame.contentDocument.documentElement;
      if (inner && inner.requestFullscreen) {
        inner.requestFullscreen().then(() => frame.focus()).catch(() => {
          frame.requestFullscreen
            ? frame.requestFullscreen()
            : frame.webkitRequestFullscreen && frame.webkitRequestFullscreen();
        });
      } else if (inner && inner.webkitRequestFullscreen) {
        inner.webkitRequestFullscreen();
        frame.focus();
      } else {
        throw new Error('Fullscreen API unavailable on inner document');
      }
    } catch (e) {
      // fallback: fullscreen the iframe element itself
      frame.requestFullscreen
        ? frame.requestFullscreen()
        : frame.webkitRequestFullscreen && frame.webkitRequestFullscreen();
    }
  });
  document.addEventListener('fullscreenchange', () => {
    // Re-assert focus on every transition into fullscreen (covers the case
    // where the user re-enters via the iframe's own 'f' shortcut too).
    if (document.fullscreenElement) frame.focus();
    presentBtn.title = document.fullscreenElement
      ? 'Quitter la présentation (ESC)'
      : 'Mode présentation plein écran';
  });

  // Safety net: some browsers never move keyboard focus into the iframe's
  // document once fullscreen starts (frame.focus() above is not reliable
  // everywhere), so the slide template's own keydown listener never sees
  // the keypress. While presenting, forward arrow/space/escape keys typed
  // in the PARENT document straight into the iframe's navigate()/goToSlide()
  // globals. Keydown events fired *inside* the iframe never bubble up to
  // this listener (separate document), so there is no double-handling.
  document.addEventListener('keydown', (e) => {
    if (!document.fullscreenElement) return;
    const win = frame.contentWindow;
    if (!win) return;
    if ((e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') && typeof win.navigate === 'function') {
      e.preventDefault();
      win.navigate(1);
    } else if ((e.key === 'ArrowLeft' || e.key === 'ArrowUp') && typeof win.navigate === 'function') {
      e.preventDefault();
      win.navigate(-1);
    } else if (e.key === 'Home' && typeof win.goToSlide === 'function') {
      win.goToSlide(0);
    } else if (e.key === 'Escape') {
      document.exitFullscreen && document.exitFullscreen();
    }
  });

  // Export buttons
  exportPptxBtn.addEventListener('click', () => triggerExport('pptx'));
  exportDocxBtn.addEventListener('click', () => triggerExport('docx'));

  // Slide action buttons
  document.getElementById('btn-insert-before').addEventListener('click', () => openSlidePicker('before'));
  document.getElementById('btn-insert-after').addEventListener('click',  () => openSlidePicker('after'));
  document.getElementById('btn-delete-slide').addEventListener('click',  deleteCurrentSlide);
  document.querySelector('#slide-picker .picker-cancel').addEventListener('click', closeSlidePicker);
  document.querySelector('#slide-picker .picker-backdrop').addEventListener('click', closeSlidePicker);

  // Document block buttons (insert before / after the current block)
  document.getElementById('btn-insert-block-before').addEventListener('click', () => openBlockPicker('before'));
  document.getElementById('btn-insert-block-after').addEventListener('click',  () => openBlockPicker('after'));
  document.querySelector('#block-picker .picker-cancel').addEventListener('click', closeBlockPicker);
  document.querySelector('#block-picker .picker-backdrop').addEventListener('click', closeBlockPicker);

  frame.addEventListener('load', onFrameLoad);
  // The iframe may already be loaded by the time this script runs (race
  // condition): detect the document/presentation mode immediately in that case.
  try {
    const d = frame.contentDocument;
    if (d && d.readyState === 'complete' && d.documentElement) onFrameLoad();
  } catch (e) { /* cross-origin or not ready yet; the load event will fire */ }
  setInterval(pollStatus, pollInterval);
})();

/* ============================================================
   Iframe load
   ============================================================ */
function onFrameLoad() {
  try {
    const doc = frame.contentDocument;
    if (!doc) return;
    // Detect presentation mode from <html data-doc-type>
    const docType = doc.documentElement.getAttribute('data-doc-type');
    isPresentation = docType === 'presentation';
    isDocument     = docType === 'document';
    isWebsite      = docType === 'website';
    updateSlideActionsVisibility();
    updateDocActionsVisibility();
    syncBrowserTabTitle(doc);
    if (editMode) injectEditMode(doc);
    injectContextMenus(doc);
    // A freshly loaded document (initial load, external agent write, or the
    // human navigating to a different file) invalidates any snapshot taken
    // against the PREVIOUS document: never let undo/redo cross that boundary.
    // EXCEPT: restoreDomSnapshot() below also uses doc.write() on this same
    // iframe, and Chromium (verified) fires the iframe's own 'load' event on
    // EVERY doc.write(), exactly like a real navigation. Without this guard,
    // performUndo()/performRedo() would restore the DOM correctly and then
    // immediately have onFrameLoad() wipe the very stacks they just updated,
    // as if a fresh unrelated document had been loaded.
    if (restoringFromUndo) {
      doc.addEventListener('keydown', handleUndoRedoKeydown);
      doc.addEventListener('keydown', blockNavKeysInEditMode, true);
      return;
    }
    resetUndoStacks();
    doc.addEventListener('keydown', handleUndoRedoKeydown);
    doc.addEventListener('keydown', blockNavKeysInEditMode, true);
  } catch (e) {
    console.warn('Could not access iframe content:', e);
  }
}

/**
 * Reflect the edited document's own <title> in the browser tab, instead of
 * the shell's hardcoded "HTML Editor" or the file name on disk. Falls back
 * to the current file name when the document has no <title> (or an empty
 * one), so the tab is never blank. Runs on every iframe load, so switching
 * files (open_file) or an external agent rewrite keeps the tab in sync, and
 * two files served on two different ports keep two distinct tab titles.
 */
function syncBrowserTabTitle(doc) {
  const docTitle = (doc.title || '').trim();
  if (docTitle) {
    document.title = docTitle;
    return;
  }
  const filename = (document.getElementById('toolbar-filename').textContent || '').trim();
  document.title = filename || 'HTML Editor';
}

/* ============================================================
   Slide actions visibility (presentation + edit mode only)
   ============================================================ */
function updateSlideActionsVisibility() {
  slideActions.style.display   = (isPresentation && editMode) ? 'inline-flex' : 'none';
  presentBtn.style.display     = isPresentation ? 'inline-flex' : 'none';
  exportPptxBtn.style.display  = isPresentation ? 'inline-flex' : 'none';
  exportDocxBtn.style.display  = 'none'; // PPTX only for presentations
}

/* ============================================================
   Document block actions visibility (document + edit mode only)
   ============================================================ */
function updateDocActionsVisibility() {
  // A website reuses the document block-insert/drag machinery (getDocumentArticle()
  // only cares about article[data-type="document"], not the html-level doc-type), but
  // deliberately gets neither export button: it has no PPTX/DOCX destination by design
  // (see skill/types/website.md), so nothing here should ever call exportContent() for it.
  const showDocBlockUi = isDocument || isWebsite;
  if (docActions) {
    docActions.style.display = (showDocBlockUi && editMode) ? 'inline-flex' : 'none';
  }
  exportDocxBtn.style.display  = isDocument ? 'inline-flex' : 'none';
  exportPptxBtn.style.display  = showDocBlockUi ? 'none' : exportPptxBtn.style.display;
}

/* ============================================================
   Export (PPTX / DOCX)
   ============================================================ */

/**
 * Trigger a file download from /export/{format}.
 * Uses a temporary <a> so the browser saves the file without navigation.
 */
function triggerExport(format) {
  const btn = format === 'pptx' ? exportPptxBtn : exportDocxBtn;
  const label = btn.textContent.trim();
  btn.disabled = true;
  btn.textContent = '...';
  fetch('/export/' + format)
    .then(r => {
      if (!r.ok) return r.json().then(j => { throw new Error(j.error || r.statusText); });
      return r.blob();
    })
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const filename = (document.getElementById('toolbar-filename').textContent || 'export').replace(/\.html?$/, '') + '.' + format;
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    })
    .catch(err => alert('Export ' + format.toUpperCase() + ' échoué : ' + err.message))
    .finally(() => { btn.disabled = false; btn.textContent = label; });
}
async function pollStatus() {
  let status;
  try { status = await fetch('/status').then(r => r.json()); }
  catch (e) { return; }

  const name = (status.filename || '').split('/').pop();
  document.getElementById('toolbar-filename').textContent = name || '—';

  if (status.update_in_progress) {
    overlay.style.display = 'flex';
    statusDot.style.color  = DOT_LLM;
    statusDot.title = 'Modification par l\'agent en cours';
    wasUpdating = true;
  } else {
    overlay.style.display = 'none';
    // Only reset to green if nothing is pending locally.
    if (!hasPendingChanges) markSaved();
    const mtimeChanged = lastMtime !== null && status.mtime !== lastMtime;
    // Reload only for EXTERNAL changes (agent wrote the file). Never reload
    // because of our own save: that would flash the iframe and lose the caret.
    const externalChange = mtimeChanged && !selfSaving && !hasPendingChanges;
    if ((wasUpdating || externalChange) && !status.update_in_progress) {
      wasUpdating = false;
      lastMtime   = status.mtime;
      reloadFrame();
      return;
    }
  }
  lastMtime = status.mtime;
}

function reloadFrame() {
  frame.src = '/content-frame?' + Date.now();
}

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
const UNDO_MAX_DEPTH = 50;
let undoStack = [];
let redoStack = [];
// True only during the doc.write() performed by restoreDomSnapshot(), so
// onFrameLoad() (which Chromium fires again on every doc.write(), verified
// experimentally: it behaves exactly like a real navigation) can tell an
// undo/redo-triggered reload apart from a genuinely new document and skip
// wiping the very stacks the in-flight performUndo()/performRedo() call is
// updating.
let restoringFromUndo = false;

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

