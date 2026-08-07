"""Tests for the pure HTML helpers in http_server."""

from __future__ import annotations

from pathlib import Path

from mcp_htmleditor.http_server import _rebuild_full_html, _strip_editor_artifacts


def test_strip_removes_injected_ids() -> None:
    """Elements with editor-injected ids are removed entirely."""
    html = (
        "<body>"
        "<div id='_mcp_format_bar'>bar</div>"
        "<div id='_mcp_insert_bar'>ins</div>"
        "<style id='_mcp_editor_styles'>x{}</style>"
        "<div id='_editor_ctx_host'>ctx</div>"
        "<p>keep</p>"
        "</body>"
    )
    out = _strip_editor_artifacts(html)
    assert "_mcp_format_bar" not in out
    assert "_mcp_insert_bar" not in out
    assert "_mcp_editor_styles" not in out
    assert "_editor_ctx_host" not in out
    assert "keep" in out


def test_strip_removes_injected_classes() -> None:
    """Editor helper classes are stripped but other classes survive."""
    html = "<p class='foo _mcp_editable bar'>x</p><span class='gtx-trans-icon'>i</span>"
    out = _strip_editor_artifacts(html)
    assert "_mcp_editable" not in out
    assert "gtx-trans-icon" not in out
    assert "foo" in out
    assert "bar" in out


def test_strip_drops_class_attr_when_empty() -> None:
    """When the only class was an artifact, the class attribute disappears."""
    html = "<p class='_mcp_editable'>x</p>"
    out = _strip_editor_artifacts(html)
    assert "class" not in out


def test_strip_removes_contenteditable() -> None:
    """contenteditable attributes are removed."""
    html = "<div contenteditable='true'>edit</div>"
    out = _strip_editor_artifacts(html)
    assert "contenteditable" not in out


def test_strip_removes_extension_attrs() -> None:
    """Browser-extension attributes (Grammarly, Translate) are stripped."""
    html = (
        "<p _msttexthash='123' data-gramm='false' data-gr-id='9' "
        "_msthidden='1'>text</p>"
    )
    out = _strip_editor_artifacts(html)
    assert "_msttexthash" not in out
    assert "data-gramm" not in out
    assert "data-gr-" not in out
    assert "_msthidden" not in out
    assert "text" in out


def test_strip_clears_duplicated_slide_options() -> None:
    """Dynamically-generated <option> nodes in #slide-select are cleared."""
    html = (
        "<select id='slide-select'>"
        "<option>Slide 1</option><option>Slide 2</option>"
        "</select>"
    )
    out = _strip_editor_artifacts(html)
    assert "slide-select" in out
    assert "<option" not in out


def test_rebuild_wraps_fragment_into_document(tmp_path: Path) -> None:
    """A canvas fragment becomes a full document."""
    out = _rebuild_full_html("<p>hi</p>", None)
    assert out.startswith("<!DOCTYPE html>")
    assert "<html>" in out
    assert "<head>" in out.lower()
    assert "<p>hi</p>" in out
    assert "</html>" in out


def test_rebuild_preserves_existing_head(tmp_path: Path) -> None:
    """The head of the existing file is carried into the rebuilt document."""
    src = tmp_path / "doc.html"
    src.write_text(
        "<!DOCTYPE html><html><head><title>Keep Me</title>"
        "<style>.a{}</style></head><body><p>old</p></body></html>",
        encoding="utf-8",
    )
    out = _rebuild_full_html("<p>new</p>", str(src))
    assert "Keep Me" in out
    assert ".a{}" in out
    assert "<p>new</p>" in out


def test_rebuild_preserves_doc_type_attr(tmp_path: Path) -> None:
    """data-doc-type on <html> is preserved in the rebuilt document."""
    src = tmp_path / "pres.html"
    src.write_text(
        '<!DOCTYPE html><html data-doc-type="presentation">'
        "<head><meta charset='UTF-8'></head><body></body></html>",
        encoding="utf-8",
    )
    out = _rebuild_full_html("<section>s</section>", str(src))
    assert 'data-doc-type="presentation"' in out


def test_rebuild_default_head_when_missing(tmp_path: Path) -> None:
    """A file without a head yields a minimal default head."""
    src = tmp_path / "nohead.html"
    src.write_text("<html><body><p>x</p></body></html>", encoding="utf-8")
    out = _rebuild_full_html("<p>y</p>", str(src))
    assert "<head>" in out.lower()
    assert 'charset="UTF-8"' in out
