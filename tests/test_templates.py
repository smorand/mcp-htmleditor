"""Tests for the template registry (mcp_htmleditor.templates)."""

from __future__ import annotations

import pytest

from mcp_htmleditor.templates import TEMPLATES, list_templates, template_path


def test_all_templates_resolve_to_existing_files() -> None:
    """Every registered template key maps to a bootstrap file on disk."""
    for key in TEMPLATES:
        path = template_path(key)
        assert path.is_file(), f"missing bootstrap for '{key}': {path}"
        assert path.suffix == ".html"


def test_ei_template_is_euro_information() -> None:
    """The 'ei' template contains Euro-Information markers."""
    content = template_path("ei").read_text(encoding="utf-8")
    assert "--ei-blue" in content
    assert 'data-doc-type="presentation"' in content


def test_carbon_template_is_presentation() -> None:
    """The 'carbon' template is a presentation."""
    content = template_path("carbon").read_text(encoding="utf-8")
    assert 'data-doc-type="presentation"' in content


def test_doc_template_is_document() -> None:
    """The 'doc' template is a document."""
    content = template_path("doc").read_text(encoding="utf-8")
    assert 'data-doc-type="document"' in content


def test_doc_perso_template_is_document() -> None:
    """The 'doc-perso' template is a document with the perso charter marker."""
    content = template_path("doc-perso").read_text(encoding="utf-8")
    assert 'data-doc-type="document"' in content
    assert 'data-doc-template="perso"' in content


def test_doc_ei_template_is_document() -> None:
    """The 'doc-ei' template is a document with the Euro-Information marker."""
    content = template_path("doc-ei").read_text(encoding="utf-8")
    assert 'data-doc-type="document"' in content
    assert 'data-doc-template="ei"' in content


def test_mail_template_is_document_with_mail_charter() -> None:
    """The 'mail' template is a document with the mail charter marker."""
    content = template_path("mail").read_text(encoding="utf-8")
    assert 'data-doc-type="document"' in content
    assert 'data-doc-template="mail"' in content


def test_mail_template_is_mail_safe() -> None:
    """The 'mail' template avoids constructs unsafe for email clients."""
    content = template_path("mail").read_text(encoding="utf-8")
    assert "<table" in content
    assert "display:flex" not in content
    assert "display: flex" not in content
    assert "display:grid" not in content
    assert "position:absolute" not in content
    assert "<script" not in content


def test_unknown_key_raises_keyerror() -> None:
    """An unknown template key raises KeyError."""
    with pytest.raises(KeyError):
        template_path("does-not-exist")


def test_list_templates_returns_all_keys() -> None:
    """list_templates returns a (key, description) pair for each template."""
    listed = list_templates()
    keys = {k for k, _ in listed}
    assert keys == set(TEMPLATES.keys())
    assert all(isinstance(desc, str) and desc for _, desc in listed)
