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

/* ============================================================
   Edit mode toggle
   ============================================================ */
/**
 * Capture-phase keydown guard injected on the iframe's document.
 * Blocks slide-navigation shortcuts (Space, arrows, Home, End, F) when the
 * user is actively editing inside a contenteditable element so keystrokes
 * reach the text instead of jumping slides. Works for all presentation files,
 * including those created before the template-side guard was added.
 */
function blockNavKeysInEditMode(e) {
  if (!editMode) return;
  const ae = e.target;
  if (!ae || !ae.isContentEditable) return;
  const navKeys = new Set([' ', 'ArrowRight', 'ArrowLeft', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'f', 'F']);
  if (navKeys.has(e.key)) e.stopPropagation();
}

function applyEditMode() {
  try {
    const doc = frame.contentDocument;
    if (!doc) return;
    if (editMode) injectEditMode(doc);
    else          removeEditMode(doc);
  } catch (e) {
    console.warn('Could not toggle edit mode:', e);
  }
}

function injectEditMode(doc) {
  doc.querySelectorAll('[data-editable~="text"]').forEach(el => {
    el.contentEditable = 'true';
    el.classList.add('_mcp_editable');
    el.addEventListener('input',     onEditableInput);
    el.addEventListener('blur',      onEditableBlur);
    el.addEventListener('mouseup',   () => { showFormatBar(doc); saveDocRange(doc); });
    el.addEventListener('keyup',     () => { showFormatBar(doc); saveDocRange(doc); });
    el.addEventListener('focus',     () => showInsertBar(doc, el));
  });
  injectEditorStyles(doc);
  createFormatBar(doc);
  createInsertBar(doc);
  enableImageDrop(doc);
  if (isDocument || isWebsite) injectDocDragHandles(doc);
  if (isPresentation) enableArchNodeDrag(doc);
}

function removeEditMode(doc) {
  doc.querySelectorAll('[data-editable~="text"]').forEach(el => {
    el.contentEditable = 'false';
    el.classList.remove('_mcp_editable');
    el.removeEventListener('input',   onEditableInput);
    el.removeEventListener('blur',    onEditableBlur);
  });
  doc.getElementById('_mcp_format_bar')?.remove();
  doc.getElementById('_mcp_insert_bar')?.remove();
  doc.getElementById('_mcp_editor_styles')?.remove();
  removeDocDragHandles(doc);
  removeArchNodeDrag(doc);
  hideFormatBar();
  hideInsertBar();
}

/* ============================================================
   Inject editor styles into iframe doc
   ============================================================ */
