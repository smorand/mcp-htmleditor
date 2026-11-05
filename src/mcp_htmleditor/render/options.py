"""Render options: the scale of the picture and the size it gives (SPEC-0008 DEC-009).

The scale is kept as a ``Decimal`` built from its text, so the size never goes through binary floats.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Final

from . import CANVAS_HEIGHT, CANVAS_WIDTH, RenderError

DEFAULT_SCALE: Final = Decimal("0.5")
MIN_SCALE: Final = Decimal("0.1")
MAX_SCALE: Final = Decimal(1)
SCALE_MESSAGE: Final = "Scale must be between 0.1 and 1"


def parse_scale(raw: str | float | None) -> Decimal:
    """The scale as a ``Decimal`` in [0.1, 1]; ``None`` gives 0.5; anything else raises ``RenderError``."""
    if raw is None:
        return DEFAULT_SCALE
    text = repr(raw) if isinstance(raw, float) else raw.strip()
    try:
        scale = Decimal(text)
    except InvalidOperation:
        raise RenderError(SCALE_MESSAGE) from None
    if not scale.is_finite() or not MIN_SCALE <= scale <= MAX_SCALE:
        raise RenderError(SCALE_MESSAGE)
    return scale


def output_size(scale: Decimal) -> tuple[int, int]:
    """``CANVAS_WIDTH x scale`` by ``CANVAS_HEIGHT x scale``, each rounded half up."""
    return _round_half_up(CANVAS_WIDTH * scale), _round_half_up(CANVAS_HEIGHT * scale)


def _round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
