/* ============================================================
   Floating format bar (selection-based)
   ============================================================ */
let _formatBar = null;

/**
 * Build a small crisp alignment icon: four horizontal bars (mimicking text
 * lines of varying width) laid out left/center/right/justified. Replaces the
 * previous emoji-square icons (⬛⬜⬜), which render as an illegible cluster
 * of tiny blocks at toolbar-button size on most platforms.
 *
 * @param {'left'|'center'|'right'|'full'} align
 */
function alignIconSvg(align) {
  const widths = [16, 11, 14, 9]; // uneven line lengths, like real text
  const rows = widths.map((w, i) => {
    const width = align === 'full' ? 16 : w;
    const x = align === 'center' ? (16 - width) / 2 : align === 'right' ? 16 - width : 0;
    const y = i * 3.6;
    return `<rect x="${x}" y="${y}" width="${width}" height="1.8" rx="0.5" fill="currentColor"/>`;
  }).join('');
  return `<svg viewBox="0 0 16 13.8" width="16" height="14" aria-hidden="true">${rows}</svg>`;
}

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
    { cmd: 'justifyLeft',   icon: alignIconSvg('left'),   title: 'Aligner à gauche'  },
    { cmd: 'justifyCenter', icon: alignIconSvg('center'), title: 'Centrer'            },
    { cmd: 'justifyRight',  icon: alignIconSvg('right'),  title: 'Aligner à droite'  },
    { cmd: 'justifyFull',   icon: alignIconSvg('full'),   title: 'Justifié'          },
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

  // The bar lives inside the iframe's own document (doc.body.appendChild),
  // so its `position: fixed` is already relative to the IFRAME's viewport,
  // not the outer page. `rect` (from range.getBoundingClientRect()) is also
  // iframe-relative already: do not add the iframe's own offset within the
  // outer page (iframeRect.top/left) on top of it, or the bar renders that
  // far too low/right and overlaps the very text it should float above.
  const iframeWin = doc.defaultView || window;
  const barW = bar.offsetWidth || 340;
  const barH = bar.offsetHeight || 32;

  let top  = rect.top - barH - 8;
  let left = rect.left + rect.width / 2 - barW / 2;

  // Clamp within the iframe's own viewport
  if (top < 4) top = rect.bottom + 8;
  if (left < 4) left = 4;
  if (left + barW > iframeWin.innerWidth - 4) left = iframeWin.innerWidth - barW - 4;

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
                 'justifyLeft','justifyCenter','justifyRight','justifyFull'];
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

  // Same iframe-relative fixed-positioning context as showFormatBar: do not
  // add the iframe's own offset within the outer page on top of coordinates
  // that are already relative to the iframe's viewport.
  const elRect = el.getBoundingClientRect();  // in iframe coords

  const top  = elRect.top - (bar.offsetHeight || 32) - 6;
  const left = elRect.right - (bar.offsetWidth  || 280);

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
    snapshotForUndo();
    const dataUri = reader.result;  // data:image/...;base64,...
    const img = `<img src="${dataUri}" alt="${file.name}" data-editable="resize,reposition" style="max-width:100%;height:auto;display:block;margin:8px 0;" />`;
    if (targetEl) {
      // Dropped onto a specific editable: append there. insertAdjacentHTML,
      // unlike execCommand('insertHTML', ...), does NOT push a step onto the
      // browser's native contenteditable undo stack — this is exactly the
      // structural gap snapshotForUndo() exists to cover for this call site.
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
