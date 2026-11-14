#!/usr/bin/env python3
"""Measure how faithful the PPTX export is to the HTML slide, for every presentation template (SPEC-0024 phase 1).

For each presentation under ``templates/``: render every slide with the product's render (960x540, scale 1),
export the deck, convert it with ``soffice`` to PDF and ``pdftoppm`` to 960x540 PNG, then score each slide.
It measures, it does not gate: the exit code is 0 unless a tool failed (``--min-score`` is the later gate).

Score definition (all in 0..1, 1 is identical):
    visual = 0.7 * ssim + 0.3 * (1 - histogram_distance)
    ssim: mean structural similarity of 8x8 blocks of the two grayscale pictures downscaled to 480x270
    histogram_distance: half the L1 distance of two normalised colour histograms (4 levels per channel, 64 bins)
Text recall: share of the distinct words of the HTML slide text (speaker notes excluded) found in the words of
the PPTX slide shapes (text frames, table cells, groups). 1 when the HTML slide has no word.
Editable ratio: shapes that are not pictures divided by all shapes (0 for a slide without shape).
Overflow: a shape with text whose box leaves the slide by more than 1 %.

Usage:
    python tools/pptx_fidelity.py [--out DIR] [--only NAME[,NAME]] [--min-score X] [--jobs N] [--reference slide|canvas]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import fmean
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Tag
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = REPO / "templates"
WIDTH, HEIGHT = 960, 540
SMALL = (480, 270)
BLOCK = 8
SSIM_WEIGHT = 0.7
HIST_WEIGHT = 0.3
HIST_LEVELS = 4
C1 = (0.01 * 255) ** 2
C2 = (0.03 * 255) ** 2
OVERFLOW_TOLERANCE = 0.01
FLATTENED_AREA = 0.9
SOFFICE_TIMEOUT = 300
PRESENTATION_MARK = re.compile(r'<html[^>]*data-doc-type="presentation"')
WORD = re.compile(r"\w+")
SKIP_TAGS = ("script", "style", "template", "noscript")
NOTES_ROLE = "speaker-notes"


@dataclass(slots=True)
class SlideResult:
    """Measures of one slide."""

    slide: str
    score: float = 0.0
    ssim: float = 0.0
    histogram: float = 0.0
    text_recall: float = 1.0
    shapes: int = 0
    pictures: int = 0
    tables: int = 0
    text_boxes: int = 0
    editable_ratio: float = 0.0
    overflow: bool = False
    empty: bool = False
    flattened: bool = False
    html_words: int = 0
    missing_words: list[str] = field(default_factory=list)
    side_by_side: str = ""


@dataclass(slots=True)
class TemplateResult:
    """Measures of one template."""

    template: str
    path: str
    slides: list[SlideResult] = field(default_factory=list)
    export_warnings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0
    error: str = ""

    @property
    def mean_score(self) -> float:
        return fmean(s.score for s in self.slides) if self.slides else 0.0

    @property
    def mean_recall(self) -> float:
        return fmean(s.text_recall for s in self.slides) if self.slides else 0.0

    @property
    def worst(self) -> SlideResult | None:
        return min(self.slides, key=lambda s: s.score, default=None)


# ---------------------------------------------------------------------------
# Pure functions: score
# ---------------------------------------------------------------------------


def to_reference(image: Image.Image) -> Image.Image:
    """RGB picture of the reference size, transparency flattened on white."""
    rgba = image.convert("RGBA")
    base = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    base.alpha_composite(rgba)
    rgb = base.convert("RGB")
    return rgb if rgb.size == (WIDTH, HEIGHT) else rgb.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def ssim(first: Image.Image, second: Image.Image) -> float:
    """Mean SSIM of non overlapping 8x8 blocks of both pictures in grayscale at 480x270, clamped to 0..1."""
    left = first.convert("L").resize(SMALL, Image.Resampling.BOX).tobytes()
    right = second.convert("L").resize(SMALL, Image.Resampling.BOX).tobytes()
    width, height = SMALL
    total = 0.0
    count = 0
    for top in range(0, height - BLOCK + 1, BLOCK):
        for start in range(0, width - BLOCK + 1, BLOCK):
            a: list[int] = []
            b: list[int] = []
            for row in range(top, top + BLOCK):
                offset = row * width + start
                a.extend(left[offset : offset + BLOCK])
                b.extend(right[offset : offset + BLOCK])
            total += _block_ssim(a, b)
            count += 1
    return max(0.0, min(1.0, total / count))


def _block_ssim(a: list[int], b: list[int]) -> float:
    n = len(a)
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    var_a = sum((x - mean_a) ** 2 for x in a) / n
    var_b = sum((y - mean_b) ** 2 for y in b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True)) / n
    numerator = (2 * mean_a * mean_b + C1) * (2 * cov + C2)
    denominator = (mean_a**2 + mean_b**2 + C1) * (var_a + var_b + C2)
    return numerator / denominator


def histogram(image: Image.Image) -> list[float]:
    """Normalised colour histogram, 4 levels per channel (64 bins)."""
    data = image.convert("RGB").resize(SMALL, Image.Resampling.BOX).tobytes()
    shift = 8 - (HIST_LEVELS.bit_length() - 1)
    bins = [0] * HIST_LEVELS**3
    for red, green, blue in zip(data[0::3], data[1::3], data[2::3], strict=True):
        bins[((red >> shift) * HIST_LEVELS + (green >> shift)) * HIST_LEVELS + (blue >> shift)] += 1
    total = sum(bins)
    return [value / total for value in bins]


def histogram_distance(first: Image.Image, second: Image.Image) -> float:
    """Half the L1 distance of the colour histograms: 0 identical, 1 disjoint."""
    return sum(abs(x - y) for x, y in zip(histogram(first), histogram(second), strict=True)) / 2


def visual_score(first: Image.Image, second: Image.Image) -> tuple[float, float, float]:
    """Return ``(combined, ssim, histogram similarity)`` of two pictures; identical pictures give 1."""
    one, two = to_reference(first), to_reference(second)
    structure = ssim(one, two)
    colour = 1 - histogram_distance(one, two)
    return SSIM_WEIGHT * structure + HIST_WEIGHT * colour, structure, colour


def words_of(text: str) -> set[str]:
    """Distinct lower case words of ``text``."""
    return set(WORD.findall(text.lower()))


def text_recall(html_words: set[str], pptx_words: set[str]) -> tuple[float, list[str]]:
    """Share of ``html_words`` present in ``pptx_words`` and the missing ones (sorted); 1 for no word."""
    if not html_words:
        return 1.0, []
    missing = sorted(html_words - pptx_words)
    return 1 - len(missing) / len(html_words), missing


def slide_text(tag: Tag) -> str:
    """Visible text of an HTML slide: no script, style, template, hidden element or speaker notes."""
    soup = BeautifulSoup(str(tag), "html.parser")
    for node in soup.find_all(SKIP_TAGS):
        node.decompose()
    for node in soup.find_all(attrs={"data-role": NOTES_ROLE}):
        node.decompose()
    for node in soup.find_all(hidden=True):
        node.decompose()
    for node in soup.find_all(style=re.compile(r"display\s*:\s*none")):
        node.decompose()
    return soup.get_text(" ")


def is_overflowing(box: tuple[int, int, int, int], slide_size: tuple[int, int]) -> bool:
    """True when a box leaves the slide by more than the tolerance (1 % of the slide side)."""
    left, top, width, height = box
    slide_w, slide_h = slide_size
    tol_x, tol_y = slide_w * OVERFLOW_TOLERANCE, slide_h * OVERFLOW_TOLERANCE
    return left < -tol_x or top < -tol_y or left + width > slide_w + tol_x or top + height > slide_h + tol_y


# ---------------------------------------------------------------------------
# PPTX inspection
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PptxSlideFacts:
    """What python-pptx sees on one slide."""

    shapes: int = 0
    pictures: int = 0
    tables: int = 0
    text_boxes: int = 0
    words: set[str] = field(default_factory=set)
    overflow: bool = False
    flattened: bool = False


def inspect_pptx(path: Path) -> list[PptxSlideFacts]:
    """One ``PptxSlideFacts`` per slide of ``path``."""
    from pptx import Presentation

    deck = Presentation(str(path))
    slide_w, slide_h = int(deck.slide_width or 1), int(deck.slide_height or 1)
    result = []
    for slide in deck.slides:
        facts = PptxSlideFacts()
        for shape in slide.shapes:
            _inspect_shape(shape, facts, slide_w, slide_h)
        result.append(facts)
    return result


def _inspect_shape(shape: Any, facts: PptxSlideFacts, slide_w: int, slide_h: int) -> None:
    if shape.shape_type == 6 and hasattr(shape, "shapes"):  # MSO_SHAPE_TYPE.GROUP
        for child in shape.shapes:
            _inspect_shape(child, facts, slide_w, slide_h)
        return
    facts.shapes += 1
    left, top, width, height = (int(v or 0) for v in (shape.left, shape.top, shape.width, shape.height))
    if shape.shape_type == 13:  # PICTURE
        facts.pictures += 1
        if width * height >= FLATTENED_AREA * slide_w * slide_h:
            facts.flattened = True
    text = ""
    if getattr(shape, "has_table", False) and shape.has_table:
        facts.tables += 1
        text = " ".join(cell.text for row in shape.table.rows for cell in row.cells)
    elif getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        text = shape.text_frame.text
    if text.strip():
        facts.text_boxes += 1
        facts.words |= words_of(text)
        if is_overflowing((left, top, width, height), (slide_w, slide_h)):
            facts.overflow = True


def editable_ratio(facts: PptxSlideFacts) -> float:
    """Shapes that are not pictures over all shapes; 0 for no shape."""
    return (facts.shapes - facts.pictures) / facts.shapes if facts.shapes else 0.0


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def find_presentations(root: Path = TEMPLATES) -> dict[str, Path]:
    """Every presentation file under ``root``, keyed by file stem, sorted."""
    found: dict[str, Path] = {}
    for path in sorted(root.rglob("*.html")):
        if PRESENTATION_MARK.search(path.read_text(encoding="utf-8")[:4000]):
            found[path.stem] = path
    return found


def render_slides(path: Path, work: Path, reference: str = "slide") -> list[tuple[str, Path]]:
    """Render every slide to 960x540; return ``(slide id, png)``.

    ``reference="canvas"`` is the product picture (``render_deck``: a 960x540 clip anchored at the slide corner, so
    a slide larger or smaller than 960x540 is cropped or padded). ``"slide"`` (default) is the whole slide box,
    scaled to 960x540, which is what the PPTX slide has to match.
    """
    from mcp_htmleditor.deck import load_deck, slide_id

    deck = load_deck(str(path))
    ids = [slide_id(tag) or f"slide-{i}" for i, tag in enumerate(deck.slides)]
    if reference == "slide":
        return _render_slide_boxes(path, work, ids)
    from mcp_htmleditor.render.service import render_deck

    pictures = []
    for index, name in enumerate(ids):
        outcome = render_deck(str(path), slide=name, scale="1")
        if outcome.path is None:
            raise RuntimeError(f"render gave no picture for {name}")
        target = work / f"{index + 1:02d}-html.png"
        shutil.copyfile(outcome.path, target)  # the render dir drops stale pictures of this file at each call
        pictures.append((name, target))
    return pictures


def _render_slide_boxes(path: Path, work: Path, ids: list[str]) -> list[tuple[str, Path]]:
    from mcp_htmleditor.render.scripts import SHOW_SLIDE_JS
    from mcp_htmleditor.render.service import SLIDE_SELECTOR, _in_browser, _open_page

    def work_in(browser: Any) -> list[tuple[str, Path]]:
        pictures = []
        for index, name in enumerate(ids):
            page, _ = _open_page(browser, str(path), 1.0)
            page.evaluate(SHOW_SLIDE_JS, index)
            target = work / f"{index + 1:02d}-html.png"
            page.locator(SLIDE_SELECTOR).nth(index).screenshot(path=str(target), animations="disabled")
            with Image.open(target) as shot:
                to_reference(shot).save(target)
            page.context.close()
            pictures.append((name, target))
        return pictures

    return _in_browser(work_in)


def export_deck(path: Path, target: Path) -> list[str]:
    """Export with the product's export; return the export warnings."""
    from mcp_htmleditor.deck.tools import export_file

    return list(export_file(str(path), "pptx", str(target)).warnings)


