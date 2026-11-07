/* ============================================================
   Text width bar (SPEC-0015)
   ============================================================
   A thin bar of the editor's own page (#width-bar), laid over the frame on
   the right edge of the text block under the pointer. It is never inserted
   into the framed document, so nothing of it can reach the saved file.

   Dragging it previews the width through the element's style object, which
   rewrites the whole style attribute (#0F62FE becomes rgb(...), url(...) gets
   quotes). The preview therefore never reaches a save: every serialization of
   the framed document runs inside withWidthPreviewSuspended(), and the saved
   style is rebuilt as text from the attribute as it was before the drag and
   written with setAttribute('style', text).
   ============================================================ */
const WIDTH_MIN = 80;
const WIDTH_MAX = 1280;
const WIDTH_STEP = 10;
const WIDTH_STEP_SHIFT = 50;
const WIDTH_BLOCKS = 'p, h1, h2, h3, h4, h5, h6, li, blockquote, figcaption, [data-editable~="text"]';
const WIDTH_ZONE = '[data-editable~="text"]';
// Layout tables (role="presentation", as in mails) hold text; data tables do not.
const WIDTH_EXCLUDED = 'img, picture, svg, video, canvas, table:not([role="presentation"]), '
  + '[data-type="arch-node"], [data-type="arch-edge"], [data-type="gantt-task"], [data-type="annotation"], '
  + '#_mcp_format_bar, #_mcp_insert_bar, ._mcp_drag_handle, '
  + '#_editor_ctx_host';

let widthBlock = null; // text block the bar is shown on
let widthDrag = null;  // {block, originalStyle, startWidth, startX, ratio, value, moved, pointerId}
let widthBarDoc = null; // framed document the hover listener is attached to

/* ── Style text (pure, no DOM) ────────────────────────────── */

/** Trimmed non empty declarations; a ';' inside (...), '...' or "..." (backslash escapes honoured) is not a separator. */
function splitStyleDeclarations(text) {
  const declarations = [];
  if (!text) return declarations;
  let current = '';
  let depth = 0;
  let quote = null;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quote) {
      current += c;
      if (c === '\\' && i + 1 < text.length) current += text[++i];
      else if (c === quote) quote = null;
    } else if (c === '"' || c === "'") {
      quote = c; current += c;
    } else if (c === '(') {
      depth++; current += c;
    } else if (c === ')') {
      depth = Math.max(0, depth - 1); current += c;
    } else if (c === ';' && depth === 0) {
      declarations.push(current); current = '';
    } else {
      current += c;
    }
  }
  declarations.push(current);
  return declarations.map(d => d.trim()).filter(d => d !== '');
}

/** Property name of one declaration: text before its first ':', trimmed, lower case. */
function styleDeclarationName(declaration) {
  const colon = declaration.indexOf(':');
  return (colon < 0 ? declaration : declaration.slice(0, colon)).trim().toLowerCase();
}

/** The declarations of `text` other than max-width, verbatim and in order. */
function styleOtherDeclarations(text) {
  return splitStyleDeclarations(text).filter(d => styleDeclarationName(d) !== 'max-width');
}

/** True when the text holds a max-width declaration, whatever its unit. */
function styleHasWidth(text) {
  return splitStyleDeclarations(text).some(d => styleDeclarationName(d) === 'max-width');
}

/** Others kept verbatim and in order, every max-width dropped, `max-width:${px}px` appended, joined with '; '. */
function styleWithWidth(text, px) {
  return styleOtherDeclarations(text).concat(`max-width:${px}px`).join('; ');
}

/** Others kept verbatim and in order, every max-width dropped, joined with '; '; null when none is left. */
function styleWithoutWidth(text) {
  const others = styleOtherDeclarations(text);
  return others.length ? others.join('; ') : null;
}

/* ── Text block under the pointer ─────────────────────────── */

/** Innermost paragraph, heading, list item, quotation, caption or zone holding `target`, laid out as a block. */
function widthBlockAt(doc, target) {
  if (!editMode || !target) return null;
  if (document.fullscreenElement || doc.fullscreenElement || overlay.style.display === 'flex') return null;
  let el = target.nodeType === Node.ELEMENT_NODE ? target : target.parentElement;
  if (!el || el.closest(WIDTH_EXCLUDED)) return null;
  const view = doc.defaultView;
  while (el && el.closest(WIDTH_ZONE)) {
    if (el.matches(WIDTH_BLOCKS)) {
      const display = view.getComputedStyle(el).display;
      if (!display.startsWith('inline') && display !== 'contents') {
        return el.getBoundingClientRect().width > 0 ? el : null;
      }
    }
    el = el.parentElement;
  }
  return null;
}

/* ── The bar ──────────────────────────────────────────────── */

function widthBarElement() { return document.getElementById('width-bar'); }

/** Lay the bar over the frame on the block's right edge, as tall as the block, inside the window. */
function widthBarPlace(block) {
  const bar = widthBarElement();
  if (!bar) return;
  const frameRect = frame.getBoundingClientRect();
  const rect = block.getBoundingClientRect();
  bar.hidden = false;
  const left = Math.min(frameRect.left + rect.right, window.innerWidth - bar.offsetWidth);
  bar.style.left = left + 'px';
  bar.style.top = (frameRect.top + rect.top) + 'px';
  bar.style.height = rect.height + 'px';
}

