# SPEC-0008 design issues

## 2026-11-03: ISSUE-001, E2E-012 cannot pass with "the scroll height of the slide element"

**Problem.** FR-NEW-003 defines `overflow` as "the scroll height of the slide element, rounded to the nearest
pixel, is greater than 540". E2E-012 puts a `height:700px` block in the body of an Euro-Information slide and
expects `overflow slide-4: content is <N>px tall, the slide is 540px` with N at least 700 and no `clipped` line.
In the real EI template the slide body clips its own content, so the slide element never reports it. The two
statements contradict each other on the shipped template.

**Evidence (measured, Chromium via Playwright 1.62, 1280x720, only the target slide `active`, on
`templates/reference/slides/example-ei-complete.html` slide-1 with `<div style="height:700px">` as first child of
`.slide-body`):**

- `slide.scrollHeight` = 540, `slide.clientHeight` = 540, `getBoundingClientRect().height` = 540
- `.slide-body.scrollHeight` = 1010, `.slide-body.clientHeight` = 370, computed `overflow` = `hidden`
- template CSS: `.slide-body { flex:1; overflow:hidden; }` (`templates/bootstrap/slides-ei-empty.html:158`) and
  `.slide { overflow:hidden }` (`:82`).

Quoted spec: "`overflow`: the scroll height of the slide element, rounded to the nearest pixel, is greater than 540:
`content is 612px tall, the slide is 540px`" (FR-NEW-003) and "E2E-012 ... one line `overflow slide-4: content is
<N>px tall, the slide is 540px` where `<N>` is an integer of at least 700 ... no `clipped` line appears".

A literal implementation reports `report: OK` for E2E-012. The product goal in Section 1 (content cut off silently)
is the clipping done by `.slide-body`, which the literal measure cannot see.

A second consequence: with the literal measure the 700px block's bottom is beyond the frame by more than 1 pixel
and "the slide does not already report `overflow`", so a `clipped` line for the block would appear, which E2E-012
forbids. Both sides of E2E-012 depend on the same missing definition.

**Needed.** One definition of the measured height that includes content clipped by descendants.

**Recommendation.** Amend FR-NEW-003 `overflow`: "the content height of the slide is the largest of the slide's
own scroll height and, for every descendant whose computed `overflow-y` is `hidden`, `clip` or `auto`, its top
offset from the slide top plus its scroll height; `overflow` is reported when that value, rounded to the nearest
pixel, is greater than 540, and the message shows that value". For the measured case this gives the body offset plus 1010,
which is more than 1010 and so at least 700. The `clipped` rule keeps its text ("when the slide does not already report `overflow`").
Default if no answer: none; the design waits for the amended text.

Resolved 2026-11-03 by the amendment of FR-NEW-003 (spec commit on main).
