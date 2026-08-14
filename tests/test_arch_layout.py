"""Tests for the declarative architecture diagram layout engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from mcp_htmleditor import arch_layout

SIMPLE_DIAGRAM = """
<!DOCTYPE html>
<html><body>
<div data-type="arch-diagram" data-diagram-id="d1" style="position:relative; width:100%; height:320px;">
  <div data-type="arch-lane" data-lane-id="ds04" data-label="ds04" data-rows="0-1"></div>
  <div data-type="arch-row" data-row="0">
    <div data-type="arch-node" data-id="agent" data-label="Agent LLM" data-shape="box"></div>
    <div data-type="arch-node" data-id="mcp" data-label="Serveur MCP" data-shape="box"></div>
  </div>
  <div data-type="arch-row" data-row="1">
    <div data-type="arch-node" data-id="file" data-label="Fichier HTML" data-span="2"></div>
  </div>
  <div data-type="arch-edge" data-from="agent" data-to="mcp" data-label="MCP stdio"></div>
  <div data-type="arch-edge" data-from="agent" data-to="file" data-label="ecriture directe"></div>
</div>
</body></html>
"""

WIDE_ROW_DIAGRAM = """
<!DOCTYPE html>
<html><body>
<div data-type="arch-diagram" style="position:relative; width:100%; height:320px;">
  <div data-type="arch-row" data-row="0">
    <div data-type="arch-node" data-id="a" data-label="A"></div>
    <div data-type="arch-node" data-id="b" data-label="B"></div>
    <div data-type="arch-node" data-id="c" data-label="C"></div>
    <div data-type="arch-node" data-id="d" data-label="D"></div>
  </div>
  <div data-type="arch-row" data-row="1" data-height-weight="0.2"></div>
  <div data-type="arch-edge" data-from="a" data-to="d"></div>
</div>
</body></html>
"""

LEGACY_DIAGRAM = """
<!DOCTYPE html>
<html><body>
<div data-type="arch-diagram" style="position:relative; width:100%; height:320px;">
  <div data-type="arch-node" data-id="x" data-label="X"
       data-x="1.0" data-y="2.0" data-width="20.0" data-height="15.0"></div>
</div>
</body></html>
"""


def _node_boxes(html: str) -> dict[str, arch_layout.PctBox]:
    """Read every node's box as diagram-relative percent, matching what the browser
    actually paints: a node nested inside an ``arch-col`` is stored col-relative
    (see ``arch_layout._to_local``), since the col is itself ``position:absolute``
    and therefore the containing block CSS resolves the node's percentages against.
    """
    soup = BeautifulSoup(html, "html.parser")
    boxes: dict[str, arch_layout.PctBox] = {}
    for node in soup.find_all(attrs={"data-type": "arch-node"}):
        box = arch_layout._existing_box(node)
        assert box is not None, f"node {node.get('data-id')} missing its computed box"
        parent = node.find_parent(attrs={"data-type": "arch-col"})
        if parent is not None:
            col_box = arch_layout._existing_box(parent)
            assert col_box is not None
            box = arch_layout.PctBox(
                x=col_box.x + box.x / 100 * col_box.width,
                y=col_box.y + box.y / 100 * col_box.height,
                width=box.width / 100 * col_box.width,
                height=box.height / 100 * col_box.height,
            )
        boxes[str(node.get("data-id"))] = box
    return boxes


def _write(tmp_path: Path, html: str, name: str = "diagram.html") -> Path:
    path = tmp_path / name
    path.write_text(html, encoding="utf-8")
    return path


def test_layout_writes_no_collision(tmp_path: Path) -> None:
    """No two node boxes overlap after computation, across a representative spec."""
    path = _write(tmp_path, SIMPLE_DIAGRAM)
    report = arch_layout.layout_file(path)

    assert report.diagrams_updated == 1
    boxes = list(_node_boxes(path.read_text(encoding="utf-8")).values())
    assert arch_layout._detect_collisions(boxes) == []


def test_same_row_nodes_share_mid_y(tmp_path: Path) -> None:
    """Two nodes declared in the same row end up with a strictly identical vertical center."""
    path = _write(tmp_path, SIMPLE_DIAGRAM)
    arch_layout.layout_file(path)

    boxes = _node_boxes(path.read_text(encoding="utf-8"))
    assert boxes["agent"].mid_y == boxes["mcp"].mid_y


def test_aligned_columns_produce_a_single_straight_line(tmp_path: Path) -> None:
    """When a row-1 node spans the full width, its mid_x aligns with a row-0 node above it,
    and the connector collapses to one vertical segment: no horizontal jog is generated."""
    single_node_rows = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:200px;">
      <div data-type="arch-row" data-row="0">
        <div data-type="arch-node" data-id="top" data-label="Top"></div>
      </div>
      <div data-type="arch-row" data-row="1">
        <div data-type="arch-node" data-id="bottom" data-label="Bottom"></div>
      </div>
      <div data-type="arch-edge" data-from="top" data-to="bottom"></div>
    </div>
    """
    path = _write(tmp_path, single_node_rows)
    arch_layout.layout_file(path)

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    edge = soup.find(attrs={"data-type": "arch-edge"})
    assert edge is not None
    assert "arch-line-v" in (edge.get("class") or [])
    assert "arch-line-h" not in (edge.get("class") or [])
    # A single vertical segment on the edge itself: no extra decorative line generated.
    decorations = soup.find_all(attrs={"data-edge-of": edge.get("data-edge-id")})
    assert not any("arch-line-h" in (d.get("class") or []) for d in decorations)