FONT_DIRS = (
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts",
    "~/Library/Fonts",
    "/usr/share/fonts",
)
# Faces the templates name but this machine does not ship, mapped to the closest installed one (harness only, H1);
# an alias only applies when the face itself is missing.
FONT_SUBSTITUTES = {"IBM Plex Sans": "Helvetica Neue", "Segoe UI": "Helvetica Neue", "IBM Plex Mono": "Menlo"}


def fontconfig_text(cache_dir: Path) -> str:
    """A self contained fontconfig file: the system font dirs, a cache inside ``cache_dir``, the substitutions.

    Without it the Homebrew soffice runs with an empty font config (``no <cachedir> elements``) and embeds a
    serif for every face (H1 of the SPEC-0024 baseline).
    """
    dirs = "".join(f"<dir>{d}</dir>" for d in FONT_DIRS)
    aliases = "".join(
        f'<alias binding="same"><family>{name}</family><accept><family>{real}</family></accept></alias>'
        for name, real in FONT_SUBSTITUTES.items()
    )
    return (
        '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>'
        f"{dirs}<cachedir>{cache_dir}</cachedir>{aliases}</fontconfig>"
    )


def soffice_environment(work: Path) -> dict[str, str]:
    """The process environment of soffice with the harness fontconfig (everything stays under ``work``)."""
    config = work / "fonts.conf"
    config.write_text(fontconfig_text(work / "fontcache"), encoding="utf-8")
    return {**os.environ, "FONTCONFIG_FILE": str(config)}