function injectEditorStyles(doc) {
  if (doc.getElementById('_mcp_editor_styles')) return;
  const s = doc.createElement('style');
  s.id = '_mcp_editor_styles';
  s.textContent = `
    ._mcp_editable { outline: 2px dashed #0f62fe !important; cursor: text; min-height: 1em; }
    ._mcp_editable:focus { outline: 2px solid #0f62fe !important; background: rgba(15,98,254,0.03); }
    #_mcp_format_bar {
      position: fixed; z-index: 99999; display: none;
      background: #161616; border-radius: 3px;
      box-shadow: 0 3px 12px rgba(0,0,0,.45);
      padding: 3px 4px; gap: 1px;
      align-items: center; flex-wrap: nowrap;
      font-family: 'IBM Plex Sans', -apple-system, sans-serif;
    }
    #_mcp_format_bar button {
      background: none; border: none; cursor: pointer;
      color: #f4f4f4; width: 28px; height: 26px;
      border-radius: 2px; font-size: 13px; font-weight: 600;
      display: flex; align-items: center; justify-content: center;
      transition: background 80ms;
    }
    #_mcp_format_bar button:hover  { background: #393939; }
    #_mcp_format_bar button.active { background: #0f62fe; }
    #_mcp_format_bar .sep { width: 1px; height: 18px; background: #525252; margin: 0 2px; }
    #_mcp_format_bar select {
      background: #262626; color: #f4f4f4; border: none;
      font-size: 11px; padding: 2px 4px; border-radius: 2px;
      height: 24px; cursor: pointer; outline: none;
    }
    #_mcp_format_bar input[type=color] {
      width: 24px; height: 24px; border: none; border-radius: 2px;
      cursor: pointer; padding: 0; background: none;
    }
    #_mcp_insert_bar {
      position: fixed; z-index: 99998; display: none;
      background: #f4f4f4; border: 1px solid #e0e0e0;
      border-radius: 2px; box-shadow: 0 2px 8px rgba(0,0,0,.15);
      padding: 3px 6px; gap: 4px; align-items: center;
      font-family: 'IBM Plex Sans', -apple-system, sans-serif;
      font-size: 11px; color: #525252;
    }
    #_mcp_insert_bar button {
      background: white; border: 1px solid #c6c6c6; cursor: pointer;
      color: #161616; padding: 3px 8px; border-radius: 2px;
      font-size: 11px; font-family: inherit;
      display: flex; align-items: center; gap: 4px;
      transition: background 80ms;
    }
    #_mcp_insert_bar button:hover { background: #e8e8e8; }
    /* Inserted table styles */
    ._mcp_table {
      width: 100%; border-collapse: collapse; margin: 12px 0;
    }
    ._mcp_table th {
      background: #161616; color: #f4f4f4; font-size: 12px;
      font-weight: 600; text-align: left;
      padding: 8px 12px; text-transform: uppercase; letter-spacing: .04em;
    }
    ._mcp_table td {
      font-size: 13px; padding: 8px 12px;
      border-bottom: 1px solid #e0e0e0; vertical-align: top;
    }
    ._mcp_table tr:last-child td { border-bottom: none; }
    ._mcp_table tr:hover td { background: #f4f4f4; }
    /* Document drag handle (reorder top-level blocks) */
    ._mcp_drag_handle {
      position: absolute; left: -26px; top: 2px;
      width: 20px; height: 22px;
      display: flex; align-items: center; justify-content: center;
      cursor: grab; color: #c6c6c6; font-size: 14px; line-height: 1;
      border-radius: 3px; user-select: none;
      opacity: 0.55; transition: opacity 80ms, color 80ms, background 80ms;
    }
    ._mcp_drag_host { position: relative; }
    ._mcp_drag_host:hover > ._mcp_drag_handle { opacity: 1; color: #525252; }
    ._mcp_drag_handle:hover { color: #0f62fe; background: #edf5ff; opacity: 1; }
    ._mcp_drag_handle:active { cursor: grabbing; }
    ._mcp_dragging { opacity: 0.45; }
    ._mcp_drop_indicator {
      height: 0; border: none; border-top: 2px solid #0f62fe;
      margin: -1px 0; padding: 0; list-style: none; pointer-events: none;
    }
    /* Arch-node drag (move boxes inside an arch-diagram) */
    ._mcp_arch_draggable { cursor: grab; }
    ._mcp_arch_grabbing  { cursor: grabbing !important; box-shadow: 0 0 0 3px rgba(15,98,254,0.35); }
  `;
  doc.head.appendChild(s);
}

/* ============================================================
   Floating format bar (selection-based)
   ============================================================ */
let _formatBar = null;

/**
 * Build a small crisp alignment icon: four horizontal bars (mimicking text
 * lines of varying width) laid out left/center/right/justified. Replaces the
 * previous emoji-square icons (⬛⬜⬜), which render as an illegible cluster
 * of tiny blocks at toolbar-button size on most platforms.
 *
 * @param {'left'|'center'|'right'|'full'} align
 */
function alignIconSvg(align) {
  const widths = [16, 11, 14, 9]; // uneven line lengths, like real text
  const rows = widths.map((w, i) => {
    const width = align === 'full' ? 16 : w;
    const x = align === 'center' ? (16 - width) / 2 : align === 'right' ? 16 - width : 0;
    const y = i * 3.6;
    return `<rect x="${x}" y="${y}" width="${width}" height="1.8" rx="0.5" fill="currentColor"/>`;
  }).join('');
  return `<svg viewBox="0 0 16 13.8" width="16" height="14" aria-hidden="true">${rows}</svg>`;
}

