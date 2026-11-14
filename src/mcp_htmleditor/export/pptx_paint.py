"""Painted PPTX finish of Breathe decks (SPEC-0023 FR-NEW-014 to FR-NEW-016, DEC-005 to DEC-007).

Breathe slides are absolute compositions on a background picture, which the flow engine of ``to_pptx`` can only
approximate. After the flowed build (kept as the degraded result), this module opens the deck in Playwright's
Chromium, measures every slide (``MEASURE_JS``, slide pixels) and repaints each PPTX slide from the measures:
the slide colour and background picture full bleed, every coloured box and border as a rectangle, every CSS
background picture (icons) and every ``<img>`` at its rendered box (``object-fit: cover`` cropped like the
browser), every text block as an editable text box with the browser's own line breaks, face, size, weight,
colour and letter spacing. The notes page written by ``_write_notes`` is kept: only the shapes are cleared.

Ported from the post export script of the Breathe source template (``breathe_pptx.py``, 2026-11-13), with: the
slide shown by the render's ``SHOW_SLIDE_JS``, any ``url()`` accepted (linked files read from ``file://``),
remote requests aborted, remote, missing and vector pictures skipped with the exporter's warnings.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import re
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Final
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Pt

from ..render.scripts import SHOW_SLIDE_JS
from ..tracing import trace_span
from .pptx_model import ExportReport
from .pptx_vectors import is_vector_src

logger = logging.getLogger(__name__)

PX: Final = 12700  # EMU per CSS px: the exporter maps 1 px to 1 pt
SLIDE_W: Final = 960
SLIDE_H: Final = 540
VIEWPORT: Final = {"width": 1600, "height": 1000}
TIMEOUT_MS: Final = 30_000
MISSING_EXECUTABLE: Final = "Executable doesn't exist"
REASON_MAX_CHARS: Final = 200
DEGRADED: Final = (
    "Breathe deck exported without the rendered finish ({reason}). Install the browser with: make install-browser"
)
NO_EXTRA: Final = "the render extra is not installed"
NO_CHROMIUM: Final = "Chromium is not installed"
UNHIDE_JS: Final = (
    "() => document.querySelectorAll('[data-type=\"slide\"]').forEach((s) => s.style.removeProperty('display'))"
)
FREEZE_CSS: Final = "*{animation:none!important;transition:none!important}.slide{scale:1!important}"
FACES: Final = {"serif": "Georgia", "sans-serif": "Trebuchet MS", "cursive": "Brush Script MT"}
REMOTE: Final = re.compile(r"^https?://")
CENTER_ALIGN: Final = frozenset({"center", "-webkit-center"})
RIGHT_ALIGN: Final = frozenset({"right", "end"})
BOLD_WEIGHT: Final = 600
OPAQUE: Final = 1

# Runs in the page: the paint list of one slide (outermost slides, by position), in paint order, in slide pixels.
MEASURE_JS: Final = r"""
(index) => {
  const slides = Array.from(document.querySelectorAll('[data-type="slide"]'))
    .filter((s) => !s.parentElement.closest('[data-type="slide"]'));
  const slide = slides[index];
  const S = slide.getBoundingClientRect();
  const px = (v) => parseFloat(v) || 0;
  const rgba = (c) => {
    const m = c && c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(parseFloat);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  };
  const urlOf = (bg) => { const m = bg && bg.match(/url\("?([^")]+)"?\)/); return m ? m[1] : null; };
  const rel = (x, y, w, h) => [x - S.left, y - S.top, w, h];
  const items = [];
  const scs = getComputedStyle(slide);
  items.push({kind: 'slide', color: rgba(scs.backgroundColor), image: urlOf(scs.backgroundImage)});
  const isInline = (el) => { const d = getComputedStyle(el).display; return d === 'inline' || d === 'contents'; };
  const hasOwnText = (el) => {
    for (const n of el.childNodes) {
      if (n.nodeType === 3 && n.data.trim()) return true;
      if (n.nodeType === 1 && n.tagName !== 'IMG' && isInline(n) && n.textContent.trim()) return true;
    }
    return false;
  };
  const styleOf = (el) => {
    const c = getComputedStyle(el);
    return {font: c.fontFamily, size: px(c.fontSize), weight: parseInt(c.fontWeight, 10) || 400,
            italic: c.fontStyle === 'italic', color: rgba(c.color),
            ls: c.letterSpacing === 'normal' ? 0 : px(c.letterSpacing), upper: c.textTransform === 'uppercase'};
  };
  function textItem(el, cs) {
    const words = [];
    let pending = false;
    function visit(node, st) {
      for (const n of node.childNodes) {
        if (n.nodeType === 3) {
          const re = /(\s+)|(\S+)/g;
          let m;
          while ((m = re.exec(n.data))) {
            if (m[1]) { pending = true; continue; }
            const r = document.createRange();
            r.setStart(n, m.index); r.setEnd(n, m.index + m[2].length);
            const rects = Array.from(r.getClientRects()).filter((q) => q.width > 0);
            if (!rects.length) continue;
            const prev = words.length ? words[words.length - 1] : null;
            // a visible gap (margin, padding of an inline element) counts as a space
            const gap = prev && !prev.br && Math.abs(rects[0].top - prev.top) < 2 && rects[0].left - prev.right > st.size * 0.2;
            words.push({t: m[2], s: st, top: rects[0].top, bottom: rects[0].bottom,
                        left: rects[0].left, right: rects[rects.length - 1].right,
                        sp: (pending || gap) && words.length > 0});
            pending = false;
          }
        } else if (n.nodeType === 1) {
          if (n.tagName === 'BR') { words.push({br: true}); pending = false; continue; }
          if (n.tagName === 'IMG' || !isInline(n)) continue;
          const c = getComputedStyle(n);
          if (c.display === 'none' || c.visibility === 'hidden') continue;
          visit(n, styleOf(n));
        }
      }
    }
    visit(el, styleOf(el));
    if (!words.filter((w) => !w.br).length) return null;
    const lines = [];
    let cur = null, lineTop = 0;
    for (const w of words) {
      if (w.br) { cur = null; continue; }
      // a new line starts when the word sits lower than half its own height under the line top
      if (!cur || w.top - lineTop > 0.5 * (w.bottom - w.top)) { cur = []; lines.push(cur); lineTop = w.top; w.sp = false; }
      cur.push(w);
    }
    const lh = cs.lineHeight === 'normal' ? px(cs.fontSize) * 1.2 : px(cs.lineHeight);
    const r = el.getBoundingClientRect();
    const cl = r.left + px(cs.borderLeftWidth) + px(cs.paddingLeft);
    const cr = r.right - px(cs.borderRightWidth) - px(cs.paddingRight);
    const ct = r.top + px(cs.borderTopWidth) + px(cs.paddingTop);
    const all = lines.flat();
    const left = Math.min(...all.map((w) => w.left)), right = Math.max(...all.map((w) => w.right));
    const first = lines[0];
    const firstTop = Math.min(...first.map((w) => w.top)), firstBottom = Math.max(...first.map((w) => w.bottom));
    const top = Math.max(ct, firstTop - (lh - (firstBottom - firstTop)) / 2);
    return {kind: 'text', align: cs.textAlign, lh: lh,
            box: rel(left, top, right - left, lines.length * lh), content: rel(cl, ct, cr - cl, 0),
            lines: lines.map((l) => l.map((w) => ({t: w.t, s: w.s, sp: w.sp})))};
  }
  function walk(el) {
    for (const ch of el.children) {
      if (['TEMPLATE', 'SCRIPT', 'STYLE'].includes(ch.tagName) || ch.hasAttribute('data-pptx-skip')) continue;
      if (ch.getAttribute('data-role') === 'speaker-notes') continue;
      const cs = getComputedStyle(ch);
      if (cs.display === 'none' || cs.visibility === 'hidden' || (cs.opacity !== '' && px(cs.opacity) === 0)) continue;
      if (isInline(ch)) continue;  // its text belongs to the parent block
      const r = ch.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) {
        const bl = px(cs.borderLeftWidth), br = px(cs.borderRightWidth), bt = px(cs.borderTopWidth), bb = px(cs.borderBottomWidth);
        const bg = rgba(cs.backgroundColor);
        const radius = px(cs.borderTopLeftRadius);
        const inner = rel(r.left + bl, r.top + bt, r.width - bl - br, r.height - bt - bb);
        if (bg && bg[3] > 0) items.push({kind: 'rect', box: inner, color: bg, radius});
        const img = urlOf(cs.backgroundImage);
        if (img) items.push({kind: 'pic', box: inner, src: img, fit: cs.backgroundSize === 'cover' ? 'cover' : 'fill'});
        const side = (w, style, color, box) => {
          const c = rgba(color);
          if (w > 0 && style !== 'none' && style !== 'hidden' && c && c[3] > 0) items.push({kind: 'rect', box, color: c, radius: 0});
        };
        side(bt, cs.borderTopStyle, cs.borderTopColor, rel(r.left, r.top, r.width, bt));
        side(bb, cs.borderBottomStyle, cs.borderBottomColor, rel(r.left, r.bottom - bb, r.width, bb));
        side(bl, cs.borderLeftStyle, cs.borderLeftColor, rel(r.left, r.top, bl, r.height));
        side(br, cs.borderRightStyle, cs.borderRightColor, rel(r.right - br, r.top, br, r.height));
        if (ch.tagName === 'IMG' && ch.currentSrc) {
          const x = r.left + bl + px(cs.paddingLeft), y = r.top + bt + px(cs.paddingTop);
          const w = r.width - bl - br - px(cs.paddingLeft) - px(cs.paddingRight);
          const h = r.height - bt - bb - px(cs.paddingTop) - px(cs.paddingBottom);
          items.push({kind: 'pic', box: rel(x, y, w, h), src: ch.currentSrc, fit: cs.objectFit,
                      natural: [ch.naturalWidth, ch.naturalHeight]});
        }
      }
      if (ch.tagName !== 'IMG' && hasOwnText(ch)) {
        const t = textItem(ch, cs);
        if (t) items.push(t);
      }
      walk(ch);
    }
  }
  walk(slide);
  return items;
}
"""


class PaintUnavailable(Exception):  # noqa: N818 - a reason, not an error the caller reports as such
    """The rendered finish cannot run; ``reason`` is the text of the degraded export warning."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def paint_presentation(prs: Any, html_path: Path, report: ExportReport) -> bool:
    """Repaint every slide of ``prs`` from the deck at ``html_path``; on failure keep the flowed slides and warn once.

    Returns True when the slides were painted. Time O(e) for e measured elements; the pictures are decoded once
    per item (python-pptx stores each distinct picture once).
    """
    count = len(prs.slides)
    with trace_span("export.pptx.paint", {"slide.count": count}) as span:
        try:
            pages = measure(html_path, count)
        except PaintUnavailable as exc:
            span.set_attribute("paint.degraded", True)
            report.warn(DEGRADED.format(reason=exc.reason))
            logger.warning("Breathe export degraded: %s", exc.reason)
            return False
        painter_base = html_path.resolve().parent
        items = 0
        for slide, page in zip(prs.slides, pages, strict=True):
            items += Painter(slide, report, painter_base).paint(page)
        span.set_attribute("paint.items", items)
    return True


