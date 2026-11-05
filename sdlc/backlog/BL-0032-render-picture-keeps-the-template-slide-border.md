# BL-0032: A rendered Carbon slide keeps its 1 px template border

Nature: BUG
Origin: SPEC-0008 converge audit (US-0067).

## Evidence

FR-NEW-001 says the picture is the 960 x 540 slide element "with no border or shadow" and that "the slide's own markup and styles are not altered".
A Carbon slide has a 1 px `#e0e0e0` border in its own style (`templates/bootstrap/slides-empty.html:90`). It appears in the picture: pixels
(0, 0), (959, 0), (0, 539) and (959, 539) at scale 1 are (224, 224, 224). The box shadow falls outside the clip.
The two spec sentences conflict for a slide that styles its own border.

## Proposal

Decide by amending FR-NEW-001: either "the slide as styled" (keep the border, drop "no border") or hide the border and shadow of the target slide
for the capture (inline style on the target in the show script, DEC-007). Then one story with a pixel test on a Carbon deck.
