"""DT-010 (SPEC-0012): the charter registry is the only source of charter facts."""

from __future__ import annotations

import ast
import inspect

from mcp_htmleditor import templates
from mcp_htmleditor.export import pptx_style, reference_docx

EXPECTED_TEMPLATES = [
    ("ei", ("bootstrap/slides-ei-empty.html", "Euro-Information presentation (Crédit Mutuel / CIC), 1 title slide")),
    ("carbon", ("bootstrap/slides-empty.html", "IBM Carbon presentation, 1 empty slide")),
    (
        "medical",
        (
            "bootstrap/slides-medical-empty.html",
            "Presentation medicale (congres/staff): teal+orange, images commentees, citations",
        ),
    ),
    ("doc", ("bootstrap/document-empty.html", "Word-like document (single column)")),
    (
        "doc-perso",
        ("bootstrap/document-perso-empty.html", "Document charte Perso (Arial, headings colores)"),
    ),
    ("doc-ei", ("bootstrap/document-ei-empty.html", "Document Euro-Information (bleu EI, Segoe UI)")),
    (
        "mail",
        ("bootstrap/mail-empty.html", "Mail HTML Carbon leger (tables imbriquees, CSS inline, 640px)"),
    ),
    (
        "website",
        (
            "bootstrap/website-empty.html",
            "Site web Carbon (nav, hero, tabs, cartes, footer), pas d'export PPTX/DOCX",
        ),
    ),
]


def test_detect_theme_body_has_no_charter_token() -> None:
    body = inspect.getsource(pptx_style.detect_theme)
    for token in ("--med-teal", "--ei-blue", "--ibm-blue"):
        assert token not in body


def test_templates_is_built_by_a_comprehension() -> None:
    tree = ast.parse(inspect.getsource(templates))
    values = [
        node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "TEMPLATES"
    ]
    assert len(values) == 1
    assert isinstance(values[0], ast.DictComp)


def test_registry_order_and_fields() -> None:
    from mcp_htmleditor.export.charters import REGISTRY

    assert [c.key for c in REGISTRY] == ["ei", "carbon", "medical", "doc", "doc-perso", "doc-ei", "mail", "website"]
    by_key = {c.key: c for c in REGISTRY}
    assert by_key["medical"].css_tokens == ("--med-teal",)
    assert by_key["medical"].css_classes == ("med-rule",)
    assert by_key["ei"].css_tokens == ("--ei-blue",)
    assert by_key["ei"].css_classes == ("slide-inner",)
    assert by_key["carbon"].css_tokens == ("--ibm-blue", "--cds-")
    assert by_key["carbon"].css_classes == ("slide-header",)
    assert {c.key: c.docx_key for c in REGISTRY if c.docx_key} == {"doc-perso": "perso", "doc-ei": "ei"}
    assert all(not c.css_tokens and not c.css_classes for c in REGISTRY if c.kind != "presentation")


def test_templates_equal_recorded_literal() -> None:
    assert list(templates.TEMPLATES.items()) == EXPECTED_TEMPLATES


def test_charter_for_identity_cases() -> None:
    assert reference_docx.charter_for("perso") is reference_docx.PERSO
    assert reference_docx.charter_for(" EI ") is reference_docx.EI
    assert reference_docx.charter_for("mail") is None
    assert reference_docx.charter_for("website") is None
    assert reference_docx.charter_for("doc-perso") is None
    assert reference_docx.charter_for(None) is None
    assert reference_docx.charter_for("") is None
    assert reference_docx.charter_keys() == ("perso", "ei")