function createFormatBar(doc) {
  if (doc.getElementById('_mcp_format_bar')) return;
  const bar = doc.createElement('div');
  bar.id = '_mcp_format_bar';

  const buttons = [
    { cmd: 'bold',          icon: '<b>B</b>',    title: 'Gras (⌘B)'         },
    { cmd: 'italic',        icon: '<i>I</i>',    title: 'Italique (⌘I)'     },
    { cmd: 'underline',     icon: '<u>U</u>',    title: 'Souligné (⌘U)'     },
    { cmd: 'strikeThrough', icon: '<s>S</s>',    title: 'Barré'              },
    { sep: true },
    { cmd: 'superscript',   icon: 'x²',          title: 'Exposant'           },
    { cmd: 'subscript',     icon: 'x₂',          title: 'Indice'             },
    { sep: true },
    { cmd: 'justifyLeft',   icon: alignIconSvg('left'),   title: 'Aligner à gauche'  },
    { cmd: 'justifyCenter', icon: alignIconSvg('center'), title: 'Centrer'            },
    { cmd: 'justifyRight',  icon: alignIconSvg('right'),  title: 'Aligner à droite'  },
    { cmd: 'justifyFull',   icon: alignIconSvg('full'),   title: 'Justifié'          },
    { sep: true },
    { cmd: 'removeFormat',  icon: '✕',           title: 'Supprimer le style' },
  ];

  buttons.forEach(def => {
    if (def.sep) {
      const s = doc.createElement('span'); s.className = 'sep'; bar.appendChild(s); return;
    }
    const btn = doc.createElement('button');
    btn.innerHTML = def.icon;
    btn.title = def.title;
    btn.dataset.cmd = def.cmd;
    btn.addEventListener('mousedown', e => {
      e.preventDefault(); // keep selection
      doc.execCommand(def.cmd, false, null);
      updateFormatBarState(doc);
      scheduleSave();
    });
    bar.appendChild(btn);
  });

  // Font size selector
  const sep2 = doc.createElement('span'); sep2.className = 'sep'; bar.appendChild(sep2);
  const sizeSelect = doc.createElement('select');
  sizeSelect.title = 'Taille police';
  [10,11,12,13,14,16,18,20,24,28,32,36,40,48].forEach(sz => {
    const opt = doc.createElement('option'); opt.value = sz; opt.textContent = sz + 'px';
    sizeSelect.appendChild(opt);
  });
  sizeSelect.addEventListener('mousedown', e => e.stopPropagation());
  sizeSelect.addEventListener('change', e => {
    doc.execCommand('fontSize', false, '7'); // placeholder
    // Apply real size via span replacement
    doc.querySelectorAll('font[size="7"]').forEach(el => {
      el.removeAttribute('size');
      el.style.fontSize = e.target.value + 'px';
    });
    scheduleSave();
  });
  bar.appendChild(sizeSelect);

  // Text color
  const sep3 = doc.createElement('span'); sep3.className = 'sep'; bar.appendChild(sep3);
  const colorInput = doc.createElement('input');
  colorInput.type = 'color'; colorInput.value = '#000000'; colorInput.title = 'Couleur texte';
  colorInput.addEventListener('mousedown', e => e.stopPropagation());
  colorInput.addEventListener('input', e => {
    doc.execCommand('foreColor', false, e.target.value);
    scheduleSave();
  });
  bar.appendChild(colorInput);

  // Highlight color
  const hlInput = doc.createElement('input');
  hlInput.type = 'color'; hlInput.value = '#ffff00'; hlInput.title = 'Surlignage';
  hlInput.addEventListener('mousedown', e => e.stopPropagation());
  hlInput.addEventListener('input', e => {
    doc.execCommand('hiliteColor', false, e.target.value);
    scheduleSave();
  });
  bar.appendChild(hlInput);

  doc.body.appendChild(bar);
  _formatBar = bar;
}

