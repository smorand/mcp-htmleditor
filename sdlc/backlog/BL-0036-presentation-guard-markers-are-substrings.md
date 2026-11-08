# BL-0036: The presentation guard markers and the BR-021 test are substring checks

Nature: DEBT (hint)
Origin: independent audit of SPEC-0016 (US-0101). Not changed by US-0101, recorded for a later story.

## Evidence

- `tests/test_presentation_templates_fullscreen.py:13` and `:51`: `MARKERS` (`:fullscreen`, `id="btn-present"`,
  `enterPresentation`, `exitPresentation`, `updateFullscreenScale`) are checked with `marker not in html`. A
  marker inside a comment, a string, or a longer identifier (`enterPresentationLater`) satisfies the guard while
  the deck has no working presenting mode; `HTML_COMMENT` exists in the file but the markers are checked on the
  raw text.
- `tests/test_skill_shipped.py:330` (BT-024, BR-021): the check is wording bound. It fails only on a sentence
  holding both `ibm-carbon` and `:fullscreen` or `plein écran`; a rephrased false claim ("le catalogue Carbon
  ne gère pas le mode présentation") passes.

## Proposal

Guard: strip comments, then match the markers structurally (a `:fullscreen` selector inside a `<style>`, an
element with `id="btn-present"`, function declarations of the three names in a `<script>`), or rely on the
behavioural e2e tests (`tests/test_reference_decks_present_e2e.py`) as the real gate and keep the guard as a
cheap pre-check. BR-021: assert the positive statement the skill must carry instead of the absence of one
phrasing.
