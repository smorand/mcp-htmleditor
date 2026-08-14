"""Deterministic layout engine for declarative architecture diagrams.

The LLM authors *topology* only: rows of nodes (``data-type="arch-row"``), nodes
(``data-type="arch-node"``) inside a row, edges between node ids
(``data-type="arch-edge"``) and optional lanes (``data-type="arch-lane"``) — never
coordinates. This module computes the final ``data-x`` / ``data-y`` /
``data-width`` / ``data-height`` percentages (and the mirroring inline ``style``)
that the existing skill, the browser renderer and the PPTX exporter already read
unchanged (see ``export/to_pptx.py::_render_arch``, which walks the diagram
recursively and does not care how the attributes were produced).

Design invariants (see ``skill/types/arch-diagram.md`` and
``.agent_docs/html-conventions.md``):

* ``arch-row`` / ``arch-lane`` are inert wrappers, never given
  ``position:relative``: every percentage stays resolved against the top level
  ``arch-diagram`` box, in the browser exactly as in the PPTX export.
* A diagram with no ``arch-row`` child is a legacy, hand authored diagram
  (``data-x``/``data-y`` written by hand): this module leaves it untouched, so
  both formats coexist in the same file without conflict.
* A node flagged ``data-layout="manual"`` (set by ``editor.js`` on the first
  mouse drag) is never repositioned again: it still reserves its slot in its
  row's column distribution, but its own box is read back from its existing
  attributes for edge routing instead of being recomputed.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from .tracing import trace_span

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (V1 scope: same-row and adjacent-row edges only)
# ---------------------------------------------------------------------------

GUTTER_ROW_PCT = 6.0
"""Vertical gap reserved between two adjacent rows, used as the elbow rail."""

GUTTER_COL_PCT = 4.0
"""Horizontal gap reserved between two adjacent nodes of the same row."""

LANE_PADDING_PCT = 3.0
"""Padding added around the union of a lane's node boxes."""

LABEL_OFFSET_PCT = 1.8
"""Offset of an edge label from the segment it annotates."""

NESTED_GUTTER_PCT = 2.0
"""Vertical gap between two nodes stacked inside one ``arch-col`` slot (tighter than
GUTTER_ROW_PCT: a col is a compact sub-stack inside a single row, not a full flow step)."""

BADGE_MIN_GUTTER_PCT = 5.0
"""Minimum vertical gap (percent of the diagram) required between two node borders
stacked in the same ``arch-col`` before a numbered step badge (".arch-edge-badge", a
fixed 14px circle in the bootstrap CSS) fits centered on their shared boundary without
touching either one. On the diagram heights actually seen in decks using this feature
(230-320px ``min-height``), 14px is 4.4-6.1% of that height; 5.0% is a representative
middle value — comfortably above ``NESTED_GUTTER_PCT`` (2.0%, the gutter a stacked pair
actually gets) so the real cramped case is always caught, while staying well below
``GUTTER_COL_PCT`` (4.0%) and ``GUTTER_ROW_PCT`` (6.0%): those are horizontal/row gutters
between genuinely different flow steps, always wide enough for a badge already, and must
never trigger this override (see ``_vertical_gap``, which only measures the VERTICAL gap: a
horizontal gap of the same magnitude is a different, already-adequate kind of space).
See ``_badge_position``, which only overrides the geometric midpoint when the actual
vertical gap on a given edge falls short of this."""

BADGE_CLEARANCE_PCT = 3.0
"""Horizontal clearance (percent of the diagram) reserved beside a stacked-node pair
when a numbered step badge has to be pushed out of a gutter narrower than its own
rendered size (see ``_badge_position``). The bootstrap CSS draws ".arch-edge-badge"
at a fixed 14px circle; this constant is an intentionally generous percent-based
proxy for "half the badge's diameter plus a small margin" that stays correct across
any diagram width, rather than a pixel value that would only be right at one size."""

_ROW_SLOT_TYPES = frozenset({"arch-node", "arch-col", "arch-spacer"})
"""Element kinds a row's direct children may be, in the declarative format (V2)."""

ALIGNMENT_TOLERANCE_PCT = 0.05
"""Below this mid_x difference, two rows are considered column-aligned (straight line)."""

ROUND_NDIGITS = 1
"""Decimal places for every written percentage, matching the existing skill convention."""

DIAGRAM_MAX_PCT = 100.0
"""The diagram's own right/bottom edge, in percent of its own box."""

_TIP_TRANSFORMS = {
    "r": "translate(-100%,-50%)",
    "l": "translate(0,-50%)",
    "d": "translate(-50%,-100%)",
    "u": "translate(-50%,0)",
}
"""Anchor transform per tip direction, matching ``skill/types/arch-diagram.md``."""

_MANAGED_EDGE_CLASSES = frozenset({"arch-edge", "arch-line-h", "arch-line-v", "dashed"})
"""Classes this module owns on an edge's anchor element; anything else is preserved."""


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PctBox:
    """An axis aligned rectangle in percent of the ``arch-diagram`` container."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        """Right edge, in percent of the container."""
        return self.x + self.width

    @property
    def bottom(self) -> float:
        """Bottom edge, in percent of the container."""
        return self.y + self.height

    @property
    def mid_x(self) -> float:
        """Horizontal center, in percent of the container."""
        return self.x + self.width / 2

    @property
    def mid_y(self) -> float:
        """Vertical center, in percent of the container."""
        return self.y + self.height / 2

    def overlaps(self, other: PctBox) -> bool:
        """Return True if this rectangle intersects ``other`` (touching edges do not count)."""
        return self.x < other.right and other.x < self.right and self.y < other.bottom and other.y < self.bottom


@dataclass(frozen=True, slots=True)
class LineSegment:
    """One straight, axis aligned piece of an edge's route, in percent."""

    axis: str
    """``"h"`` for a horizontal segment, ``"v"`` for a vertical one."""
    x: float
    y: float
    length: float
    """Width of the segment when ``axis == "h"``, height when ``axis == "v"``."""


@dataclass(frozen=True, slots=True)
class EdgeGeometry:
    """Fully resolved geometry of one connector: segments, tip, label and step badge."""

    segments: tuple[LineSegment, ...]
    tip_direction: str
    """One of ``"r"``, ``"l"``, ``"u"``, ``"d"``, always pointing at the target node."""
    tip_x: float
    tip_y: float
    label_x: float
    label_y: float
    label_align: str
    """``"center"`` (horizontal segment, ``translateX(-50%)``) or ``"side"`` (vertical segment)."""
    mid_x: float
    """True on-segment midpoint (no label offset applied): where a numbered step badge sits,
    UNLESS the source and target nodes are too close together for the badge's own size
    (``BADGE_MIN_GUTTER_PCT``): ``_render_edge`` then overrides it with ``_badge_position``
    instead, since this raw midpoint would otherwise sit inside a gutter too narrow to hold
    a badge without overlapping both nodes' borders."""
    mid_y: float