def rasterize(pptx: Path, work: Path) -> list[Path]:
    """PPTX to PDF (soffice) to 960x540 PNG pages (pdftoppm); return the pages in order."""
    profile = work / "lo-profile"
    command = [
        "soffice",
        f"-env:UserInstallation=file://{profile}",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(work),
        str(pptx),
    ]
    subprocess.run(command, check=True, capture_output=True, timeout=SOFFICE_TIMEOUT, env=soffice_environment(work))
    pdf = work / f"{pptx.stem}.pdf"
    prefix = work / "pptx"
    ppm = ["pdftoppm", "-png", "-r", "72", "-scale-to-x", str(WIDTH), "-scale-to-y", str(HEIGHT), str(pdf), str(prefix)]
    subprocess.run(ppm, check=True, capture_output=True, timeout=SOFFICE_TIMEOUT)
    return sorted(work.glob("pptx-*.png"))


def side_by_side(left: Image.Image, right: Image.Image, target: Path) -> None:
    """Write ``left | right`` as one PNG."""
    canvas = Image.new("RGB", (WIDTH * 2 + 8, HEIGHT), (255, 0, 255))
    canvas.paste(to_reference(left), (0, 0))
    canvas.paste(to_reference(right), (WIDTH + 8, 0))
    canvas.save(target)


