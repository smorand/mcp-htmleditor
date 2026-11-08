/* ============================================================
   Context menus (injected into iframe)
   ============================================================ */
/* ============================================================
   Declarative arch-diagram mouse editing (add/remove node, add edge)

   These write the SAME markup the LLM authors (arch-row / arch-node /
   arch-edge, see skill/topics/arch-diagram.md): no position is ever computed
   here client-side. Every structural change is followed by saveThenLayout(),
   which persists the DOM then asks the server to run the Python layout
   engine (POST /arch-layout) exactly as `mcp-htmleditor arch-layout` would,
   so the browser never reimplements the row/col distribution or the edge
   routing in JS.
   ============================================================ */

function isDeclarativeArchDiagram(diagram) {
  return !!diagram.querySelector('[data-type="arch-row"]');
}

/** Assign a stable data-id to a node that does not have one yet (older
    diagrams, or a node added before this feature existed). */
function ensureNodeId(node, diagram) {
  if (node.dataset.id) return node.dataset.id;
  const used = new Set(
    [...diagram.querySelectorAll('[data-type="arch-node"]')].map(n => n.dataset.id).filter(Boolean)
  );
  let n = 0;
  let id = 'node-0';
  while (used.has(id)) { n += 1; id = 'node-' + n; }
  node.dataset.id = id;
  return id;
}

/** Persist the DOM, then ask the server to recompute every declarative
    diagram in the file (the browser never computes positions itself). */
async function saveThenLayout() {
  await saveContent();
  try {
    const res = await fetch('/arch-layout', { method: 'POST' });
    const body = await res.json();
    if (body.warnings && body.warnings.length) {
      console.warn('arch-layout warnings:', body.warnings);
    }
  } catch (e) {
    console.warn('arch-layout request failed:', e);
  }
}

/** ＋ Ajouter nœud (declarative diagram): choose an existing row or a new one,
    insert a plain arch-node, then recompute positions server-side. */
function addArchNodeDeclarative(doc, diagram) {
  const rows = [...diagram.querySelectorAll('[data-type="arch-row"]')];
  const label = prompt('Libellé du nœud :', 'Nouveau nœud');
  if (!label) return;

  // Resolve which row to target BEFORE snapshotting: a row-choice prompt can
  // still be cancelled here, and snapshotForUndo() must only run once the
  // mutation is certain to happen (a cancelled prompt must never push an
  // undo entry with nothing to actually undo).
  let chosenRowNumber = null;
  if (rows.length > 1) {
    const indices = rows.map(r => r.dataset.row).join(', ');
    const chosen = prompt(`Numéro de rangée existante (${indices}), ou un nouveau numéro :`, rows[rows.length - 1].dataset.row);
    if (chosen === null) return;
    chosenRowNumber = chosen.trim();
  }

  snapshotForUndo();

  let targetRow;
  if (rows.length === 0) {
    targetRow = doc.createElement('div');
    targetRow.dataset.type = 'arch-row';
    targetRow.dataset.row = '0';
    diagram.insertBefore(targetRow, diagram.firstChild);
  } else if (rows.length === 1) {
    targetRow = rows[0];
  } else {
    targetRow = rows.find(r => r.dataset.row === chosenRowNumber);
    if (!targetRow) {
      targetRow = doc.createElement('div');
      targetRow.dataset.type = 'arch-row';
      targetRow.dataset.row = chosenRowNumber;
      diagram.appendChild(targetRow);
    }
  }

  const node = doc.createElement('div');
  node.dataset.type = 'arch-node';
  node.dataset.label = label;
  node.dataset.shape = 'box';
  ensureNodeId(node, diagram);
  node.style.cssText = 'border:2px solid #333; background:#f5f5f5; color:#262626; border-radius:4px;';
  node.textContent = label;
  targetRow.appendChild(node);

  saveThenLayout();
}

/** Supprimer: also drop every arch-edge that referenced this node (dangling
    data-from/data-to would otherwise silently stop rendering a connector). */
function removeArchNode(doc, diagram, node) {
  const id = node.dataset.id;
  if (id) {
    diagram.querySelectorAll(`[data-type="arch-edge"][data-from="${id}"], [data-type="arch-edge"][data-to="${id}"]`)
      .forEach(edge => {
        const edgeId = edge.dataset.edgeId;
        if (edgeId) diagram.querySelectorAll(`[data-edge-of="${edgeId}"]`).forEach(deco => deco.remove());
        edge.remove();
      });
  }
  node.remove();
  saveThenLayout();
}

/** Enter "pick a target" mode after "➜ Créer une arête depuis ce nœud": the
    next click on another arch-node of the SAME diagram creates the edge.
    Escape or clicking the same node cancels. */
function startArchConnect(doc, sourceNode) {
  cancelArchConnect(doc);
  archConnectSource = { node: sourceNode, doc };
  sourceNode.style.outline = '3px solid #0f62fe';
  doc.body.style.cursor = 'crosshair';

  const onClick = e => {
    const target = e.target.closest && e.target.closest('[data-type="arch-node"]');
    if (!target) return;
    e.preventDefault();
    e.stopPropagation();
    finishArchConnect(doc, target);
  };
  const onKey = e => { if (e.key === 'Escape') cancelArchConnect(doc); };

  archConnectSource.onClick = onClick;
  archConnectSource.onKey = onKey;
  doc.addEventListener('click', onClick, { capture: true });
  doc.addEventListener('keydown', onKey);
}

