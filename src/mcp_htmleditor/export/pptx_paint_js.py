"""Page scripts of the painted PPTX export (SPEC-0024): the generic measure of one slide, in the browser.

``MEASURE_JS`` is charter agnostic: it reads computed styles and geometry only, never a class or a selector of a
template. It returns the paint list of one slide in paint order, every coordinate in the 960 x 540 point space of the
PPTX (the slide box scaled), as plain dictionaries consumed by the painter modules:

``slide`` (colour, gradient, image), ``rect`` (box, colour, gradient, radius per corner, uniform border, shadow,
opacity), ``pic`` (box, source, fit, natural size), ``raster`` (an ``<svg>``, ``<canvas>`` or vector ``<img>`` the
caller screenshots), ``text`` (lines of styled words, bullet), ``table`` (grid, cells).
"""

from __future__ import annotations

from typing import Final

# Copies the computed style of the ::before and ::after pseudo elements that draw something (a string, or a box with a
# background or a border) onto real spans, once, so the walk below measures them like any element.
PSEUDO_JS: Final = r"""
const PSEUDO_PROPS = ['display','position','left','right','top','bottom','width','height','margin-top','margin-right',
  'margin-bottom','margin-left','padding-top','padding-right','padding-bottom','padding-left','border-top-width',
  'border-right-width','border-bottom-width','border-left-width','border-top-style','border-right-style',
  'border-bottom-style','border-left-style','border-top-color','border-right-color','border-bottom-color',
  'border-left-color','border-top-left-radius','border-top-right-radius','border-bottom-right-radius',
  'border-bottom-left-radius','background-color','background-image','background-size','background-position',
  'background-repeat','color','font-family','font-size','font-weight','font-style','line-height','letter-spacing',
  'text-transform','text-align','opacity','transform','box-shadow','box-sizing','flex','align-self','vertical-align',
  'white-space','text-decoration-line','float'];
function materialisePseudo(slide) {
  if (!document.getElementById('pptx-pseudo-style')) {
    const style = document.createElement('style');
    style.id = 'pptx-pseudo-style';
    style.textContent = '[data-pptx-nb]::before{content:none!important}[data-pptx-na]::after{content:none!important}';
    document.head.appendChild(style);
  }
  for (const el of [slide, ...slide.querySelectorAll('*')]) {
    if (el.closest('[data-pptx-pseudo],svg,[data-role="speaker-notes"]')) continue;
    for (const which of ['::before', '::after']) {
      const ps = getComputedStyle(el, which);
      const m = ps.content.match(/^"((?:[^"\\]|\\.)*)"$/);
      if (!m) continue;
      const text = m[1].replace(/\\(.)/g, '$1');
      const bgc = ps.backgroundColor.match(/rgba?\(([^)]+)\)/);
      const bga = bgc ? (bgc[1].split(/[\s,\/]+/).filter(Boolean).map(parseFloat)[3] ?? 1) : 0;
      const framed = ['top', 'right', 'bottom', 'left'].some((s) => parseFloat(ps['border-' + s + '-width']) > 0
        && ps['border-' + s + '-style'] !== 'none');
      if (!text.trim() && !(bga > 0) && !framed && ps.backgroundImage === 'none') continue;
      const span = document.createElement('span');
      span.setAttribute('data-pptx-pseudo', '');
      for (const name of PSEUDO_PROPS) span.style.setProperty(name, ps.getPropertyValue(name));
      span.textContent = text;
      if (which === '::before') { el.insertBefore(span, el.firstChild); el.setAttribute('data-pptx-nb', ''); }
      else { el.appendChild(span); el.setAttribute('data-pptx-na', ''); }
    }
  }
}
"""

