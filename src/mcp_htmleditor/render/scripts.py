"""Page scripts of the render (SPEC-0008 DEC-010, DEC-022): the spec measures transcribed as JavaScript.

Both are evaluated in the live page; the presentation file is never written.
"""

from __future__ import annotations

from typing import Final

# Shows the slide at index ``idx`` alone and waits for its animations to finish.
SHOW_SLIDE_JS: Final = """async (idx) => {
  const slides = Array.from(document.querySelectorAll('[data-type="slide"]'));
  slides.forEach((slide, i) => {
    slide.classList.toggle('active', i === idx);
    if (i !== idx) slide.style.setProperty('display', 'none', 'important');
  });
  const target = slides[idx];
  if (getComputedStyle(target).display === 'none') target.style.setProperty('display', 'block');
  document.getAnimations().forEach((animation) => {
    try { animation.finish(); } catch (error) { animation.cancel(); }
  });
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}"""

# Shows the slide at ``idx`` (the index, never the id), then measures it: the content height and the elements
# outside the slide frame. ``fonts`` stays empty until the font problems exist.
MEASURE_SLIDE_JS: Final = (
    """async (idx) => {
  const show = """
    + SHOW_SLIDE_JS
    + """;
  await show(idx);
  const slide = Array.from(document.querySelectorAll('[data-type="slide"]'))[idx];
  const frame = slide.getBoundingClientRect();
  const rendered = Array.from(slide.querySelectorAll('*')).filter(
    (el) => el.getClientRects().length > 0 && getComputedStyle(el).display !== 'none'
  );
  let content = slide.scrollHeight;
  for (const d of rendered) {
    if (!['hidden', 'clip', 'auto'].includes(getComputedStyle(d).overflowY)) continue;
    content = Math.max(content, d.getBoundingClientRect().top - frame.top + d.scrollHeight);
  }
  content = Math.round(content);
  const selector = (el) => {
    const classes = (el.getAttribute('class') || '').split(/\\s+/).filter(Boolean);
    return [el.tagName.toLowerCase(), ...classes].join('.');
  };
  const clipped = [];
  const reported = [];
  for (const el of rendered) {
    const box = el.getBoundingClientRect();
    if (box.width === 0 && box.height === 0) continue;
    if (reported.some((parent) => parent.contains(el))) continue;
    const outside = box.left < frame.left - 1 || box.right > frame.right + 1 || box.top < frame.top - 1
      || (content <= 540 && box.bottom > frame.bottom + 1);
    if (!outside) continue;
    reported.push(el);
    clipped.push(selector(el));
  }
  return { content, clipped, fonts: [] };
}"""
)
