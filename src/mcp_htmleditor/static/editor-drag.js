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
      snapshotForUndo();
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

    let moved = false;
    const onMove = ev => {
      // Snapshot BEFORE the first actual mutation of this drag, not on every
      // pointermove: one drag gesture is one undo step, not one per pixel.
      if (!moved) snapshotForUndo();
      moved = true;
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
      // A node actually dragged by a human is locked: a future automatic
      // recompute (mcp-htmleditor arch-layout / layout_arch_diagram) must
      // never reposition it again. See arch_layout.py's _write_node_box.
      if (moved) node.dataset.layout = 'manual';
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