# Geometry and style helpers shared by the walk.
HELPERS_JS: Final = r"""
const px = (v) => parseFloat(v) || 0;
const rgba = (c) => {
  const m = c && c.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(parseFloat);
  return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
};
const urlOf = (bg) => { const m = bg && bg.match(/url\("?([^")]+)"?\)/); return m ? m[1] : null; };
const gradientOf = (bg) => (bg && /linear-gradient\(/.test(bg) ? bg : null);
const isInline = (el) => { const d = getComputedStyle(el).display; return d === 'inline' || d === 'contents'; };
const radiusOf = (cs, w, h) => ['TopLeft', 'TopRight', 'BottomRight', 'BottomLeft'].map((k) => {
  const v = cs['border' + k + 'Radius'];
  return v.indexOf('%') > 0 ? parseFloat(v) / 100 * Math.min(w, h) : px(v);
});
const sideOf = (cs, side) => ({w: px(cs['border' + side + 'Width']), style: cs['border' + side + 'Style'],
                               color: rgba(cs['border' + side + 'Color'])});
const drawn = (b) => b.w > 0 && b.style !== 'none' && b.style !== 'hidden' && b.color && b.color[3] > 0;
const opacityOf = (cs) => (cs.opacity === '' ? 1 : px(cs.opacity));
const effectiveOpacity = (el, stop) => {
  let o = 1;
  for (let n = el; n && n !== stop; n = n.parentElement) o *= opacityOf(getComputedStyle(n));
  return o;
};
const RASTER = new Set(['svg', 'canvas']);
const isRaster = (el) => RASTER.has(el.tagName.toLowerCase()) || (el.tagName === 'IMG'
  && /(^data:image\/svg|\.svg(\?|#|$))/i.test(el.currentSrc || el.src || ''));
"""