@dataclass(frozen=True, slots=True)
class LayoutReport:
    """Result of laying out every declarative diagram found in one file."""

    file: str
    diagrams_updated: int
    warnings: tuple[str, ...]


class ArchLayoutError(Exception):
    """Raised when a diagram's declarative spec cannot be laid out."""


# ---------------------------------------------------------------------------
# Small parsing helpers (own copies: this module has no export/pptx coupling)
# ---------------------------------------------------------------------------


def _safe_int(value: object, *, default: int) -> int:
    """Parse an int-like attribute value, falling back to ``default`` on failure."""
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, *, default: float) -> float:
    """Parse a float-like attribute value, falling back to ``default`` on failure."""
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _parse_row_range(value: str) -> tuple[int, int]:
    """Parse a lane's ``data-rows`` value (``"0-1"`` or ``"0"``) into a (start, end) pair."""
    text = value.strip()
    if "-" in text:
        start_text, end_text = text.split("-", 1)
        return int(start_text), int(end_text)
    index = int(text)
    return index, index


def _existing_box(node: Tag) -> PctBox | None:
    """Read back a node's already written box from its own attributes, if present."""
    try:
        return PctBox(
            x=float(str(node["data-x"])),
            y=float(str(node["data-y"])),
            width=float(str(node["data-width"])),
            height=float(str(node["data-height"])),
        )
    except (KeyError, ValueError):
        return None


def _style_attr(element: Tag) -> str | None:
    """Return an element's ``style`` attribute as a plain string.

    bs4 types every attribute as possibly multi-valued (``str | list[str] |
    None``); ``style`` never legitimately is, so this narrows it back to what
    ``_merge_style`` expects.
    """
    value = element.get("style")
    if isinstance(value, list):
        return " ".join(value)
    return value


def _merge_style(existing: str | None, overrides: dict[str, str]) -> str:
    """Merge CSS ``overrides`` into an existing inline ``style`` string, overrides winning."""
    props: dict[str, str] = {}
    for part in (existing or "").split(";"):
        if ":" not in part:
            continue
        key, _, val = part.partition(":")
        key = key.strip().lower()
        if key:
            props[key] = val.strip()
    props.update(overrides)
    return "; ".join(f"{key}:{val}" for key, val in props.items()) + ";"


def _merged_classes(element: Tag, *managed_classes: str) -> list[str]:
    """Return the element's classes with the ones this module owns replaced by ``managed_classes``."""
    existing = [c for c in (element.get("class") or []) if c not in _MANAGED_EDGE_CLASSES]
    return [*existing, *managed_classes]


# ---------------------------------------------------------------------------
# Row / column distribution
# ---------------------------------------------------------------------------


def _row_weight(row: Tag) -> float:
    """Read a row's ``data-height-weight`` (default 1.0, equal share)."""
    return max(_safe_float(row.get("data-height-weight"), default=1.0), 0.1)


def _node_span(node: Tag) -> float:
    """Read a node's ``data-span`` (default 1.0, one column unit)."""
    return max(_safe_float(node.get("data-span"), default=1.0), 0.1)


def _compute_row_boxes(rows: list[Tag]) -> list[tuple[float, float]]:
    """Return (top, height) in percent for each row, top to bottom.

    Rows share ``100 - GUTTER_ROW_PCT * (n - 1)`` percent by weight
    (``data-height-weight``, default equal), with a fixed gutter between
    adjacent rows reserved as the elbow rail for adjacent-row connectors.
    """
    if not rows:
        return []
    total_gutter = GUTTER_ROW_PCT * (len(rows) - 1)
    available = max(0.0, 100.0 - total_gutter)
    weights = [_row_weight(row) for row in rows]
    weight_sum = sum(weights)
    boxes: list[tuple[float, float]] = []
    top = 0.0
    for weight in weights:
        height = available * (weight / weight_sum)
        boxes.append((top, height))
        top += height + GUTTER_ROW_PCT
    return boxes


def _resolve_locked_box(node: Tag, computed: PctBox, container: PctBox | None = None) -> PctBox:
    """Freeze a node's box if it is locked with ``data-layout="manual"``, else use ``computed``.

    Both the return value and ``computed`` are diagram-relative (used for edge
    routing, lanes, collision checks). When ``container`` is given (the node is
    nested inside an ``arch-col``), the node's *stored* attributes are in
    ``container``-relative percent (see ``_to_local``): convert them back to
    diagram-relative before returning, so callers never need to know whether a
    box came from a nested slot.
    """
    if node.get("data-layout") != "manual":
        return computed
    existing = _existing_box(node)
    if existing is None:
        return computed
    if container is None:
        return existing
    return PctBox(
        x=container.x + existing.x / 100 * container.width,
        y=container.y + existing.y / 100 * container.height,
        width=existing.width / 100 * container.width,
        height=existing.height / 100 * container.height,
    )


def _to_local(box: PctBox, container: PctBox) -> PctBox:
    """Convert a diagram-relative box into percent relative to ``container``.

    Required because an ``arch-col`` is itself ``position:absolute`` (so it can
    be placed against the diagram like a node), which makes it, per CSS, the
    containing block for its OWN absolutely positioned children: their written
    ``left``/``top``/``width``/``height`` percentages resolve against the col's
    box in the browser, not the diagram's. Everything else in this module keeps
    working in diagram-relative percent; only the values written to a nested
    node's own attributes go through this conversion.
    """
    return PctBox(
        x=(box.x - container.x) / container.width * 100 if container.width else 0.0,
        y=(box.y - container.y) / container.height * 100 if container.height else 0.0,
        width=box.width / container.width * 100 if container.width else 0.0,
        height=box.height / container.height * 100 if container.height else 0.0,
    )


def _compute_col_boxes(nodes: list[Tag], slot_box: PctBox) -> dict[str, PctBox]:
    """Distribute ``nodes`` top to bottom inside one ``arch-col`` slot, by ``data-height-weight``.

    This is what lets a single row slot hold a compact vertical sub-stack (e.g.
    two status tiles stacked inside one lane, beside a single wide node in the
    same row) instead of forcing every node in a row onto one shared height.
    """
    if not nodes:
        return {}
    total_gutter = NESTED_GUTTER_PCT * (len(nodes) - 1)
    available = max(0.0, slot_box.height - total_gutter)
    weights = [_row_weight(node) for node in nodes]
    weight_sum = sum(weights)
    boxes: dict[str, PctBox] = {}
    top = slot_box.y
    for node, weight in zip(nodes, weights, strict=True):
        height = available * (weight / weight_sum)
        node_id = str(node.get("data-id") or "")
        boxes[node_id] = PctBox(x=slot_box.x, y=top, width=slot_box.width, height=height)
        top += height + NESTED_GUTTER_PCT
    return boxes


