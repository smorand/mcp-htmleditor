/**
 * editor.js — mcp-htmleditor
 *
 * Initialises GrapesJS, wires the polling loop, slide navigation,
 * custom context menus, block panel, and auto-save.
 */

/* ============================================================
   Constants / globals
   ============================================================ */
let editor = null;
let pollInterval = 1000;          // ms, overridden from /status
let lastMtime = null;
let wasUpdating = false;
let currentSlideIndex = 0;
let slides = [];                  // Array of GrapesJS components (data-type="slide")

/* ============================================================
   Bootstrap — fetch content then init GrapesJS
   ============================================================ */
(async function init() {
  // 1. Fetch current poll interval from /status
  try {
    const st = await fetch('/status').then(r => r.json());
    pollInterval = st.poll_interval || 1000;
    lastMtime = st.mtime;
  } catch (e) {
    console.warn('Could not reach /status, using defaults', e);
  }

  // 2. Fetch initial HTML content
  let initialHtml = '';
  try {
    initialHtml = await fetch('/content').then(r => r.text());
  } catch (e) {
    console.warn('Could not load /content', e);
    initialHtml = '<p>No content loaded.</p>';
  }

  // 3. Extract body content for GrapesJS (it cannot handle <!DOCTYPE>)
  const bodyContent = extractBody(initialHtml);

  // 4. Detect presentation mode
  const isPresentation = /data-doc-type=["']presentation["']/i.test(initialHtml);

  // 5. Init GrapesJS
  editor = grapesjs.init({
    container: '#gjs',
    height: '100vh',
    width: 'auto',
    fromElement: false,
    components: bodyContent,
    storageManager: false,  // We handle save manually
    deviceManager: { devices: [] },
    panels: { defaults: [] },
    blockManager: {
      appendTo: '#blocks',
      blocks: [],
    },
    styleManager: {
      sectors: [
        {
          name: 'General',
          open: true,
          properties: ['display', 'position', 'top', 'left', 'width', 'height'],
        },
        {
          name: 'Typography',
          open: false,
          properties: ['font-family', 'font-size', 'font-weight', 'color', 'text-align'],
        },
        {
          name: 'Decorations',
          open: false,
          properties: ['background-color', 'border', 'border-radius', 'padding', 'margin'],
        },
      ],
    },
  });

  // 6. Register custom blocks
  registerBlocks(editor);

  // 7. Custom context menus
  registerContextMenus(editor);

  // 8. Auto-save on change
  let saveTimer = null;
  editor.on('update', () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => saveContent(), 500);
  });

  // 9. Slide navigation
  if (isPresentation) {
    initSlideNav(editor);
  }

  // 10. Start polling
  setInterval(pollStatus, pollInterval);
})();

/* ============================================================
   HTML utilities
   ============================================================ */

/** Extract the content of <body> from a full HTML document string. */
function extractBody(html) {
  const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  if (bodyMatch) return bodyMatch[1];
  // No <body> tag: return as-is
  return html;
}

/* ============================================================
   Save
   ============================================================ */
async function saveContent() {
  if (!editor) return;
  const html = editor.getHtml();
  try {
    await fetch('/content', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html }),
    });
  } catch (e) {
    console.warn('Auto-save failed', e);
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

  const overlay = document.getElementById('update-overlay');

  // Show / hide overlay
  if (status.update_in_progress) {
    overlay.style.display = 'flex';
    wasUpdating = true;
  } else {
    overlay.style.display = 'none';

    // If update just completed OR mtime changed (external edit), reload
    const mtimeChanged = lastMtime !== null && status.mtime !== lastMtime;
    if ((wasUpdating || mtimeChanged) && !status.update_in_progress) {
      wasUpdating = false;
      lastMtime = status.mtime;
      await reloadContent();
      return;
    }
  }

  lastMtime = status.mtime;
}