# Text of one block: words with their style and rectangles, grouped in the browser's own lines.
TEXT_JS: Final = r"""
const FACE_CACHE = new Map();
const PROBE = document.createElement('canvas').getContext('2d');
const probeWidth = (face, base) => { PROBE.font = '72px ' + face + ', ' + base; return PROBE.measureText('mmmmmmmmmmlliWQ@').width; };
const GENERIC = new Set(['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui', 'ui-sans-serif', 'ui-serif']);
// the first face of a font-family list the browser really has (a stack names fonts the machine may not ship)
function resolveFace(list) {
  if (FACE_CACHE.has(list)) return FACE_CACHE.get(list);
  let found = null;
  for (const raw of list.split(',')) {
    const face = raw.trim().replace(/^['"]|['"]$/g, '');
    if (!face) continue;
    const quoted = JSON.stringify(face);
    if (GENERIC.has(face) || face.startsWith('-')
        || probeWidth(quoted, 'monospace') !== probeWidth('monospace', 'monospace')
        || probeWidth(quoted, 'serif') !== probeWidth('serif', 'serif')) { found = face; break; }
  }
  FACE_CACHE.set(list, found || list);
  return found || list;
}
const styleOf = (el) => {
  const c = getComputedStyle(el);
  return {font: resolveFace(c.fontFamily), size: px(c.fontSize) * K.x, weight: parseInt(c.fontWeight, 10) || 400,
          italic: c.fontStyle === 'italic', color: rgba(c.color),
          ls: c.letterSpacing === 'normal' ? 0 : px(c.letterSpacing) * K.x, upper: c.textTransform === 'uppercase',
          under: c.textDecorationLine.indexOf('underline') >= 0, strike: c.textDecorationLine.indexOf('line-through') >= 0};
};
const hasOwnText = (el) => {
  for (const n of el.childNodes) {
    if (n.nodeType === 3 && n.data.trim()) return true;
    if (n.nodeType === 1 && !isRaster(n) && n.tagName !== 'IMG' && isInline(n) && n.textContent.trim()) return true;
  }
  return false;
};
const hasChipOrBlock = (cell) => Array.from(cell.querySelectorAll('*')).some((n) => {
  const c = getComputedStyle(n);
  if (c.display === 'none') return false;
  if (!isInline(n) && n.tagName !== 'BR') return true;
  return isRaster(n) || n.tagName === 'IMG' || (rgba(c.backgroundColor) || [0, 0, 0, 0])[3] > 0
    || ['Top', 'Right', 'Bottom', 'Left'].some((s) => drawn(sideOf(c, s)));
});
function bulletOf(el, cs) {
  if (cs.display !== 'list-item' || cs.listStyleType === 'none') return null;
  const mk = getComputedStyle(el, '::marker');
  let index = 1;
  const list = el.parentElement;
  if (list && list.tagName === 'OL') {
    const start = parseInt(list.getAttribute('start'), 10);
    index = (isNaN(start) ? 1 : start) + Array.from(list.children).filter((c) => c.tagName === 'LI').indexOf(el);
    if (el.hasAttribute('value')) index = parseInt(el.getAttribute('value'), 10) || index;
  }
  return {type: cs.listStyleType, color: rgba(mk.color) || rgba(cs.color), index: index};
}
function chipsOf(n, c, op, chips) {
  const bg = rgba(c.backgroundColor);
  const sides = ['Top', 'Right', 'Bottom', 'Left'].map((s) => sideOf(c, s));
  if (!((bg && bg[3] > 0) || sides.some(drawn))) return;
  const uniform = sides.every((b) => b.w === sides[0].w && b.color && sides[0].color && b.color.join() === sides[0].color.join());
  for (const q of n.getClientRects()) {
    chips.push({kind: 'rect', box: rel(q.left, q.top, q.width, q.height), color: bg, op: op,
                radius: radiusOf(c, q.width, q.height).map((v) => v * K.x),
                border: uniform && drawn(sides[0]) ? {w: sides[0].w * K.x, color: sides[0].color, style: sides[0].style} : null});
  }
}
function textItem(el, cs, op) {
  const words = [];
  const chips = [];
  let pending = false;
  function visit(node, st) {
    for (const n of node.childNodes) {
      if (n.nodeType === 3) {
        const re = /(\s+)|(\S+)/g;
        let m;
        while ((m = re.exec(n.data))) {
          if (m[1]) { pending = true; continue; }
          const r = document.createRange();
          r.setStart(n, m.index); r.setEnd(n, m.index + m[2].length);
          const rects = Array.from(r.getClientRects()).filter((q) => q.width > 0);
          if (!rects.length) continue;
          const prev = words.length ? words[words.length - 1] : null;
          const gap = prev && !prev.br && Math.abs(rects[0].top - prev.top) < 2 && rects[0].left - prev.right > st.size / K.x * 0.2;
          words.push({t: m[2], s: st, top: rects[0].top, bottom: rects[0].bottom,
                      left: rects[0].left, right: rects[rects.length - 1].right,
                      sp: (pending || gap) && words.length > 0});
          pending = false;
        }
      } else if (n.nodeType === 1) {
        if (n.tagName === 'BR') { words.push({br: true}); pending = false; continue; }
        if (n.tagName === 'IMG' || isRaster(n) || !isInline(n)) continue;
        const c = getComputedStyle(n);
        if (c.display === 'none' || c.visibility === 'hidden') continue;
        chipsOf(n, c, op, chips);
        visit(n, styleOf(n));
      }
    }
  }
  visit(el, styleOf(el));
  if (!words.filter((w) => !w.br).length) return null;
  const lines = [];
  let cur = null, lineTop = 0;
  for (const w of words) {
    if (w.br) { cur = null; continue; }
    if (!cur || w.top - lineTop > 0.5 * (w.bottom - w.top)) { cur = []; lines.push(cur); lineTop = w.top; w.sp = false; }
    cur.push(w);
  }
  const lh = cs.lineHeight === 'normal' ? px(cs.fontSize) * 1.2 : px(cs.lineHeight);
  const r = el.getBoundingClientRect();
  const cl = r.left + px(cs.borderLeftWidth) + px(cs.paddingLeft);
  const cr = r.right - px(cs.borderRightWidth) - px(cs.paddingRight);
  const ct = r.top + px(cs.borderTopWidth) + px(cs.paddingTop);
  const all = lines.flat();
  const left = Math.min(...all.map((w) => w.left)), right = Math.max(...all.map((w) => w.right));
  const first = lines[0];
  const firstTop = Math.min(...first.map((w) => w.top)), firstBottom = Math.max(...first.map((w) => w.bottom));
  const top = Math.max(ct, firstTop - (lh - (firstBottom - firstTop)) / 2);
  return {kind: 'text', align: cs.textAlign, lh: lh * K.y, op: op, bullet: bulletOf(el, cs), chips: chips,
          box: rel(left, top, right - left, lines.length * lh), content: rel(cl, ct, cr - cl, 0),
          lines: lines.map((l) => l.map((w) => ({t: w.t, s: w.s, sp: w.sp})))};
}
"""