def _row_slots(row: Tag) -> list[Tag]:
    """Return a row's direct children that are a slot: ``arch-node``, ``arch-col`` or ``arch-spacer``."""
    return row.find_all(attrs={"data-type": lambda v: v in _ROW_SLOT_TYPES}, recursive=False)


def _resolve_row_slots(row: Tag, row_top: float, row_height: float) -> dict[str, PctBox]:
    """Compute the boxes of every real node in one row, recursing into ``arch-col`` slots.

    Each direct child of the row is one horizontal slot, proportional to its
    ``data-span`` (default 1, exactly as before). A slot that is an
    ``arch-node`` gets that slot's box directly (V1 behaviour, unchanged). A
    slot that is an ``arch-col`` instead gets its box used as the frame for a
    nested vertical stack (``_compute_col_boxes``), so several small nodes can
    share one column while a wide node next to them keeps the full row height.
    An ``arch-spacer`` slot reserves width and produces no node box: it is how
    a node in one row aligns under a specific node of a different row without
    spanning the whole row (see ``skill/types/arch-diagram.md``).
    """
    slots = _row_slots(row)
    if not slots:
        return {}
    total_gutter = GUTTER_COL_PCT * (len(slots) - 1)
    available = max(0.0, 100.0 - total_gutter)
    spans = [_node_span(slot) for slot in slots]
    span_sum = sum(spans)
    resolved: dict[str, PctBox] = {}
    left = 0.0
    for slot, span in zip(slots, spans, strict=True):
        width = available * (span / span_sum)
        slot_box = PctBox(x=left, y=row_top, width=width, height=row_height)
        slot_type = str(slot.get("data-type"))
        if slot_type == "arch-node":
            node_id = str(slot.get("data-id") or "")
            box = _resolve_locked_box(slot, slot_box)
            resolved[node_id] = box
            _write_node_box(slot, box)
        elif slot_type == "arch-col":
            # The col itself also gets a written box (like a node): it is what
            # lets an arch-col carry its own border/background, positioned at
            # the right place, wrapping the nested nodes it distributes.
            _write_node_box(slot, slot_box)
            inner_nodes = slot.find_all(attrs={"data-type": "arch-node"}, recursive=False)
            inner_computed = _compute_col_boxes(inner_nodes, slot_box)
            for inner_node in inner_nodes:
                inner_id = str(inner_node.get("data-id") or "")
                # Kept diagram-relative for routing/lanes/collisions...
                diagram_box = _resolve_locked_box(inner_node, inner_computed[inner_id], container=slot_box)
                resolved[inner_id] = diagram_box
                # ...but written col-relative, since the col is the browser's
                # actual containing block for this node's percentages.
                _write_node_box(inner_node, _to_local(diagram_box, slot_box))
        # arch-spacer: width already reserved above, no box to resolve or render.
        left += width + GUTTER_COL_PCT
    return resolved


def _write_node_box(node: Tag, box: PctBox) -> None:
    """Write a node's computed box as ``data-x/y/width/height`` plus the mirroring inline style.

    Never overwrites a node flagged ``data-layout="manual"``: that node's position
    was set by a human drag in the browser and must survive future recomputations.
    """
    if node.get("data-layout") == "manual":
        return
    x, y, w, h = (round(v, ROUND_NDIGITS) for v in (box.x, box.y, box.width, box.height))
    node["data-x"] = f"{x}"
    node["data-y"] = f"{y}"
    node["data-width"] = f"{w}"
    node["data-height"] = f"{h}"
    node["style"] = _merge_style(
        _style_attr(node),
        {"position": "absolute", "left": f"{x}%", "top": f"{y}%", "width": f"{w}%", "height": f"{h}%"},
    )


# ---------------------------------------------------------------------------
# Edge geometry
# ---------------------------------------------------------------------------


def _boxes_share_a_band(source: PctBox, target: PctBox) -> bool:
    """True when a straight horizontal line between ``source`` and ``target`` makes sense:
    their vertical ranges overlap.

    Two nodes declared in the same ``arch-row`` no longer guarantees the same
    height once ``arch-col`` lets a row hold a nested vertical stack: a tall
    node beside a 3-deep stack shares a row with all three, but only overlaps
    each of them for part of its own height. Routing must key off the actual
    boxes, never off the row index.
    """
    return min(source.bottom, target.bottom) - max(source.y, target.y) > 0


def _band_entry_y(source: PctBox, target: PctBox) -> float:
    """Pick the y for a horizontal connector: the middle of the overlap when the two
    boxes' vertical ranges intersect, else the closest point on ``source`` to ``target``'s
    own centre (so the line still leaves from a point that exists on the source box).
    """
    overlap_top = max(source.y, target.y)
    overlap_bottom = min(source.bottom, target.bottom)
    if overlap_bottom > overlap_top:
        return (overlap_top + overlap_bottom) / 2
    return min(max(target.mid_y, source.y), source.bottom)


def _same_row_geometry(source: PctBox, target: PctBox) -> EdgeGeometry:
    """Route a connector between two nodes that share a vertical band: one straight
    horizontal line, entering ``target`` at a y that is guaranteed to land on its body
    (see ``_band_entry_y``), not necessarily at ``source``'s own centre.

    The tip always ends on the target's near edge, whichever side it is on, so
    the arrow direction always matches ``data-from`` -> ``data-to`` regardless
    of which node happens to sit visually on the left.
    """
    y = _band_entry_y(source, target)
    if source.mid_x <= target.mid_x:
        x_start, x_end, tip_direction, tip_x = source.right, target.x, "r", target.x
    else:
        x_start, x_end, tip_direction, tip_x = target.right, source.x, "l", target.right
    width = max(0.0, x_end - x_start)
    segments = (LineSegment("h", x_start, y, width),) if width > 0 else ()
    mid_x = (x_start + x_end) / 2 if width > 0 else tip_x
    return EdgeGeometry(
        segments=segments,
        tip_direction=tip_direction,
        tip_x=tip_x,
        tip_y=y,
        label_x=mid_x,
        label_y=y + LABEL_OFFSET_PCT,
        label_align="center",
        mid_x=mid_x,
        mid_y=y,
    )


_OBSTACLE_CLEARANCE_PCT = 0.5
"""Half-thickness used to test whether a straight segment cuts through another node."""


