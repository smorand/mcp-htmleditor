"""BL-0033: the painted PPTX export keeps the ``max-width`` of a text (the editor's width bar writes it).

The painted export lays out text with the browser, so a block narrowed to 300 px comes out as a text box of about
300 points; a block without ``max-width`` keeps the width of its container.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from tests.deck_support import run_cli
from tests.render_support import needs_chromium

SLIDE = (
    '<!DOCTYPE html><html data-doc-type="presentation"><body>'
    '<section class="slide active" data-type="slide" data-id="s1" data-title="One" '
    'style="width:960px;height:540px;position:relative">'
    '<p id="narrow" style="max-width:300px">Narrowed to three hundred pixels with enough words to wrap on several '
    "lines for sure yes.</p>"
    '<p id="wide">Full width paragraph with enough words to stay on a single line when the box is wide.</p>'
    "</section></body></html>"
)


def box_widths(path: Path) -> dict[str, float]:
    """Width in points of each text box, keyed by the first word of its text."""
    widths = {}
    for shape in Presentation(str(path)).slides[0].shapes:
        if shape.has_text_frame and shape.text_frame.text.strip():
            widths[shape.text_frame.text.split()[0]] = shape.width / 12700
    return widths


@needs_chromium
def test_a_text_with_max_width_keeps_it_in_the_painted_pptx(tmp_path: Path) -> None:
    deck = tmp_path / "deck.html"
    deck.write_text(SLIDE, encoding="utf-8")
    output = tmp_path / "out.pptx"

    _, stderr, code = run_cli("export", "pptx", str(deck), str(output))

    widths = box_widths(output)
    assert code == 0, stderr
    assert "without the rendered finish" not in stderr
    assert 280 <= widths["Narrowed"] <= 340
    assert widths["Full"] > 500
