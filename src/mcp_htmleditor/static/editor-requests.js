/**
 * editor-requests.js: mcp-htmleditor (SPEC-0010, US-0055)
 *
 * The person's side of the request loop: the "Ask AI" panel that queues a
 * request for the current slide, and the always visible "Requests (n)" side
 * list with a Delete button per request.
 *
 * An IIFE: it reads no top level binding of editor.js and exposes no global.
 * Every string that comes from the record goes in through textContent, never
 * innerHTML (DEC-012): the agent's text is data, not markup.
 */
(function () {
  const askAiBtn     = document.getElementById('ask-ai-btn');
  const askAiPanel   = document.getElementById('ask-ai-panel');
  const askAiText    = document.getElementById('ask-ai-text');
  const askAiSlide   = document.getElementById('ask-ai-slide');
  const askAiQueue   = document.getElementById('ask-ai-queue');
  const askAiMessage = document.getElementById('ask-ai-message');
  const requestsHeading = document.getElementById('requests-heading');
  const requestsList    = document.getElementById('requests-list');

  const DELETE_FAILURE = 'Could not delete the request: ';

  let askAiRememberedSlide = null;   // data-id of the slide of the last click or selection (DEC-013)
  let requestsFetchCount   = 0;      // a late answer of an older fetch is dropped
  const requestsAttached   = new WeakSet();

  /* ---------- the current slide (DEC-013) ---------- */

  function requestsFrameDocument() {
    const frame = document.getElementById('content-frame');
    try {
      return frame ? frame.contentDocument : null;
    } catch (e) {
      return null;
    }
  }

  function requestsSlideIdOf(node) {
    const element = node && node.nodeType !== 1 ? node.parentElement : node;
    const slide = element && element.closest ? element.closest('[data-type="slide"]') : null;
    return slide ? slide.getAttribute('data-id') : null;
  }

  function requestsRemember(node) {
    const id = requestsSlideIdOf(node);
    if (id) askAiRememberedSlide = id;
  }

  function requestsAttachListeners(doc) {
    if (!doc || requestsAttached.has(doc)) return;
    requestsAttached.add(doc);
    doc.addEventListener('click', (event) => requestsRemember(event.target));
    doc.addEventListener('selectionchange', () => {
      const selection = doc.getSelection();
      if (selection) requestsRemember(selection.anchorNode);
    });
  }

  /** The remembered slide if the document still has it, else the first slide, else null. */
  function askAiCurrentSlide() {
    const doc = requestsFrameDocument();
    if (!doc) return null;
    let first = null;
    for (const slide of doc.querySelectorAll('[data-type="slide"]')) {
      const id = slide.getAttribute('data-id');
      if (!id) continue;
      if (id === askAiRememberedSlide) return id;
      if (first === null) first = id;
    }
    return first;
  }

  function askAiRefreshSlide() {
    const id = askAiCurrentSlide();
    askAiSlide.textContent = 'Slide: ' + (id === null ? 'none' : id);
    return id;
  }

  /* ---------- the panel ---------- */

  /** The popover is wider than the side list: the list starts below it while it is open. */
  function requestsPlaceSide() {
    const bottom = askAiPanel.hidden ? 0 : Math.ceil(askAiPanel.getBoundingClientRect().bottom) + 6;
    document.getElementById('requests-side').style.setProperty('--requests-top', Math.max(bottom, 25) + 'px');
  }

  function askAiSetOpen(open) {
    askAiPanel.hidden = !open;
    requestsPlaceSide();
    askAiBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) askAiRefreshSlide();
  }

  function requestsShowMessage(text) {
    askAiMessage.textContent = text;
    if (askAiPanel.hidden) askAiSetOpen(true);
  }

  async function requestsPostJson(path, payload) {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    let data = null;
    try {
      data = await response.json();
    } catch (e) {
      data = null;
    }
    if (data && data.ok === true) return data;
    const error = data && typeof data.error === 'string' && data.error ? data.error : 'HTTP ' + response.status;
    throw new Error(error);
  }

  async function askAiSubmit() {
    if (askAiQueue.disabled) return;
    const slide = askAiRefreshSlide();
    askAiQueue.disabled = true;
    try {
      const data = await requestsPostJson('/requests', { instruction: askAiText.value, slide: slide });
      askAiText.value = '';
      requestsShowMessage('Request ' + data.request.id + ' queued');
      await requestsRefresh();
    } catch (error) {
      requestsShowMessage(error.message);
    } finally {
      askAiQueue.disabled = false;
    }
  }

  /* ---------- the side list ---------- */

  async function requestsDelete(id) {
    try {
      await requestsPostJson('/requests/delete', { id: id });
    } catch (error) {
      const text = error.message;
      requestsShowMessage(text.startsWith(DELETE_FAILURE) ? text : DELETE_FAILURE + text);
      return;
    }
    await requestsRefresh();
  }

  function requestsLineText(request) {
    const parts = [request.id, request.status, request.slide || '-', request.title];
    if (request.status === 'skipped' && request.reason) parts.push(request.reason);
    return parts.join(' ');
  }

  function requestsRenderLine(request) {
    const item = document.createElement('li');
    item.setAttribute('data-request-id', request.id);
    const text = document.createElement('span');
    text.className = 'request-text';
    text.textContent = requestsLineText(request);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'request-delete';
    button.textContent = 'Delete';
    button.addEventListener('click', () => requestsDelete(request.id));
    item.append(text, button);
    return item;
  }

  function requestsRender(snapshot) {
    requestsHeading.textContent = 'Requests (' + snapshot.pending + ')';
    requestsList.replaceChildren(...snapshot.requests.map(requestsRenderLine));
  }

  async function requestsRefresh() {
    const ticket = ++requestsFetchCount;
    try {
      const response = await fetch('/requests', { cache: 'no-store' });
      if (!response.ok) return;
      const snapshot = await response.json();
      if (ticket === requestsFetchCount && Array.isArray(snapshot.requests)) requestsRender(snapshot);
    } catch (e) {
      /* the connection notice of editor.js reports a lost server; the list keeps its last state */
    }
  }

  /* ---------- wiring ---------- */

  if (window.ResizeObserver) new ResizeObserver(requestsPlaceSide).observe(askAiPanel);
  askAiBtn.addEventListener('click', () => askAiSetOpen(askAiPanel.hidden));
  askAiQueue.addEventListener('click', askAiSubmit);

  const requestsFrame = document.getElementById('content-frame');
  if (requestsFrame) {
    requestsFrame.addEventListener('load', () => {
      requestsAttachListeners(requestsFrameDocument());
      if (!askAiPanel.hidden) askAiRefreshSlide();
    });
    requestsAttachListeners(requestsFrameDocument());
  }
  requestsRefresh();
})();