function cancelArchConnect(doc) {
  if (!archConnectSource) return;
  archConnectSource.node.style.outline = '';
  doc.body.style.cursor = '';
  doc.removeEventListener('click', archConnectSource.onClick, { capture: true });
  doc.removeEventListener('keydown', archConnectSource.onKey);
  archConnectSource = null;
}

function finishArchConnect(doc, targetNode) {
  const source = archConnectSource.node;
  if (targetNode === source) { cancelArchConnect(doc); return; }
  const diagram = source.closest('[data-type="arch-diagram"]');
  ensureNodeId(source, diagram);
  ensureNodeId(targetNode, diagram);

  const label = prompt('Libellé de l\'arête (optionnel) :', '') || '';
  snapshotForUndo();
  const edge = doc.createElement('div');
  edge.dataset.type = 'arch-edge';
  edge.dataset.from = source.dataset.id;
  edge.dataset.to = targetNode.dataset.id;
  if (label) edge.dataset.label = label;
  diagram.appendChild(edge);

  cancelArchConnect(doc);
  saveThenLayout();
}

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
          snapshotForUndo();
          el.style.width = Math.min(100, (parseFloat(el.style.width) || 30) * 1.2).toFixed(1) + '%';
          scheduleSave();
        }},
        { label: 'Réduire (-20%)',  action: () => {
          snapshotForUndo();
          el.style.width = Math.max(5,   (parseFloat(el.style.width) || 30) * 0.8).toFixed(1) + '%';
          scheduleSave();
        }},
        { label: 'Renommer', action: () => {
          const name = prompt('Libellé :', el.textContent.trim());
          if (name !== null) { snapshotForUndo(); el.textContent = name; el.dataset.label = name; scheduleSave(); }
        }},
        { label: 'Supprimer', action: () => { snapshotForUndo(); el.remove(); scheduleSave(); }},
      ];

    case 'arch-node': {
      const diagram = el.closest('[data-type="arch-diagram"]');
      const items = [
        { label: 'Renommer', action: () => {
          const name = prompt('Libellé :', el.textContent.trim());
          if (name !== null) { snapshotForUndo(); el.textContent = name; el.dataset.label = name; scheduleSave(); }
        }},
        { label: 'Changer forme', action: () => {
          const shape = prompt('Forme (box/circle/diamond) :', el.dataset.shape || 'box');
          if (shape) { snapshotForUndo(); el.dataset.shape = shape; scheduleSave(); }
        }},
      ];
      if (diagram && isDeclarativeArchDiagram(diagram)) {
        ensureNodeId(el, diagram);
        items.push({ label: '➜ Créer une arête depuis ce nœud', action: () => {
          startArchConnect(doc, el);
        }});
      }
      items.push({ label: 'Supprimer', action: () => {
        snapshotForUndo();
        if (diagram && isDeclarativeArchDiagram(diagram)) {
          removeArchNode(doc, diagram, el);
        } else {
          el.remove(); scheduleSave();
        }
      }});
      return items;
    }

    case 'annotation':
      return [
        { label: 'Éditer texte', action: () => {
          const text = prompt('Texte :', el.textContent.trim());
          if (text !== null) { snapshotForUndo(); el.textContent = text; scheduleSave(); }
        }},
        { label: 'Supprimer', action: () => { snapshotForUndo(); el.remove(); scheduleSave(); }},
      ];

    case 'table':
      return tableContextMenu(el, doc);

    case 'gantt':
      return [{ label: '＋ Ajouter tâche', action: () => {
        const label = prompt('Libellé :', 'Nouvelle tâche');
        if (!label) return;
        snapshotForUndo();
        const task = doc.createElement('div');
        task.dataset.type = 'gantt-task'; task.dataset.label = label;
        task.style.cssText = 'background:#4a90d9;color:white;padding:4px 8px;margin:2px 0;border-radius:3px;width:30%;';
        task.textContent = label;
        el.appendChild(task); scheduleSave();
      }}];

    case 'arch-diagram':
      if (isDeclarativeArchDiagram(el)) {
        return [{ label: '＋ Ajouter nœud (rangée existante ou nouvelle)', action: () => {
          addArchNodeDeclarative(doc, el);
        }}];
      }
      // Legacy diagram (no arch-row yet): keep the historical hand-positioned
      // node, unrelated to the declarative engine (see skill/topics/arch-diagram.md).
      return [{ label: '＋ Ajouter nœud', action: () => {
        const label = prompt('Libellé :', 'Nouveau nœud');
        if (!label) return;
        snapshotForUndo();
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
    { label: '＋ Ajouter ligne',             action: () => { snapshotForUndo(); addTableRow(tbl, doc); scheduleSave(); }},
    { label: '− Supprimer dernière ligne',   action: () => { snapshotForUndo(); removeLastTableRow(tbl); scheduleSave(); }},
    { label: '＋ Ajouter colonne',           action: () => { snapshotForUndo(); addTableCol(tbl, doc); scheduleSave(); }},
    { label: '− Supprimer dernière colonne', action: () => { snapshotForUndo(); removeLastTableCol(tbl); scheduleSave(); }},
    { label: '✕ Supprimer le tableau',       action: () => { snapshotForUndo(); tbl.remove(); scheduleSave(); }},
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
