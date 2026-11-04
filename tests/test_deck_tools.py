"""Template, new and export services and their command line (SPEC-0007/US-0045)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from pptx import Presentation

from mcp_htmleditor import config as config_module
from mcp_htmleditor.deck import DeckError, tools
from mcp_htmleditor.templates import list_templates
from tests.deck_support import FIXED_TIME, deck_ei, run_cli, write_deck

REPO = Path(__file__).resolve().parents[1]
KEYS = ["ei", "carbon", "medical", "doc", "doc-perso", "doc-ei", "mail", "website"]
UNKNOWN_TEMPLATE = f'error: Unknown template "x". Valid templates: {", ".join(KEYS)}'
NO_SLIDE = 'error: No slide exported: check that the document has data-type="slide" elements.'
PANDOC_MISSING = "pandoc not found in PATH: install pandoc to export to DOCX."
needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc is not installed")


@pytest.fixture(autouse=True)
def repo_templates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Read templates from the repo and work inside an empty directory."""
    monkeypatch.setenv("HTMLEDITOR_TEMPLATES_DIR", str(REPO / "templates"))
    config_module.reset_settings_cache()
    monkeypatch.chdir(tmp_path)
    yield
    config_module.reset_settings_cache()


def test_listing_keys_and_descriptions_in_registry_order() -> None:
    """AT-1: eight entries, registry order, descriptions from list_templates()."""
    listing = tools.template_listing()
    assert [entry["key"] for entry in listing] == KEYS
    assert [(entry["key"], entry["description"]) for entry in listing] == list_templates()
    assert all(entry["description"] for entry in listing)


def test_templates_command_keeps_its_layout() -> None:
    """AT-1: first line unchanged, one line per key."""
    out, err, code = run_cli("templates")
    lines = out.splitlines()
    assert (err, code) == ("", 0)
    assert lines[0] == "Templates disponibles (mcp-htmleditor new <key> <fichier>):"
    assert lines[1] == ""
    assert [line.split()[0] for line in lines[2:]] == KEYS
    assert lines[2] == f"  {'ei':<8} {list_templates()[0][1]}"


def test_new_unknown_template_then_create_then_refuse_overwrite() -> None:
    """AT-2: unknown key, creation with the existing success line, then no overwrite."""
    out, err, code = run_cli("new", "x", "a.html")
    assert (out, err.strip(), code) == ("", UNKNOWN_TEMPLATE, 1)
    assert not Path("a.html").exists()

    out, err, code = run_cli("new", "doc", "a.html")
    assert (out, code) == ("Créé: a.html  (template: doc)\n", 0)
    assert Path("a.html").read_bytes() == (REPO / "templates/bootstrap/document-empty.html").read_bytes()

    os.utime("a.html", (FIXED_TIME, FIXED_TIME))
    out, err, code = run_cli("new", "doc", "a.html")
    assert (out, err.strip(), code) == ("", "error: File already exists: a.html", 1)
    assert Path("a.html").stat().st_mtime == FIXED_TIME


def test_new_checks_the_template_key_before_the_target() -> None:
    """The unknown template error wins over an existing target."""
    Path("a.html").write_text("keep", encoding="utf-8")
    out, err, code = run_cli("new", "x", "a.html")
    assert (out, err.strip(), code) == ("", UNKNOWN_TEMPLATE, 1)
    assert Path("a.html").read_text(encoding="utf-8") == "keep"


def test_new_serve_still_serves_the_created_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """--serve keeps its flow: the file is created, then handed to the server helper."""
    from mcp_htmleditor import cli as cli_module

    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(cli_module, "_serve_file", lambda *args, **kwargs: calls.append((args, kwargs)))
    out, _, code = run_cli("new", "doc", "s.html", "--serve", "--port", "7850", "--no-browser")
    assert code == 0
    assert out == "Créé: s.html  (template: doc)\n"
    assert calls == [(("s.html", 7850, None, "localhost"), {"open_browser": False})]


def test_export_errors() -> None:
    """AT-3: unknown format first, missing input for both formats, nothing created."""
    write_deck(Path("a.html"), (REPO / "templates/bootstrap/document-empty.html").read_text(encoding="utf-8"))
    out, err, code = run_cli("export", "foo", "a.html", "out")
    assert (out, err.strip(), code) == ("", 'error: Unknown export format "foo". Valid formats: pptx, docx', 1)
    out, err, code = run_cli("export", "foo", "ghost.html", "out")
    assert err.strip().startswith("error: Unknown export format")
    for fmt, target in (("pptx", "out.pptx"), ("docx", "out.docx")):
        out, err, code = run_cli("export", fmt, "ghost.html", target)
        assert (out, err.strip(), code) == ("", "error: File not found: ghost.html", 1)
        assert not Path(target).exists()


def test_export_pptx_of_a_document_without_slide_fails() -> None:
    """AT-3: a document with no slide element is an error and writes no output."""
    run_cli("new", "doc", "a.html")
    out, err, code = run_cli("export", "pptx", "a.html", "out.pptx")
    assert (out, err.strip(), code) == ("", NO_SLIDE, 1)
    assert not Path("out.pptx").exists()


