/* ============================================================
   Save
   ============================================================ */
function onEditableInput()  { markPending(); clearTimeout(saveTimer); saveTimer = setTimeout(saveContent, 800); }
function onEditableBlur()   { clearTimeout(saveTimer); saveContent(); }
function scheduleSave()     { markPending(); clearTimeout(saveTimer); saveTimer = setTimeout(saveContent, 600); }

async function saveContent() {
  try {
    const doc = frame.contentDocument;
    if (!doc) return;

    // Strip editor artifacts on a detached clone, never on the live DOM:
    // removing contenteditable from the focused zone would move focus to
    // <body> and drop the keystrokes typed after the save (SPEC-0004).
    const clone = doc.documentElement.cloneNode(true);
    clone.querySelectorAll('[contenteditable]').forEach(el => {
      el.removeAttribute('contenteditable');
      el.style.outline = ''; el.style.cursor = '';
    });
    clone.querySelectorAll('#_mcp_format_bar, #_mcp_insert_bar').forEach(bar => { bar.style.display = 'none'; });
    clone.querySelectorAll('._mcp_drag_handle, ._mcp_drop_indicator').forEach(node => node.remove());
    clone.querySelectorAll('._mcp_drag_host').forEach(host => host.classList.remove('_mcp_drag_host'));

    const html = '<!DOCTYPE html>\n' + clone.outerHTML;

    selfSaving = true;
    await fetch('/content', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html }),
    });

    // Adopt the on-disk mtime produced by our own write, so the next poll
    // does not mistake it for an external change and reload the iframe.
    try {
      const st = await fetch('/status').then(r => r.json());
      lastMtime = st.mtime;
    } catch (e) { /* keep previous mtime; worst case one harmless reload */ }
    selfSaving = false;

    markSaved();
    saveTimer = null;

  } catch (e) {
    selfSaving = false;
    console.warn('Save failed:', e);
  }
}