def _segment_box(segment: LineSegment) -> PctBox:
    """A thin box around one segment, used only to test for obstacle crossings."""
    if segment.axis == "h":
        return PctBox(
            x=segment.x,
            y=segment.y - _OBSTACLE_CLEARANCE_PCT,
            width=segment.length,
            height=_OBSTACLE_CLEARANCE_PCT * 2,
        )
    return PctBox(
        x=segment.x - _OBSTACLE_CLEARANCE_PCT,
        y=segment.y,
        width=_OBSTACLE_CLEARANCE_PCT * 2,
        height=segment.length,
    )


def _crosses_any_obstacle(geometry: EdgeGeometry, obstacles: list[PctBox]) -> bool:
    """True when any segment of ``geometry`` cuts through one of ``obstacles``.

    Needed because "two nodes share a vertical band" (see ``_boxes_share_a_band``)
    only says a straight horizontal line is *geometrically possible* between them;
    it says nothing about a third node sitting between the two in that same band
    (e.g. a fan-out from one source to several targets at increasing x, where a
    nearer target's box sits directly in the path to a farther one).
    """
    return any(_segment_box(segment).overlaps(obstacle) for segment in geometry.segments for obstacle in obstacles)


def _adjacent_row_geometry(source: PctBox, target: PctBox, *, source_above: bool) -> EdgeGeometry:
    """Route a connector between two nodes in different rows.

    Two aligned columns (same ``mid_x``, within a small tolerance) collapse to
    a single straight vertical line: no arithmetic can make it crooked, both
    ends share literally the same x. Otherwise the route is a vertical/
    horizontal/vertical elbow through the gutter rail between the two rows.
    """
    aligned = abs(source.mid_x - target.mid_x) < ALIGNMENT_TOLERANCE_PCT
    tip_direction = "d" if source_above else "u"
    tip_x = target.mid_x
    tip_y = target.y if source_above else target.bottom

    segments: tuple[LineSegment, ...]
    if aligned:
        start_y = source.bottom if source_above else target.bottom
        end_y = target.y if source_above else source.y
        length = max(0.0, end_y - start_y)
        segments = (LineSegment("v", source.mid_x, start_y, length),)
        mid_y = start_y + length / 2
        return EdgeGeometry(
            segments=segments,
            tip_direction=tip_direction,
            tip_x=tip_x,
            tip_y=tip_y,
            label_x=source.mid_x + LABEL_OFFSET_PCT,
            label_y=mid_y,
            label_align="side",
            mid_x=source.mid_x,
            mid_y=mid_y,
        )

    rail_y = (source.bottom + target.y) / 2 if source_above else (target.bottom + source.y) / 2
    x_left, x_right = sorted((source.mid_x, target.mid_x))
    if source_above:
        v1 = LineSegment("v", source.mid_x, source.bottom, max(0.0, rail_y - source.bottom))
        v2 = LineSegment("v", target.mid_x, rail_y, max(0.0, target.y - rail_y))
    else:
        v1 = LineSegment("v", source.mid_x, rail_y, max(0.0, source.y - rail_y))
        v2 = LineSegment("v", target.mid_x, target.bottom, max(0.0, rail_y - target.bottom))
    segments = (v1, LineSegment("h", x_left, rail_y, x_right - x_left), v2)
    mid_x = (source.mid_x + target.mid_x) / 2
    return EdgeGeometry(
        segments=segments,
        tip_direction=tip_direction,
        tip_x=tip_x,
        tip_y=tip_y,
        label_x=mid_x,
        label_y=rail_y + LABEL_OFFSET_PCT,
        label_align="center",
        mid_x=mid_x,
        mid_y=rail_y,
    )


def _side_exit_geometry(source: PctBox, target: PctBox, *, exit_right: bool) -> EdgeGeometry:
    """Route a cross-row connector by leaving ``source`` through its own left/right edge
    (never its bottom/top), dropping through the column gutter just outside that edge, and
    entering ``target`` from its near side.

    Chosen over ``_adjacent_row_geometry``'s bottom/top elbow whenever the target is more
    horizontally than vertically offset from the source (see ``_route_edge``): that elbow's
    horizontal leg runs the FULL row-to-row gutter rail regardless of how close the two
    boxes already are in x, which visually reads as "hugging whatever sits directly below
    source before turning" on a case like ``ia_chat`` (stacked above ``ia_studio`` in the
    same ``arch-col``) reaching sideways into ``api_iachat``. Exiting through the side
    instead starts the horizontal motion immediately, at the row's own height, which is
    both shorter (no detour down to a rail only to come back up/down again) and reads as a
    single diagonal-ish move instead of a right-angle detour around a sibling.

    The channel sits at ``GUTTER_COL_PCT / 2`` past source's own edge: real free space only
    when nothing else occupies that gutter's height range, which the caller (``_route_edge``)
    must verify with ``_crosses_any_obstacle`` before using this geometry, exactly as every
    other candidate route in this module.
    """
    channel_x = source.right + GUTTER_COL_PCT / 2 if exit_right else source.x - GUTTER_COL_PCT / 2
    source_edge_x = source.right if exit_right else source.x
    h1 = LineSegment(
        "h", min(source_edge_x, channel_x), source.mid_y, abs(channel_x - source_edge_x) or GUTTER_COL_PCT / 2
    )
    v = LineSegment("v", channel_x, min(source.mid_y, target.mid_y), abs(target.mid_y - source.mid_y))
    entering_from_right = channel_x >= target.mid_x
    tip_direction = "l" if entering_from_right else "r"
    tip_x = target.right if entering_from_right else target.x
    h2 = LineSegment("h", min(channel_x, tip_x), target.mid_y, abs(channel_x - tip_x))
    return EdgeGeometry(
        segments=(h1, v, h2),
        tip_direction=tip_direction,
        tip_x=tip_x,
        tip_y=target.mid_y,
        label_x=channel_x,
        label_y=(source.mid_y + target.mid_y) / 2,
        label_align="side",
        mid_x=channel_x,
        mid_y=(source.mid_y + target.mid_y) / 2,
    )


