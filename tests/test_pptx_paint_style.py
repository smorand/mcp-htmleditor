"""Pure CSS to PPTX mappings of the painted export (SPEC-0024 FR-2, FR-3, FR-4): no browser, no deck."""

from __future__ import annotations

import pytest

from mcp_htmleditor.export.pptx_paint_style import (
    Bullet,
    alpha_of,
    bullet_for,
    first_face,
    fit_picture,
    hanging_indent,
    line_dash,
    parse_colour,
    parse_gradient,
    parse_position,
    parse_shadow,
    rgb,
    shape_for_radii,
    table_span,
    to_emu,
)

NONE = (0.0, 0.0, 0.0, 0.0)


def test_shape_for_radii_picks_the_preset() -> None:
    assert shape_for_radii((0, 0, 0, 0), 100, 50) == ("rect", ())
    assert shape_for_radii((12, 12, 12, 12), 100, 50) == ("round", (0.24,))
    assert shape_for_radii((80, 80, 80, 80), 100, 50) == ("round", (0.5,))  # capped at half the short side
    assert shape_for_radii((40, 40, 40, 40), 80, 80) == ("ellipse", ())  # 50 % of a square
    assert shape_for_radii((8, 8, 0, 0), 100, 50) == ("round_top", (0.16, 0.0))
    assert shape_for_radii((8, 0, 0, 0), 100, 50)[0] == "round"  # mixed corners keep the largest


def test_parse_gradient_angle_and_stops() -> None:
    css = "linear-gradient(135deg, rgb(26, 26, 46) 0%, rgb(22, 33, 62) 60%, rgb(15, 52, 96) 100%)"
    gradient = parse_gradient(css)
    assert gradient is not None
    assert gradient.angle == 45  # CSS 135deg is OOXML 45 (clockwise from the right)
    assert [round(p, 2) for p, _ in gradient.stops] == [0.0, 0.6, 1.0]
    assert gradient.stops[0][1] == (26, 26, 46, 1.0)


def test_parse_gradient_defaults_and_directions() -> None:
    plain = parse_gradient("linear-gradient(rgb(0, 0, 0), rgba(255, 255, 255, 0.5))")
    assert plain is not None
    assert plain.angle == 90  # CSS default 180deg: top to bottom
    assert [p for p, _ in plain.stops] == [0.0, 1.0]
    assert plain.stops[1][1][3] == 0.5
    right = parse_gradient("linear-gradient(to right, rgb(0, 0, 0), rgb(9, 9, 9))")
    assert right is not None
    assert right.angle == 0
    corner = parse_gradient("linear-gradient(to bottom right, rgb(0, 0, 0), rgb(9, 9, 9))")
    assert corner is not None
    assert corner.angle == 45


def test_parse_gradient_spreads_missing_positions() -> None:
    gradient = parse_gradient("linear-gradient(0deg, rgb(1, 1, 1), rgb(2, 2, 2), rgb(3, 3, 3), rgb(4, 4, 4))")
    assert gradient is not None
    assert [round(p, 3) for p, _ in gradient.stops] == [0.0, 0.333, 0.667, 1.0]


@pytest.mark.parametrize(
    "css",
    [None, "", "none", "url(a.png)", "radial-gradient(rgb(0, 0, 0), rgb(1, 1, 1))", "linear-gradient(red, blue)"],
)
def test_parse_gradient_rejects_what_it_cannot_map(css: str | None) -> None:
    assert parse_gradient(css) is None


def test_parse_shadow_keeps_simple_outer_shadows_only() -> None:
    shadow = parse_shadow("rgba(0, 0, 0, 0.4) 0px 8px 32px 0px")
    assert shadow is not None
    assert (shadow.dx, shadow.dy, shadow.blur) == (0, 8, 32)
    assert shadow.colour[3] == 0.4
    assert shadow.distance == 8
    assert shadow.direction == 90  # straight down
    assert parse_shadow("rgba(0, 0, 0, 0.2) 4px 4px 8px 3px") is None  # spread
    assert parse_shadow("rgba(0, 0, 0, 0.2) 0px 0px 8px 0px inset") is None
    assert parse_shadow("none") is None
    assert parse_shadow("rgba(0, 0, 0, 0) 0px 1px 2px 0px") is None