def test_fan_out_detours_around_an_intervening_node_in_the_same_row(tmp_path: Path) -> None:
    """A -> D shares a band with B and C sitting physically between them: a plain straight
    line would cut through both, so it must detour below the row instead."""
    path = _write(tmp_path, WIDE_ROW_DIAGRAM)
    arch_layout.layout_file(path)

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    boxes = _node_boxes(path.read_text(encoding="utf-8"))
    edge = soup.find(attrs={"data-type": "arch-edge"})
    assert edge is not None
    assert "arch-line-v" in (edge.get("class") or [])
    h_lines = [el for el in soup.find_all("div") if "arch-line-h" in (el.get("class") or [])]
    assert h_lines, "expected a horizontal detour segment below b/c"
    detour_y = float(str(h_lines[0]["style"]).split("top:")[1].split("%")[0])
    assert detour_y >= max(boxes["b"].bottom, boxes["c"].bottom)


def test_idempotent_second_run_produces_identical_output(tmp_path: Path) -> None:
    """Running the layout twice on an unchanged spec writes byte-identical output."""
    path = _write(tmp_path, SIMPLE_DIAGRAM)
    arch_layout.layout_file(path)
    first_pass = path.read_text(encoding="utf-8")

    arch_layout.layout_file(path)
    second_pass = path.read_text(encoding="utf-8")

    assert first_pass == second_pass


def test_manual_locked_node_keeps_its_position(tmp_path: Path) -> None:
    """A node flagged data-layout=manual is never repositioned, even when a sibling changes."""
    path = _write(tmp_path, SIMPLE_DIAGRAM)
    arch_layout.layout_file(path)

    html = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    mcp_node = soup.find(attrs={"data-type": "arch-node", "data-id": "mcp"})
    assert mcp_node is not None
    mcp_node["data-layout"] = "manual"
    mcp_node["data-x"] = "70.0"
    mcp_node["data-y"] = "40.0"
    mcp_node["data-width"] = "10.0"
    mcp_node["data-height"] = "10.0"
    # Widen the agent node's span so the row's distribution would otherwise shift "mcp".
    agent_node = soup.find(attrs={"data-type": "arch-node", "data-id": "agent"})
    assert agent_node is not None
    agent_node["data-span"] = "3"
    path.write_text(str(soup), encoding="utf-8")

    arch_layout.layout_file(path)

    boxes = _node_boxes(path.read_text(encoding="utf-8"))
    assert boxes["mcp"] == arch_layout.PctBox(x=70.0, y=40.0, width=10.0, height=10.0)


def test_lane_bounding_box_contains_its_rows_with_padding(tmp_path: Path) -> None:
    """The lane's box strictly contains every node box in its declared row range, plus padding,
    and never exceeds the diagram's own bounds."""
    path = _write(tmp_path, SIMPLE_DIAGRAM)
    arch_layout.layout_file(path)

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    lane = soup.find(attrs={"data-type": "arch-lane"})
    assert lane is not None
    lane_box = arch_layout._existing_box(lane)
    assert lane_box is not None

    boxes = _node_boxes(path.read_text(encoding="utf-8"))
    for box in boxes.values():
        assert lane_box.x <= box.x
        assert lane_box.y <= box.y
        assert lane_box.right >= box.right
        assert lane_box.bottom >= box.bottom
    assert lane_box.x >= 0.0
    assert lane_box.y >= 0.0
    assert lane_box.right <= 100.0
    assert lane_box.bottom <= 100.0