def _detour_geometry(source: PctBox, target: PctBox, rail_y: float) -> EdgeGeometry:
    """Route an elbow through an explicit ``rail_y`` that is not necessarily between
    ``source`` and ``target`` (typically just below an entire row), so the horizontal
    leg clears a node sitting in a column between the two, instead of cutting through it.

    Unlike ``_adjacent_row_geometry``, the entry direction into each box is decided
    independently (``rail_y`` can be below both boxes, above both, or between them).
    """
    v1 = (
        LineSegment("v", source.mid_x, source.bottom, max(0.0, rail_y - source.bottom))
        if rail_y >= source.bottom
        else LineSegment("v", source.mid_x, rail_y, max(0.0, source.y - rail_y))
    )
    if rail_y >= target.bottom:
        v2 = LineSegment("v", target.mid_x, target.bottom, max(0.0, rail_y - target.bottom))
        tip_direction, tip_y = "u", target.bottom
    else:
        v2 = LineSegment("v", target.mid_x, rail_y, max(0.0, target.y - rail_y))
        tip_direction, tip_y = "d", target.y
    x_left, x_right = sorted((source.mid_x, target.mid_x))
    segments = (v1, LineSegment("h", x_left, rail_y, x_right - x_left), v2)
    mid_x = (source.mid_x + target.mid_x) / 2
    return EdgeGeometry(
        segments=segments,
        tip_direction=tip_direction,
        tip_x=target.mid_x,
        tip_y=tip_y,
        label_x=mid_x,
        label_y=rail_y + LABEL_OFFSET_PCT,
        label_align="center",
        mid_x=mid_x,
        mid_y=rail_y,
    )


def _side_detour_geometry(source: PctBox, target: PctBox, channel_x: float, exit_rail_y: float) -> EdgeGeometry:
    """Route via a vertical channel at ``channel_x`` (a column gutter just outside
    ``target``, see ``_best_detour``): out of ``source`` to ``exit_rail_y`` (the row's
    own below/above rail, whichever is clear on the source side), across to the
    channel, along the channel to ``target``'s own height, then horizontally into
    target's near side.

    Last resort when both ``source`` and ``target`` are blocked on the row-detour side
    that would normally reach them (e.g. ``source`` has a sibling above it AND
    ``target`` has a sibling below it: no single "below the row" or "above the row"
    rail can reach both free sides at once). ``channel_x`` must be a genuine gutter
    (the diagram's own outer edge is NOT reliably empty: a full-width row's outermost
    column commonly touches x=0 or x=100 exactly, so "outside the diagram" and "outside
    the column" are not the same thing there). Leaving ``source`` via a row rail first
    (rather than at its own mid_y) avoids cutting through whatever else sits between
    ``source`` and the channel in the same row.
    """
    entering_from_right = channel_x >= target.mid_x
    tip_direction = "l" if entering_from_right else "r"
    tip_x = target.right if entering_from_right else target.x
    v1 = (
        LineSegment("v", source.mid_x, source.bottom, max(0.0, exit_rail_y - source.bottom))
        if exit_rail_y >= source.bottom
        else LineSegment("v", source.mid_x, exit_rail_y, max(0.0, source.y - exit_rail_y))
    )
    x_left, x_right = sorted((source.mid_x, channel_x))
    h1 = LineSegment("h", x_left, exit_rail_y, x_right - x_left)
    v2 = LineSegment("v", channel_x, min(exit_rail_y, target.mid_y), abs(target.mid_y - exit_rail_y))
    h2 = LineSegment("h", min(channel_x, tip_x), target.mid_y, abs(channel_x - tip_x))
    return EdgeGeometry(
        segments=(v1, h1, v2, h2),
        tip_direction=tip_direction,
        tip_x=tip_x,
        tip_y=target.mid_y,
        label_x=channel_x,
        label_y=(exit_rail_y + target.mid_y) / 2,
        label_align="side",
        mid_x=channel_x,
        mid_y=(exit_rail_y + target.mid_y) / 2,
    )


def _best_detour(
    source: PctBox, target: PctBox, *, row_top: float, row_height: float, obstacles: list[PctBox]
) -> EdgeGeometry:
    """Try a detour below the row, then above it, then around the diagram's outer
    margin, and keep the first that does not cut through an obstacle (falls back to
    "below" if none is clean).

    A rail below the row is not automatically safe: if ``target`` is the top of its
    own ``arch-col`` with a sibling directly beneath it, entering from below cuts
    through that sibling. Routing above the row instead enters from the free top
    edge — unless ``source`` itself has a sibling directly ABOVE it, in which case
    neither a single "below" nor "above" rail can reach both free sides at once (see
    ``_side_detour_geometry``).
    """
    below_y = min(row_top + row_height + GUTTER_ROW_PCT / 2, 99.0)
    below = _detour_geometry(source, target, rail_y=below_y)
    if not _crosses_any_obstacle(below, obstacles):
        return below
    above_y = max(row_top - GUTTER_ROW_PCT / 2, 1.0)
    above = _detour_geometry(source, target, rail_y=above_y)
    if not _crosses_any_obstacle(above, obstacles):
        return above
    # A column gutter just outside target is genuine empty space (reserved by the
    # distribution algorithm) even when the diagram's own outer edge is not — EXCEPT
    # when target's own column already reaches that edge (a full-width row's outermost
    # column commonly touches x=0 or x=100 exactly): skip a channel that would fall
    # outside the diagram, it is not real space, just an out-of-bounds coordinate.
    candidate_channels = [
        x for x in (target.right + GUTTER_COL_PCT / 2, target.x - GUTTER_COL_PCT / 2) if 0.0 <= x <= DIAGRAM_MAX_PCT
    ]
    for channel_x in candidate_channels:
        for exit_rail_y in (below_y, above_y):
            side = _side_detour_geometry(source, target, channel_x, exit_rail_y)
            if not _crosses_any_obstacle(side, obstacles):
                return side
    return below


