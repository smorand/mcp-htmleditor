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

  snapshotForUndo();
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
  snapshotForUndo();
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
