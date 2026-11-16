# BL-0049: Web library mode (slides.scm-platform.org)

Nature: FEAT
Origin: user request 2026-11-16 (publishing Lamya's two WCBIP decks, then generalising).

## What

A new way to run the product: a sign-in protected web library. After a Google sign-in the person sees the folders
they can access (home page), then the presentations of a folder, can upload and delete presentations according to
their role (Admin, RW, RO per folder), and opens a presentation in the full editor with every option of the local
mode (edit, full screen, presenter notes, download HTML and PPTX). The administrator (only seb.morand@gmail.com) has
a panel to create and delete folders and manage the emails and roles of each folder. Nothing is public. English
interface. Deployed at slides.scm-platform.org; the folder "WCBIP Melbourne Décembre 2026" is seeded with Lamya's two
decks. The local single-file mode stays unchanged.

## Why

Lamya needs a private link to her decks with the presenter window and the editor; the public static site has no
protection and no editing. Also answers BL-0019 (authentication beyond loopback) for this mode.

## Evidence

- One deck per process, no multi-user, no sign-in: `src/mcp_htmleditor/http_server.py:1118-1160`, `state.py:177-181`.
- No OAuth, cookie or session code exists in `src`.
- Credentials file `~/.credentials/scm-pwd-web.json` (project `scm-pwd`) has no redirect address for
  `slides.scm-platform.org`: to add in the Google console before deployment.

## Notes

Out of scope for now: create a deck from a template in the interface, rename, move between folders, several admins.
