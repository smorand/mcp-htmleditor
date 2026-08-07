"""Export HTML to PPTX using python-pptx.

Parses an HTML file produced by mcp-htmleditor (sections with data-type="slide")
and generates a PowerPoint presentation. Each <section data-type="slide"> becomes
one slide.

Supported elements per slide:
- Text blocks (h1-h6, p, div with data-editable="text")
- Images (<img>)
- Gantt charts (data-type="gantt") → table
- Architecture diagrams (data-type="arch-diagram") → shapes
- Tables (data-type="table" or plain <table>)
- Annotated images (data-type="annotated-image")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag
from pptx import Presentation
from pptx.util import Emu, Inches, Pt

# ---------------------------------------------------------------------------
# Slide dimensions (standard 4:3 — 10" × 7.5")
# ---------------------------------------------------------------------------
SLIDE_WIDTH_IN = 10.0
SLIDE_HEIGHT_IN = 7.5
SLIDE_WIDTH_EMU = Inches(SLIDE_WIDTH_IN)
SLIDE_HEIGHT_EMU = Inches(SLIDE_HEIGHT_IN)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def to_pptx(input_html: str, output_pptx: str) -> None:
    """Convert an HTML file to a PPTX presentation.

    Args:
        input_html: Path to the source HTML file.
        output_pptx: Destination path for the generated .pptx file.
    """
    html = Path(input_html).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH_EMU
    prs.slide_height = SLIDE_HEIGHT_EMU

    blank_layout = prs.slide_layouts[6]  # blank layout

    slides = soup.find_all("section", attrs={"data-type": "slide"})
    if not slides:
        # Treat the entire body as a single slide
        slides = [soup.body] if soup.body else [soup]

    for section in slides:
        slide = prs.slides.add_slide(blank_layout)
        _process_slide(slide, section)

    Path(output_pptx).parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_pptx)


# ---------------------------------------------------------------------------
# Slide processing
# ---------------------------------------------------------------------------

def _process_slide(slide: Any, section: Tag) -> None:
    """Populate a pptx slide from an HTML section element."""
    for child in section.children:
        if not isinstance(child, Tag):
            continue
        dtype = child.get("data-type", "")
        if dtype == "gantt":
            _add_gantt(slide, child)
        elif dtype == "arch-diagram":
            _add_arch_diagram(slide, child)
        elif dtype == "annotated-image":
            _add_annotated_image(slide, child)
        elif dtype in ("table",) or child.name == "table":
            _add_table(slide, child)
        elif child.name == "img":
            _add_image(slide, child)
        else:
            _add_text_element(slide, child)


# ---------------------------------------------------------------------------
# Position extraction
# ---------------------------------------------------------------------------

def _parse_pct(value: str) -> float:
    """Parse a percentage string like '10%' into a float 0-100."""
    m = re.match(r"([\d.]+)%", value.strip())
    return float(m.group(1)) if m else 0.0


def _parse_px(value: str) -> float:
    """Parse a px value string like '120px' into a float."""
    m = re.match(r"([\d.]+)px", value.strip())
    return float(m.group(1)) if m else 0.0


def _extract_position(style: str) -> dict[str, float | None]:
    """Extract left/top/width/height from an inline CSS style string.

    Values are returned as Emu (int). None means the dimension was not found.
    """
    result: dict[str, float | None] = {
        "left": None,
        "top": None,
        "width": None,
        "height": None,
    }
    if not style:
        return result

    props: dict[str, str] = {}
    for part in style.split(";"):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            props[k.strip().lower()] = v.strip()

    def to_emu(key: str, total_in: float) -> float | None:
        val = props.get(key)
        if val is None:
            return None
        if "%" in val:
            return float(Inches(_parse_pct(val) / 100.0 * total_in))
        if "px" in val:
            # Assume 96 DPI → 1px = 1/96 inch
            return float(Inches(_parse_px(val) / 96.0))
        return None

    result["left"] = to_emu("left", SLIDE_WIDTH_IN)
    result["top"] = to_emu("top", SLIDE_HEIGHT_IN)
    result["width"] = to_emu("width", SLIDE_WIDTH_IN)
    result["height"] = to_emu("height", SLIDE_HEIGHT_IN)
    return result


def _default_positions(
    index: int, total: int
) -> tuple[Emu, Emu, Emu, Emu]:
    """Compute a default grid position for elements without inline positioning."""
    if index == 0:
        # Title at top
        left = Inches(0.5)
        top = Inches(0.3)
        width = Inches(9.0)
        height = Inches(1.2)
    else:
        # Content area below title, stacked vertically
        content_height = SLIDE_HEIGHT_IN - 1.8
        slot_h = content_height / max(total - 1, 1)
        left = Inches(0.5)
        top = Inches(1.8 + (index - 1) * slot_h)
        width = Inches(9.0)
        height = Inches(max(slot_h - 0.1, 0.5))
    return left, top, width, height


def _resolve_position(
    element: Tag, index: int, total: int
) -> tuple[Emu, Emu, Emu, Emu]:
    """Return (left, top, width, height) as Emu for an element."""
    style = element.get("style", "")
    pos = _extract_position(style)

    left_raw = pos["left"]
    top_raw = pos["top"]
    width_raw = pos["width"]
    height_raw = pos["height"]

    if all(v is not None for v in (left_raw, top_raw, width_raw, height_raw)):
        return (
            Emu(int(left_raw)),  # type: ignore[arg-type]  # python-pptx Emu accepts int
            Emu(int(top_raw)),  # type: ignore[arg-type]  # python-pptx Emu accepts int
            Emu(int(width_raw)),  # type: ignore[arg-type]  # python-pptx Emu accepts int
            Emu(int(height_raw)),  # type: ignore[arg-type]  # python-pptx Emu accepts int
        )

    return _default_positions(index, total)


# ---------------------------------------------------------------------------
# Element renderers
# ---------------------------------------------------------------------------

def _add_text_element(slide: Any, element: Tag, index: int = 0, total: int = 1) -> None:
    """Add a text box to the slide from a text-bearing element."""
    text = element.get_text(separator="\n").strip()
    if not text:
        return

    left, top, width, height = _resolve_position(element, index, total)
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    tf.text = text

    # Style the first paragraph based on tag name
    para = tf.paragraphs[0]
    run = para.runs[0] if para.runs else para.add_run()
    tag = element.name or ""
    if tag in ("h1", "h2"):
        run.font.bold = True
        run.font.size = Pt(28 if tag == "h1" else 22)
    elif tag in ("h3", "h4"):
        run.font.bold = True
        run.font.size = Pt(18)
    else:
        run.font.size = Pt(14)


def _add_image(slide: Any, element: Tag, index: int = 0, total: int = 1) -> None:
    """Add an image to the slide."""
    src = element.get("src", "")
    if not src or src.startswith("data:"):
        # Skip base64 images (too complex for V1 — positional placeholder only)
        return

    # Resolve relative paths
    img_path = Path(src)
    if not img_path.is_absolute():
        img_path = Path.cwd() / img_path

    if not img_path.exists():
        return

    left, top, width, height = _resolve_position(element, index, total)
    slide.shapes.add_picture(str(img_path), left, top, width, height)


def _add_table(slide: Any, element: Tag, index: int = 0, total: int = 1) -> None:
    """Convert an HTML table to a python-pptx table."""
    rows = element.find_all("tr")
    if not rows:
        return

    col_count = max(
        sum(int(td.get("colspan", 1)) for td in row.find_all(["td", "th"]))
        for row in rows
    )
    row_count = len(rows)
    if col_count == 0:
        return

    left, top, width, height = _resolve_position(element, index, total)
    table_shape = slide.shapes.add_table(row_count, col_count, left, top, width, height)
    tbl = table_shape.table

    for r_idx, row in enumerate(rows):
        cells = row.find_all(["td", "th"])
        c_idx = 0
        for cell in cells:
            if c_idx >= col_count:
                break
            cell_text = cell.get_text().strip()
            tbl.cell(r_idx, c_idx).text = cell_text
            c_idx += int(cell.get("colspan", 1))


def _add_gantt(slide: Any, gantt_el: Tag) -> None:
    """Render a Gantt chart as a table in the slide."""
    tasks = gantt_el.find_all(attrs={"data-type": "gantt-task"})
    if not tasks:
        # Fallback: look for generic child elements with data-label
        tasks = gantt_el.find_all(attrs={"data-label": True})

    headers = ["Task", "Start", "End", "Label"]
    rows_data: list[list[str]] = [headers]
    for task in tasks:
        label = task.get("data-label", task.get_text().strip() or "Task")
        start = task.get("data-start", "")
        end = task.get("data-end", "")
        color = task.get("data-color", "")
        rows_data.append([label, start, end, color])

    row_count = len(rows_data)
    col_count = 4
    if row_count == 0:
        return

    left = Inches(0.5)
    top = Inches(1.5)
    width = Inches(9.0)
    height = Inches(min(row_count * 0.5, 5.5))

    table_shape = slide.shapes.add_table(row_count, col_count, left, top, width, height)
    tbl = table_shape.table
    for r_idx, row in enumerate(rows_data):
        for c_idx, cell_text in enumerate(row):
            tbl.cell(r_idx, c_idx).text = cell_text


def _add_arch_diagram(slide: Any, diagram_el: Tag) -> None:
    """Render architecture diagram nodes as labelled rectangles."""
    nodes = diagram_el.find_all(attrs={"data-type": "arch-node"})
    for node in nodes:
        label = node.get("data-label", node.get_text().strip() or "Node")
        # Positions from data attributes (in % of slide)
        x_pct = float(node.get("data-x", "10"))
        y_pct = float(node.get("data-y", "10"))
        w_pct = float(node.get("data-width", "20"))
        h_pct = float(node.get("data-height", "10"))

        left = Inches(x_pct / 100.0 * SLIDE_WIDTH_IN)
        top = Inches(y_pct / 100.0 * SLIDE_HEIGHT_IN)
        width = Inches(w_pct / 100.0 * SLIDE_WIDTH_IN)
        height = Inches(h_pct / 100.0 * SLIDE_HEIGHT_IN)

        shape = slide.shapes.add_textbox(left, top, width, height)
        shape.text_frame.text = label

        # Add a simple border
        from pptx.util import Pt as _Pt
        shape.line.width = _Pt(1)


def _add_annotated_image(slide: Any, container: Tag) -> None:
    """Render an annotated image: base image + annotation text boxes."""
    img_tag = container.find("img")
    if img_tag:
        _add_image(slide, img_tag)

    annotations = container.find_all(attrs={"data-type": "annotation"})
    for ann in annotations:
        x_pct = float(ann.get("data-x", "50"))
        y_pct = float(ann.get("data-y", "50"))
        text = ann.get_text().strip()

        left = Inches(x_pct / 100.0 * SLIDE_WIDTH_IN)
        top = Inches(y_pct / 100.0 * SLIDE_HEIGHT_IN)
        width = Inches(2.0)
        height = Inches(0.4)

        txBox = slide.shapes.add_textbox(left, top, width, height)
        txBox.text_frame.text = text
