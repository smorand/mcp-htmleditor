# BL-0031: Render limits found while reviewing SPEC-0008 stories

Nature: FEAT
Origin: US-0061 and US-0065 reviews (SPEC-0008).

## Evidence

- US-0061: a first slide whose box starts below the 900 px viewport cannot be clipped (DEC-008 uses `bounding_box` as the clip):
  `Rendering failed: Page.screenshot: Clipped area is either empty or outside the resulting image`.
  Real decks have a header of about 50 px, so this is rare.
- US-0065: the `font` rule (spec: ignore only `sans-serif`, `serif`, `monospace`, `system-ui`) reports the standard system font stack
  `-apple-system, BlinkMacSystemFont` on macOS (`font slide-1: "-apple-system" is not available, fallback used`) and also
  `ui-sans-serif`, `cursive`, `emoji`.
- US-0065: a multi line script error message prints on several stdout lines; an empty `src` prints `image slide-6:  did not load`;
  the same missing image twice prints two identical lines.

## Proposal

Amend SPEC-0008 FR-NEW-003 (generic family list, one line per image source per slide, message normalisation) and DEC-008
(scroll the target into view before the clip). One small story each once the spec is amended.