async function reloadContent() {
  try {
    const html = await fetch('/content').then(r => r.text());
    const bodyContent = extractBody(html);
    editor.setComponents(bodyContent);
    // Re-init slide nav if needed
    const isPresentation = /data-doc-type=["']presentation["']/i.test(html);
    if (isPresentation) {
      initSlideNav(editor);
    }
  } catch (e) {
    console.warn('Reload failed', e);
  }
}

/* ============================================================
   Slide navigation
   ============================================================ */
function initSlideNav(ed) {
  // Collect slide components
  slides = [];
  ed.getComponents().each(comp => {
    if (comp.get('attributes')?.['data-type'] === 'slide') {
      slides.push(comp);
    }
  });

  if (slides.length === 0) return;

  const nav = document.getElementById('slide-nav');
  nav.style.display = 'flex';
  currentSlideIndex = 0;
  showSlide(0);

  document.getElementById('nav-prev').onclick = () => {
    if (currentSlideIndex > 0) showSlide(currentSlideIndex - 1);
  };
  document.getElementById('nav-next').onclick = () => {
    if (currentSlideIndex < slides.length - 1) showSlide(currentSlideIndex + 1);
  };
}

function showSlide(index) {
  currentSlideIndex = index;
  // Hide all slides, show only the current one
  slides.forEach((s, i) => {
    const el = s.getEl();
    if (el) el.style.display = i === index ? '' : 'none';
  });
  document.getElementById('nav-info').textContent =
    `Slide ${index + 1} / ${slides.length}`;
}

/* ============================================================
   Custom context menus
   ============================================================ */
function registerContextMenus(ed) {
  ed.on('component:contextmenu', (component, event) => {
    event.preventDefault();
    const dtype = component.get('attributes')?.['data-type'] || '';
    const items = getContextMenuItems(dtype, component);
    if (!items.length) return;
    showContextMenu(event, items);
  });
}

function getContextMenuItems(dtype, component) {
  switch (dtype) {
    case 'gantt-task':
      return [
        {
          label: 'Agrandir (+20%)',
          action: () => {
            const w = component.getStyle()['width'] || '100%';
            component.addStyle({ width: scalePercent(w, 1.2) });
          },
        },
        {
          label: 'Réduire (-20%)',
          action: () => {
            const w = component.getStyle()['width'] || '100%';
            component.addStyle({ width: scalePercent(w, 0.8) });
          },
        },
        {
          label: 'Renommer',
          action: () => {
            const name = prompt('Nouveau nom :', component.get('attributes')['data-label'] || '');
            if (name !== null) component.addAttributes({ 'data-label': name });
          },
        },
        { label: 'Supprimer', action: () => component.remove() },
      ];

    case 'arch-node':
      return [
        {
          label: 'Renommer',
          action: () => {
            const name = prompt('Nouveau nom :', component.get('attributes')['data-label'] || '');
            if (name !== null) {
              component.addAttributes({ 'data-label': name });
              component.set('content', name);
            }
          },
        },
        {
          label: 'Changer forme',
          action: () => {
            const shape = prompt('Forme (box/circle/diamond) :', component.get('attributes')['data-shape'] || 'box');
            if (shape) component.addAttributes({ 'data-shape': shape });
          },
        },
        { label: 'Supprimer', action: () => component.remove() },
      ];

    case 'annotation':
      return [
        {
          label: 'Éditer texte',
          action: () => {
            const text = prompt('Texte :', component.get('content') || '');
            if (text !== null) component.set('content', text);
          },
        },
        { label: 'Supprimer', action: () => component.remove() },
      ];

    case 'table':
      return [
        {
          label: 'Ajouter ligne',
          action: () => addTableRow(component),
        },
        {
          label: 'Supprimer ligne',
          action: () => removeLastTableRow(component),
        },
        {
          label: 'Ajouter colonne',
          action: () => addTableCol(component),
        },
        {
          label: 'Supprimer colonne',
          action: () => removeLastTableCol(component),
        },
      ];

    case 'gantt':
      return [
        {
          label: 'Ajouter tâche',
          action: () => addGanttTask(component),
        },
      ];

    case 'arch-diagram':
      return [
        {
          label: 'Ajouter nœud',
          action: () => addArchNode(component),
        },
      ];

    case 'annotated-image':
      return [
        {
          label: 'Ajouter annotation',
          action: () => addAnnotation(component),
        },
      ];

    default:
      return [];
  }
}

function showContextMenu(event, items) {
  // Remove any existing context menu
  const existing = document.getElementById('_gjs_ctx_menu');
  if (existing) existing.remove();

  const menu = document.createElement('div');
  menu.id = '_gjs_ctx_menu';
  menu.style.cssText = [
    'position:fixed',
    `top:${event.clientY}px`,
    `left:${event.clientX}px`,
    'background:white',
    'border:1px solid #ccc',
    'border-radius:4px',
    'box-shadow:0 2px 8px rgba(0,0,0,.2)',
    'z-index:99999',
    'min-width:160px',
  ].join(';');

  items.forEach(item => {
    const btn = document.createElement('div');
    btn.textContent = item.label;
    btn.style.cssText = 'padding:8px 14px;cursor:pointer;font-size:13px;';
    btn.onmouseenter = () => (btn.style.background = '#f0f0f0');
    btn.onmouseleave = () => (btn.style.background = '');
    btn.onclick = () => {
      item.action();
      menu.remove();
    };
    menu.appendChild(btn);
  });

  document.body.appendChild(menu);
  const dismiss = () => { menu.remove(); document.removeEventListener('click', dismiss); };
  setTimeout(() => document.addEventListener('click', dismiss), 10);
}

/* ============================================================
   Table helpers
   ============================================================ */
function addTableRow(tableComp) {
  const tbody = tableComp.find('tbody')[0] || tableComp;
  const existingRows = tbody.find('tr');
  const colCount = existingRows.length
    ? existingRows[existingRows.length - 1].find('td').length || 1
    : 3;
  const cells = Array(colCount).fill('<td>&nbsp;</td>').join('');
  tbody.append(`<tr>${cells}</tr>`);
}

function removeLastTableRow(tableComp) {
  const tbody = tableComp.find('tbody')[0] || tableComp;
  const rows = tbody.find('tr');
  if (rows.length > 1) rows[rows.length - 1].remove();
}

function addTableCol(tableComp) {
  tableComp.find('tr').forEach(row => {
    row.append('<td>&nbsp;</td>');
  });
}

function removeLastTableCol(tableComp) {
  tableComp.find('tr').forEach(row => {
    const cells = row.find('td, th');
    if (cells.length > 1) cells[cells.length - 1].remove();
  });
}

/* ============================================================
   Gantt helpers
   ============================================================ */
function addGanttTask(ganttComp) {
  const label = prompt('Libellé de la tâche :', 'Nouvelle tâche');
  if (!label) return;
  const start = prompt('Date de début (YYYY-MM) :', '2024-01');
  const end   = prompt('Date de fin (YYYY-MM) :', '2024-03');
  ganttComp.append(
    `<div data-type="gantt-task" data-label="${label}" data-start="${start || ''}" data-end="${end || ''}"
         style="background:#4a90d9;color:white;padding:4px 8px;margin:2px 0;border-radius:3px;">
      ${label}
    </div>`
  );
}

/* ============================================================
   Arch-diagram helpers
   ============================================================ */
function addArchNode(diagramComp) {
  const label = prompt('Libellé du nœud :', 'Nouveau nœud');
  if (!label) return;
  diagramComp.append(
    `<div data-type="arch-node" data-label="${label}" data-shape="box" data-x="10" data-y="10" data-width="20" data-height="10"
         style="display:inline-block;border:1px solid #333;padding:8px 16px;margin:8px;border-radius:4px;background:#fff;">
      ${label}
    </div>`
  );
}

/* ============================================================
   Annotated image helpers
   ============================================================ */
function addAnnotation(imgComp) {
  const text = prompt('Texte de l\'annotation :', '');
  if (!text) return;
  imgComp.append(
    `<div data-type="annotation" data-x="50" data-y="50"
         style="position:absolute;left:50%;top:50%;background:rgba(255,255,0,0.8);
                padding:4px 8px;border-radius:3px;font-size:12px;">
      ${text}
    </div>`
  );
}

/* ============================================================
   Utility
   ============================================================ */
function scalePercent(cssValue, factor) {
  const m = String(cssValue).match(/([\d.]+)(%?)/);
  if (!m) return cssValue;
  return (parseFloat(m[1]) * factor).toFixed(1) + (m[2] || '%');
}

/* ============================================================
   Block registration
   ============================================================ */
function registerBlocks(ed) {
  // -- Slide vide --
  ed.BlockManager.add('slide-empty', {
    label: 'Slide vide',
    category: 'Slides',
    content: `<section data-type="slide" data-id="slide-${Date.now()}" data-title="Nouveau slide"
                style="width:100%;min-height:400px;padding:40px;box-sizing:border-box;background:#fff;">
      <h2 data-editable="text" style="margin:0 0 20px">Titre du slide</h2>
      <p data-editable="text">Contenu…</p>
    </section>`,
  });

  // -- Gantt --
  ed.BlockManager.add('gantt', {
    label: 'Gantt',
    category: 'Composants',
    content: `<div data-type="gantt" style="width:100%;overflow-x:auto;padding:8px;">
      <div style="font-weight:bold;margin-bottom:8px;">Roadmap</div>
      <div data-type="gantt-task" data-label="Tâche 1" data-start="2024-01" data-end="2024-03"
           style="background:#4a90d9;color:white;padding:4px 8px;margin:2px 0;border-radius:3px;width:30%;">
        Tâche 1
      </div>
      <div data-type="gantt-task" data-label="Tâche 2" data-start="2024-03" data-end="2024-06"
           style="background:#7ed321;color:white;padding:4px 8px;margin:2px 0;border-radius:3px;width:30%;margin-left:30%;">
        Tâche 2
      </div>
    </div>`,
  });

  // -- Nœud architecture --
  ed.BlockManager.add('arch-node', {
    label: 'Nœud archi',
    category: 'Composants',
    content: `<div data-type="arch-node" data-label="Service" data-shape="box" data-x="10" data-y="20" data-width="20" data-height="10"
                style="display:inline-block;border:2px solid #333;padding:10px 20px;border-radius:4px;background:#f5f5f5;font-weight:bold;">
      Service
    </div>`,
  });

  // -- Image annotée --
  ed.BlockManager.add('annotated-image', {
    label: 'Image annotée',
    category: 'Composants',
    content: `<div data-type="annotated-image" style="position:relative;display:inline-block;">
      <img src="https://placehold.co/600x400" alt="Image" data-editable="resize,reposition" style="width:100%;" />
      <div data-type="annotation" data-x="20" data-y="30"
           style="position:absolute;left:20%;top:30%;background:rgba(255,255,0,0.85);padding:4px 8px;border-radius:3px;font-size:12px;">
        Annotation exemple
      </div>
    </div>`,
  });

  // -- Tableau 3×3 --
  ed.BlockManager.add('table-3x3', {
    label: 'Tableau 3×3',
    category: 'Composants',
    content: `<table data-type="table" style="width:100%;border-collapse:collapse;">
      <thead>
        <tr>
          <th style="border:1px solid #ccc;padding:8px;background:#f0f0f0;">Col 1</th>
          <th style="border:1px solid #ccc;padding:8px;background:#f0f0f0;">Col 2</th>
          <th style="border:1px solid #ccc;padding:8px;background:#f0f0f0;">Col 3</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="border:1px solid #ccc;padding:8px;">A1</td>
          <td style="border:1px solid #ccc;padding:8px;">A2</td>
          <td style="border:1px solid #ccc;padding:8px;">A3</td>
        </tr>
        <tr>
          <td style="border:1px solid #ccc;padding:8px;">B1</td>
          <td style="border:1px solid #ccc;padding:8px;">B2</td>
          <td style="border:1px solid #ccc;padding:8px;">B3</td>
        </tr>
      </tbody>
    </table>`,
  });

  // -- Section document --
  ed.BlockManager.add('document-section', {
    label: 'Section document',
    category: 'Document',
    content: `<section data-type="document-section" style="margin-bottom:32px;">
      <h2 data-editable="text">Section titre</h2>
      <p data-editable="text">Contenu de la section. Modifiez ce texte selon vos besoins.</p>
    </section>`,
  });

  // -- Arch diagram --
  ed.BlockManager.add('arch-diagram', {
    label: 'Schéma archi',
    category: 'Composants',
    content: `<div data-type="arch-diagram" style="position:relative;min-height:200px;border:1px dashed #ccc;padding:16px;">
      <div data-type="arch-node" data-label="Frontend" data-shape="box"
           style="display:inline-block;border:2px solid #4a90d9;padding:8px 16px;border-radius:4px;background:#e8f0fe;margin:8px;">
        Frontend
      </div>
      <span style="font-size:24px;vertical-align:middle;">→</span>
      <div data-type="arch-node" data-label="API" data-shape="box"
           style="display:inline-block;border:2px solid #333;padding:8px 16px;border-radius:4px;background:#f5f5f5;margin:8px;">
        API
      </div>
    </div>`,
  });
}
