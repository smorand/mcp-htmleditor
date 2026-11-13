/**
 * editor-notes.js: mcp-htmleditor (SPEC-0022 FR-8)
 *
 * The speaker notes panel: #notes-btn toggles #notes-panel, a textarea bound to the current slide of the
 * framed deck. Typing writes <aside data-role="speaker-notes"> as a direct child of the slide (created when
 * missing, removed when empty, plain text through textContent), then schedules the normal save.
 * An IIFE; its one global is notesSync, called by editor.js when the visibility of the toolbar changes.
 * It reads editMode, isPresentation and scheduleSave of editor.js at call time.
 */
(function () {
  const notesBtn   = document.getElementById('notes-btn');
  const notesPanel = document.getElementById('notes-panel');
  const notesText  = document.getElementById('notes-text');
  const notesFrame = document.getElementById('content-frame');
  const SLIDE = '[data-type="slide"]';
  const ASIDE = 'aside[data-role="speaker-notes"]';

  let notesObserver = null;
  let notesSlide = null;   // the slide the textarea is bound to

  function notesDoc() {
    try { return notesFrame.contentDocument; } catch (e) { return null; }
  }

  function notesCurrentSlide(doc) {
    if (!doc) return null;
    return doc.querySelector(SLIDE + '.active, ' + SLIDE + '[data-fs-current]') || doc.querySelector(SLIDE);
  }

  function notesAsideOf(slide) {
    for (const child of slide.children) {
      if (child.matches(ASIDE)) return child;
    }
    return null;
  }

  /** Bind the textarea to the slide now current; never overwrite what the person is typing in it. */
  function notesBind() {
    const slide = notesCurrentSlide(notesDoc());
    if (slide === notesSlide) return;
    notesSlide = slide;
    const aside = slide ? notesAsideOf(slide) : null;
    notesText.value = aside ? aside.textContent : '';
    notesText.disabled = !slide;
  }

  function notesObserve() {
    if (notesObserver) notesObserver.disconnect();
    notesObserver = null;
    notesSlide = null;
    const doc = notesDoc();
    if (doc && doc.body && window.MutationObserver) {
      notesObserver = new MutationObserver(notesBind);
      notesObserver.observe(doc.body, {
        attributes: true, subtree: true, attributeFilter: ['class', 'data-fs-current'],
      });
    }
    notesBind();
  }

  function notesWrite() {
    const slide = notesSlide;
    if (!slide || !slide.isConnected) return;
    const value = notesText.value;
    let aside = notesAsideOf(slide);
    if (value.trim() === '') {
      if (aside) aside.remove();
    } else {
      if (!aside) {
        aside = slide.ownerDocument.createElement('aside');
        aside.setAttribute('data-role', 'speaker-notes');
        slide.appendChild(aside);
      }
      aside.textContent = value;
    }
    scheduleSave();
  }

  /** Visible only on a presentation in edit mode; the panel closes with the button. */
  function notesSync() {
    const show = isPresentation && editMode;
    notesBtn.style.display = show ? 'inline-flex' : 'none';
    if (!show) setOpen(false);
  }
  window.notesSync = notesSync;

  function setOpen(open) {
    notesPanel.hidden = !open;
    notesBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) notesBind();
  }

  notesBtn.addEventListener('click', () => setOpen(notesPanel.hidden));
  notesText.addEventListener('input', notesWrite);
  notesFrame.addEventListener('load', notesObserve);
  notesObserve();
})();
