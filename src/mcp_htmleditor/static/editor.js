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
let insertPosition = null;    // 'before' | 'after' when slide picker is open
let blockPosition  = null;    // 'before' | 'after' when block picker is open
let lastDocRange   = null;    // saved caret range in document mode

const frame        = document.getElementById('content-frame');
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
  });

  // Present button: fullscreen the iframe (only visible for presentations)
  presentBtn.addEventListener('click', () => {
    frame.requestFullscreen
      ? frame.requestFullscreen()
      : frame.webkitRequestFullscreen && frame.webkitRequestFullscreen();
  });
  frame.addEventListener('fullscreenchange', () => {
    presentBtn.title = document.fullscreenElement
      ? 'Quitter la présentation (ESC)'
      : 'Mode présentation plein écran';
  });

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
    updateSlideActionsVisibility();
    updateDocActionsVisibility();
    if (editMode) injectEditMode(doc);
    injectContextMenus(doc);
  } catch (e) {
    console.warn('Could not access iframe content:', e);
  }
}

/* ============================================================
   Slide actions visibility (presentation + edit mode only)
   ============================================================ */
function updateSlideActionsVisibility() {
  slideActions.style.display = (isPresentation && editMode) ? 'inline-flex' : 'none';
  presentBtn.style.display   = isPresentation ? 'inline-flex' : 'none';
}

/* ============================================================
   Document block actions visibility (document + edit mode only)
   ============================================================ */
function updateDocActionsVisibility() {
  if (docActions) {
    docActions.style.display = (isDocument && editMode) ? 'inline-flex' : 'none';
  }
}