def test_legacy_diagram_without_rows_is_left_untouched(tmp_path: Path) -> None:
    """A diagram with no arch-row child (legacy manual format) is never modified."""
    path = _write(tmp_path, LEGACY_DIAGRAM)
    before = path.read_text(encoding="utf-8")

    report = arch_layout.layout_file(path)

    assert report.diagrams_updated == 0
    assert path.read_text(encoding="utf-8") == before


def test_diagram_id_filter_restricts_the_update(tmp_path: Path) -> None:
    """Passing diagram_id only lays out the matching diagram, leaving others untouched."""
    two_diagrams = SIMPLE_DIAGRAM.replace(
        "</body></html>",
        LEGACY_DIAGRAM.split("<body>")[1].replace("</body></html>", "") + "</body></html>",
    )
    path = _write(tmp_path, two_diagrams)

    report = arch_layout.layout_file(path, diagram_id="d1")

    assert report.diagrams_updated == 1


def test_row_skip_edge_is_flagged_out_of_scope(tmp_path: Path) -> None:
    """An edge spanning more than one row is still routed but produces a documented warning."""
    three_rows = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:300px;">
      <div data-type="arch-row" data-row="0"><div data-type="arch-node" data-id="a" data-label="A"></div></div>
      <div data-type="arch-row" data-row="1"><div data-type="arch-node" data-id="b" data-label="B"></div></div>
      <div data-type="arch-row" data-row="2"><div data-type="arch-node" data-id="c" data-label="C"></div></div>
      <div data-type="arch-edge" data-from="a" data-to="c"></div>
    </div>
    """
    path = _write(tmp_path, three_rows)
    report = arch_layout.layout_file(path)

    assert report.diagrams_updated == 1
    assert any("hors scope V1" in warning for warning in report.warnings)


def test_check_diagram_detects_overlap_on_legacy_markup() -> None:
    """check_diagram works standalone on hand authored data-x/data-y nodes (no arch-row)."""
    overlapping = """
    <div data-type="arch-diagram" style="position:relative;">
      <div data-type="arch-node" data-id="a" data-label="A"
           data-x="10" data-y="10" data-width="30" data-height="20"></div>
      <div data-type="arch-node" data-id="b" data-label="B"
           data-x="20" data-y="15" data-width="30" data-height="20"></div>
    </div>
    """
    soup = BeautifulSoup(overlapping, "html.parser")
    diagram = soup.find(attrs={"data-type": "arch-diagram"})
    assert diagram is not None

    problems = arch_layout.check_diagram(diagram)

    assert len(problems) == 1
    assert "A" in problems[0]
    assert "B" in problems[0]


def test_arch_col_stacks_two_nodes_inside_one_row_slot(tmp_path: Path) -> None:
    """An arch-col slot holds two stacked nodes beside a full-height node in the same row,
    without the stacked nodes overlapping each other or the wide neighbour."""
    spec = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:200px;">
      <div data-type="arch-row" data-row="0">
        <div data-type="arch-node" data-id="wide" data-label="Coffre-fort"></div>
        <div data-type="arch-col">
          <div data-type="arch-node" data-id="top" data-label="Observabilite"></div>
          <div data-type="arch-node" data-id="bottom" data-label="Evaluation"></div>
        </div>
      </div>
    </div>
    """
    path = _write(tmp_path, spec)
    report = arch_layout.layout_file(path)

    assert report.diagrams_updated == 1
    boxes = _node_boxes(path.read_text(encoding="utf-8"))
    # The two stacked nodes share the wide node's row height but not each other's space.
    assert boxes["top"].bottom <= boxes["bottom"].y
    assert boxes["top"].x == boxes["bottom"].x
    assert boxes["top"].width == boxes["bottom"].width
    all_boxes = list(boxes.values())
    assert arch_layout._detect_collisions(all_boxes) == []