# Native table: the grid is the union of the cell edges, so spans come out of the geometry.
TABLE_JS: Final = r"""
function tableItem(table, op) {
  const cells = Array.from(table.querySelectorAll('td, th')).filter((c) => c.closest('table') === table);
  if (!cells.length || cells.some(hasChipOrBlock)) return null;
  const edge = (v) => Math.round(v * 2) / 2;
  const xs = new Set(), ys = new Set();
  for (const c of cells) {
    const q = c.getBoundingClientRect();
    xs.add(edge(q.left)); xs.add(edge(q.right)); ys.add(edge(q.top)); ys.add(edge(q.bottom));
  }
  const gx = Array.from(xs).sort((a, b) => a - b), gy = Array.from(ys).sort((a, b) => a - b);
  const at = (list, v) => list.indexOf(edge(v));
  const fillOf = (c) => {
    for (let n = c; n && n !== table.parentElement; n = n.parentElement) {
      const bg = rgba(getComputedStyle(n).backgroundColor);
      if (bg && bg[3] > 0) return bg;
    }
    return null;
  };
  const out = [];
  for (const c of cells) {
    const q = c.getBoundingClientRect(), cs = getComputedStyle(c);
    const text = hasOwnText(c) ? textItem(c, cs, op) : null;
    const c0 = at(gx, q.left), c1 = at(gx, q.right), r0 = at(gy, q.top), r1 = at(gy, q.bottom);
    if (c0 < 0 || c1 <= c0 || r0 < 0 || r1 <= r0) return null;
    out.push({r: r0, c: c0, rs: r1 - r0, cs: c1 - c0, fill: fillOf(c), valign: cs.verticalAlign, text: text,
              pad: [px(cs.paddingLeft) * K.x, px(cs.paddingTop) * K.y, px(cs.paddingRight) * K.x, px(cs.paddingBottom) * K.y],
              borders: ['Top', 'Right', 'Bottom', 'Left'].map((s) => { const b = sideOf(cs, s);
                return drawn(b) ? {w: b.w * K.x, color: b.color, style: b.style} : null; })});
  }
  return {kind: 'table', op: op, box: rel(gx[0], gy[0], gx[gx.length - 1] - gx[0], gy[gy.length - 1] - gy[0]),
          cols: gx.slice(1).map((v, i) => (v - gx[i]) * K.x), rows: gy.slice(1).map((v, i) => (v - gy[i]) * K.y),
          cells: out};
}
"""