function widthBarShow(block) {
  widthBlock = block;
  widthBarPlace(block);
}

function widthBarHide() {
  widthBlock = null;
  const bar = widthBarElement();
  if (bar) bar.hidden = true;
  widthReadoutHide();
}

function widthReadoutShow(value) {
  const readout = document.getElementById('width-readout');
  if (!readout) return;
  readout.textContent = `${value} px`;
  readout.hidden = false;
}

function widthReadoutHide() {
  const readout = document.getElementById('width-readout');
  if (readout) readout.hidden = true;
}

/** The bar's block is gone, hidden or off the document (slide change, reload): hide; otherwise follow it. */
function widthBarFollow() {
  const block = widthBlock;
  if (!block || widthDrag) return;
  if (!block.isConnected || block.getBoundingClientRect().width === 0) widthBarHide();
  else widthBarPlace(block);
}

function widthPointInRect(x, y, rect) {
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

/** The pointer left the framed document: hide, unless it went onto the bar (shell coordinates of the event). */
function onWidthFramePointerLeave(e) {
  if (widthDrag || !widthBlock) return;
  const frameRect = frame.getBoundingClientRect();
  const barRect = widthBarElement().getBoundingClientRect();
  if (!widthPointInRect(frameRect.left + e.clientX, frameRect.top + e.clientY, barRect)) widthBarHide();
}

/** The pointer left the bar: hide, unless it went back onto the block. */
function onWidthBarPointerLeave(e) {
  if (widthDrag || !widthBlock) return;
  const frameRect = frame.getBoundingClientRect();
  const rect = widthBlock.getBoundingClientRect();
  if (!widthPointInRect(e.clientX - frameRect.left, e.clientY - frameRect.top, rect)) widthBarHide();
}

/** Called by onFrameLoad(): a new document never starts with the bar shown. A drag is dropped without touching
    its block, which belongs to the document that is gone; nothing is saved. */
function widthBarOnFrameLoad() {
  widthDrag = null;
  widthBarHide();
}

/** Called by pollStatus() when it shows the update overlay: the agent is writing, a drag is cancelled, no bar. */
function widthBarOnAgentUpdate() {
  widthDragCancel();
  widthBarHide();
}

/** True while the bar is pressed: pollStatus() then leaves an external write for the release save's conflict. */
function widthDragActive() {
  return widthDrag !== null;
}

/** Hover on the framed document: the bar follows the text block under the pointer, synchronously. */
function onWidthFramePointerMove(e) {
  if (widthDrag) return;
  const block = widthBlockAt(e.currentTarget, e.target);
  if (block) widthBarShow(block);
  else widthBarHide();
}

/** Called at the end of injectEditMode(doc). */
function widthBarAttach(doc) {
  if (widthBarDoc && widthBarDoc !== doc) widthFrameListeners(widthBarDoc, 'removeEventListener');
  widthBarDoc = doc;
  widthFrameListeners(doc, 'addEventListener');
}

/** Add or remove the listeners of the framed document (the same functions, so a second add is a no-op). */
function widthFrameListeners(doc, method) {
  doc[method]('pointermove', onWidthFramePointerMove);
  doc.documentElement[method]('pointerleave', onWidthFramePointerLeave);
  doc[method]('scroll', widthBarFollow, true);
  doc[method]('click', widthBarFollow);
  doc[method]('keyup', widthBarFollow);
}

/** Called in removeEditMode(doc): listener removed, drag cancelled, bar hidden. */
function widthBarDetach(doc) {
  widthFrameListeners(doc, 'removeEventListener');
  if (widthBarDoc === doc) widthBarDoc = null;
  widthDragCancel();
  widthBarHide();
}

/* ── Drag ─────────────────────────────────────────────────── */

/** Put the style attribute text back exactly, or remove the attribute when it was absent. */
function widthStyleRestore(block, text) {
  if (text === null) block.removeAttribute('style');
  else block.setAttribute('style', text);
}

/** Width at the press plus the pointer's travel, in slide pixels, stepped and kept within the bounds. */
function widthDragValue(drag, clientX, single) {
  const raw = drag.startWidth + (clientX - drag.startX) / drag.ratio;
  const stepped = single ? Math.round(raw) : Math.round(raw / WIDTH_STEP) * WIDTH_STEP;
  return Math.min(WIDTH_MAX, Math.max(WIDTH_MIN, stepped));
}

function onWidthBarPointerDown(e) {
  if (e.button !== 0 || !widthBlock) return;
  e.preventDefault();
  const bar = e.currentTarget;
  bar.focus();
  bar.setPointerCapture(e.pointerId);
  const block = widthBlock;
  const view = block.ownerDocument.defaultView;
  const ratio = block.offsetWidth ? block.getBoundingClientRect().width / block.offsetWidth : 1;
  widthDrag = {
    block,
    originalStyle: block.getAttribute('style'),
    startWidth: parseFloat(view.getComputedStyle(block).width),
    startX: e.clientX,
    ratio: ratio || 1,
    value: null,
    moved: false,
    pointerId: e.pointerId,
  };
}

function onWidthBarPointerMove(e) {
  const drag = widthDrag;
  if (!drag || e.pointerId !== drag.pointerId) return;
  if (e.clientX !== drag.startX) drag.moved = true;
  if (!drag.moved) return;
  drag.value = widthDragValue(drag, e.clientX, e.altKey);
  drag.block.style.setProperty('max-width', drag.value + 'px');
  widthReadoutShow(drag.value);
  widthBarPlace(drag.block);
}

function onWidthBarPointerUp(e) {
  const drag = widthDrag;
  if (!drag || e.pointerId !== drag.pointerId) return;
  widthDrag = null;
  widthReadoutHide();
  if (!drag.moved || drag.value === null) return;
  widthStyleRestore(drag.block, drag.originalStyle);
  widthChange(drag.block, styleWithWidth(drag.originalStyle, drag.value));
  widthBarPlace(drag.block);
}

/** pointercancel, or the capture lost without a pointerup (pointerup ends the drag first): cancel. */
function onWidthBarPointerInterrupted(e) {
  if (widthDrag && e.pointerId === widthDrag.pointerId) widthDragCancel();
}

/** Interrupted drag: the text is back at its width before the drag, nothing saved. */
function widthDragCancel() {
  const drag = widthDrag;
  if (!drag) return;
  widthDrag = null;
  widthReadoutHide();
  if (drag.moved) widthStyleRestore(drag.block, drag.originalStyle);
}

/** One width change: original text back, undo snapshot, new text, then the normal save. */
function widthCommit(block, originalStyle, text) {
  widthStyleRestore(block, originalStyle);
  snapshotForUndo();
  widthStyleRestore(block, text);
  markPending();
  saveContent();
}

/* ── Keyboard and reset ───────────────────────────────────── */

/** Apply `text` (null: no style attribute) as one width change, unless the style text would not change. */
function widthChange(block, text) {
  const originalStyle = block.getAttribute('style');
  if (text === originalStyle) return;
  widthCommit(block, originalStyle, text);
  widthBarPlace(block);
}

/** Give the template's width back: drop max-width; a text without one is left alone (no rebuild). */
function widthReset(block) {
  const originalStyle = block.getAttribute('style');
  if (!styleHasWidth(originalStyle)) return;
  widthChange(block, styleWithoutWidth(originalStyle));
}

/** The bar's block when a key or double click may act on it: shown, still in the document, no drag running. */
function widthActionBlock() {
  if (widthDrag || !widthBlock || !widthBlock.isConnected) return null;
  return widthBlock;
}

/** Right and Left step the width on the slide by 10 (50 with Shift); Delete and Backspace reset. Undo and redo
    shortcuts go to the editor's own handler, which listens on the framed document only (FR-009). Other keys untouched. */
function onWidthBarKeyDown(e) {
  if ((e.ctrlKey || e.metaKey) && 'zZyY'.includes(e.key) && e.key.length === 1) {
    handleUndoRedoKeydown(e);
    return;
  }
  const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
  const reset = e.key === 'Delete' || e.key === 'Backspace';
  if (!step && !reset) return;
  e.preventDefault();
  const block = widthActionBlock();
  if (!block) return;
  if (reset) {
    widthReset(block);
    return;
  }
  const view = block.ownerDocument.defaultView;
  const current = Math.round(parseFloat(view.getComputedStyle(block).width));
  const value = Math.min(WIDTH_MAX, Math.max(WIDTH_MIN, current + step * (e.shiftKey ? WIDTH_STEP_SHIFT : WIDTH_STEP)));
  widthChange(block, styleWithWidth(block.getAttribute('style'), value));
}

function onWidthBarDoubleClick(e) {
  e.preventDefault();
  const block = widthActionBlock();
  if (block) widthReset(block);
}

/** Run `fn` with the original style text in place of a drag preview, then re-apply the preview; return fn(). */
function withWidthPreviewSuspended(fn) {
  const drag = widthDrag;
  if (!drag || !drag.moved || drag.value === null) return fn();
  widthStyleRestore(drag.block, drag.originalStyle);
  try {
    return fn();
  } finally {
    drag.block.style.setProperty('max-width', drag.value + 'px');
  }
}

function initWidthBar() {
  const bar = widthBarElement();
  if (!bar) return;
  bar.addEventListener('pointerdown', onWidthBarPointerDown);
  bar.addEventListener('pointermove', onWidthBarPointerMove);
  bar.addEventListener('pointerup', onWidthBarPointerUp);
  bar.addEventListener('pointercancel', onWidthBarPointerInterrupted);
  bar.addEventListener('lostpointercapture', onWidthBarPointerInterrupted);
  bar.addEventListener('keydown', onWidthBarKeyDown);
  bar.addEventListener('dblclick', onWidthBarDoubleClick);
  bar.addEventListener('pointerleave', onWidthBarPointerLeave);
  window.addEventListener('resize', widthBarFollow);
}

initWidthBar();
