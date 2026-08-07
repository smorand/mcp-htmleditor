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
let isPresentation = false;   // detected from data-doc-type
let isDocument     = false;   // detected from data-doc-type
let insertPosition = null;    // 'before' | 'after' when slide picker is open
let lastDocRange   = null;    // saved caret range in document mode

const frame        = document.getElementById('content-frame');
const overlay      = document.getElementById('update-overlay');
const savedBadge   = document.getElementById('toolbar-saved');
const statusDot    = document.getElementById('toolbar-status');
const editCheckbox = document.getElementById('edit-mode-checkbox');
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

  editCheckbox.addEventListener('change', () => {
    editMode = editCheckbox.checked;
    applyEditMode();
    updateSlideActionsVisibility();
    updateDocActionsVisibility();
  });

  // Slide action buttons
  document.getElementById('btn-insert-before').addEventListener('click', () => openSlidePicker('before'));
  document.getElementById('btn-insert-after').addEventListener('click',  () => openSlidePicker('after'));
  document.getElementById('btn-delete-slide').addEventListener('click',  deleteCurrentSlide);
  document.querySelector('#slide-picker .picker-cancel').addEventListener('click', closeSlidePicker);
  document.querySelector('#slide-picker .picker-backdrop').addEventListener('click', closeSlidePicker);

  // Document block button
  document.getElementById('btn-insert-block').addEventListener('click', openBlockPicker);
  document.querySelector('#block-picker .picker-cancel').addEventListener('click', closeBlockPicker);
  document.querySelector('#block-picker .picker-backdrop').addEventListener('click', closeBlockPicker);

  frame.addEventListener('load', onFrameLoad);
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
    statusDot.style.color  = '#f1c21b';
    wasUpdating = true;
  } else {
    overlay.style.display = 'none';
    statusDot.style.color  = '#42be65';
    const mtimeChanged = lastMtime !== null && status.mtime !== lastMtime;
    if ((wasUpdating || mtimeChanged) && !status.update_in_progress) {
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
        node.style.cssText = 'display:inline-block;border:2px solid #333;padding:8px 16px;border-radius:4px;background:#f5f5f5;margin:8px;';
        node.textContent = label;
        el.appendChild(node); scheduleSave();
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
function onEditableInput()  { clearTimeout(saveTimer); saveTimer = setTimeout(saveContent, 800); }
function onEditableBlur()   { clearTimeout(saveTimer); saveContent(); }
function scheduleSave()     { clearTimeout(saveTimer); saveTimer = setTimeout(saveContent, 600); }

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

    const html = '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;

    // Restore
    backup.forEach(({ el, ce, outline, cursor }) => {
      el.contentEditable = ce; el.style.outline = outline; el.style.cursor = cursor;
    });
    if (fb) fb.style.display = fbDisplay;
    if (ib) ib.style.display = ibDisplay;

    await fetch('/content', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html }),
    });

    savedBadge.style.display = 'inline';
    clearTimeout(savedBadge._timer);
    savedBadge._timer = setTimeout(() => { savedBadge.style.display = 'none'; }, 1500);

  } catch (e) {
    console.warn('Save failed:', e);
  }
}

/* ============================================================
   Slide management (presentation mode)
   ============================================================
   Insère/supprime des slides typées et maintient la cohérence:
   - ids séquentiels slide-0..slide-N
   - const TOTAL et slideNames[] dans le <script> de navigation
   - eyebrow "Slide 0N / TT" et footer "Slide N / TT"
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
 *  in the document, so inserted slides reuse the same cover/logos. */
function resolveTemplateAssets(html, doc) {
  const grab = sel => { const el = doc.querySelector(sel); return el ? el.getAttribute('src') : ''; };
  const map = {
    '{{COVER}}':    grab('.slide-cover-img'),
    '{{CM}}':       grab('img.logo-cm'),
    '{{CIC}}':      grab('img.logo-cic'),
    '{{EI}}':       grab('img.logo-ei'),
    '{{CHEVRONS}}': grab('.slide-foot-logo img'),
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

    // eyebrow "… Slide 0N / TT"
    const eyebrow = slide.querySelector('.slide-eyebrow');
    if (eyebrow) {
      eyebrow.textContent = eyebrow.textContent.replace(
        /Slide\s*\d+\s*\/\s*\d+/i,
        `Slide ${String(i + 1).padStart(2, '0')} / ${String(total).padStart(2, '0')}`
      );
      // If no "Slide N / TT" pattern existed, leave text untouched.
    }

    // footer "Slide N / TT"
    const footer = slide.querySelector('.slide-footer-right');
    if (footer) footer.textContent = `Slide ${i + 1} / ${total}`;

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
function openBlockPicker() {
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
    card.addEventListener('click', () => { insertDocBlock(key); closeBlockPicker(); });
    grid.appendChild(card);
  });
  document.getElementById('block-picker').style.display = 'flex';
}

function closeBlockPicker() {
  document.getElementById('block-picker').style.display = 'none';
}

/* -- Insert a block -------------------------------------------- */
function insertDocBlock(blockKey) {
  const doc = frame.contentDocument;
  if (!doc) return;
  if (typeof DOC_BLOCKS === 'undefined') return;
  const block = DOC_BLOCKS[blockKey];
  if (!block) return;

  const article = getDocumentArticle(doc);
  if (!article) return;

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
      ref.parentNode.insertBefore(node, ref.nextSibling);
    } else {
      article.appendChild(node);
    }
    // Make freshly inserted block editable if edit mode is on.
    if (node.nodeType === 1) makeDocBlockEditable(doc, node);
  });

  lastDocRange = null;
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
