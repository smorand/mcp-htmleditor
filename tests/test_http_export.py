"""Tests for the /export/pptx and /export/docx HTTP routes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp_htmleditor import state as state_module


def test_export_routes_registered() -> None:
    """GET dispatch table includes /export/pptx and /export/docx."""
    import inspect

    from mcp_htmleditor import http_server

    src = inspect.getsource(http_server)
    assert '"/export/pptx"' in src
    assert '"/export/docx"' in src
    assert "_export_pptx" in src
    assert "_export_docx" in src


def test_export_pptx_uses_to_pptx_and_streams(fresh_state: state_module.EditorState, html_file: Path) -> None:
    """_export_pptx writes to a tmp file via to_pptx then reads it back."""
    import tempfile

    fresh_state.set_file(str(html_file))
    fake_bytes = b"PK\x03\x04fake-pptx"
    captured: dict[str, object] = {}

    def _fake_pptx(src: str, dst: str) -> MagicMock:
        captured["src"] = src
        captured["dst"] = dst
        Path(dst).write_bytes(fake_bytes)
        return MagicMock(slide_count=2)

    with patch("mcp_htmleditor.export.to_pptx.to_pptx", side_effect=_fake_pptx):
        from mcp_htmleditor.export.to_pptx import to_pptx

        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            to_pptx(str(html_file), tmp_path)
            data = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    assert data == fake_bytes
    assert captured["src"] == str(html_file)


def test_export_docx_uses_to_docx_and_streams(fresh_state: state_module.EditorState, html_file: Path) -> None:
    """_export_docx writes to a tmp file via to_docx then reads it back."""
    import tempfile

    fresh_state.set_file(str(html_file))
    fake_bytes = b"PK\x03\x04fake-docx"
    captured: dict[str, object] = {}

    def _fake_docx(src: str, dst: str) -> MagicMock:
        captured["src"] = src
        Path(dst).write_bytes(fake_bytes)
        return MagicMock(charter="default", reference_docx=None)

    with patch("mcp_htmleditor.export.to_docx.to_docx", side_effect=_fake_docx):
        from mcp_htmleditor.export.to_docx import to_docx

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            to_docx(str(html_file), tmp_path)
            data = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    assert data == fake_bytes
    assert captured["src"] == str(html_file)