def _route_edge(
    source: PctBox,
    target: PctBox,
    *,
    row_diff: int,
    row_geom: tuple[float, float],
    obstacles: list[PctBox],
) -> EdgeGeometry:
    """Pick the right geometry for one edge, keyed off the real boxes, never the row index:
    an ``arch-col`` can put two same-row nodes at very different heights, so "same row"
    no longer implies "a straight horizontal line makes sense" (see ``_boxes_share_a_band``).
    ``obstacles`` is every other node's box in the diagram: a straight line or a detour is
    only used when it does not cut through one of them (see ``_crosses_any_obstacle`` and
    ``_best_detour``, which tries routing both below and above the row).
    """
    row_top, row_height = row_geom
    if _boxes_share_a_band(source, target):
        candidate = _same_row_geometry(source, target)
        if not _crosses_any_obstacle(candidate, obstacles):
            return candidate
        return _best_detour(source, target, row_top=row_top, row_height=row_height, obstacles=obstacles)

    aligned = abs(source.mid_x - target.mid_x) < ALIGNMENT_TOLERANCE_PCT
    if row_diff == 0 and not aligned:
        # Different arch-col slots of the SAME nominal row (not simply stacked in
        # the same column): a naive elbow between them would cut straight through
        # whatever sits in a column between the two, since it is also inside that
        # row's vertical span. Detour below or above the whole row instead.
        return _best_detour(source, target, row_top=row_top, row_height=row_height, obstacles=obstacles)

    if not aligned and abs(source.mid_x - target.mid_x) > abs(source.mid_y - target.mid_y):
        # More horizontal offset than vertical: a bottom/top elbow's horizontal leg would
        # run the row-to-row gutter rail for the full dx regardless of how close the two
        # boxes already are, which reads as hugging a sibling before turning (see
        # _side_exit_geometry). Try leaving through source's own near side first, in both
        # directions, and only fall through to the elbow if neither is obstacle-free.
        toward_target = source.mid_x <= target.mid_x
        for exit_right in (toward_target, not toward_target):
            side = _side_exit_geometry(source, target, exit_right=exit_right)
            channel_x = side.mid_x
            if 0.0 <= channel_x <= DIAGRAM_MAX_PCT and not _crosses_any_obstacle(side, obstacles):
                return side

    elbow = _adjacent_row_geometry(source, target, source_above=source.mid_y <= target.mid_y)
    if not _crosses_any_obstacle(elbow, obstacles):
        return elbow
    # The elbow's own rail (the midpoint of the gap between source and target) only
    # ever considers the two of them: a third node sharing target's (or source's) col
    # can still sit exactly on that rail (e.g. the OTHER node stacked in the same col
    # as target). Fall back to the same obstacle-aware detour used for same-row cases.
    return _best_detour(source, target, row_top=row_top, row_height=row_height, obstacles=obstacles)


def _segment_class(axis: str) -> str:
    """CSS class for one segment, matching the classes already shipped in the bootstraps."""
    return "arch-line-h" if axis == "h" else "arch-line-v"


_SEGMENT_COLOR_PROP = {"h": "border-top-color", "v": "border-left-color"}
"""Which CSS border side carries an ``arch-line-*`` segment's colour, per axis."""

_TIP_COLOR_PROP = {
    "r": "border-left-color",
    "l": "border-right-color",
    "d": "border-top-color",
    "u": "border-bottom-color",
}
"""Which CSS border side carries an ``arch-tip-*`` triangle's colour, per direction."""


def _segment_style(segment: LineSegment, color: str | None = None) -> dict[str, str]:
    """Inline style for one line segment, in percent of the diagram container.

    ``color`` overrides the bootstrap's fixed ``.arch-line-*`` colour (an edge's
    optional ``data-color``, matching the accent of the flow it belongs to).
    """
    x, y, length = (round(v, ROUND_NDIGITS) for v in (segment.x, segment.y, segment.length))
    style = {"position": "absolute", "left": f"{x}%", "top": f"{y}%"}
    style["width" if segment.axis == "h" else "height"] = f"{length}%"
    if color:
        style[_SEGMENT_COLOR_PROP[segment.axis]] = color
    return style


def _tip_style(geometry: EdgeGeometry, color: str | None = None) -> dict[str, str]:
    """Inline style for a connector's arrow tip, anchored via ``transform`` on the target edge."""
    x, y = (round(v, ROUND_NDIGITS) for v in (geometry.tip_x, geometry.tip_y))
    style = {
        "position": "absolute",
        "left": f"{x}%",
        "top": f"{y}%",
        "transform": _TIP_TRANSFORMS[geometry.tip_direction],
    }
    if color:
        style[_TIP_COLOR_PROP[geometry.tip_direction]] = color
    return style


def _label_style(geometry: EdgeGeometry, color: str | None = None) -> dict[str, str]:
    """Inline style for a connector's label, centered on a horizontal run or set beside a vertical one."""
    x, y = (round(v, ROUND_NDIGITS) for v in (geometry.label_x, geometry.label_y))
    style = {"position": "absolute", "left": f"{x}%", "top": f"{y}%"}
    if geometry.label_align == "center":
        style["transform"] = "translateX(-50%)"
    if color:
        style["color"] = color
    return style


def _ensure_edge_id(edge: Tag, counter: itertools.count[int]) -> str:
    """Assign a stable ``data-edge-id`` on first encounter; reuse it on later runs.

    This is what makes re-running the layout idempotent: the decorative
    elements generated for one edge are always found and replaced by the same
    key, instead of accumulating duplicates across repeated calls.
    """
    edge_id = edge.get("data-edge-id")
    if not edge_id:
        edge_id = f"edge-{next(counter)}"
        edge["data-edge-id"] = edge_id
    return str(edge_id)


def _clear_edge_decoration(diagram: Tag, edge_id: str) -> None:
    """Remove the decorative elements a previous layout run generated for one edge."""
    for decoration in diagram.find_all(attrs={"data-edge-of": edge_id}):
        decoration.decompose()


def _vertical_gap(source: PctBox, target: PctBox) -> float:
    """Vertical gap between two node boxes stacked one above the other, in percent of the
    diagram; ``0.0`` when they share a vertical band (side by side, or overlapping).

    Deliberately vertical-only: a horizontal gap of the same magnitude is a genuine,
    already wide-enough gutter between flow steps (``GUTTER_COL_PCT``/``GUTTER_ROW_PCT``),
    never the cramped ``arch-col`` stacking gap (``NESTED_GUTTER_PCT``) this check exists
    to catch. Used by ``_render_edge`` to decide whether a numbered step badge needs
    ``_badge_position``'s side offset instead of the geometric midpoint.
    """
    return max(0.0, target.y - source.bottom, source.y - target.bottom)


def _badge_position(source: PctBox, target: PctBox, obstacles: list[PctBox]) -> tuple[float, float]:
    """Pick a clear spot for a numbered step badge when the two nodes it marks are too
    close together for the badge's own size (see ``BADGE_MIN_GUTTER_PCT``): typically two
    nodes stacked directly one above the other inside the same ``arch-col``, connected by
    a same-row or adjacent-row edge whose segment collapses to (near) zero length.

    The geometric midpoint between the two node borders sits in that cramped gutter, so it
    always overlaps both borders. Widening the gutter globally (``NESTED_GUTTER_PCT``) would
    loosen every stacked-col diagram's spacing just to fix the rare badge case; instead the
    badge itself is pushed sideways, just outside the pair's combined bounding box, on
    whichever side (right first, then left) does not collide with another node. Vertically
    it stays centered on the real border between the two nodes, so it still visually reads
    as marking that specific boundary.
    """
    boundary_y = (source.bottom + target.y) / 2 if source.bottom <= target.y else (target.bottom + source.y) / 2
    left = min(source.x, target.x)
    right = max(source.right, target.right)
    for candidate_x in (right + BADGE_CLEARANCE_PCT, left - BADGE_CLEARANCE_PCT):
        if not (0.0 <= candidate_x <= DIAGRAM_MAX_PCT):
            continue
        probe = PctBox(x=candidate_x - 0.1, y=boundary_y - 0.1, width=0.2, height=0.2)
        if not any(probe.overlaps(obstacle) for obstacle in obstacles):
            return candidate_x, boundary_y
    # Both sides are blocked (or off-diagram): fall back to the geometric midpoint rather
    # than a coordinate outside 0-100%, a cosmetic overlap beats an invisible badge.
    return (source.mid_x + target.mid_x) / 2, boundary_y