def test_nested_node_percentages_are_written_relative_to_its_col(tmp_path: Path) -> None:
    """A node inside an arch-col is written in col-relative percent, not diagram-relative:
    an arch-col is itself position:absolute, so per CSS it is the containing block for its
    own absolutely positioned children. Writing diagram-relative values there would make
    the browser resolve them against the col's (smaller) box, shrinking/misplacing them.
    """
    spec = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:200px;">
      <div data-type="arch-row" data-row="0">
        <div data-type="arch-node" data-id="wide" data-label="Wide"></div>
        <div data-type="arch-col">
          <div data-type="arch-node" data-id="top" data-label="Top"></div>
          <div data-type="arch-node" data-id="bottom" data-label="Bottom"></div>
        </div>
      </div>
    </div>
    """
    path = _write(tmp_path, spec)
    arch_layout.layout_file(path)

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    col = soup.find(attrs={"data-type": "arch-col"})
    col_box = arch_layout._existing_box(col)
    assert col_box is not None
    top_node = soup.find(attrs={"data-id": "top"})
    top_local = arch_layout._existing_box(top_node)
    assert top_local is not None
    # Written col-relative: a node spanning half the col's own height should read
    # roughly 50%, regardless of what percentage that height represents of the
    # whole diagram.
    assert 40.0 <= top_local.height <= 60.0
    # Converting back to diagram-relative (what the browser actually paints, since
    # the col is position:absolute) must reproduce the same absolute box a
    # diagram-relative-unaware reader would expect: fully inside the col, and
    # together with "bottom" spanning the whole col height.
    diagram_relative_top = arch_layout.PctBox(
        x=col_box.x + top_local.x / 100 * col_box.width,
        y=col_box.y + top_local.y / 100 * col_box.height,
        width=top_local.width / 100 * col_box.width,
        height=top_local.height / 100 * col_box.height,
    )
    assert diagram_relative_top.x == col_box.x
    assert diagram_relative_top.right <= col_box.right + 0.1
    assert diagram_relative_top.y == col_box.y


def test_arch_col_itself_receives_a_written_box(tmp_path: Path) -> None:
    """The arch-col wrapper gets its own position/size written, like a node, so it can
    carry a border/background at the right place (see the bootstrap CSS + ::before label)."""
    spec = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:200px;">
      <div data-type="arch-row" data-row="0">
        <div data-type="arch-node" data-id="wide" data-label="Wide"></div>
        <div data-type="arch-col" data-label="Card">
          <div data-type="arch-node" data-id="top" data-label="Top"></div>
          <div data-type="arch-node" data-id="bottom" data-label="Bottom"></div>
        </div>
      </div>
    </div>
    """
    path = _write(tmp_path, spec)
    arch_layout.layout_file(path)

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    col = soup.find(attrs={"data-type": "arch-col"})
    assert col is not None
    box = arch_layout._existing_box(col)
    assert box is not None
    inner = _node_boxes(path.read_text(encoding="utf-8"))
    assert box.x <= inner["top"].x
    assert box.right >= inner["top"].right
    assert box.y <= inner["top"].y
    assert box.bottom >= inner["bottom"].bottom