def test_export_pptx_with_zero_slides_logs_the_warnings(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The exporter reporting zero slides logs its warnings, then raises."""
    from mcp_htmleditor.export.pptx_model import ExportReport

    report = ExportReport(slide_count=0, warnings=["image lost"])
    monkeypatch.setattr("mcp_htmleditor.export.to_pptx.to_pptx", lambda src, out: report)
    write_deck(Path("a.html"), deck_ei())
    with caplog.at_level("WARNING"), pytest.raises(DeckError, match=r"No slide exported"):
        tools.export_file("a.html", "pptx", "o.pptx")
    assert "image lost" in caplog.text


def test_export_pptx_success_and_docx_success() -> None:
    """AT-4: eight slides, then a real docx when pandoc is present."""
    write_deck(Path("deck.html"), deck_ei())
    out, _, code = run_cli("export", "pptx", "deck.html", "out.pptx")
    lines = out.splitlines()
    assert code == 0
    assert lines[0] == "Exporting deck.html → out.pptx (PPTX)"
    assert lines[-1] == "Done. 8 slide(s) exportee(s)."
    assert len(Presentation("out.pptx").slides) == 8


@needs_pandoc
def test_export_docx_success() -> None:
    """AT-4: the docx command prints Done. and writes a zip with word/document.xml."""
    run_cli("new", "doc", "a.html")
    out, _, code = run_cli("export", "docx", "a.html", "a.docx")
    assert code == 0
    assert out.splitlines()[0] == "Exporting a.html → a.docx (DOCX via pandoc)"
    assert out.splitlines()[-1] == "Done."
    with zipfile.ZipFile("a.docx") as archive:
        assert "word/document.xml" in archive.namelist()


def test_create_file_makes_parents_and_records_a_span(monkeypatch: pytest.MonkeyPatch) -> None:
    """AT-5: parent directories, returned path, file.write span with template.key and file.size."""
    spans: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def record(name: str, attributes: dict[str, Any]) -> Iterator[Any]:
        attrs = dict(attributes)
        spans.append((name, attrs))

        class Span:
            def set_attribute(self, key: str, value: Any) -> None:
                attrs[key] = value

        yield Span()

    monkeypatch.setattr(tools, "trace_span", record)
    created = tools.create_file("doc", "sub/dir/b.html")
    assert created == Path("sub/dir/b.html")
    size = (REPO / "templates/bootstrap/document-empty.html").stat().st_size
    assert spans == [("file.write", {"file.path": "sub/dir/b.html", "template.key": "doc", "file.size": size})]


def test_create_file_never_overwrites_even_if_it_appears_late(monkeypatch: pytest.MonkeyPatch) -> None:
    """The existence test is the exclusive open itself, so a file created in between survives."""
    monkeypatch.setattr(Path, "exists", lambda self: False)
    Path("c.html").write_text("mine", encoding="utf-8")
    with pytest.raises(DeckError, match=r"File already exists: c.html"):
        tools.create_file("doc", "c.html")
    assert Path("c.html").read_text(encoding="utf-8") == "mine"


def test_create_file_reports_a_missing_template_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A registered key whose file cannot be found gives the missing template error."""
    empty = tmp_path / "none"
    empty.mkdir()
    monkeypatch.setattr("mcp_htmleditor.templates.template_search_path", lambda: [empty])
    with pytest.raises(DeckError, match=r"^Template file is missing: "):
        tools.create_file("doc", "d.html")
    assert not Path("d.html").exists()


def test_create_file_reports_a_failed_write() -> None:
    """A target that cannot be created gives Cannot write <file>."""
    Path("blocker").write_text("x", encoding="utf-8")
    with pytest.raises(DeckError, match=r"^Cannot write blocker/e.html: "):
        tools.create_file("doc", "blocker/e.html")


def test_export_file_without_pandoc(monkeypatch: pytest.MonkeyPatch) -> None:
    """AT-5: pandoc hidden gives the pandoc not found error."""
    run_cli("new", "doc", "a.html")
    monkeypatch.setenv("PATH", "")
    with pytest.raises(DeckError) as raised:
        tools.export_file("a.html", "docx", "x.docx")
    assert str(raised.value) == PANDOC_MISSING


def test_export_file_pandoc_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pandoc exit is reported with its stderr, or the exit code when stderr is empty."""
    run_cli("new", "doc", "a.html")

    def failing(stderr: str) -> Any:
        def run(src: str, out: str) -> None:
            raise subprocess.CalledProcessError(3, "pandoc", stderr=stderr)

        return run

    monkeypatch.setattr("mcp_htmleditor.export.to_docx.to_docx", failing(" boom \n"))
    with pytest.raises(DeckError, match=r"^pandoc failed: boom$"):
        tools.export_file("a.html", "docx", "x.docx")
    monkeypatch.setattr("mcp_htmleditor.export.to_docx.to_docx", failing(""))
    with pytest.raises(DeckError, match=r"^pandoc failed: exit code 3$"):
        tools.export_file("a.html", "docx", "x.docx")


def test_export_format_is_exact_lower_case() -> None:
    """AT-5: PPTX is not pptx."""
    write_deck(Path("a.html"), deck_ei())
    with pytest.raises(DeckError, match=r'^Unknown export format "PPTX". Valid formats: pptx, docx$'):
        tools.export_file("a.html", "PPTX", "o.pptx")


@needs_pandoc
def test_export_file_docx_outcome() -> None:
    """The docx outcome carries the charter fields and a zero slide count."""
    run_cli("new", "doc-perso", "p.html")
    outcome = tools.export_file("p.html", "docx", "p.docx")
    assert (outcome.output, outcome.slide_count, outcome.charter) == ("p.docx", 0, "perso")
    assert outcome.reference_docx is not None


def test_importing_the_tools_module_does_not_load_the_exporters() -> None:
    """AT-5: lazy imports keep python-pptx and python-docx out of the import."""
    code = (
        "import sys, mcp_htmleditor.deck.tools\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('pptx', 'docx') "
        "or m in ('mcp_htmleditor.export.to_pptx', 'mcp_htmleditor.export.to_docx')]\n"
        "sys.exit(1 if bad else 0)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)  # noqa: S603
    assert result.returncode == 0, result.stderr
