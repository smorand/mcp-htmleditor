"""Names of the PPTX exporter stay importable from ``to_pptx`` after the split (SPEC-0012/DT-003)."""

from __future__ import annotations

import importlib
from pathlib import Path

from mcp_htmleditor.export import pptx_style

MODEL_PATH = Path(__file__).resolve().parent.parent / "src" / "mcp_htmleditor" / "export" / "pptx_model.py"


def test_public_names_import_from_to_pptx() -> None:
    from mcp_htmleditor.export.to_pptx import (
        SLIDE_H_IN,
        SLIDE_W_IN,
        ExportReport,
        _column_widths,
        find_slides,
        to_pptx,
    )

    assert SLIDE_W_IN == pptx_style.SLIDE_W_IN
    assert SLIDE_H_IN == pptx_style.SLIDE_H_IN
    assert callable(find_slides)
    assert ExportReport().slide_count == 0
    assert callable(_column_widths)
    assert to_pptx.__module__ == "mcp_htmleditor.export.to_pptx"


def test_column_widths_lives_in_pptx_model() -> None:
    from mcp_htmleditor.export.to_pptx import _column_widths

    assert _column_widths.__module__ == "mcp_htmleditor.export.pptx_model"


def test_pptx_model_exports_types_and_base() -> None:
    assert MODEL_PATH.is_file()
    model = importlib.import_module("mcp_htmleditor.export.pptx_model")
    for name in ("_Context", "_Block", "_Column", "_Region", "_Para", "_ColumnBasis", "_BuilderBase", "SKIP_TAGS"):
        assert hasattr(model, name), name


def test_pptx_model_has_no_back_import_nor_mangled_names() -> None:
    source = MODEL_PATH.read_text(encoding="utf-8")
    lines = [line.strip() for line in source.splitlines()]
    assert not [line for line in lines if line.startswith(("from .to_pptx", "from mcp_htmleditor.export.to_pptx"))]
    assert "self.__" not in source
    assert not [line for line in lines if line.startswith(("def __", "class __"))]
    assert len(lines) <= 450