def measure_template(name: str, path: Path, out: Path, reference: str = "slide") -> TemplateResult:
    """Run the whole pipeline for one template."""
    from mcp_htmleditor.deck import load_deck

    started = time.monotonic()
    result = TemplateResult(name, str(path.relative_to(REPO)))
    folder = out / name
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    try:
        html_pictures = render_slides(path, folder, reference)
        pptx = folder / f"{name}.pptx"
        result.export_warnings = export_deck(path, pptx)
        pages = rasterize(pptx, folder)
        facts = inspect_pptx(pptx)
        _score_slides(result, load_deck(str(path)).slides, (html_pictures, pages, facts), folder)
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
    result.seconds = time.monotonic() - started
    return result


def _score_slides(
    result: TemplateResult,
    tags: tuple[Tag, ...],
    measured: tuple[list[tuple[str, Path]], list[Path], list[PptxSlideFacts]],
    folder: Path,
) -> None:
    html_pictures, pages, facts = measured
    if not (len(html_pictures) == len(pages) == len(facts)):
        result.warnings.append(
            f"count mismatch: {len(html_pictures)} html slides, {len(facts)} pptx slides, {len(pages)} pdf pages"
        )
    for index, (name, html_png) in enumerate(html_pictures):
        slide = SlideResult(name)
        if index < len(pages):
            with Image.open(html_png) as html_image, Image.open(pages[index]) as page_image:
                slide.score, slide.ssim, slide.histogram = visual_score(html_image, page_image)
                target = folder / f"{index + 1:02d}-{_safe(name)}-side.png"
                side_by_side(html_image, page_image, target)
                slide.side_by_side = str(target)
        fact = facts[index] if index < len(facts) else PptxSlideFacts()
        html_words = words_of(slide_text(tags[index]))
        slide.html_words = len(html_words)
        slide.text_recall, slide.missing_words = text_recall(html_words, fact.words)
        slide.shapes, slide.pictures, slide.tables = fact.shapes, fact.pictures, fact.tables
        slide.text_boxes, slide.overflow, slide.flattened = fact.text_boxes, fact.overflow, fact.flattened
        slide.editable_ratio = editable_ratio(fact)
        slide.empty = fact.shapes == 0
        result.slides.append(slide)
    result.warnings += _slide_warnings(result)


