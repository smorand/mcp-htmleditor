/**
 * editor.js — mcp-htmleditor (v2: iframe-based, no GrapesJS)
 *
 * Le HTML est servi tel quel dans un <iframe>. Ce script gère:
 *  - Polling /status pour détecter les modifications LLM et recharger l'iframe
 *  - Overlay "modification en cours"
 *  - Mode édition: injection de contenteditable dans l'iframe + sauvegarde
 *  - Context menus par data-type (injectés dans l'iframe)
 */

let pollInterval = 1000;
let lastMtime = null;
let wasUpdating = false;
let editMode = false;
let saveTimer = null;

const frame = document.getElementById('content-frame');
const overlay = document.getElementById('update-overlay');
const savedBadge = document.getElementById('toolbar-saved');
const statusDot = document.getElementById('toolbar-status');
const editCheckbox = document.getElementById('edit-mode-checkbox');

/* ============================================================
   Bootstrap
   ============================================================ */
(async function init() {
  // Fetch poll interval + initial mtime
  try {
    const st = await fetch('/status').then(r => r.json());
    pollInterval = st.poll_interval || 1000;
    lastMtime = st.mtime;
    const name = (st.filename || '').split('/').pop();
    document.getElementById('toolbar-filename').textContent = name;
    document.title = name || 'HTML Editor';
  } catch (e) {
    console.warn('Could not reach /status', e);
  }

  // Edit mode toggle
  editCheckbox.addEventListener('change', () => {
    editMode = editCheckbox.checked;
    applyEditMode();
  });

  // Wait for iframe to load, then wire it up
  frame.addEventListener('load', onFrameLoad);

  // Start polling
  setInterval(pollStatus, pollInterval);
})();

/* ============================================================
   Iframe load callback
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
  try {
    status = await fetch('/status').then(r => r.json());
  } catch (e) {
    return;
  }

  // Update filename in toolbar if changed
  const name = (status.filename || '').split('/').pop();
  document.getElementById('toolbar-filename').textContent = name || '—';

  if (status.update_in_progress) {
    overlay.style.display = 'flex';
    statusDot.style.color = '#f1c21b';
    wasUpdating = true;
  } else {
    overlay.style.display = 'none';
    statusDot.style.color = '#42be65';

    const mtimeChanged = lastMtime !== null && status.mtime !== lastMtime;
    if ((wasUpdating || mtimeChanged) && !status.update_in_progress) {
      wasUpdating = false;
      lastMtime = status.mtime;
      reloadFrame();
      return;
    }
  }

  lastMtime = status.mtime;
}

function reloadFrame() {
  // Reload the iframe without reloading the parent page
  frame.src = '/content-frame?' + Date.now();
}

/* ============================================================
   Edit mode: inject contenteditable on [data-editable="text"]
   ============================================================ */
function applyEditMode() {
  try {
    const doc = frame.contentDocument;
    if (!doc) return;
    if (editMode) {
      injectEditMode(doc);
    } else {
      removeEditMode(doc);
    }
  } catch (e) {
    console.warn('Could not toggle edit mode:', e);
  }
}

function injectEditMode(doc) {
  // Make elements with data-editable="text" contenteditable
  doc.querySelectorAll('[data-editable~="text"]').forEach(el => {
    el.contentEditable = 'true';
    el.style.outline = '2px dashed #0f62fe';
    el.style.cursor = 'text';
    el.style.minHeight = '1em';

    el.addEventListener('input', onEditableInput);
    el.addEventListener('blur', onEditableBlur);
  });
}

function removeEditMode(doc) {
  doc.querySelectorAll('[data-editable~="text"]').forEach(el => {
    el.contentEditable = 'false';
    el.style.outline = '';
    el.style.cursor = '';
    el.removeEventListener('input', onEditableInput);
    el.removeEventListener('blur', onEditableBlur);
  });
}

function onEditableInput() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveContent, 800);
}

function onEditableBlur() {
  clearTimeout(saveTimer);
  saveContent();
}

/* ============================================================
   Save: POST the full iframe HTML to /content
   ============================================================ */
async function saveContent() {
  try {
    const doc = frame.contentDocument;
    if (!doc) return;

    // Temporarily remove contenteditable markers before saving
    const editables = doc.querySelectorAll('[contenteditable]');
    const saved = [];
    editables.forEach(el => {
      saved.push({ el, ce: el.contentEditable, outline: el.style.outline, cursor: el.style.cursor });
      el.removeAttribute('contenteditable');
      el.style.outline = '';
      el.style.cursor = '';
    });

    const html = '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;

    // Restore
    saved.forEach(({ el, ce, outline, cursor }) => {
      el.contentEditable = ce;
      el.style.outline = outline;
      el.style.cursor = cursor;
    });

    await fetch('/content', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html }),
    });

    // Flash saved badge
    savedBadge.style.display = 'inline';
    clearTimeout(savedBadge._timer);
    savedBadge._timer = setTimeout(() => { savedBadge.style.display = 'none'; }, 1500);

  } catch (e) {
    console.warn('Save failed:', e);
  }
}

/* ============================================================
   Context menus (injected into iframe document)
   ============================================================ */
