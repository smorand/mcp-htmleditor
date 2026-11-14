# SPEC-0022: Keyboard shortcuts, requests panel toggle, presenter mode and speaker notes

> Id: SPEC-0022 | Nature: FEAT | Status: specified (user request, 5 points) | Depends on: SPEC-0017 (pointer)

## Requirements

- FR-1 A toolbar button `#requests-toggle` opens and closes the `#requests-side` panel (Requests + AI suggestions).
  Closed by default. `aria-expanded` and `aria-controls="requests-side"` kept in sync. The label shows the pending
  count: `Requests (n)`. Second click closes.
- FR-2 Key `P`/`p` toggles the presentation pointer (same effect as `L`, which stays). No effect in edit mode.
- FR-3 Key `F`/`f` toggles fullscreen presentation (enter, or leave when already in).
- FR-4 Key `E`/`e` toggles edit mode (editor only).
- FR-5 Keys work (a) in a deck opened directly as a file (`file://`, no server) for `F`, `P`, `S`, and (b) through
  the editor server, whether keyboard focus is in the iframe or in the editor shell, for `E`, `F`, `P`, `S`.
  In a deck opened directly, `E` has nothing to toggle (no editor): it does nothing. Keys are ignored with Ctrl, Meta
  or Alt held, and when focus is in an input, textarea, select or contenteditable element.
- FR-6 Speaker notes. Stored in the slide: `<aside data-role="speaker-notes">plain text, newlines kept</aside>` as a
  direct child of the `[data-type="slide"]` element. Hidden on screen and in print by a rule in the deck block
  (`[data-role="speaker-notes"]{display:none !important}`, an attribute selector, never a class, the PPTX exporter
  only reads class rules). The PPTX export writes them into the slide's notes page.
- FR-7 Presenter mode. Key `S`/`s` (and `window.togglePresenter()`, and the editor toolbar button `#presenter-btn`)
  opens a presenter window (`window.open`, name `deck-presenter`) showing: the current slide, the next slide (or an
  "end" marker), the speaker notes of the current slide (large, font size adjustable), slide counter, elapsed timer
  with reset, wall clock, previous/next buttons; keys `ArrowLeft/Right/Up/Down`, Space, Home, End navigate. Pressing
  `S` again (or closing the window) closes it. The main window follows the presenter and the reverse. Works from `file://`.
- FR-8 Editing notes: in the editor, in edit mode on a presentation, a `#notes-btn` button ("Notes") toggles a
  `#notes-panel` docked at the bottom with a textarea bound to the current slide's notes. Typing writes the aside
  (created when missing, removed when emptied) and schedules the normal save. An open presenter window shows the change live.

## Contract between deck, presenter and editor (postMessage, target origin `*`, sender checked by `event.source`)

- deck block (new, markers `<!-- deck-presenter:begin -->` / `<!-- deck-presenter:end -->`, source
  `templates/bootstrap/slides-empty.html`, synced by `tools/sync_deck_pointer.py` generalized to both blocks, checked by
  `make check-generated`) defines `window.togglePresenter()`, `window.openPresenter()`, `window.closePresenter()`,
  `window.isPresenterOpen()` and the key handler for `F P S E`. The three existing per template handlers keep the `L` line; the
  `f` line is removed from the 11 templates (the block owns `F`). `P` also calls the deck's `togglePointer()`.
- deck to presenter: `{type:'deck-state', index, total, titles:[...], notes:[...]}` on open, on every slide change
  (MutationObserver on the slides' `class`/`data-fs-current`) and on every notes change.
- presenter to deck: `{type:'deck-cmd', cmd:'next'|'prev'|'goto'|'close', index?}`; the deck calls its own
  `navigate(±1)` / `goToSlide(i)`.
- deck to editor shell (when framed): `{type:'deck-key', key:'e'}` for `E`; shell checks `event.source === frame.contentWindow`.
- Slide previews in the presenter: two iframes built with `srcdoc` from the deck's own HTML (+ `<base href>`), name
  `deck-preview`; an injected script shows only slide N, hides the chrome, scales it to fit, and follows
  `{type:'preview-goto', index}` messages. In a `deck-preview` window the block installs no handler and opens nothing.
- The editor iframe `sandbox` gains `allow-popups allow-popups-to-escape-sandbox`.

## Acceptance (each is a test)

FR-1 toggle open/close/aria/count; FR-2..FR-4 each key on and off, upper and lower case, ignored in a textarea and
with Ctrl; FR-5 through `file://` page and through `serve_deck`, focus in iframe and in shell; FR-6 hidden, survives a save
round trip, PPTX notes text equals the aside text; FR-7 popup opens, shows notes and next slide title, navigation both
ways, `S` closes; FR-8 typing in the textarea changes the file on disk and the open presenter; all 11 templates carry the block
(guard test). `make check` passes.

## Amendment 2026-11-14: shortcuts help

- Editor shell: an icon button `#help-btn` (SVG, title and aria-label "Raccourcis clavier") sits at the far right of the toolbar, after the
  DOCX and PPTX buttons. It toggles `#help-panel` (role dialog, `aria-expanded` and `aria-controls` kept in sync; Escape, a second click and
  a click outside close it). The table lists Deck, Editor, Presenter window keys and the Requests, Notes and Ask AI buttons.
- Key `?` (`event.key === '?'`, any layout) toggles it, with the same filters as the other keys (ignored in input, textarea, select,
  contenteditable and with Ctrl, Meta or Alt). A framed deck posts `{type:'deck-key', key:'?'}`; the shell checks `event.source`.
- A deck opened alone shows its own overlay `#deck-help` on `?` (ids only, hidden in print, Esc or a second `?` closes); framed, the deck
  block shows none. The presenter window help gains the `L` pointer line and the `?` entry.
- Tests: `tests/test_help_shortcuts_e2e.py`.

## Amendment 2026-11-14: icon toolbar, tooltips, download

- Every control of the black toolbar is an icon without visible text (Ask AI, Édition, undo, redo, Present, Pointeur, Présentateur, Notes,
  Requests, PPTX, DOCX, slide and block actions, Download, help). Ids are unchanged; each has an `aria-label` equal to its tooltip name.
  `Requests (n)` moved to the corner badge `#requests-badge` (`(n)`) and to the `aria-label`. `#edit-mode-btn` keeps `aria-pressed` and its dot.
- The native `title` is removed from these controls. A shared `#tb-tip` shows `data-tip` and an optional `data-keys` (kbd) below the control
  after exactly 1 s (CSS `transition-delay`) of hover or `:focus-visible`; it hides at once on leave, blur, click and Escape, never overflows the
  right edge, and has `pointer-events: none`.
- New `GET /download`: the loaded file unmodified as an attachment under its own name (ASCII `filename` plus `filename*`), `no-store`, no state
  write, same gates as `/status`, 404 without a file. The `#download-btn` anchor sits just before `#help-btn`, which stays last.
- The help panel keeps its Buttons group and gains the Download line. Tests: `tests/test_toolbar_icons_e2e.py`.