def test_arch_spacer_aligns_a_node_above_a_specific_column(tmp_path: Path) -> None:
    """An arch-spacer reserves width without producing a node box, letting a single-node row
    align with one specific column of a wider row below it (the ds04 IA Gen Proxy case)."""
    spec = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:200px;">
      <div data-type="arch-row" data-row="0">
        <div data-type="arch-node" data-id="above" data-label="IA Gen Proxy"></div>
        <div data-type="arch-spacer"></div>
        <div data-type="arch-spacer"></div>
      </div>
      <div data-type="arch-row" data-row="1">
        <div data-type="arch-node" data-id="first" data-label="vLLM"></div>
        <div data-type="arch-node" data-id="second" data-label="Qwen"></div>
        <div data-type="arch-node" data-id="third" data-label="slot libre"></div>
      </div>
    </div>
    """
    path = _write(tmp_path, spec)
    arch_layout.layout_file(path)

    boxes = _node_boxes(path.read_text(encoding="utf-8"))
    assert boxes["above"].x == boxes["first"].x
    assert boxes["above"].width == boxes["first"].width
    all_boxes = list(boxes.values())
    assert arch_layout._detect_collisions(all_boxes) == []


def test_edge_step_badge_sits_on_the_true_segment_midpoint(tmp_path: Path) -> None:
    """A data-step badge is rendered at the segment's on-line midpoint (no label offset)."""
    spec = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:200px;">
      <div data-type="arch-row" data-row="0">
        <div data-type="arch-node" data-id="a" data-label="A"></div>
        <div data-type="arch-node" data-id="b" data-label="B"></div>
      </div>
      <div data-type="arch-edge" data-from="a" data-to="b" data-step="5" data-color="#2CA02C"></div>
    </div>
    """
    path = _write(tmp_path, spec)
    arch_layout.layout_file(path)

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    badge = soup.find(attrs={"class": "arch-edge-badge"})
    assert badge is not None
    assert badge.get_text() == "5"
    assert "background:#2CA02C" in str(badge.get("style"))


def test_edge_data_color_overrides_the_default_accent(tmp_path: Path) -> None:
    """data-color on an edge tints its segment, tip and label instead of the CSS default."""
    spec = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:200px;">
      <div data-type="arch-row" data-row="0">
        <div data-type="arch-node" data-id="a" data-label="A"></div>
        <div data-type="arch-node" data-id="b" data-label="B"></div>
      </div>
      <div data-type="arch-edge" data-from="a" data-to="b" data-label="go" data-color="#E377C2"></div>
    </div>
    """
    path = _write(tmp_path, spec)
    arch_layout.layout_file(path)

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    edge = soup.find(attrs={"data-type": "arch-edge"})
    tip = soup.find(attrs={"class": "arch-tip"})
    label = soup.find(attrs={"class": "arch-edge-label"})
    assert "border-top-color:#E377C2" in str(edge.get("style"))
    assert "border-left-color:#E377C2" in str(tip.get("style"))
    assert "color:#E377C2" in str(label.get("style"))