# The walk: one pass over the slide subtree in document order.
WALK_JS: Final = r"""
function boxItems(cs, r, op, items) {
  const bl = px(cs.borderLeftWidth), br = px(cs.borderRightWidth), bt = px(cs.borderTopWidth), bb = px(cs.borderBottomWidth);
  const bg = rgba(cs.backgroundColor);
  const radius = radiusOf(cs, r.width, r.height).map((v) => v * K.x);
  const rounded = radius.some((v) => v > 0);
  const sides = ['Top', 'Right', 'Bottom', 'Left'].map((s) => sideOf(cs, s));
  const uniform = sides.every((b) => b.w === sides[0].w && b.style === sides[0].style
    && b.color && sides[0].color && b.color.join() === sides[0].color.join());
  const framed = rounded && uniform && drawn(sides[0]);
  const gradient = gradientOf(cs.backgroundImage);
  const inner = rel(r.left + bl, r.top + bt, r.width - bl - br, r.height - bt - bb);
  const hasBg = bg && bg[3] > 0;
  const shadow = cs.boxShadow !== 'none' && cs.boxShadow.indexOf('inset') < 0 ? cs.boxShadow : null;
  if (hasBg || gradient || framed) {
    items.push({kind: 'rect', box: rounded ? rel(r.left, r.top, r.width, r.height) : inner, color: hasBg ? bg : null,
                gradient: gradient, radius: radius, op: op, shadow: hasBg || gradient ? shadow : null,
                border: framed ? {w: sides[0].w * K.x, color: sides[0].color, style: sides[0].style} : null});
  }
  const img = urlOf(cs.backgroundImage);
  if (img) {
    const bs = cs.backgroundSize;
    items.push({kind: 'pic', box: inner, src: img, op: op, position: cs.backgroundPosition,
                fit: bs === 'cover' ? 'cover' : bs === 'contain' ? 'contain' : 'fill'});
  }
  if (framed) return;
  const side = (b, box) => { if (drawn(b)) items.push({kind: 'rect', box: box, color: b.color, radius: [0, 0, 0, 0], op: op}); };
  side(sides[0], rel(r.left, r.top, r.width, bt));
  side(sides[2], rel(r.left, r.bottom - bb, r.width, bb));
  side(sides[3], rel(r.left, r.top, bl, r.height));
  side(sides[1], rel(r.right - br, r.top, br, r.height));
}
function pictureItem(ch, cs, r, op) {
  const bl = px(cs.borderLeftWidth), bt = px(cs.borderTopWidth);
  const x = r.left + bl + px(cs.paddingLeft), y = r.top + bt + px(cs.paddingTop);
  const w = r.width - bl - px(cs.borderRightWidth) - px(cs.paddingLeft) - px(cs.paddingRight);
  const h = r.height - bt - px(cs.borderBottomWidth) - px(cs.paddingTop) - px(cs.paddingBottom);
  return {kind: 'pic', box: rel(x, y, w, h), src: ch.currentSrc, fit: cs.objectFit, op: op,
          position: cs.objectPosition, natural: [ch.naturalWidth, ch.naturalHeight]};
}
function walk(el, items) {
  for (const ch of el.children) {
    if (['TEMPLATE', 'SCRIPT', 'STYLE', 'NOSCRIPT', 'BUTTON'].includes(ch.tagName) || ch.hasAttribute('data-pptx-skip')) continue;
    if (ch.getAttribute('data-role') === 'speaker-notes') continue;
    const cs = getComputedStyle(ch);
    if (cs.display === 'none' || cs.visibility === 'hidden' || opacityOf(cs) === 0) continue;
    const r = ch.getBoundingClientRect();
    const op = effectiveOpacity(ch, SLIDE.parentElement);
    if (isRaster(ch)) {
      if (r.width > 0 && r.height > 0) {
        const id = index + '-' + (RASTER_SEQ++);
        ch.setAttribute('data-pptx-raster', id);
        items.push({kind: 'raster', box: rel(r.left, r.top, r.width, r.height), rid: id, op: op,
                    alt: (ch.getAttribute('aria-label') || ch.getAttribute('alt') || ch.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 600)});
      }
      continue;
    }
    if (isInline(ch) && ch.tagName !== 'IMG') continue;  // its text belongs to the parent block
    if (r.width > 0 && r.height > 0) {
      boxItems(cs, r, op, items);
      if (ch.tagName === 'IMG' && ch.currentSrc) items.push(pictureItem(ch, cs, r, op));
      if (ch.tagName === 'TABLE') {
        const t = tableItem(ch, op);
        if (t) { items.push(t); continue; }
      }
    }
    if (ch.tagName !== 'IMG' && hasOwnText(ch)) {
      const t = textItem(ch, cs, op);
      if (t) { for (const chip of t.chips) items.push(chip); items.push(t); }
    }
    walk(ch, items);
  }
}
"""

_HEAD: Final = r"""
(index) => {
  const slides = Array.from(document.querySelectorAll('[data-type="slide"]'))
    .filter((s) => !s.parentElement.closest('[data-type="slide"]'));
  const SLIDE = slides[index];
  const S = SLIDE.getBoundingClientRect();
  const K = {x: 960 / S.width, y: 540 / S.height};
  const rel = (x, y, w, h) => [(x - S.left) * K.x, (y - S.top) * K.y, w * K.x, h * K.y];
  let RASTER_SEQ = 0;
"""

_TAIL: Final = r"""
  materialisePseudo(SLIDE);
  const items = [];
  const scs = getComputedStyle(SLIDE);
  let base = rgba(scs.backgroundColor);
  for (let n = SLIDE.parentElement; n && !(base && base[3] > 0); n = n.parentElement) base = rgba(getComputedStyle(n).backgroundColor);
  items.push({kind: 'slide', color: base, gradient: gradientOf(scs.backgroundImage), image: urlOf(scs.backgroundImage)});
  walk(SLIDE, items);
  const inside = (b) => b[0] < 960 && b[1] < 540 && b[0] + b[2] > 0 && b[1] + b[3] > 0;
  return items.filter((i) => i.kind === 'slide' || inside(i.box));
}
"""

MEASURE_JS: Final = _HEAD + PSEUDO_JS + HELPERS_JS + TEXT_JS + TABLE_JS + WALK_JS + _TAIL