/* ============================================================
   Polling
   ============================================================ */
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
   Edit mode toggle
   ============================================================ */
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
  if (isDocument)     injectDocDragHandles(doc);
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
    { cmd: 'justifyLeft',   icon: '⬛⬜⬜',      title: 'Aligner gauche'    },
    { cmd: 'justifyCenter', icon: '⬜⬛⬜',      title: 'Centrer'            },
    { cmd: 'justifyRight',  icon: '⬜⬜⬛',      title: 'Aligner droite'    },
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

  // Position above the selection, within iframe viewport
  const iframeRect = frame.getBoundingClientRect();
  const barW = bar.offsetWidth || 340;
  const barH = bar.offsetHeight || 32;

  let top  = iframeRect.top + rect.top - barH - 8;
  let left = iframeRect.left + rect.left + rect.width / 2 - barW / 2;

  // Clamp within viewport
  if (top < 4) top = iframeRect.top + rect.bottom + 8;
  if (left < 4) left = 4;
  if (left + barW > window.innerWidth - 4) left = window.innerWidth - barW - 4;

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
                 'justifyLeft','justifyCenter','justifyRight'];
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

  const iframeRect = frame.getBoundingClientRect();
  const elRect     = el.getBoundingClientRect();  // in iframe coords

  const top  = iframeRect.top  + elRect.top - (bar.offsetHeight || 32) - 6;
  const left = iframeRect.left + elRect.right - (bar.offsetWidth  || 280);

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
    const dataUri = reader.result;  // data:image/...;base64,...
    const img = `<img src="${dataUri}" alt="${file.name}" data-editable="resize,reposition" style="max-width:100%;height:auto;display:block;margin:8px 0;" />`;
    if (targetEl) {
      // Dropped onto a specific editable: append there
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

/* ============================================================
   Context menus (injected into iframe)
   ============================================================ */
function injectContextMenus(doc) {
  doc.addEventListener('contextmenu', e => {
    let el = e.target;
    let dtype = null;
    while (el && el !== doc.body) {
      if (el.dataset && el.dataset.type) { dtype = el.dataset.type; break; }
      el = el.parentElement;
    }
    if (!dtype) return;

    const items = getContextMenuItems(dtype, el, doc);
    if (!items.length) return;

    e.preventDefault();
    showContextMenu(doc, e.clientX, e.clientY, items);
  });
}

function getContextMenuItems(dtype, el, doc) {
  switch (dtype) {
    case 'gantt-task':
      return [
        { label: 'Agrandir (+20%)', action: () => {
          el.style.width = Math.min(100, (parseFloat(el.style.width) || 30) * 1.2).toFixed(1) + '%';
          scheduleSave();
        }},
        { label: 'Réduire (-20%)',  action: () => {
          el.style.width = Math.max(5,   (parseFloat(el.style.width) || 30) * 0.8).toFixed(1) + '%';
          scheduleSave();
        }},
        { label: 'Renommer', action: () => {
          const name = prompt('Libellé :', el.textContent.trim());
          if (name !== null) { el.textContent = name; el.dataset.label = name; scheduleSave(); }
        }},
        { label: 'Supprimer', action: () => { el.remove(); scheduleSave(); }},
      ];

    case 'arch-node':
      return [
        { label: 'Renommer', action: () => {
          const name = prompt('Libellé :', el.textContent.trim());
          if (name !== null) { el.textContent = name; el.dataset.label = name; scheduleSave(); }
        }},
        { label: 'Changer forme', action: () => {
          const shape = prompt('Forme (box/circle/diamond) :', el.dataset.shape || 'box');
          if (shape) { el.dataset.shape = shape; scheduleSave(); }
        }},
        { label: 'Supprimer', action: () => { el.remove(); scheduleSave(); }},
      ];

    case 'annotation':
      return [
        { label: 'Éditer texte', action: () => {
          const text = prompt('Texte :', el.textContent.trim());
          if (text !== null) { el.textContent = text; scheduleSave(); }
        }},
        { label: 'Supprimer', action: () => { el.remove(); scheduleSave(); }},
      ];

    case 'table':
      return tableContextMenu(el, doc);

    case 'gantt':
      return [{ label: '＋ Ajouter tâche', action: () => {
        const label = prompt('Libellé :', 'Nouvelle tâche');
        if (!label) return;
        const task = doc.createElement('div');
        task.dataset.type = 'gantt-task'; task.dataset.label = label;
        task.style.cssText = 'background:#4a90d9;color:white;padding:4px 8px;margin:2px 0;border-radius:3px;width:30%;';
        task.textContent = label;
        el.appendChild(task); scheduleSave();
      }}];

    case 'arch-diagram':
      return [{ label: '＋ Ajouter nœud', action: () => {
        const label = prompt('Libellé :', 'Nouveau nœud');
        if (!label) return;
        const node = doc.createElement('div');
        node.dataset.type = 'arch-node'; node.dataset.label = label; node.dataset.shape = 'box';
        node.dataset.x = '40.0'; node.dataset.y = '40.0';
        node.style.cssText = 'position:absolute; left:40.0%; top:40.0%; display:inline-block;'
          + 'border:2px solid #333; padding:8px 16px; border-radius:4px; background:#f5f5f5;';
        node.textContent = label;
        // Container must be a positioning context for percentage coords.
        if (getComputedStyle(el).position === 'static') el.style.position = 'relative';
        el.appendChild(node);
        if (editMode) makeArchNodeDraggable(doc, node);
        scheduleSave();
      }}];

    default:
      return [];
  }
}

/* table context menu — also used by right-click on _mcp_table */
function tableContextMenu(tableEl, doc) {
  // Find the table root from any child
  const tbl = tableEl.closest ? tableEl.closest('table') || tableEl : tableEl;
  return [
    { label: '＋ Ajouter ligne',             action: () => { addTableRow(tbl, doc); scheduleSave(); }},
    { label: '− Supprimer dernière ligne',   action: () => { removeLastTableRow(tbl); scheduleSave(); }},
    { label: '＋ Ajouter colonne',           action: () => { addTableCol(tbl, doc); scheduleSave(); }},
    { label: '− Supprimer dernière colonne', action: () => { removeLastTableCol(tbl); scheduleSave(); }},
    { label: '✕ Supprimer le tableau',       action: () => { tbl.remove(); scheduleSave(); }},
  ];
}

function showContextMenu(doc, x, y, items) {
  doc.getElementById('_editor_ctx')?.remove();
  document.getElementById('_editor_ctx_host')?.remove();

  const menu = document.createElement('div');
  menu.id = '_editor_ctx_host';
  const ifrRect = frame.getBoundingClientRect();
  const absX = ifrRect.left + x;
  const absY = ifrRect.top  + y;

  menu.style.cssText = [
    'position:fixed',
    `top:${absY}px`, `left:${absX}px`,
    'background:white', 'border:1px solid #c6c6c6',
    'box-shadow:0 4px 12px rgba(0,0,0,.2)',
    'z-index:99999', 'min-width:200px',
    'font-family:IBM Plex Sans,-apple-system,sans-serif',
    'font-size:13px', 'border-radius:2px',
  ].join(';');

  items.forEach(item => {
    const btn = document.createElement('div');
    btn.textContent = item.label;
    btn.style.cssText = 'padding:8px 16px;cursor:pointer;';
    btn.onmouseenter = () => (btn.style.background = '#e8e8e8');
    btn.onmouseleave = () => (btn.style.background = '');
    btn.onclick = () => { item.action(); menu.remove(); };
    menu.appendChild(btn);
  });

  document.body.appendChild(menu);
  const dismiss = e => {
    if (!menu.contains(e.target)) { menu.remove(); document.removeEventListener('mousedown', dismiss); }
  };
  setTimeout(() => document.addEventListener('mousedown', dismiss), 10);
}

/* ============================================================
   Table DOM helpers
   ============================================================ */
function addTableRow(tbl, doc) {
  const tbody = tbl.querySelector('tbody') || tbl;
  const rows  = tbody.querySelectorAll('tr');
  const cols  = rows.length ? rows[rows.length - 1].querySelectorAll('td,th').length : 3;
  const tr    = doc.createElement('tr');
  for (let i = 0; i < cols; i++) {
    const td = doc.createElement('td'); td.innerHTML = '&nbsp;'; tr.appendChild(td);
  }
  tbody.appendChild(tr);
}

function removeLastTableRow(tbl) {
  const tbody = tbl.querySelector('tbody') || tbl;
  const rows  = tbody.querySelectorAll('tr');
  if (rows.length > 1) rows[rows.length - 1].remove();
}

function addTableCol(tbl, doc) {
  tbl.querySelectorAll('tr').forEach(row => {
    const last = row.querySelector('th') ? 'th' : 'td';
    const cell = doc.createElement(last); cell.innerHTML = '&nbsp;';
    row.appendChild(cell);
  });
}

function removeLastTableCol(tbl) {
  tbl.querySelectorAll('tr').forEach(row => {
    const cells = row.querySelectorAll('td,th');
    if (cells.length > 1) cells[cells.length - 1].remove();
  });
}

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

    // Temporarily strip editor artifacts before serialising
    const editables = [...doc.querySelectorAll('[contenteditable]')];
    const backup = editables.map(el => ({
      el, ce: el.contentEditable,
      outline: el.style.outline, cursor: el.style.cursor,
    }));
    editables.forEach(el => {
      el.removeAttribute('contenteditable');
      el.style.outline = ''; el.style.cursor = '';
    });

    // Hide bars while serializing
    const fb = doc.getElementById('_mcp_format_bar');
    const ib = doc.getElementById('_mcp_insert_bar');
    const fbDisplay = fb?.style.display; const ibDisplay = ib?.style.display;
    if (fb) fb.style.display = 'none';
    if (ib) ib.style.display = 'none';

    // Detach drag artifacts (handles + drop indicator) so they never reach disk.
    // They are re-injected right after serialization, keeping the live DOM intact.
    const detachedDrag = detachDragArtifacts(doc);

    const html = '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;

    // Restore
    backup.forEach(({ el, ce, outline, cursor }) => {
      el.contentEditable = ce; el.style.outline = outline; el.style.cursor = cursor;
    });
    if (fb) fb.style.display = fbDisplay;
    if (ib) ib.style.display = ibDisplay;
    reattachDragArtifacts(detachedDrag);

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

/* ============================================================
   Slide management (presentation mode)
   ============================================================
   Insère/supprime des slides typées et maintient la cohérence:
   - ids séquentiels slide-0..slide-N
   - const TOTAL et slideNames[] dans le <script> de navigation
   - eyebrow "Slide 0N / TT"
   - pied de page Carbon .slide-footer-right ("Slide N / TT")
   - pied de page EI .slide-foot-page ("N")
   - <option> du dropdown (régénérées par le JS du template)
   ============================================================ */

/** Get the array of slide <article> elements in the iframe, in order. */
function getSlides(doc) {
  return [...doc.querySelectorAll('article[data-type="slide"]')];
}

/** Determine the currently displayed slide index (the .active one). */
function getCurrentSlideIndex(doc) {
  const slides = getSlides(doc);
  const idx = slides.findIndex(s => s.classList.contains('active'));
  return idx >= 0 ? idx : 0;
}

/* ── Picker modal ─────────────────────────────────────────────── */
function openSlidePicker(position) {
  insertPosition = position;
  const grid = document.getElementById('picker-grid');
  grid.innerHTML = '';
  const layouts = getLayouts(frame.contentDocument);
  Object.entries(layouts).forEach(([key, layout]) => {
    const card = document.createElement('button');
    card.className = 'picker-card';
    card.innerHTML =
      `<span class="picker-card-icon">${layout.icon}</span>` +
      `<span class="picker-card-label">${layout.label}</span>` +
      `<span class="picker-card-desc">${layout.description}</span>`;
    card.addEventListener('click', () => { insertSlide(key, insertPosition); closeSlidePicker(); });
    grid.appendChild(card);
  });
  document.getElementById('slide-picker').style.display = 'flex';
}

function closeSlidePicker() {
  document.getElementById('slide-picker').style.display = 'none';
  insertPosition = null;
}

/* ── Insert ───────────────────────────────────────────────────── */
function insertSlide(layoutKey, position) {
  const doc = frame.contentDocument;
  if (!doc) return;
  const layout = getLayouts(doc)[layoutKey];
  if (!layout) return;

  const slides = getSlides(doc);
  const curIdx = getCurrentSlideIndex(doc);
  const uid = 'slide-' + Date.now();

  // Build slide HTML, resolve template assets (EI cover/logos), then insert
  let html = layout.html.replace(/\{\{ID\}\}/g, uid).trim();
  html = resolveTemplateAssets(html, doc);
  const tmp = doc.createElement('div');
  tmp.innerHTML = html;
  const newSlide = tmp.firstElementChild;
  newSlide.classList.remove('active');

  // Insert relative to current slide
  const ref = slides[curIdx];
  if (position === 'before') {
    ref.parentNode.insertBefore(newSlide, ref);
  } else {
    ref.parentNode.insertBefore(newSlide, ref.nextSibling);
  }

  renumberSlides(doc);
  makeEditableIfNeeded(doc, newSlide);
  saveContent();
}

/** Replace EI template asset placeholders with data URIs already embedded
 *  in the document, so inserted slides reuse the same cover/logos.
 *
 *  Two sources, in order: an existing element of the document (a slide already
 *  carrying the asset), then the `data-asset-*` fallback on <html>. The fallback
 *  is what makes a freshly created file work: a bootstrap with a single title
 *  slide has no `.slide-foot-logo img` to copy the chevrons from. */
function resolveTemplateAssets(html, doc) {
  const grab = sel => { const el = doc.querySelector(sel); return el ? el.getAttribute('src') : ''; };
  const fallback = name => doc.documentElement.getAttribute('data-asset-' + name) || '';
  const asset = (sel, name) => grab(sel) || fallback(name);
  const map = {
    '{{COVER}}':    asset('.slide-cover-img', 'cover'),
    '{{CM}}':       asset('img.logo-cm', 'cm'),
    '{{CIC}}':      asset('img.logo-cic', 'cic'),
    '{{EI}}':       asset('img.logo-ei', 'ei'),
    '{{CHEVRONS}}': asset('.slide-foot-logo img', 'chevrons'),
  };
  Object.entries(map).forEach(([ph, uri]) => { html = html.split(ph).join(uri || ''); });
  return html;
}

/* ── Delete ───────────────────────────────────────────────────── */
function deleteCurrentSlide() {
  const doc = frame.contentDocument;
  if (!doc) return;
  const slides = getSlides(doc);
  if (slides.length <= 1) {
    alert('Impossible de supprimer la dernière slide.');
    return;
  }
  const curIdx = getCurrentSlideIndex(doc);
  if (!confirm(`Supprimer la slide ${curIdx + 1} ?`)) return;
  slides[curIdx].remove();
  renumberSlides(doc);
  saveContent();
}

/* ── Renumbering: keeps the whole document coherent ───────────── */
function renumberSlides(doc) {
  const slides = getSlides(doc);
  const total = slides.length;

  slides.forEach((slide, i) => {
    const id = 'slide-' + i;
    slide.id = id;
    slide.setAttribute('data-id', id);

    // eyebrow "… Slide 0N / TT" (les formes "{{N}} / {{TT}}" issues d'un layout
    // fraîchement inséré sont résolues par la même passe)
    const eyebrow = slide.querySelector('.slide-eyebrow');
    if (eyebrow) {
      eyebrow.textContent = eyebrow.textContent.replace(
        /Slide\s*(?:\d+|\{\{N\}\})\s*\/\s*(?:\d+|\{\{TT\}\})/i,
        `Slide ${String(i + 1).padStart(2, '0')} / ${String(total).padStart(2, '0')}`
      );
      // If no "Slide N / TT" pattern existed, leave text untouched.
    }

    // Carbon footer: "Slide N / TT"
    const footer = slide.querySelector('.slide-footer-right');
    if (footer) footer.textContent = `Slide ${i + 1} / ${total}`;

    // EI footer: page number alone ("N"), on the slides that carry a foot
    const footPage = slide.querySelector('.slide-foot-page');
    if (footPage) footPage.textContent = String(i + 1);

    // active state: keep first active
    slide.classList.toggle('active', i === 0);
  });

  // Update the navigation <script>: TOTAL + slideNames[]
  updateNavScript(doc, slides);

  // Rebuild dropdown options via the template's own buildOptions() if present
  const win = frame.contentWindow;
  try {
    if (win && typeof win.buildOptions === 'function') win.buildOptions();
    if (win && typeof win.goToSlide === 'function') win.goToSlide(0);
  } catch (e) { /* template may not expose these; ignore */ }
}

/** Rewrite `const TOTAL = …` and `const slideNames = [ … ]` in the nav script. */
function updateNavScript(doc, slides) {
  const scripts = [...doc.querySelectorAll('script')];
  const navScript = scripts.find(s => /const\s+TOTAL\s*=/.test(s.textContent));
  if (!navScript) return;

  const names = slides.map(s => (s.getAttribute('data-title') || 'Slide').replace(/"/g, '\\"'));
  let src = navScript.textContent;

  src = src.replace(/const\s+TOTAL\s*=\s*\d+\s*;/,
                    `const TOTAL = ${slides.length};`);
  src = src.replace(/const\s+slideNames\s*=\s*\[[\s\S]*?\];/,
                    'const slideNames = [\n    ' + names.map(n => `"${n}"`).join(',\n    ') + ',\n  ];');

  navScript.textContent = src;
}

/** If edit mode is active, wire up the new slide's editable zones. */
function makeEditableIfNeeded(doc, slide) {
  if (!editMode) return;
  slide.querySelectorAll('[data-editable~="text"]').forEach(el => {
    el.contentEditable = 'true';
    el.classList.add('_mcp_editable');
    el.addEventListener('input',   onEditableInput);
    el.addEventListener('blur',    onEditableBlur);
    el.addEventListener('mouseup', () => showFormatBar(doc));
    el.addEventListener('keyup',   () => showFormatBar(doc));
    el.addEventListener('focus',   () => showInsertBar(doc, el));
  });
  enableImageDrop(doc);
  // Wire drag on any arch-node inside the freshly inserted slide.
  slide.querySelectorAll('[data-type="arch-node"]').forEach(node => makeArchNodeDraggable(doc, node));
}

/* ============================================================
   Document block management (document mode)
   ============================================================
   Insere des blocs (titre, sous-titre, h1-h5, paragraphe, tableau, liste)
   a la position du curseur, ou a la fin de l'article document si aucune
   selection. Reutilise le picker modal (meme CSS que le picker de slides).
   ============================================================ */

/** Get the document <article> element in the iframe. */
function getDocumentArticle(doc) {
  return doc.querySelector('article[data-type="document"]');
}

/** Remember the last caret position inside an editable (document mode). */
function saveDocRange(doc) {
  if (!isDocument) return;
  const sel = doc.getSelection();
  if (sel && sel.rangeCount) lastDocRange = sel.getRangeAt(0).cloneRange();
}

/* -- Block picker modal ---------------------------------------- */
function openBlockPicker(position) {
  blockPosition = (position === 'before') ? 'before' : 'after';
  const grid = document.getElementById('block-picker-grid');
  grid.innerHTML = '';
  if (typeof DOC_BLOCKS === 'undefined') return;
  Object.entries(DOC_BLOCKS).forEach(([key, block]) => {
    const card = document.createElement('button');
    card.className = 'picker-card';
    card.innerHTML =
      `<span class="picker-card-icon">${block.icon}</span>` +
      `<span class="picker-card-label">${block.label}</span>` +
      `<span class="picker-card-desc">${block.description}</span>`;
    card.addEventListener('click', () => { insertDocBlock(key, blockPosition); closeBlockPicker(); });
    grid.appendChild(card);
  });
  document.getElementById('block-picker').style.display = 'flex';
}

function closeBlockPicker() {
  document.getElementById('block-picker').style.display = 'none';
  blockPosition = null;
}

/* -- Insert a block -------------------------------------------- */
function insertDocBlock(blockKey, position) {
  const doc = frame.contentDocument;
  if (!doc) return;
  if (typeof DOC_BLOCKS === 'undefined') return;
  const block = DOC_BLOCKS[blockKey];
  if (!block) return;

  const article = getDocumentArticle(doc);
  if (!article) return;

  const before = (position === 'before');
  const container = article.querySelector('.ei-doc-body') || article;

  // Build the block node from its HTML fragment.
  const tmp = doc.createElement('div');
  tmp.innerHTML = block.html.trim();
  const nodes = [...tmp.childNodes].filter(
    n => n.nodeType !== 3 || (n.textContent && n.textContent.trim())
  );

  // Find a top-level insertion reference from the saved caret range.
  const ref = docBlockInsertionRef(doc, article);

  nodes.forEach(node => {
    if (ref && ref.parentNode) {
      // Insert before or after the current top-level block.
      ref.parentNode.insertBefore(node, before ? ref : ref.nextSibling);
    } else if (before) {
      container.insertBefore(node, container.firstChild);
    } else {
      container.appendChild(node);
    }
    // Make freshly inserted block editable if edit mode is on.
    if (node.nodeType === 1) makeDocBlockEditable(doc, node);
  });

  lastDocRange = null;
  if (isDocument && editMode) injectDocDragHandles(doc);
  saveContent();
}

/** Return the direct child of the document body area after which to insert,
 *  based on the saved caret, or null to append at the end. */
function docBlockInsertionRef(doc, article) {
  if (!lastDocRange) return null;
  let node = lastDocRange.startContainer;
  if (node.nodeType === 3) node = node.parentNode;
  // Climb until the node is a direct child of the article (or its body wrapper).
  const container = article.querySelector('.ei-doc-body') || article;
  while (node && node.parentNode && node.parentNode !== container) {
    node = node.parentNode;
  }
  return (node && node.parentNode === container) ? node : null;
}

/** Wire a newly inserted block's editable zones (document mode). */
function makeDocBlockEditable(doc, blockEl) {
  if (!editMode) return;
  const targets = [];
  if (blockEl.matches && blockEl.matches('[data-editable~="text"]')) targets.push(blockEl);
  if (blockEl.querySelectorAll) {
    blockEl.querySelectorAll('[data-editable~="text"]').forEach(el => targets.push(el));
  }
  targets.forEach(el => {
    el.contentEditable = 'true';
    el.classList.add('_mcp_editable');
    el.addEventListener('input',   onEditableInput);
    el.addEventListener('blur',    onEditableBlur);
    el.addEventListener('mouseup', () => { showFormatBar(doc); saveDocRange(doc); });
    el.addEventListener('keyup',   () => { showFormatBar(doc); saveDocRange(doc); });
    el.addEventListener('focus',   () => showInsertBar(doc, el));
  });
  enableImageDrop(doc);
}

/* ============================================================
   Document block reorder (drag handles)
   ============================================================
   En mode document + edition, chaque bloc de premier niveau de l'article
   (ou de son wrapper .ei-doc-body) recoit une poignee de drag a sa gauche.
   On tire la poignee pour reordonner verticalement les blocs. Apres le drop,
   l'ordre des blocs dans le DOM = l'ordre visuel; RIEN d'autre ne change.
   La poignee (classe/id _mcp_drag_handle) est un artefact d'edition: elle
   n'est jamais serialisee (voir detachDragArtifacts + strip cote serveur).
   ============================================================ */

/** Container holding the top-level document blocks. */
function getDocBlockContainer(doc) {
  const article = getDocumentArticle(doc);
  if (!article) return null;
  return article.querySelector('.ei-doc-body') || article;
}

/** True for elements that must not receive a drag handle (editor artifacts). */
function isDocArtifact(el) {
  if (!el || el.nodeType !== 1) return true;
  if (el.id && el.id.startsWith('_mcp')) return true;
  if (el.classList && (el.classList.contains('_mcp_drag_handle') ||
                       el.classList.contains('_mcp_drop_indicator'))) return true;
  return el.tagName === 'SCRIPT' || el.tagName === 'STYLE';
}

/** Add a drag handle to every top-level block in document mode. */
function injectDocDragHandles(doc) {
  const container = getDocBlockContainer(doc);
  if (!container) return;
  [...container.children].forEach(block => {
    if (isDocArtifact(block)) return;
    if (block.querySelector(':scope > ._mcp_drag_handle')) return;
    block.classList.add('_mcp_drag_host');
    const handle = doc.createElement('span');
    handle.className = '_mcp_drag_handle';
    handle.setAttribute('draggable', 'true');
    handle.setAttribute('contenteditable', 'false');
    handle.title = 'Glisser pour reordonner ce bloc';
    handle.textContent = '\u2839'; // braille dots, reads as a grip
    wireDragHandle(doc, handle, block, container);
    block.appendChild(handle);
  });
}

/** Remove every drag handle + host marker (leave the blocks intact). */
function removeDocDragHandles(doc) {
  doc.querySelectorAll('._mcp_drag_handle').forEach(h => h.remove());
  doc.querySelectorAll('._mcp_drag_host').forEach(b => b.classList.remove('_mcp_drag_host'));
  doc.querySelectorAll('._mcp_drop_indicator').forEach(i => i.remove());
}

let _dragBlock = null;

/** Wire native HTML5 drag on one handle to reorder its parent block. */
function wireDragHandle(doc, handle, block, container) {
  handle.addEventListener('dragstart', e => {
    _dragBlock = block;
    block.classList.add('_mcp_dragging');
    if (e.dataTransfer) { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', ''); }
  });
  handle.addEventListener('dragend', () => {
    block.classList.remove('_mcp_dragging');
    removeDropIndicator(doc);
    _dragBlock = null;
  });

  // The container listens for dragover/drop once; wire it lazily here.
  if (!container._mcpDropWired) {
    container._mcpDropWired = true;
    container.addEventListener('dragover', e => {
      if (!_dragBlock) return;
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
      const after = blockAfterPointer(doc, container, e.clientY);
      showDropIndicator(doc, container, after);
    });
    container.addEventListener('drop', e => {
      if (!_dragBlock) return;
      e.preventDefault();
      const after = blockAfterPointer(doc, container, e.clientY);
      removeDropIndicator(doc);
      if (after === _dragBlock) return;
      if (after == null) container.appendChild(_dragBlock);
      else               container.insertBefore(_dragBlock, after);
      scheduleSave();
    });
  }
}

/** Return the block that should sit AFTER the drop point (or null for end). */
function blockAfterPointer(doc, container, clientY) {
  const blocks = [...container.children].filter(
    b => !isDocArtifact(b) && b !== _dragBlock
  );
  for (const b of blocks) {
    const rect = b.getBoundingClientRect();
    if (clientY < rect.top + rect.height / 2) return b;
  }
  return null;
}

/** Draw the blue drop line before `ref` (or at the end when ref is null). */
function showDropIndicator(doc, container, ref) {
  let ind = doc.getElementById('_mcp_drop_indicator');
  if (!ind) {
    ind = doc.createElement('div');
    ind.id = '_mcp_drop_indicator';
    ind.className = '_mcp_drop_indicator';
  }
  if (ref) container.insertBefore(ind, ref);
  else     container.appendChild(ind);
}

function removeDropIndicator(doc) {
  doc.getElementById('_mcp_drop_indicator')?.remove();
}

/* ============================================================
   Drag artifact detach/reattach (keep the saved file clean)
   ============================================================
   Before serializing, we physically detach the drag handles and the drop
   indicator so `doc.documentElement.outerHTML` never contains them, then we
   re-attach them so the live editing DOM keeps working. The server also strips
   _mcp_drag_handle as a safety net (belt and suspenders).
   ============================================================ */
function detachDragArtifacts(doc) {
  const parents = [];
  doc.querySelectorAll('._mcp_drag_handle, ._mcp_drop_indicator').forEach(node => {
    parents.push({ node, parent: node.parentNode });
    node.remove();
  });
  const hosts = [...doc.querySelectorAll('._mcp_drag_host')];
  hosts.forEach(h => h.classList.remove('_mcp_drag_host'));
  return { parents, hosts };
}

function reattachDragArtifacts(state) {
  if (!state) return;
  state.parents.forEach(({ node, parent }) => { if (parent) parent.appendChild(node); });
  state.hosts.forEach(h => h.classList.add('_mcp_drag_host'));
}

/* ============================================================
   Arch-node drag (move boxes inside an arch-diagram)
   ============================================================
   En mode edition, les noeuds [data-type="arch-node"] d'un conteneur
   [data-type="arch-diagram"] deviennent deplacables a la souris (pointer
   events). La position est stockee en attributs LISIBLES data-x / data-y en
   POURCENTAGES (0-100) relatifs au conteneur, PLUS le style inline
   left/top en % pour le rendu. Le LLM lit data-x/data-y directement.
   ============================================================ */

/** Wire drag on every arch-node of every arch-diagram in the doc. */
function enableArchNodeDrag(doc) {
  doc.querySelectorAll('[data-type="arch-diagram"]').forEach(diagram => {
    if (getComputedStyle(diagram).position === 'static') diagram.style.position = 'relative';
    diagram.querySelectorAll('[data-type="arch-node"]').forEach(node => makeArchNodeDraggable(doc, node));
  });
}

/** Remove drag wiring/markers from arch-nodes (leave positions intact). */
function removeArchNodeDrag(doc) {
  doc.querySelectorAll('[data-type="arch-node"]').forEach(node => {
    node.classList.remove('_mcp_arch_draggable', '_mcp_arch_grabbing');
    if (node._mcpArchDown) {
      node.removeEventListener('pointerdown', node._mcpArchDown);
      node._mcpArchDown = null;
    }
  });
}

/** Make one arch-node draggable via pointer events, writing data-x/data-y (%). */
function makeArchNodeDraggable(doc, node) {
  const diagram = node.closest('[data-type="arch-diagram"]');
  if (!diagram) return;
  if (getComputedStyle(diagram).position === 'static') diagram.style.position = 'relative';
  if (node._mcpArchDown) return; // already wired
  node.classList.add('_mcp_arch_draggable');

  const onDown = e => {
    if (e.button !== 0) return;
    // Avoid hijacking text editing: only drag from the node itself, not children.
    e.preventDefault();
    const rect  = diagram.getBoundingClientRect();
    const nRect = node.getBoundingClientRect();
    // Pointer offset within the node, so the box does not jump on grab.
    const offX = e.clientX - nRect.left;
    const offY = e.clientY - nRect.top;
    const wasEditable = node.getAttribute('contenteditable');
    node.setAttribute('contenteditable', 'false');
    node.classList.add('_mcp_arch_grabbing');
    node.style.position = 'absolute';

    const onMove = ev => {
      const x = clampPct(((ev.clientX - offX - rect.left) / rect.width) * 100);
      const y = clampPct(((ev.clientY - offY - rect.top)  / rect.height) * 100);
      applyArchNodePosition(node, x, y);
    };
    const onUp = () => {
      doc.removeEventListener('pointermove', onMove);
      doc.removeEventListener('pointerup', onUp);
      node.classList.remove('_mcp_arch_grabbing');
      if (wasEditable === null) node.removeAttribute('contenteditable');
      else                      node.setAttribute('contenteditable', wasEditable);
      scheduleSave();
    };
    doc.addEventListener('pointermove', onMove);
    doc.addEventListener('pointerup', onUp);
  };

  node._mcpArchDown = onDown;
  node.addEventListener('pointerdown', onDown);
}

/** Clamp a percentage into [0, 100] and round to 1 decimal. */
function clampPct(v) {
  return Math.round(Math.min(100, Math.max(0, v)) * 10) / 10;
}

/** Write readable position: data-x/data-y (%) + inline left/top (%). */
function applyArchNodePosition(node, x, y) {
  node.dataset.x = x.toFixed(1);
  node.dataset.y = y.toFixed(1);
  node.style.position = 'absolute';
  node.style.left = x.toFixed(1) + '%';
  node.style.top  = y.toFixed(1) + '%';
}
