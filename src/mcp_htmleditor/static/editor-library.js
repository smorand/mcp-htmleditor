// Editor shell of the web library mode (SPEC-0025, DEC-038): prefixes the editor's own requests with the base of the
// presentation and keeps the frame reload under it. Loaded only by the shell the library serves; the editor scripts
// are untouched. No cookie, no storage. An answer that carries a `code` (denied, session_expired, DEC-040) is shown
// as the editor's only notice, in English, with no prefix; a quiet pause of the poll is never a lost connection.
(function () {
  const meta = document.querySelector('meta[name="editor-config"]');
  if (!meta) return;
  const config = JSON.parse(meta.content);
  const base = config.base;
  const EDITOR_PATHS = ['/content', '/status', '/requests', '/requests/delete', '/review/apply', '/arch-layout',
    '/export/pptx', '/download'];
  const nativeFetch = window.fetch.bind(window);
  const DENIED = 'Access denied.';
  const EXPIRED = 'Your session has expired. Sign in again to save.';
  let pollCode;

  window.fetch = async function (input, init) {
    if (typeof input !== 'string' || !EDITOR_PATHS.includes(input.split('?')[0])) return nativeFetch(input, init);
    const options = Object.assign({}, init);
    const headers = new Headers(options.headers);
    headers.set('X-Editor', '1');
    options.headers = headers;
    const response = await nativeFetch(base + input, options);
    let code;
    if (response.status === 401 || response.status === 403) {
      try {
        code = (await response.clone().json()).code;
      } catch (error) {
        code = undefined;
      }
    }
    window.__libraryCode = code;
    if (input.split('?')[0] === '/status') pollCode = code;
    return response;
  };

  if (config.readOnly) {
    // DEC-039: the editor's own listeners (loaded after this script) never see the key E or the deck's edit message.
    document.addEventListener('keydown', function (e) {
      if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || String(e.key).toLowerCase() !== 'e') return;
      e.preventDefault();
      e.stopImmediatePropagation();
    }, true);
    window.addEventListener('message', function (e) {
      const data = e.data;
      if (data && data.type === 'deck-key' && String(data.key).toLowerCase() === 'e') e.stopImmediatePropagation();
    }, true);
  }

  /** The HTML download goes through fetch: a refused or ended one never saves a page of the library as a file. */
  async function downloadHtml(event) {
    event.preventDefault();
    const response = await window.fetch('/download');
    if (response.status === 200) {
      const link = document.createElement('a');
      link.href = URL.createObjectURL(await response.blob());
      link.download = document.getElementById('toolbar-filename').textContent || 'presentation.html';
      link.click();
      URL.revokeObjectURL(link.href);
    } else if (window.__libraryCode === 'session_expired') {
      if (typeof hasPendingChanges !== 'undefined' && hasPendingChanges) showNotice('save-error', EXPIRED);
      else window.location.href = config.library + '/';
    } else if (window.__libraryCode === 'denied') {
      window.alert(DENIED);
    } else {
      window.alert(response.statusText || 'HTTP ' + response.status);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const showSaveErrorOriginal = window.showSaveError;
    window.showSaveError = function (text) {
      if (text === DENIED || text === EXPIRED) showNotice('save-error', text);
      else showSaveErrorOriginal(text);
    };
    const notePollFailureOriginal = window.notePollFailure;
    window.notePollFailure = function () {
      if (!pollCode) notePollFailureOriginal();
    };
    const nativeAlert = window.alert.bind(window);
    window.alert = function (message) {
      nativeAlert(String(message).endsWith(DENIED) ? DENIED : message);
    };
    const downloadButton = document.getElementById('download-btn');
    if (downloadButton) downloadButton.addEventListener('click', downloadHtml);
    // editor.js assigns the absolute path '/content-frame?...': on the content origin that would blank the deck.
    window.reloadFrame = function () {
      document.getElementById('content-frame').src = base + '/content-frame?' + Date.now();
    };
  });
})();
