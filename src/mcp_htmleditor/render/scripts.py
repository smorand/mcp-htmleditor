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

# The images of the presentation that did not load: inside a slide, ``complete`` and a ``naturalWidth`` of 0 (a
# viewBox only SVG has a non zero ``naturalWidth``). ``src`` is the attribute as written. Evaluate after ``load``.
IMAGES_JS: Final = """() => {
  const slides = Array.from(document.querySelectorAll('[data-type="slide"]'));
  const failed = [];
  for (const img of document.querySelectorAll('img')) {
    const slide = img.closest('[data-type="slide"]');
    if (!slide || !img.hasAttribute('src') || !img.complete || img.naturalWidth !== 0) continue;
    failed.push({ slide_index: slides.indexOf(slide), src: img.getAttribute('src') });
  }
  return failed;
}"""

# Shows the slide at ``idx`` (the index, never the id), then measures it: the content height, the elements outside
# the slide frame and the font names that are not installed. A name is installed when, once loaded, a probe text drawn
# with ``<name>, <base>`` is wider or narrower than with ``<base>`` alone for one of three base families
# (``document.fonts.check`` says true for any name, so it is not used).
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
  const generic = ['sans-serif', 'serif', 'monospace', 'system-ui'];
  const families = (el) => {
    const names = [];
    const pattern = /"([^"]*)"|'([^']*)'|([^,]+)/g;
    for (const m of getComputedStyle(el).fontFamily.matchAll(pattern)) {
      const name = (m[1] ?? m[2] ?? m[3]).trim();
      if (name && !generic.includes(name.toLowerCase())) names.push(name);
    }
    return names;
  };
  const probe = document.createElement('canvas').getContext('2d');
  const widthOf = (font) => {
    probe.font = font;
    return probe.measureText('mmmmmmmmmmlli 0123456789').width;
  };
  const bases = ['monospace', 'serif', 'sans-serif'];
  const installed = async (name) => {
    const raw = JSON.stringify(name);
    try { await document.fonts.load('72px ' + raw); } catch (e) { return false; }
    return bases.some((base) => widthOf('72px ' + raw + ',' + base) !== widthOf('72px ' + base));
  };
  const lists = new Map();
  const holders = [slide, ...slide.querySelectorAll('*')].filter(
    (el) => !['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE'].includes(el.tagName)
      && Array.from(el.childNodes).some((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim() !== '')
  );
  for (const el of holders) {
    const names = families(el);
    if (names.length > 0) lists.set(JSON.stringify(names), names);
  }
  const fonts = [];
  for (const names of lists.values()) {
    let found = false;
    for (const name of names) found = found || await installed(name);
    if (!found && !fonts.includes(names[0])) fonts.push(names[0]);
  }
  return { content, clipped, fonts };
}"""
)