@dataclass(frozen=True, slots=True)
class _EdgeEndpoints:
    """The two node boxes an edge connects, plus every other node's box in the diagram.

    Bundled so ``_render_edge`` stays under the project's max-arguments lint budget;
    only used to compute a step badge's clear spot on a cramped stacked pair (see
    ``_badge_position``), everything else about rendering comes from ``EdgeGeometry``.
    """

    source: PctBox
    target: PctBox
    obstacles: list[PctBox]


def _render_edge(
    soup: BeautifulSoup,
    edge: Tag,
    edge_id: str,
    geometry: EdgeGeometry,
    endpoints: _EdgeEndpoints,
) -> None:
    """Turn one resolved ``EdgeGeometry`` into DOM elements.

    The caller must have already cleared any decoration left by a previous run
    (see ``_clear_edge_decoration``), so this function only ever adds nodes.
    ``data-color`` on the edge (optional) overrides the bootstrap's single
    fixed accent colour on every piece: segments, tip and label. ``endpoints`` is only
    used for ``_badge_position`` on a cramped stacked pair. ``data-style`` (``dashed``)
    is read straight off ``edge`` rather than taking a separate parameter.
    """
    dashed = ["dashed"] if str(edge.get("data-style") or "solid") == "dashed" else []
    color = str(edge.get("data-color") or "") or None

    if not geometry.segments:
        edge["style"] = _merge_style(_style_attr(edge), {"position": "absolute", "display": "none"})
    else:
        first, *rest = geometry.segments
        edge["class"] = _merged_classes(edge, "arch-edge", _segment_class(first.axis), *dashed)
        edge["style"] = _merge_style(_style_attr(edge), _segment_style(first, color))
        for segment in rest:
            decoration = soup.new_tag("div")
            decoration["class"] = ["arch-edge", _segment_class(segment.axis), *dashed]
            decoration["data-edge-of"] = edge_id
            decoration["style"] = "; ".join(f"{k}:{v}" for k, v in _segment_style(segment, color).items()) + ";"
            edge.insert_after(decoration)

    tip = soup.new_tag("div")
    tip["class"] = ["arch-edge", "arch-tip", f"arch-tip-{geometry.tip_direction}"]
    tip["data-edge-of"] = edge_id
    tip["style"] = "; ".join(f"{k}:{v}" for k, v in _tip_style(geometry, color).items()) + ";"
    edge.insert_after(tip)

    label_text = edge.get("data-label")
    if label_text:
        label = soup.new_tag("div")
        label["class"] = ["arch-edge-label"]
        label["data-edge-of"] = edge_id
        label["style"] = "; ".join(f"{k}:{v}" for k, v in _label_style(geometry, color).items()) + ";"
        label.string = str(label_text)
        edge.insert_after(label)

    step = edge.get("data-step")
    if step:
        source, target, obstacles = endpoints.source, endpoints.target, endpoints.obstacles
        badge_color = str(edge.get("data-color") or "#284AAA")
        stacked = abs(source.mid_x - target.mid_x) < ALIGNMENT_TOLERANCE_PCT or (
            source.x < target.right and target.x < source.right
        )
        if stacked and 0.0 < _vertical_gap(source, target) < BADGE_MIN_GUTTER_PCT:
            raw_badge_x, raw_badge_y = _badge_position(source, target, obstacles)
        else:
            raw_badge_x, raw_badge_y = geometry.mid_x, geometry.mid_y
        badge_x, badge_y = (round(v, ROUND_NDIGITS) for v in (raw_badge_x, raw_badge_y))
        badge = soup.new_tag("div")
        badge["class"] = ["arch-edge-badge"]
        badge["data-edge-of"] = edge_id
        badge["style"] = (
            f"position:absolute; left:{badge_x}%; top:{badge_y}%; "
            f"background:{badge_color}; transform:translate(-50%,-50%);"
        )
        badge.string = str(step)
        edge.insert_after(badge)


# ---------------------------------------------------------------------------
# Lanes
# ---------------------------------------------------------------------------


def _layout_lane(lane: Tag, row_boxes_by_index: dict[int, list[PctBox]]) -> None:
    """Compute a lane's bounding box from the union of its declared rows' resolved node boxes.

    The box is always derived, never guessed: this is what makes a lane
    incapable of clipping a node it is supposed to contain, unlike an ad hoc
    dashed box sized by hand.
    """
    raw_range = str(lane.get("data-rows") or "")
    if not raw_range:
        return
    try:
        start, end = _parse_row_range(raw_range)
    except ValueError:
        logger.warning("arch-lane %s: data-rows invalide (%r), lane ignoree.", lane.get("data-lane-id"), raw_range)
        return

    boxes = [box for index in range(start, end + 1) for box in row_boxes_by_index.get(index, [])]
    if not boxes:
        return

    min_x = max(0.0, min(b.x for b in boxes) - LANE_PADDING_PCT)
    min_y = max(0.0, min(b.y for b in boxes) - LANE_PADDING_PCT)
    max_x = min(100.0, max(b.right for b in boxes) + LANE_PADDING_PCT)
    max_y = min(100.0, max(b.bottom for b in boxes) + LANE_PADDING_PCT)

    x, y, w, h = (round(v, ROUND_NDIGITS) for v in (min_x, min_y, max_x - min_x, max_y - min_y))
    lane["data-x"] = f"{x}"
    lane["data-y"] = f"{y}"
    lane["data-width"] = f"{w}"
    lane["data-height"] = f"{h}"
    lane["style"] = _merge_style(
        _style_attr(lane),
        {"position": "absolute", "left": f"{x}%", "top": f"{y}%", "width": f"{w}%", "height": f"{h}%"},
    )


# ---------------------------------------------------------------------------
# Collision detection (also usable standalone, e.g. on legacy hand authored diagrams)
# ---------------------------------------------------------------------------


def _detect_collisions(boxes: list[PctBox]) -> list[tuple[int, int]]:
    """Return the index pairs of boxes whose rectangles overlap."""
    return [(i, j) for i in range(len(boxes)) for j in range(i + 1, len(boxes)) if boxes[i].overlaps(boxes[j])]