function injectContextMenus(doc) {
  doc.addEventListener('contextmenu', e => {
    // Walk up from target to find a data-type element
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
        {
          label: 'Agrandir (+20%)',
          action: () => {
            const w = parseFloat(el.style.width) || 30;
            el.style.width = Math.min(100, w * 1.2).toFixed(1) + '%';
            scheduleSave();
          },
        },
        {
          label: 'Réduire (-20%)',
          action: () => {
            const w = parseFloat(el.style.width) || 30;
            el.style.width = Math.max(5, w * 0.8).toFixed(1) + '%';
            scheduleSave();
          },
        },
        {
          label: 'Renommer',
          action: () => {
            const name = prompt('Nouveau libellé :', el.textContent.trim());
            if (name !== null) { el.textContent = name; el.dataset.label = name; scheduleSave(); }
          },
        },
        {
          label: 'Supprimer',
          action: () => { el.remove(); scheduleSave(); },
        },
      ];

    case 'arch-node':
      return [
        {
          label: 'Renommer',
          action: () => {
            const name = prompt('Nouveau libellé :', el.textContent.trim());
            if (name !== null) { el.textContent = name; el.dataset.label = name; scheduleSave(); }
          },
        },
        {
          label: 'Changer forme',
          action: () => {
            const shape = prompt('Forme (box / circle / diamond) :', el.dataset.shape || 'box');
            if (shape) { el.dataset.shape = shape; scheduleSave(); }
          },
        },
        {
          label: 'Supprimer',
          action: () => { el.remove(); scheduleSave(); },
        },
      ];

    case 'annotation':
      return [
        {
          label: 'Éditer texte',
          action: () => {
            const text = prompt('Texte :', el.textContent.trim());
            if (text !== null) { el.textContent = text; scheduleSave(); }
          },
        },
        {
          label: 'Supprimer',
          action: () => { el.remove(); scheduleSave(); },
        },
      ];

    case 'table':
      return [
        {
          label: 'Ajouter ligne',
          action: () => { addTableRow(el); scheduleSave(); },
        },
        {
          label: 'Supprimer dernière ligne',
          action: () => { removeLastTableRow(el); scheduleSave(); },
        },
        {
          label: 'Ajouter colonne',
          action: () => { addTableCol(el); scheduleSave(); },
        },
        {
          label: 'Supprimer dernière colonne',
          action: () => { removeLastTableCol(el); scheduleSave(); },
        },
      ];

    case 'gantt':
      return [
        {
          label: 'Ajouter tâche',
          action: () => {
            const label = prompt('Libellé :', 'Nouvelle tâche');
            if (!label) return;
            const task = doc.createElement('div');
            task.dataset.type = 'gantt-task';
            task.dataset.label = label;
            task.style.cssText = 'background:#4a90d9;color:white;padding:4px 8px;margin:2px 0;border-radius:3px;width:30%;';
            task.textContent = label;
            el.appendChild(task);
            scheduleSave();
          },
        },
      ];

    case 'arch-diagram':
      return [
        {
          label: 'Ajouter nœud',
          action: () => {
            const label = prompt('Libellé :', 'Nouveau nœud');
            if (!label) return;
            const node = doc.createElement('div');
            node.dataset.type = 'arch-node';
            node.dataset.label = label;
            node.dataset.shape = 'box';
            node.style.cssText = 'display:inline-block;border:2px solid #333;padding:8px 16px;border-radius:4px;background:#f5f5f5;margin:8px;';
            node.textContent = label;
            el.appendChild(node);
            scheduleSave();
          },
        },
      ];

    default:
      return [];
  }
}

function showContextMenu(doc, x, y, items) {
  // Remove any existing
  const existing = doc.getElementById('_editor_ctx_menu');
  if (existing) existing.remove();
  const existingParent = document.getElementById('_editor_ctx_menu_host');
  if (existingParent) existingParent.remove();

  // Build menu in the parent frame (to avoid iframe z-index issues)
  const menu = document.createElement('div');
  menu.id = '_editor_ctx_menu_host';
  menu.style.cssText = [
    'position:fixed',
    `top:${y + frame.getBoundingClientRect().top}px`,
    `left:${x + frame.getBoundingClientRect().left}px`,
    'background:white',
    'border:1px solid #c6c6c6',
    'box-shadow:0 4px 12px rgba(0,0,0,.2)',
    'z-index:99999',
    'min-width:180px',
    'font-family:IBM Plex Sans,-apple-system,sans-serif',
    'font-size:13px',
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
   Table helpers (DOM-based)
   ============================================================ */
function addTableRow(tableEl) {
  const tbody = tableEl.querySelector('tbody') || tableEl;
  const rows = tbody.querySelectorAll('tr');
  const colCount = rows.length ? rows[rows.length - 1].querySelectorAll('td,th').length : 3;
  const tr = tableEl.ownerDocument.createElement('tr');
  for (let i = 0; i < colCount; i++) {
    const td = tableEl.ownerDocument.createElement('td');
    td.innerHTML = '&nbsp;';
    tr.appendChild(td);
  }
  tbody.appendChild(tr);
}

function removeLastTableRow(tableEl) {
  const tbody = tableEl.querySelector('tbody') || tableEl;
  const rows = tbody.querySelectorAll('tr');
  if (rows.length > 1) rows[rows.length - 1].remove();
}

function addTableCol(tableEl) {
  tableEl.querySelectorAll('tr').forEach(row => {
    const cell = tableEl.ownerDocument.createElement(row.querySelector('th') ? 'th' : 'td');
    cell.innerHTML = '&nbsp;';
    row.appendChild(cell);
  });
}

function removeLastTableCol(tableEl) {
  tableEl.querySelectorAll('tr').forEach(row => {
    const cells = row.querySelectorAll('td,th');
    if (cells.length > 1) cells[cells.length - 1].remove();
  });
}

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveContent, 600);
}