function showFormatBar(doc) {
  const bar = doc.getElementById('_mcp_format_bar');
  if (!bar) return;
  const sel = doc.getSelection();
  if (!sel || sel.isCollapsed) { bar.style.display = 'none'; return; }

  const range = sel.getRangeAt(0);
  const rect  = range.getBoundingClientRect();
  if (!rect.width) { bar.style.display = 'none'; return; }

  bar.style.display = 'flex';

  // The bar lives inside the iframe's own document (doc.body.appendChild),
  // so its `position: fixed` is already relative to the IFRAME's viewport,
  // not the outer page. `rect` (from range.getBoundingClientRect()) is also
  // iframe-relative already: do not add the iframe's own offset within the
  // outer page (iframeRect.top/left) on top of it, or the bar renders that
  // far too low/right and overlaps the very text it should float above.
  const iframeWin = doc.defaultView || window;
  const barW = bar.offsetWidth || 340;
  const barH = bar.offsetHeight || 32;

  let top  = rect.top - barH - 8;
  let left = rect.left + rect.width / 2 - barW / 2;

  // Clamp within the iframe's own viewport
  if (top < 4) top = rect.bottom + 8;
  if (left < 4) left = 4;
  if (left + barW > iframeWin.innerWidth - 4) left = iframeWin.innerWidth - barW - 4;

  bar.style.top  = top + 'px';
  bar.style.left = left + 'px';

  updateFormatBarState(doc);
}

function hideFormatBar() {
  const bar = document.querySelector('#content-frame')?.contentDocument?.getElementById('_mcp_format_bar');
  if (bar) bar.style.display = 'none';
}

function updateFormatBarState(doc) {
  const bar = doc.getElementById('_mcp_format_bar');
  if (!bar) return;
  const cmds = ['bold','italic','underline','strikeThrough','superscript','subscript',
                 'justifyLeft','justifyCenter','justifyRight','justifyFull'];
  cmds.forEach(cmd => {
    const btn = bar.querySelector(`[data-cmd="${cmd}"]`);
    if (btn) btn.classList.toggle('active', doc.queryCommandState(cmd));
  });
}

// Hide format bar when clicking outside selection
document.addEventListener('mousedown', e => {
  const bar = frame.contentDocument?.getElementById('_mcp_format_bar');
  if (bar && bar.style.display !== 'none') {
    // Don't hide if clicking inside the bar (handled by mousedown on buttons)
    const iframeRect = frame.getBoundingClientRect();
    const barRect    = bar.getBoundingClientRect();
    // barRect is in iframe coords, convert to page coords
    const absTop  = iframeRect.top  + parseFloat(bar.style.top  || 0);
    // bar is fixed in iframe viewport which maps to page differently;
    // simpler: just let the selection event re-evaluate visibility
  }
});

/* ============================================================
   Insert bar (shown at top-right of focused editable)
   ============================================================ */
let _activeEditable = null;

function createInsertBar(doc) {
  if (doc.getElementById('_mcp_insert_bar')) return;
  const bar = doc.createElement('div');
  bar.id = '_mcp_insert_bar';
  bar.innerHTML = '<span>Insérer:</span>';

  const buttons = [
    { label: '🖼 Image',   action: () => insertImage(doc) },
    { label: '⊞ Tableau', action: () => insertTable(doc) },
    { label: '— Ligne HR', action: () => { doc.execCommand('insertHorizontalRule'); scheduleSave(); } },
    { label: '🔗 Lien',    action: () => insertLink(doc) },
  ];

  buttons.forEach(def => {
    const btn = doc.createElement('button');
    btn.innerHTML = def.label;
    btn.addEventListener('mousedown', e => { e.preventDefault(); def.action(); });
    bar.appendChild(btn);
  });

  doc.body.appendChild(bar);
}

