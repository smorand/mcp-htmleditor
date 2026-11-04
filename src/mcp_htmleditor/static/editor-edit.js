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
