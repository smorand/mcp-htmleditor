// Editor shell of the web library mode (SPEC-0025, DEC-038): prefixes the editor's own requests with the base of the
// presentation and keeps the frame reload under it. Loaded only by the shell the library serves; the editor scripts
// are untouched. No cookie, no storage.
(function () {
  const meta = document.querySelector('meta[name="editor-config"]');
  if (!meta) return;
  const config = JSON.parse(meta.content);
  const base = config.base;
  const EDITOR_PATHS = ['/content', '/status', '/requests', '/requests/delete', '/review/apply', '/arch-layout',
    '/export/pptx', '/download'];
  const nativeFetch = window.fetch.bind(window);

  window.fetch = async function (input, init) {
    if (typeof input !== 'string' || !EDITOR_PATHS.includes(input.split('?')[0])) return nativeFetch(input, init);
    const options = Object.assign({}, init);
    const headers = new Headers(options.headers);
    headers.set('X-Editor', '1');
    options.headers = headers;
    const response = await nativeFetch(base + input, options);
    if (response.status === 401 || response.status === 403) {
      try {
        window.__libraryCode = (await response.clone().json()).code;
      } catch (error) {
        window.__libraryCode = undefined;
      }
    }
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

  document.addEventListener('DOMContentLoaded', function () {
    // editor.js assigns the absolute path '/content-frame?...': on the content origin that would blank the deck.
    window.reloadFrame = function () {
      document.getElementById('content-frame').src = base + '/content-frame?' + Date.now();
    };
  });
})();