def check_diagram(diagram: Tag) -> list[str]:
    """Geometric sanity check for one ``arch-diagram``: overlapping nodes.

    Legacy (hand authored ``data-x``/``data-y``, no ``arch-row``) diagrams
    only: this is the safety net for the format the skill still documents for
    very small diagrams (2-3 nodes), where the layout engine above never runs
    and nothing else verifies the hand written coordinates.

    A declarative diagram (at least one ``arch-row``) is deliberately OUT of
    scope and always returns ``[]``: ``_layout_diagram`` already guarantees
    non-overlapping placement by construction (row/column/gutter math), and a
    node nested inside an ``arch-col`` has its ``data-x``/``data-y`` written
    *col-relative* (see ``_to_local``), not diagram-relative — comparing those
    raw attributes across nodes from different columns as if they shared one
    coordinate space produces false "overlap" positives (confirmed: hundreds
    of them on every declarative diagram in a real deck). Resolving nested
    boxes back to diagram-relative before comparing would fix that, but there
    is no product path calling this function on a declarative diagram (only
    its own tests did), so the correct minimum fix is to not pretend to
    support a shape this function cannot safely check, rather than add dead
    complexity no caller needs.
    """
    if diagram.find(attrs={"data-type": "arch-row"}) is not None:
        return []
    nodes = diagram.find_all(attrs={"data-type": "arch-node"})
    boxes: list[PctBox] = []
    labels: list[str] = []
    for node in nodes:
        box = _existing_box(node)
        if box is None:
            continue
        boxes.append(box)
        labels.append(str(node.get("data-label") or node.get("data-id") or "?"))
    return [f"chevauchement: '{labels[i]}' et '{labels[j]}' se superposent." for i, j in _detect_collisions(boxes)]


# ---------------------------------------------------------------------------
# Diagram orchestration
# ---------------------------------------------------------------------------


def _layout_diagram(soup: BeautifulSoup, diagram: Tag) -> tuple[bool, list[str]]:
    """Lay out one ``arch-diagram`` element in place.

    Returns ``(updated, warnings)``. ``updated`` is False when the diagram has
    no ``arch-row`` child: it is a legacy, hand authored diagram and is left
    untouched.
    """
    rows = sorted(
        diagram.find_all(attrs={"data-type": "arch-row"}),
        key=lambda row: _safe_int(row.get("data-row"), default=0),
    )
    if not rows:
        return False, []

    warnings: list[str] = []
    row_geoms = _compute_row_boxes(rows)
    node_boxes: dict[str, PctBox] = {}
    node_row: dict[str, int] = {}
    row_boxes_by_index: dict[int, list[PctBox]] = {}

    for row_index, (row, (row_top, row_height)) in enumerate(zip(rows, row_geoms, strict=True)):
        if not _row_slots(row):
            continue
        resolved = _resolve_row_slots(row, row_top, row_height)
        row_boxes_by_index[row_index] = list(resolved.values())
        # _resolve_row_slots already wrote every node's own attributes (diagram-
        # relative for a direct slot, col-relative for one nested in an arch-col,
        # see _to_local). This loop only does bookkeeping: node -> diagram-
        # relative box / row index, for edge routing, lanes and warnings. It must
        # NOT call _write_node_box again, or a nested node's correct col-relative
        # write would be overwritten with its diagram-relative box.
        for node in row.find_all(attrs={"data-type": "arch-node"}):
            node_id = str(node.get("data-id") or "")
            if not node_id or node_id not in resolved:
                warnings.append(f"arch-node sans data-id dans la rangee {row_index}: arete non routable.")
                continue
            node_boxes[node_id] = resolved[node_id]
            node_row[node_id] = row_index

    edge_counter = itertools.count()
    for edge in diagram.find_all(attrs={"data-type": "arch-edge"}):
        edge_id = _ensure_edge_id(edge, edge_counter)
        from_id = str(edge.get("data-from") or "")
        to_id = str(edge.get("data-to") or "")
        source = node_boxes.get(from_id)
        target = node_boxes.get(to_id)
        if source is None or target is None:
            warnings.append(f"arch-edge {from_id}->{to_id}: noeud introuvable, arete ignoree.")
            continue

        row_diff = node_row[to_id] - node_row[from_id]
        if abs(row_diff) > 1:
            warnings.append(
                f"arch-edge {from_id}->{to_id}: traverse {abs(row_diff)} rangees, hors scope V1 "
                "(risque de chevaucher une rangee intermediaire, non verifie)."
            )
        obstacles = [box for nid, box in node_boxes.items() if nid not in (from_id, to_id)]
        geometry = _route_edge(
            source, target, row_diff=row_diff, row_geom=row_geoms[node_row[from_id]], obstacles=obstacles
        )
        _clear_edge_decoration(diagram, edge_id)
        _render_edge(soup, edge, edge_id, geometry, _EdgeEndpoints(source, target, obstacles))

    for lane in diagram.find_all(attrs={"data-type": "arch-lane"}):
        _layout_lane(lane, row_boxes_by_index)

    collisions = _detect_collisions(list(node_boxes.values()))
    if collisions:
        warnings.append(
            f"auto-verification: {len(collisions)} chevauchement(s) detecte(s) apres calcul "
            "(bug du moteur de layout, a signaler)."
        )
    return True, warnings


def layout_file(path: str | Path, diagram_id: str | None = None) -> LayoutReport:
    """Compute and write the layout of every declarative ``arch-diagram`` in ``path``.

    A diagram is "declarative" when it contains at least one ``arch-row``
    child; legacy diagrams (plain ``arch-node``/``data-x`` authored by hand)
    are left untouched, so both formats coexist in the same file. Pass
    ``diagram_id`` (matched against ``data-diagram-id``) to restrict the run
    to one diagram in a file that has several.
    """
    file_path = Path(path)
    with trace_span("arch_layout.layout_file", {"file.path": str(file_path)}) as span:
        html = file_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        diagrams: list[Tag] = list(soup.find_all(attrs={"data-type": "arch-diagram"}))
        if diagram_id:
            diagrams = [d for d in diagrams if d.get("data-diagram-id") == diagram_id]

        warnings: list[str] = []
        updated = 0
        for diagram in diagrams:
            was_updated, diagram_warnings = _layout_diagram(soup, diagram)
            updated += int(was_updated)
            warnings.extend(diagram_warnings)

        if updated:
            file_path.write_text(str(soup), encoding="utf-8")

        span.set_attribute("arch_layout.diagrams_updated", updated)
        span.set_attribute("arch_layout.warnings", len(warnings))
        logger.info("arch_layout %s: %d diagram(s) updated, %d warning(s)", file_path, updated, len(warnings))
        return LayoutReport(file=str(file_path), diagrams_updated=updated, warnings=tuple(warnings))
