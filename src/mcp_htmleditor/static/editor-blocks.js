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
  if (!isDocument && !isWebsite) return;
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

  snapshotForUndo();
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
  if ((isDocument || isWebsite) && editMode) injectDocDragHandles(doc);
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