def _slide_warnings(result: TemplateResult) -> list[str]:
    notes = []
    for label, flag in (("overflow", "overflow"), ("empty", "empty"), ("flattened", "flattened")):
        names = [s.slide for s in result.slides if getattr(s, flag)]
        if names:
            notes.append(f"{label}: {', '.join(names)}")
    if result.export_warnings:
        notes.append(f"{len(result.export_warnings)} export warning(s)")
    return notes


def _safe(name: str) -> str:
    return re.sub(r"[^\w.-]", "_", name)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def summary_table(results: list[TemplateResult]) -> str:
    """Compact fixed width table: template, slides, mean score, worst slide, text recall, warnings."""
    rows = [("template", "slides", "mean", "worst slide", "recall", "warnings")]
    for r in results:
        if r.error:
            rows.append((r.template, "-", "-", "-", "-", f"ERROR {r.error}"))
            continue
        worst = r.worst
        worst_text = f"{worst.slide} {worst.score:.2f}" if worst else "-"
        rows.append(
            (
                r.template,
                str(len(r.slides)),
                f"{r.mean_score:.3f}",
                worst_text,
                f"{r.mean_recall:.2f}",
                str(len(r.warnings)),
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip() for row in rows)


def markdown_report(results: list[TemplateResult]) -> str:
    """The ``report.md`` text."""
    lines = ["# PPTX fidelity report", "", "```", summary_table(results), "```", ""]
    for r in results:
        lines += [f"## {r.template}", "", f"`{r.path}`, {r.seconds:.0f} s", ""]
        if r.error:
            lines += [f"ERROR: {r.error}", ""]
            continue
        lines += ["| slide | score | ssim | colour | recall | shapes | pics | tables | texts | editable | flags |"]
        lines += ["|---|---|---|---|---|---|---|---|---|---|---|"]
        for s in r.slides:
            flags = ",".join(
                f for f, on in (("overflow", s.overflow), ("empty", s.empty), ("flattened", s.flattened)) if on
            )
            lines.append(
                f"| {s.slide} | {s.score:.2f} | {s.ssim:.2f} | {s.histogram:.2f} | {s.text_recall:.2f} | {s.shapes} "
                f"| {s.pictures} | {s.tables} | {s.text_boxes} | {s.editable_ratio:.2f} | {flags} |"
            )
        lines += [""] + [f"- {w}" for w in r.warnings] + [""]
    return "\n".join(lines)


def write_reports(results: list[TemplateResult], out: Path) -> None:
    """Write ``report.md`` and ``report.json`` in ``out``."""
    (out / "report.md").write_text(markdown_report(results), encoding="utf-8")
    payload = [{**asdict(r), "mean_score": r.mean_score, "mean_recall": r.mean_recall} for r in results]
    (out / "report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PPTX export fidelity against the HTML render")
    parser.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "pptx-fidelity")
    parser.add_argument("--only", default="", help="comma separated template names (file stems)")
    parser.add_argument("--min-score", type=float, default=None, help="exit 1 when a template mean is below")
    parser.add_argument(
        "--reference",
        choices=("slide", "canvas"),
        default="slide",
        help="slide: whole slide box; canvas: product 960x540 clip",
    )
    parser.add_argument(
        "--jobs", type=int, default=3, help="templates measured in parallel (soffice has its own profile)"
    )
    return parser.parse_args(argv)


def missing_tools() -> list[str]:
    return [tool for tool in ("soffice", "pdftoppm") if shutil.which(tool) is None]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    absent = missing_tools()
    if absent:
        print(
            f"pptx-fidelity needs {', '.join(absent)} on PATH (brew install --cask libreoffice; brew install poppler)",
            file=sys.stderr,
        )
        return 2
    templates = find_presentations()
    if args.only:
        wanted = set(args.only.split(","))
        unknown = wanted - set(templates)
        if unknown:
            print(f"unknown template(s): {', '.join(sorted(unknown))}; known: {', '.join(templates)}", file=sys.stderr)
            return 2
        templates = {k: v for k, v in templates.items() if k in wanted}
    args.out.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = list(
            pool.map(lambda item: measure_template(item[0], item[1], args.out, args.reference), templates.items())
        )
    write_reports(results, args.out)
    print(summary_table(results))
    print(f"\nreport: {args.out / 'report.md'}")
    if any(r.error for r in results):
        return 1
    if args.min_score is not None and any(r.mean_score < args.min_score for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