def test_shadow_without_offset_has_no_direction() -> None:
    shadow = parse_shadow("rgb(0, 0, 0) 0px 0px 10px 0px")
    assert shadow is not None
    assert (shadow.distance, shadow.direction) == (0, 0)


def test_fit_picture_cover_crops_the_long_side() -> None:
    box, crop = fit_picture("cover", (10, 20, 100, 100), (200, 100))
    assert box == (10, 20, 100, 100)
    assert crop == (0.25, 0.0, 0.25, 0.0)
    _, tall = fit_picture("cover", (0, 0, 100, 100), (100, 200))
    assert tall == (0.0, 0.25, 0.0, 0.25)


def test_fit_picture_honours_object_position() -> None:
    _, crop = fit_picture("cover", (0, 0, 100, 100), (200, 100), "0% 50%")
    assert crop == (0.0, 0.0, 0.5, 0.0)
    assert parse_position("right bottom") == (1.0, 1.0)
    assert parse_position(None) == (0.5, 0.5)
    assert parse_position("25%") == (0.25, 0.5)


def test_fit_picture_contain_shrinks_the_box() -> None:
    box, crop = fit_picture("contain", (0, 0, 100, 100), (200, 100))
    assert box == (0, 25, 100, 50)
    assert crop == NONE
    box, _ = fit_picture("contain", (0, 0, 100, 100), (100, 200))
    assert box == (25, 0, 50, 100)


def test_fit_picture_stretches_when_it_cannot_decide() -> None:
    for fit, natural in (("fill", (10, 10)), ("cover", None), ("cover", (0, 0)), ("none", (5, 5))):
        assert fit_picture(fit, (1, 2, 30, 40), natural) == ((1, 2, 30, 40), NONE)


def test_bullet_for_markers_and_numbers() -> None:
    assert bullet_for("disc") == Bullet("\u2022", None)
    assert bullet_for("circle").char == "\u25e6"
    assert bullet_for("square").char == "\u25aa"
    assert bullet_for("decimal") == Bullet(None, "arabicPeriod")
    assert bullet_for("upper-roman").numbering == "romanUcPeriod"
    assert bullet_for("lower-alpha").numbering == "alphaLcPeriod"
    assert bullet_for('"\u2014 "') == Bullet("\u2014", None)
    assert bullet_for("unknown-kind").char == "\u2022"


def test_hanging_indent_grows_with_the_font() -> None:
    assert hanging_indent(8) == 10.8
    assert hanging_indent(4) == 10.0  # never narrower than a marker
    assert hanging_indent(20) > hanging_indent(12)


def test_table_span_is_inclusive() -> None:
    assert table_span({"r": 1, "c": 0, "rs": 2, "cs": 3}) == (1, 0, 2, 2)
    assert table_span({"r": 0, "c": 4, "rs": 1, "cs": 1}) == (0, 4, 0, 4)


def test_colour_helpers() -> None:
    assert parse_colour("rgb(10, 20, 30)") == (10, 20, 30, 1.0)
    assert parse_colour("rgba(10, 20, 30, 0.25)") == (10, 20, 30, 0.25)
    assert parse_colour("transparent") is None
    assert str(rgb((255.4, 0, 300))) == "FF00FF"
    assert alpha_of((1, 2, 3, 0.5), 0.5) == 0.25
    assert alpha_of((1, 2, 3), 0.8) == 0.8
    assert alpha_of(None, 2.0) == 1.0


def test_first_face_skips_system_aliases_and_maps_generics() -> None:
    assert first_face('-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif') == "Segoe UI"
    assert first_face("'IBM Plex Sans', Arial") == "IBM Plex Sans"
    assert first_face("serif") == "Georgia"
    assert first_face("monospace") == "Courier New"
    assert first_face("") == "Arial"


def test_unit_conversions() -> None:
    assert to_emu((1, 2, 3, 4)) == (12700, 25400, 38100, 50800)
    assert to_emu((0, 0, 0, 0))[2:] == (1, 1)  # a hairline survives
    assert line_dash("dashed") == "dash"
    assert line_dash("dotted") == "sysDot"
    assert line_dash("solid") is None