def measure(html_path: Path, count: int) -> list[list[dict[str, Any]]]:
    """The paint list of the first ``count`` slides, measured in Chromium; ``PaintUnavailable`` when it cannot run.

    Runs in a worker thread of its own: Playwright's sync API refuses a thread that already holds an asyncio loop
    (an embedding application, a test session), and the export must not depend on its caller's thread.
    """
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="breathe-paint") as pool:
        return pool.submit(_measure_in_browser, html_path, count).result()


def _measure_in_browser(html_path: Path, count: int) -> list[list[dict[str, Any]]]:
    try:
        from playwright.sync_api import Error, sync_playwright  # noqa: PLC0415 - optional render extra
    except ImportError:
        raise PaintUnavailable(NO_EXTRA) from None
    try:
        with sync_playwright() as driver:
            try:
                browser = driver.chromium.launch()
            except Error as exc:
                if MISSING_EXECUTABLE in str(exc):
                    raise PaintUnavailable(NO_CHROMIUM) from None
                raise PaintUnavailable(f"Chromium could not start: {_first_line(exc)}") from None
            try:
                return _measure_pages(browser, html_path, count)
            finally:
                browser.close()
    except PaintUnavailable:
        raise
    except Exception as exc:
        raise PaintUnavailable(f"the render failed: {_first_line(exc)}") from None


