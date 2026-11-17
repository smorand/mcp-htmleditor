# Web library pages: the design system (SPEC-0025, app-design)

The library pages (sign in, home, folder, administration, refusal pages) follow `~/projects/perso/app-design` (read its
`COMPONENTS.md` and `THEMING.md`). The editor page is not part of it and keeps its own look. Light and dark only.

## Pieces

- `static/library.css`: GENERATED, never edited by hand. `make sync-library-design` (`tools/sync_library_design.py`, `DESIGN=<css dir>`)
  takes the light and dark blocks of `tokens.css`, the shared `:root` tokens and `app.css` of the design system, drops every rule
  that names another theme (`green`, `carbon`), removes the `@import`, then appends `tools/library-additions.css` (the only file to
  edit: what the design system does not ship). Re run it when the design system changes.
- `static/theme.js`: loaded first, not deferred, so `data-theme` is set before the first paint: `localStorage` `library-theme`
  when it is `light` or `dark`, else the system's `prefers-color-scheme`. `library.js` toggles it (`[data-theme-toggle]`).
- `library/components.py`: `document()` (head, theme script, stylesheet, deferred script), the logo, the ridge, the Google mark.
  `library/icons.py`: the 24 by 24 outlines of the design system as inline SVG (`icon("name", "sm")`). No text lives in these two files.
- `library/pages.py`: every page and text (DEC-055). Pages use `_app_page` (bar + `main`) except sign in (`.auth`), refusal and unavailable
  (`.center-note`).

## Rules that come from the page policy

`default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:`: no `style` attribute, no inline script or style, no
external file, no font file (Inter and Fraunces fall back to the system fonts), no `<use href>` to a sprite (icons are inline). Colours only
through the tokens. `tests/test_library_design_*` fail on a `style=`, an absolute address or a console violation.

## Gallery

- Home: `ul.folders.cards.grid.g3 > li.card.hover.folder-card` (a tab drawn by `::before` gives the folder shape), a tile with the folder
  icon, the name as a stretched link (`a::after`), role badge and `N presentation(s)` (`FolderView.count`).
- Folder page: `ul.presentations.cards.grid.g3 > li.card.hover.pres-card`: `.cover` (the ridge, with `img src="/cover/<pid>"` over it),
  name link, `<time>`, size, `Delete` for writers. `library.js` hides a cover that answers 404 (error events are caught on the way down).
- `GET /cover/<pid>` (`VIEW`): `covers.first_cover` reads the first slide of the file as text and returns its largest raster `data:` picture
  (png, jpeg, webp, gif, at least 2000 base64 characters, at most 4 MiB), never an SVG. No rendering: the image has no Chromium.
  `Library.cover` caches by (mtime, size), 64 entries. An unknown presentation is the uniform `Access denied.` (DEC-023); none: `404`.
- One question dialog serves Replace and Delete; its first button is disabled and the dialog stays open until the request ends, so a double
  click never reaches the card under it.

## Tests

`visible_texts` (`library_support.py`) lists the page's own texts first and the bar's (`Administration`, `Sign out`) last. The controls
of every page start with the bar: `Switch theme`, `Sign out` (the theme button has no text, its name is its `aria-label`).