def test_detour_avoids_an_intervening_column_in_the_same_row(tmp_path: Path) -> None:
    """Two nodes in the same nominal row but different, non-overlapping arch-col slots
    route below the whole row instead of cutting through the column between them."""
    spec = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:200px;">
      <div data-type="arch-row" data-row="0">
        <div data-type="arch-col">
          <div data-type="arch-node" data-id="left_top" data-label="LeftTop"></div>
          <div data-type="arch-node" data-id="left_bottom" data-label="LeftBottom"></div>
        </div>
        <div data-type="arch-col">
          <div data-type="arch-node" data-id="mid_top" data-label="MidTop"></div>
          <div data-type="arch-node" data-id="mid_bottom" data-label="MidBottom"></div>
          <div data-type="arch-node" data-id="mid_extra" data-label="MidExtra"></div>
        </div>
        <div data-type="arch-col">
          <div data-type="arch-node" data-id="right_top" data-label="RightTop"></div>
          <div data-type="arch-node" data-id="right_bottom" data-label="RightBottom"></div>
        </div>
      </div>
      <div data-type="arch-row" data-row="1" data-height-weight="0.2"></div>
      <div data-type="arch-edge" data-from="left_bottom" data-to="right_top"></div>
    </div>
    """
    path = _write(tmp_path, spec)
    arch_layout.layout_file(path)

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    boxes = _node_boxes(path.read_text(encoding="utf-8"))
    # left_bottom and right_top do not share a band (bottom-half vs top-half),
    # so a direct elbow would cut through the middle column spanning the full height.
    assert not arch_layout._boxes_share_a_band(boxes["left_bottom"], boxes["right_top"])
    h_lines = [el for el in soup.find_all("div") if "arch-line-h" in (el.get("class") or [])]
    assert h_lines, "expected a horizontal detour segment"
    # The exact shape (below the row, or via a column gutter) is an implementation
    # detail; what must hold is that no segment cuts through the middle column.
    edge = soup.find(attrs={"data-type": "arch-edge"})
    edge_id = edge.get("data-edge-id")
    mid_boxes = [boxes["mid_top"], boxes["mid_bottom"], boxes["mid_extra"]]
    for seg in [edge, *soup.find_all(attrs={"data-edge-of": edge_id})]:
        style = str(seg.get("style"))
        if "left:" not in style or "top:" not in style:
            continue
        x = float(style.split("left:")[1].split("%", maxsplit=1)[0])
        y = float(style.split("top:")[1].split("%", maxsplit=1)[0])
        width = float(style.split("width:")[1].split("%", maxsplit=1)[0]) if "width:" in style else 0.5
        height = float(style.split("height:")[1].split("%", maxsplit=1)[0]) if "height:" in style else 0.5
        seg_box = arch_layout.PctBox(x=x, y=y, width=max(width, 0.5), height=max(height, 0.5))
        for obstacle in mid_boxes:
            assert not seg_box.overlaps(obstacle), f"segment {seg} cuts through the middle column"


def test_detour_does_not_cut_through_a_sibling_below_the_target(tmp_path: Path) -> None:
    """When the target is the TOP node of a col with a sibling directly beneath it (e.g. an
    "API" box under a "MCP server" box), a detour entering from below would cut straight
    through that sibling: the engine must instead enter from above (the target's free side).
    """
    spec = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:320px;">
      <div data-type="arch-row" data-row="0" data-height-weight="0.2"></div>
      <div data-type="arch-row" data-row="1">
        <div data-type="arch-node" data-id="registre" data-label="Registre"></div>
        <div data-type="arch-col">
          <div data-type="arch-node" data-id="mcp1" data-label="MCP server 1"></div>
          <div data-type="arch-node" data-id="api1" data-label="API 1"></div>
        </div>
        <div data-type="arch-col">
          <div data-type="arch-node" data-id="mcp2" data-label="MCP server 2"></div>
          <div data-type="arch-node" data-id="api2" data-label="API 2"></div>
        </div>
      </div>
      <div data-type="arch-row" data-row="2" data-height-weight="0.2"></div>
      <div data-type="arch-edge" data-from="registre" data-to="mcp2"></div>
    </div>
    """
    # Representative of the real case (skill/checks/arch-diagram-checklist.md): the
    # blocked target has a free row above it to route through (an empty margin row
    # here, an "IT11" telemetry row in the real deck). A single first/last row with
    # nothing above AND nothing below is a narrower, accepted residual limitation
    # (side-entry routing is not implemented), not the shape this test represents.
    path = _write(tmp_path, spec)
    arch_layout.layout_file(path)

    boxes = _node_boxes(path.read_text(encoding="utf-8"))
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    edge = soup.find(attrs={"data-type": "arch-edge"})
    edge_id = edge.get("data-edge-id")
    segments = [edge, *soup.find_all(attrs={"data-edge-of": edge_id})]
    v_lines = [s for s in segments if "arch-line-v" in (s.get("class") or [])]

    def _seg_box(el: Any) -> arch_layout.PctBox:
        style = str(el.get("style"))
        x = float(style.split("left:")[1].split("%", maxsplit=1)[0])
        y = float(style.split("top:")[1].split("%", maxsplit=1)[0])
        height = float(style.split("height:")[1].split("%", maxsplit=1)[0]) if "height:" in style else 0.0
        return arch_layout.PctBox(x=x - 0.5, y=y, width=1.0, height=height)

    api2_box = boxes["api2"]
    for line in v_lines:
        assert not _seg_box(line).overlaps(api2_box), f"vertical segment cuts through api2: {line}"


def test_side_detour_used_when_source_and_target_are_each_blocked_on_their_free_side(
    tmp_path: Path,
) -> None:
    """Source has a sibling directly above it (blocking the 'above' rail) AND target has a
    sibling directly below it (blocking the 'below' rail): neither single rail can reach
    both free sides at once, so the engine must go around the diagram's outer margin."""
    spec = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:320px;">
      <div data-type="arch-row" data-row="-1" data-height-weight="0.2"></div>
      <div data-type="arch-row" data-row="0">
        <div data-type="arch-col">
          <div data-type="arch-node" data-id="top_left" data-label="Above source"></div>
          <div data-type="arch-node" data-id="source" data-label="Source"></div>
        </div>
        <div data-type="arch-node" data-id="middle" data-label="Middle"></div>
        <div data-type="arch-col">
          <div data-type="arch-node" data-id="target" data-label="Target"></div>
          <div data-type="arch-node" data-id="below_target" data-label="Below target"></div>
        </div>
      </div>
      <div data-type="arch-row" data-row="1" data-height-weight="0.2"></div>
      <div data-type="arch-edge" data-from="source" data-to="target"></div>
    </div>
    """
    path = _write(tmp_path, spec)
    arch_layout.layout_file(path)

    boxes = _node_boxes(path.read_text(encoding="utf-8"))
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    edge = soup.find(attrs={"data-type": "arch-edge"})
    edge_id = edge.get("data-edge-id")
    all_segments = [edge, *soup.find_all(attrs={"data-edge-of": edge_id})]

    def _seg_box(el: Any) -> arch_layout.PctBox:
        style = str(el.get("style"))
        x = float(style.split("left:")[1].split("%", maxsplit=1)[0])
        y = float(style.split("top:")[1].split("%", maxsplit=1)[0])
        width = float(style.split("width:")[1].split("%", maxsplit=1)[0]) if "width:" in style else 1.0
        height = float(style.split("height:")[1].split("%", maxsplit=1)[0]) if "height:" in style else 1.0
        return arch_layout.PctBox(x=x, y=y, width=max(width, 0.5), height=max(height, 0.5))

    line_segments = [
        s for s in all_segments if "arch-line-h" in (s.get("class") or []) or "arch-line-v" in (s.get("class") or [])
    ]
    obstacles = [boxes["top_left"], boxes["middle"], boxes["below_target"]]
    for seg in line_segments:
        seg_box = _seg_box(seg)
        for obstacle in obstacles:
            assert not seg_box.overlaps(obstacle), f"segment {seg} cuts through {obstacle}"


def test_adjacent_row_elbow_avoids_a_sibling_of_the_target(tmp_path: Path) -> None:
    """A cross-row edge's own elbow rail is the midpoint between source and target only:
    a third node sharing target's col (e.g. "Evaluation" stacked below "Observabilite")
    can still sit exactly on that computed rail. Must fall back to an obstacle-aware
    detour instead of cutting through that sibling."""
    spec = """
    <div data-type="arch-diagram" style="position:relative; width:100%; height:250px;">
      <div data-type="arch-row" data-row="0">
        <div data-type="arch-node" data-id="vault" data-label="Vault"></div>
        <div data-type="arch-col">
          <div data-type="arch-node" data-id="obs" data-label="Observabilite"></div>
          <div data-type="arch-node" data-id="evalu" data-label="Evaluation"></div>
        </div>
      </div>
      <div data-type="arch-row" data-row="1" data-height-weight="1.3">
        <div data-type="arch-node" data-id="gateway" data-label="Gateway"></div>
        <div data-type="arch-node" data-id="registre" data-label="Registre"></div>
      </div>
      <div data-type="arch-edge" data-from="gateway" data-to="obs" data-label="Traces"></div>
    </div>
    """
    path = _write(tmp_path, spec)
    arch_layout.layout_file(path)

    boxes = _node_boxes(path.read_text(encoding="utf-8"))
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    edge = soup.find(attrs={"data-from": "gateway", "data-to": "obs"})
    edge_id = edge.get("data-edge-id")
    segments = [edge, *soup.find_all(attrs={"data-edge-of": edge_id})]

    def _seg_box(el: Any) -> arch_layout.PctBox:
        style = str(el.get("style"))
        x = float(style.split("left:")[1].split("%", maxsplit=1)[0])
        y = float(style.split("top:")[1].split("%", maxsplit=1)[0])
        width = float(style.split("width:")[1].split("%", maxsplit=1)[0]) if "width:" in style else 0.5
        height = float(style.split("height:")[1].split("%", maxsplit=1)[0]) if "height:" in style else 0.5
        return arch_layout.PctBox(x=x, y=y, width=max(width, 0.5), height=max(height, 0.5))

    for seg in segments:
        if "left:" not in str(seg.get("style") or ""):
            continue
        seg_box = _seg_box(seg)
        assert not seg_box.overlaps(boxes["evalu"]), f"segment {seg} cuts through Evaluation"


def test_check_diagram_clean_on_legacy_markup_without_overlap() -> None:
    """check_diagram returns no problem for two non overlapping hand authored nodes."""
    clean = """
    <div data-type="arch-diagram" style="position:relative;">
      <div data-type="arch-node" data-id="a" data-label="A"
           data-x="0" data-y="0" data-width="20" data-height="20"></div>
      <div data-type="arch-node" data-id="b" data-label="B"
           data-x="30" data-y="0" data-width="20" data-height="20"></div>
    </div>
    """
    soup = BeautifulSoup(clean, "html.parser")
    diagram = soup.find(attrs={"data-type": "arch-diagram"})
    assert diagram is not None

    assert arch_layout.check_diagram(diagram) == []