def _measure_pages(browser: Any, html_path: Path, count: int) -> list[list[dict[str, Any]]]:
    page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
    page.set_default_timeout(TIMEOUT_MS)
    page.route(REMOTE, lambda route: route.abort())
    page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=TIMEOUT_MS)
    page.add_style_tag(content=FREEZE_CSS)
    page.evaluate("document.fonts.ready")
    found = page.evaluate(
        "() => Array.from(document.querySelectorAll('[data-type=\"slide\"]'))"
        ".filter((s) => !s.parentElement.closest('[data-type=\"slide\"]')).length"
    )
    if found != count:
        raise PaintUnavailable(f"the render failed: {found} slides rendered for {count} exported")
    pages = []
    for index in range(count):
        # SHOW_SLIDE_JS hides the other slides with an inline display: clear it first, or the next slide shown
        # keeps an inline "block" instead of its own (flex) display and its pushed or centred content moves.
        page.evaluate(UNHIDE_JS)
        page.evaluate(SHOW_SLIDE_JS, index)
        pages.append(page.evaluate(MEASURE_JS, index))
    return pages


def _first_line(exc: BaseException) -> str:
    lines = str(exc).strip().splitlines()
    return (lines[0] if lines else type(exc).__name__)[:REASON_MAX_CHARS]


