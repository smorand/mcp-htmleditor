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

const frame        = document.getElementById('content-frame');
const overlay      = document.getElementById('update-overlay');
const savedBadge   = document.getElementById('toolbar-saved');
const statusDot    = document.getElementById('toolbar-status');
const editCheckbox = document.getElementById('edit-mode-checkbox');

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
  });

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
    if (editMode) injectEditMode(doc);
    injectContextMenus(doc);
  } catch (e) {
    console.warn('Could not access iframe content:', e);
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
    el.addEventListener('mouseup',   () => showFormatBar(doc));
    el.addEventListener('keyup',     () => showFormatBar(doc));
    el.addEventListener('focus',     () => showInsertBar(doc, el));
  });
  injectEditorStyles(doc);
  createFormatBar(doc);
  createInsertBar(doc);
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
  const url = prompt('URL ou chemin de l\'image :', 'https://');
  if (!url) return;
  const alt = prompt('Texte alternatif :', '');
  doc.execCommand('insertHTML', false,
    `<img src="${url}" alt="${alt || ''}" style="max-width:100%;height:auto;display:block;margin:8px 0;" />`
  );
  scheduleSave();
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