function showInsertBar(doc, el) {
  const bar = doc.getElementById('_mcp_insert_bar');
  if (!bar) return;
  _activeEditable = el;

  bar.style.display = 'flex';

  // Same iframe-relative fixed-positioning context as showFormatBar: do not
  // add the iframe's own offset within the outer page on top of coordinates
  // that are already relative to the iframe's viewport.
  const elRect = el.getBoundingClientRect();  // in iframe coords

  const top  = elRect.top - (bar.offsetHeight || 32) - 6;
  const left = elRect.right - (bar.offsetWidth  || 280);

  bar.style.top  = Math.max(4, top)  + 'px';
  bar.style.left = Math.max(4, left) + 'px';
}

function hideInsertBar() {
  const bar = frame.contentDocument?.getElementById('_mcp_insert_bar');
  if (bar) bar.style.display = 'none';
}

/* ============================================================
   Insert helpers
   ============================================================ */
function insertImage(doc) {
  // Local file picker → embed as base64 (single-page portability)
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.addEventListener('change', () => {
    const file = input.files && input.files[0];
    if (!file) return;
    embedImageFile(doc, file);
  });
  input.click();
}

/** Read a File as a base64 data URI and insert it at the current selection. */
function embedImageFile(doc, file, targetEl) {
  const reader = new FileReader();
  reader.onload = () => {
    snapshotForUndo();
    const dataUri = reader.result;  // data:image/...;base64,...
    const img = `<img src="${dataUri}" alt="${file.name}" data-editable="resize,reposition" style="max-width:100%;height:auto;display:block;margin:8px 0;" />`;
    if (targetEl) {
      // Dropped onto a specific editable: append there. insertAdjacentHTML,
      // unlike execCommand('insertHTML', ...), does NOT push a step onto the
      // browser's native contenteditable undo stack — this is exactly the
      // structural gap snapshotForUndo() exists to cover for this call site.
      targetEl.insertAdjacentHTML('beforeend', img);
    } else {
      doc.execCommand('insertHTML', false, img);
    }
    scheduleSave();
  };
  reader.readAsDataURL(file);
}

/** Enable drag-and-drop of local image files onto editable text zones. */
function enableImageDrop(doc) {
  doc.querySelectorAll('[data-editable~="text"]').forEach(el => {
    el.addEventListener('dragover', e => {
      if (e.dataTransfer && [...e.dataTransfer.items].some(i => i.kind === 'file')) {
        e.preventDefault();
        el.style.boxShadow = 'inset 0 0 0 3px #0f62fe';
      }
    });
    el.addEventListener('dragleave', () => { el.style.boxShadow = ''; });
    el.addEventListener('drop', e => {
      el.style.boxShadow = '';
      if (!e.dataTransfer) return;
      const files = [...e.dataTransfer.files].filter(f => f.type.startsWith('image/'));
      if (!files.length) return;
      e.preventDefault();
      files.forEach(f => embedImageFile(doc, f, el));
    });
  });
}

function insertTable(doc) {
  const cols = parseInt(prompt('Nombre de colonnes :', '3') || '3', 10);
  const rows = parseInt(prompt('Nombre de lignes (hors en-tête) :', '3') || '3', 10);
  if (!cols || !rows) return;

  const headers = Array.from({length: cols}, (_, i) =>
    `<th>Colonne ${i + 1}</th>`
  ).join('');

  const bodyRows = Array.from({length: rows}, () => {
    const cells = Array.from({length: cols}, () => '<td>&nbsp;</td>').join('');
    return `<tr>${cells}</tr>`;
  }).join('');

  const html = `
    <table class="_mcp_table" data-type="table">
      <thead><tr>${headers}</tr></thead>
      <tbody>${bodyRows}</tbody>
    </table>
  `;
  doc.execCommand('insertHTML', false, html);
  scheduleSave();
}

function insertLink(doc) {
  const url = prompt('URL :', 'https://');
  if (!url) return;
  doc.execCommand('createLink', false, url);
  // Open in new tab
  const sel = doc.getSelection();
  if (sel && !sel.isCollapsed) {
    const anchor = sel.anchorNode?.parentElement?.closest('a');
    if (anchor) anchor.target = '_blank';
  }
  scheduleSave();
}