def first_face(family: str) -> str:
    """The first face of a CSS ``font-family`` list, generic families mapped to the Breathe faces."""
    face = family.split(",", maxsplit=1)[0].strip().strip("'\"")
    return FACES.get(face, face)


def rgb(colour: Sequence[float]) -> RGBColor:
    return RGBColor(*(max(0, min(255, round(v))) for v in colour[:3]))


class Painter:
    """Repaints one PPTX slide from the measured HTML slide."""

    def __init__(self, slide: Any, report: ExportReport, base_dir: Path) -> None:
        self.slide = slide
        self.report = report
        self.base_dir = base_dir

    def paint(self, items: list[dict[str, Any]]) -> int:
        """Clear the slide's shapes, then draw the items in order; return how many were drawn."""
        tree = self.slide.shapes._spTree
        for shape in list(self.slide.shapes):
            tree.remove(shape._element)
        drawers = {"slide": self.background, "rect": self.rect, "pic": self.picture, "text": self.text}
        for item in items:
            drawers[item["kind"]](item)
        return len(items)

    @staticmethod
    def emu(box: Sequence[float]) -> tuple[int, int, int, int]:
        x, y, w, h = box
        return round(x * PX), round(y * PX), max(round(w * PX), 1), max(round(h * PX), 1)

    def background(self, item: dict[str, Any]) -> None:
        if item.get("color"):
            fill = self.slide.background.fill
            fill.solid()
            fill.fore_color.rgb = rgb(item["color"])
        if item.get("image"):
            self.picture({"box": [0, 0, SLIDE_W, SLIDE_H], "src": item["image"], "fit": "fill"})

    def rect(self, item: dict[str, Any]) -> None:
        x, y, w, h = self.emu(item["box"])
        radius = item.get("radius", 0)
        width, height = item["box"][2], item["box"][3]
        if radius and radius >= min(width, height) / 2 - 0.5:
            kind = MSO_SHAPE.OVAL
        elif radius:
            kind = MSO_SHAPE.ROUNDED_RECTANGLE
        else:
            kind = MSO_SHAPE.RECTANGLE
        shape = self.slide.shapes.add_shape(kind, x, y, w, h)
        if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
            shape.adjustments[0] = min(radius / min(width, height), 0.5)
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(item["color"])
        if item["color"][3] < OPAQUE:
            solid = shape._element.spPr.find(qn("a:solidFill"))
            colour = solid.find(qn("a:srgbClr")) if solid is not None else None
            if colour is not None:
                colour.append(colour.makeelement(qn("a:alpha"), {"val": str(round(item["color"][3] * 100000))}))
        shape.line.fill.background()
        style = shape._element.find(qn("p:style"))  # theme references bring a shadow and an outline
        if style is not None:
            shape._element.remove(style)

    def _source(self, src: str) -> io.BytesIO | str | None:
        """Bytes of a measured picture: a data URI, or a local file; remote, missing and vector pictures skipped."""
        if not src or is_vector_src(src):
            return None
        if src.startswith("data:"):
            header, _, payload = src.partition(",")
            if "base64" not in header:
                return None
            try:
                return io.BytesIO(base64.b64decode(payload, validate=False))
            except (binascii.Error, ValueError):
                self.report.warn("Image data URI illisible ignoree.")
                return None
        if REMOTE.match(src):
            self.report.warn(f"Image distante non telechargee: {src[:60]}")
            return None
        parsed = urlparse(src)
        path = Path(url2pathname(unquote(parsed.path))) if parsed.scheme == "file" else self.base_dir / src
        if not path.is_file():
            self.report.warn(f"Image introuvable, ignoree: {path}")
            return None
        return str(path)

    def picture(self, item: dict[str, Any]) -> None:
        source = self._source(item["src"])
        if source is None:
            return
        x, y, w, h = self.emu(item["box"])
        try:
            pic = self.slide.shapes.add_picture(source, x, y, w, h)
        except Exception as exc:
            self.report.warn(f"Image non inseree ({exc}): {item['src'][:40]}")
            return
        natural = item.get("natural")
        if item.get("fit") == "cover" and natural and natural[0] and natural[1]:
            box_ratio = item["box"][2] / item["box"][3]
            img_ratio = natural[0] / natural[1]
            if img_ratio > box_ratio:  # too wide: crop left and right
                pic.crop_left = pic.crop_right = (1 - box_ratio / img_ratio) / 2
            elif img_ratio < box_ratio:
                pic.crop_top = pic.crop_bottom = (1 - img_ratio / box_ratio) / 2

    def text(self, item: dict[str, Any]) -> None:
        bx, by, bw, bh = item["box"]
        cx, _cy, cw, _ch = item["content"]
        slack = max(bw * 0.08, 6)  # no wrap: a slightly wider face never breaks a line
        if item["align"] in CENTER_ALIGN:
            bw = max(bw, cw) + 2 * slack
            bx = cx + cw / 2 - bw / 2
            align = PP_ALIGN.CENTER
        elif item["align"] in RIGHT_ALIGN:
            right = bx + bw
            bw += slack
            bx = right - bw
            align = PP_ALIGN.RIGHT
        else:
            bw += slack
            align = PP_ALIGN.LEFT
        frame = self.slide.shapes.add_textbox(*self.emu([bx, by, bw, bh])).text_frame
        frame.word_wrap = False
        frame.auto_size = MSO_AUTO_SIZE.NONE
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
        frame.vertical_anchor = MSO_ANCHOR.TOP
        for index, line in enumerate(item["lines"]):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.alignment = align
            paragraph.line_spacing = Pt(item["lh"])
            paragraph.space_before = paragraph.space_after = Pt(0)
            for text, style in _runs(line):
                self._run(paragraph, text, style)

    @staticmethod
    def _run(paragraph: Any, text: str, style: dict[str, Any]) -> None:
        run = paragraph.add_run()
        run.text = text
        face = first_face(style["font"])
        font = run.font
        font.name = face
        font.size = Pt(style["size"])
        font.bold = style["weight"] >= BOLD_WEIGHT
        font.italic = style["italic"]
        if style["color"]:
            font.color.rgb = rgb(style["color"])
        properties = run._r.get_or_add_rPr()
        if style["ls"]:
            properties.set("spc", str(round(style["ls"] * 100)))
        for tag in ("a:ea", "a:cs"):  # same face for every script
            node = properties.find(qn(tag))
            if node is None:
                node = properties.makeelement(qn(tag), {})
                properties.append(node)
            node.set("typeface", face)


def _runs(line: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """Merge the words of one line into runs of the same style; spaces as measured, upper case applied."""
    runs: list[list[Any]] = []
    for word in line:
        text = (" " if word["sp"] else "") + (word["t"].upper() if word["s"]["upper"] else word["t"])
        if runs and runs[-1][1] == word["s"]:
            runs[-1][0] += text
        else:
            runs.append([text, word["s"]])
    return [(text, style) for text, style in runs]
