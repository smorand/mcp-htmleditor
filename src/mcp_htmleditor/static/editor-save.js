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
    clone.querySelectorAll('[contenteditable]').forEach(el => {
      el.removeAttribute('contenteditable');
      el.style.outline = ''; el.style.cursor = '';
    });
    clone.querySelectorAll('#_mcp_format_bar, #_mcp_insert_bar').forEach(bar => { bar.style.display = 'none'; });
    clone.querySelectorAll('._mcp_drag_handle, ._mcp_drop_indicator').forEach(node => node.remove());
    clone.querySelectorAll('._mcp_drag_host').forEach(host => host.classList.remove('_mcp_drag_host'));
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

/** A save while presenting (or after) writes none of the deck's runtime state (SPEC-0016 R2):
 *  `data-fs-current` goes, and `--fs-scale` leaves <html>'s style as text, so every other declaration
 *  keeps its bytes (SPEC-0015 DEC-003); a style left empty is removed. */
function stripPresentingState(root) {
  root.querySelectorAll('[data-fs-current]').forEach(el => el.removeAttribute('data-fs-current'));
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
