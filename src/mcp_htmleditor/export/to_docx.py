"""Export HTML to DOCX using pandoc.

Pandoc maps semantic HTML tags to Word styles natively: ``<h1>``..``<h5>`` become
the "Heading 1".."Heading 5" paragraph styles, ``<p>`` body text, ``<table>`` a
Word table, ``<ul>``/``<ol>`` list paragraphs, ``<sup>``/``<sub>`` superscript and
subscript runs. Templates must therefore use real semantic tags (not styled
``<div>``) for the mapping to work.

Two things pandoc cannot do on its own, handled here:

1. **Single document title.** Pandoc derives the Word ``Title`` style from the
   document metadata, itself read from ``<head><title>``, while the body
   ``<h1 class="doc-title">`` becomes an extra ``Heading1``: the title appeared
   twice in every export. The HTML is therefore preprocessed (BeautifulSoup):
   ``.doc-title`` and ``.doc-subtitle`` are lifted out of the body and passed as
   pandoc metadata, so the title is styled ``Title`` once and the subtitle gets
   the native ``Subtitle`` style instead of an ordinary paragraph.
2. **Charter.** Without ``--reference-doc`` pandoc applies its own theme and the
   charter (fonts, heading colours, underlines, table header) is lost. The
   charter is detected from ``data-doc-template`` and a matching reference
   document is generated on the fly (see :mod:`.reference_docx`).

The preprocessed HTML is written to a temporary file; ``--resource-path`` keeps
relative image references resolvable from the original directory.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from .reference_docx import charter_for, reference_docx_for

SVG_ADVICE = "Regle: figures en PNG, jamais en SVG."


@dataclass(frozen=True)
class PreprocessedHtml:
    """HTML prepared for pandoc, with the document metadata lifted out.

    Attributes:
        html: HTML source with ``.doc-title`` / ``.doc-subtitle`` removed.
        title: Text of ``.doc-title``, or None when the template has none.
        subtitle: Text of ``.doc-subtitle``, or None when absent.
        charter: Value of ``data-doc-template``, or None for the standard charter.
        warnings: Diagnostics found while reading the HTML (SVG figures).
    """

    html: str
    title: str | None
    subtitle: str | None
    charter: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DocxExportResult:
    """Outcome of a DOCX export.

    Attributes:
        charter: Charter key detected in the HTML, or None.
        reference_docx: Reference document actually passed to pandoc, or None
            when the charter is standard, unknown, or its generation failed.
        warnings: Diagnostics for the user (SVG figures, missing charter,
            pandoc warnings).
    """

    charter: str | None
    reference_docx: Path | None
    warnings: tuple[str, ...]


def to_docx(input_html: str, output_docx: str) -> DocxExportResult:
    """Convert an HTML file to DOCX using pandoc.

    Args:
        input_html: Path to the source HTML file.
        output_docx: Path where the DOCX file will be written.

    Returns:
        The export result: detected charter, reference document used, and the
        warnings worth showing to the user.

    Raises:
        subprocess.CalledProcessError: If pandoc exits with a non-zero code.
        FileNotFoundError: If pandoc is not available in PATH.
    """
    input_path = Path(input_html).resolve()
    output_path = Path(output_docx)
    prepared = preprocess_html(input_path.read_text(encoding="utf-8", errors="replace"))

    warnings = list(prepared.warnings)
    reference = reference_docx_for(prepared.charter)
    if prepared.charter and reference is None:
        warnings.append(_charter_warning(prepared.charter))

    handle, staging_name = tempfile.mkstemp(prefix="htmleditor-docx-", suffix=".html")
    os.close(handle)
    staging = Path(staging_name)
    try:
        staging.write_text(prepared.html, encoding="utf-8")
        command = [
            "pandoc",
            "-f",
            "html",
            str(staging),
            "-o",
            str(output_path),
            "--standalone",
            "--resource-path",
            str(input_path.parent),
        ]
        if prepared.title:
            command += ["--metadata", f"title={prepared.title}"]
        if prepared.subtitle:
            command += ["--metadata", f"subtitle={prepared.subtitle}"]
        if reference is not None:
            command += [f"--reference-doc={reference}"]
        completed = subprocess.run(command, capture_output=True, check=True, text=True)
    finally:
        staging.unlink(missing_ok=True)

    warnings.extend(pandoc_warnings(completed.stderr))
    return DocxExportResult(charter=prepared.charter, reference_docx=reference, warnings=tuple(warnings))


def preprocess_html(html: str) -> PreprocessedHtml:
    """Lift the document title and subtitle out of the HTML body.

    ``.doc-title`` and ``.doc-subtitle`` are removed from the body and returned
    separately so they can be passed as pandoc metadata: this is what removes the
    duplicated title (``Title`` plus ``Heading1``) and gives the subtitle the
    native Word ``Subtitle`` style. Templates without those classes (the standard
    charter) are returned unchanged.

    Args:
        html: HTML source of the document.

    Returns:
        The preprocessed HTML with the extracted metadata and diagnostics.
    """
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one(".doc-title")
    subtitle_el = soup.select_one(".doc-subtitle")
    title = title_el.get_text(" ", strip=True) if title_el is not None else None
    subtitle = subtitle_el.get_text(" ", strip=True) if subtitle_el is not None else None
    warnings = svg_warnings(soup)

    for element in (title_el, subtitle_el):
        if element is not None:
            element.decompose()
    if title and soup.title is not None:
        soup.title.string = title

    charter_el = soup.select_one("[data-doc-template]")
    charter = None
    if charter_el is not None:
        value = str(charter_el.get("data-doc-template", "")).strip()
        charter = value or None

    return PreprocessedHtml(
        html=str(soup),
        title=title or None,
        subtitle=subtitle or None,
        charter=charter,
        warnings=warnings,
    )


def svg_warnings(soup: BeautifulSoup) -> tuple[str, ...]:
    """Return one warning per SVG figure found in the document.

    Pandoc cannot compute the intrinsic size of an SVG (it needs
    ``rsvg-convert``) so the image is embedded unscaled, and older Word versions
    do not display it at all.

    Args:
        soup: Parsed document.

    Returns:
        A tuple of human-readable warnings, empty when no SVG is used.
    """
    warnings: list[str] = []
    for image in soup.find_all("img"):
        source = str(image.get("src", ""))
        if source.lower().split("?")[0].endswith(".svg"):
            warnings.append(f"Image SVG detectee ({source}): pandoc ne peut pas la dimensionner "
                            f"et Word ancien ne l'affiche pas. {SVG_ADVICE}")
        elif source.lower().startswith("data:image/svg"):
            warnings.append(f"Image SVG en base64 detectee: pandoc ne peut pas la dimensionner "
                            f"et Word ancien ne l'affiche pas. {SVG_ADVICE}")
    if soup.find("svg") is not None:
        warnings.append(f"Balise <svg> en ligne detectee: pandoc l'ignore a l'export DOCX. {SVG_ADVICE}")
    return tuple(warnings)


def pandoc_warnings(stderr: str) -> tuple[str, ...]:
    """Extract the pandoc diagnostics worth showing, in order and deduplicated.

    Args:
        stderr: Raw standard error captured from pandoc.

    Returns:
        A tuple of ``pandoc: ...`` prefixed messages.
    """
    seen: dict[str, None] = {}
    for raw in stderr.splitlines():
        line = " ".join(raw.split())
        if line:
            seen.setdefault(f"pandoc: {line}", None)
    return tuple(seen)


def _charter_warning(charter: str) -> str:
    """Return the warning shown when a charter cannot be applied."""
    if charter_for(charter) is None:
        return (f"Charte '{charter}' inconnue: export avec les styles pandoc par defaut "
                f"(chartes connues: perso, ei).")
    return (f"Charte '{charter}' non appliquee: generation du reference.docx impossible, "
            f"export avec les styles pandoc par defaut.")
