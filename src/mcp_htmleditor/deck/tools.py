"""Template, new and export services shared by the command line and the agent tools (SPEC-0007).

Nothing here prints: ``cli.py`` echoes the outcomes and turns ``DeckError`` into ``error: <message>``.
``export.to_pptx`` and ``export.to_docx`` are imported lazily, they cost more than the rest of the CLI.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..templates import list_templates, template_path
from ..tracing import trace_span
from . import DeckError, load_deck

logger = logging.getLogger(__name__)

EXPORT_FORMATS = ("pptx", "docx")
NO_SLIDE_MESSAGE = 'No slide exported: check that the document has data-type="slide" elements.'
PANDOC_MISSING_MESSAGE = "pandoc not found in PATH: install pandoc to export to DOCX."


@dataclass(frozen=True, slots=True)
class ExportOutcome:
    """What an export produced: the output path, its warnings and the pptx or docx specifics."""

    output: str
    warnings: list[str]
    slide_count: int
    charter: str | None
    reference_docx: str | None


def template_listing() -> list[dict[str, str]]:
    """Return ``[{"key", "description"}]`` for every template, in registry order."""
    return [{"key": key, "description": description} for key, description in list_templates()]


def create_file(template: str, file: str) -> Path:
    """Copy the bootstrap of ``template`` to ``file``, creating parents, never overwriting."""
    keys = [key for key, _ in list_templates()]
    if template not in keys:
        raise DeckError(f'Unknown template "{template}". Valid templates: {", ".join(keys)}')
    try:
        content = template_path(template).read_bytes()
    except FileNotFoundError as exc:
        raise DeckError(f"Template file is missing: {exc}") from None
    dest = Path(file)
    with trace_span("file.write", {"file.path": str(dest), "template.key": template}) as span:
        _write_new(dest, content)
        span.set_attribute("file.size", len(content))
    logger.info("Created %s from template %s", dest, template)
    return dest


def _write_new(dest: Path, content: bytes) -> None:
    """Write ``content`` at ``dest`` with exclusive creation, so an existing file is never touched."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DeckError(f"Cannot write {dest}: {exc.strerror or exc}") from None
    try:
        with dest.open("xb") as handle:
            handle.write(content)
    except FileExistsError:
        raise DeckError(f"File already exists: {dest}") from None
    except OSError as exc:
        raise DeckError(f"Cannot write {dest}: {exc.strerror or exc}") from None


def export_file(file: str, fmt: str, output: str) -> ExportOutcome:
    """Export ``file`` to ``fmt`` (``pptx`` or ``docx``, exact lower case) at ``output``."""
    if fmt not in EXPORT_FORMATS:
        raise DeckError(f'Unknown export format "{fmt}". Valid formats: {", ".join(EXPORT_FORMATS)}')
    if fmt == "pptx":
        return _export_pptx(file, output)
    return _export_docx(file, output)


def _export_pptx(file: str, output: str) -> ExportOutcome:
    """Export to PPTX; a document without any slide element is an error and writes nothing."""
    from ..export.to_pptx import to_pptx  # noqa: PLC0415 - python-pptx, never at import

    if not load_deck(file).slides:
        raise DeckError(NO_SLIDE_MESSAGE)
    report = to_pptx(file, output)
    if report.slide_count == 0:
        for warning in report.warnings:
            logger.warning("%s", warning)
        raise DeckError(NO_SLIDE_MESSAGE)
    return ExportOutcome(output, list(report.warnings), report.slide_count, None, None)


def _export_docx(file: str, output: str) -> ExportOutcome:
    """Export to DOCX through pandoc."""
    from ..export.to_docx import to_docx  # noqa: PLC0415 - loaded on demand

    if not Path(file).is_file():
        raise DeckError(f"File not found: {file}")
    try:
        result = to_docx(file, output)
    except FileNotFoundError:
        raise DeckError(PANDOC_MISSING_MESSAGE) from None
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or f"exit code {exc.returncode}"
        raise DeckError(f"pandoc failed: {detail}") from None
    reference = None if result.reference_docx is None else str(result.reference_docx)
    return ExportOutcome(output, list(result.warnings), 0, result.charter, reference)
