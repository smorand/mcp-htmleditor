/* ============================================================
   Save
   ============================================================ */
function onEditableInput()  { markPending(); clearTimeout(saveTimer); saveTimer = setTimeout(saveContent, 800); }
function onEditableBlur()   { clearTimeout(saveTimer); saveContent(); }
function scheduleSave()     { markPending(); clearTimeout(saveTimer); saveTimer = setTimeout(saveContent, 600); }

/* Saves run one after the other, so a save never sends a base mtime that an earlier one is about to replace. */
function saveContent(options) {
  saveChain = saveChain.then(() => runSave(options));
  return saveChain;
}

async function runSave(options) {
  const force = !!(options && options.force === true);
  if (conflictActive && !force) return; // the conflict choice comes first, no autosave meanwhile
  try {
    const doc = frame.contentDocument;
    if (!doc) return;

    // Strip editor artifacts on a detached clone, never on the live DOM:
    // removing contenteditable from the focused zone would move focus to
    // <body> and drop the keystrokes typed after the save (SPEC-0004).
    // A width drag preview is taken out around the clone, so a save during a drag writes the width
    // the text had before it (SPEC-0015).
    const clone = withWidthPreviewSuspended(() => doc.documentElement.cloneNode(true));
    stripEditorArtifacts(clone); // a clone is thrown away: its restore is not needed
    stripPresentingState(clone);

    const payload = { html: '<!DOCTYPE html>\n' + clone.outerHTML };
    if (baseMtime !== null) payload.base_mtime = baseMtime;
    if (force) payload.force = true;

    selfSaving = true;
    const res = await fetch('/content', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    let answer = {};
    try { answer = await res.json(); } catch (e) { /* no JSON body: the status alone decides */ }

    if (res.status === 200) onSaveAccepted(answer);
    else if (res.status === 409) onSaveConflict(answer);
    else showSaveError(answer.error || res.statusText || ('HTTP ' + res.status));
  } catch (e) {
    showSaveError(e && e.message ? e.message : String(e));
  } finally {
    selfSaving = false;
    saveCount++;
  }
}

/** Take the editor's artifacts out of `root` (a document or a detached element), the one list shared by the
 *  save (on a clone) and the undo snapshot (on the live document, see editor-undo.js captureDomSnapshot):
 *  contenteditable with its outline and cursor, the format and insert bars hidden, the drag handles, drop
 *  indicator and drag hosts (see editor-drag.js detachDragArtifacts). Returns a function putting every
 *  artifact back as it was. */
function stripEditorArtifacts(root) {
  const editables = [...root.querySelectorAll('[contenteditable]')];
  const backup = editables.map(el => ({
    el, ce: el.contentEditable,
    outline: el.style.outline, cursor: el.style.cursor,
  }));
  editables.forEach(el => {
    el.removeAttribute('contenteditable');
    el.style.outline = ''; el.style.cursor = '';
  });

  // querySelectorAll, not getElementById: a detached clone has no getElementById.
  const bars = [...root.querySelectorAll('#_mcp_format_bar, #_mcp_insert_bar')].map(bar => ({ bar, display: bar.style.display }));
  bars.forEach(({ bar }) => { bar.style.display = 'none'; });

  const detachedDrag = detachDragArtifacts(root);

  return function restore() {
    backup.forEach(({ el, ce, outline, cursor }) => {
      el.contentEditable = ce; el.style.outline = outline; el.style.cursor = cursor;
    });
    bars.forEach(({ bar, display }) => { bar.style.display = display; });
    reattachDragArtifacts(detachedDrag);
  };
}

/** A save while presenting (or after) writes none of the deck's runtime state (SPEC-0016 R2):
 *  `data-fs-current` goes, and `--fs-scale` leaves <html>'s style as text, so every other declaration
 *  keeps its bytes (SPEC-0015 DEC-003); a style left empty is removed. The pointer's layer (dot and ring) and
 *  its state on <html> go too (SPEC-0017 DEC-014); the deck's own pointer code and CSS stay. */
function stripPresentingState(root) {
  root.querySelectorAll('[data-fs-current]').forEach(el => el.removeAttribute('data-fs-current'));
  root.querySelectorAll('#deck-pointer-layer').forEach(node => node.remove());
  root.removeAttribute('data-deck-pointer');
  const style = root.getAttribute('style');
  if (style === null) return;
  const kept = style.split(';').filter(part => !/^\s*--fs-scale\s*:/.test(part)).join(';');
  if (kept.trim() === '' || kept.trim() === ';') root.removeAttribute('style');
  else if (kept !== style) root.setAttribute('style', kept);
}

/** 200: the answer's mtime is both the next base and the poll's reference, so our own write never reloads. */
function onSaveAccepted(answer) {
  if (typeof answer.mtime === 'number') { baseMtime = answer.mtime; lastMtime = answer.mtime; }
  conflictActive = false;
  pollFailures = 0;
  hideNotice('save-conflict');
  hideNotice('save-error');
  hideNotice('connection-lost');
  markSaved();
  saveTimer = null;
}

/** 409: the file changed on disk; keep the unsaved state and let the user choose. */
function onSaveConflict(answer) {
  conflictActive = true;
  conflictMtime = typeof answer.mtime === 'number' ? answer.mtime : null;
  hideNotice('save-error');
  showNotice('save-conflict');
}

/* ============================================================
   Notices (#notices): no focusable element except the two conflict buttons, never focused by script
   ============================================================ */
function showNotice(id, text) {
  const el = document.getElementById(id);
  if (!el) return;
  if (text !== undefined) el.querySelector('.notice-text').textContent = text;
  el.hidden = false;
}

function hideNotice(id) {
  const el = document.getElementById(id);
  if (el) el.hidden = true;
}

function showSaveError(text) {
  console.warn('Save failed:', text);
  showNotice('save-error', 'Save failed: ' + text);
}

/** Reload: show the file as it is on disk, drop the unsaved edits, forget the conflict. */
function reloadFromDisk() {
  clearTimeout(saveTimer);
  if (conflictMtime !== null) { baseMtime = conflictMtime; lastMtime = conflictMtime; }
  conflictActive = false;
  hideNotice('save-conflict');
  hideNotice('save-error');
  markSaved();
  reloadFrame();
}

function initNotices() {
  const reload = document.getElementById('save-conflict-reload');
  const keep = document.getElementById('save-conflict-keep');
  if (reload) reload.addEventListener('click', reloadFromDisk);
  if (keep) keep.addEventListener('click', () => saveContent({ force: true }));
}

/** One status poll: count failures, show the notice at three in a row, clear it at the next success. */
function notePollFailure() {
  pollFailures++;
  if (pollFailures >= POLL_FAILURE_LIMIT) showNotice('connection-lost');
}

function notePollSuccess() {
  pollFailures = 0;
  hideNotice('connection-lost');
}
