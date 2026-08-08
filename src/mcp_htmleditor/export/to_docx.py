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
3. **Repeated letterhead.** An HTML letterhead is a block in the page flow, so
   pandoc turns it into body paragraphs printed once, above the title. The
   reference document carries a real Word header and footer instead (see
   :mod:`.docx_header_footer`), which Word repeats on every page; the now
   redundant HTML blocks (``.ei-doc-head``, ``.ei-doc-foot``) are therefore
   dropped from the body. They are dropped only when the reference document was
   actually built and its charter really provides that letterhead, so a failed
   generation degrades to the old output rather than losing the information.

The preprocessed HTML is written to a temporary file; ``--resource-path`` keeps
relative image references resolvable from the original directory.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from ..tracing import trace_span
from .reference_docx import charter_for, has_page_furniture, reference_docx_for

logger = logging.getLogger(__name__)

SVG_ADVICE = "Regle: figures en PNG, jamais en SVG."

#: Decorative blocks that a Word header or footer replaces. They are removed from
#: the body only when the charter really ships that Word letterhead.
PAGE_FURNITURE_SELECTORS: tuple[str, ...] = (".ei-doc-head", ".ei-doc-foot")


@dataclass(frozen=True)
class PreprocessedHtml:
    """HTML prepared for pandoc, with the document metadata lifted out.

    Attributes:
        html: HTML source with ``.doc-title`` / ``.doc-subtitle`` removed.
        title: Text of ``.doc-title``, or None when the template has none.
        subtitle: Text of ``.doc-subtitle``, or None when absent.
        charter: Value of ``data-doc-template``, or None for the standard charter.
        warnings: Diagnostics found while reading the HTML (SVG figures).
        stripped_furniture: Number of decorative letterhead blocks removed from
            the body because Word repeats them as a header or a footer.
    """

    html: str
    title: str | None
    subtitle: str | None
    charter: str | None
    warnings: tuple[str, ...]
    stripped_furniture: int = 0


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
    with trace_span("export.docx", {"file.path": str(input_path)}) as span:
        source = input_path.read_text(encoding="utf-8", errors="replace")
        charter_key = detect_charter(source)
        span.set_attribute("export.charter", charter_key or "standard")

        reference = reference_docx_for(charter_key)
        # Dropping the decorative blocks is only safe once Word really reproduces
        # them: a charter without a letterhead, or a reference document that
        # could not be built, keeps them in the body.
        strip = reference is not None and has_page_furniture(charter_key)
        prepared = preprocess_html(source, strip_page_furniture=strip)

        warnings = list(prepared.warnings)
        if charter_key and reference is None:
            warnings.append(_charter_warning(charter_key))

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
            with trace_span("tool.pandoc", {"tool.operation": "html-to-docx", "file.path": str(output_path)}):
                # Fixed argument list, pandoc resolved from PATH: no shell involved.
                completed = subprocess.run(command, capture_output=True, check=True, text=True)  # noqa: S603
        finally:
            staging.unlink(missing_ok=True)

        warnings.extend(pandoc_warnings(completed.stderr))
        span.set_attribute("warning.count", len(warnings))
        logger.info(
            "DOCX export: %s -> %s (charte: %s, %d warning(s))",
            input_path,
            output_path,
            prepared.charter or "standard",
            len(warnings),
        )
        return DocxExportResult(charter=prepared.charter, reference_docx=reference, warnings=tuple(warnings))


def detect_charter(html: str) -> str | None:
    """Return the charter key declared by a document, or None.

    Read before preprocessing, because whether the decorative letterhead blocks
    may be dropped from the body depends on the reference document built for that
    charter.

    Args:
        html: HTML source of the document.

    Returns:
        The ``data-doc-template`` value, or None when absent or empty.
    """
    return _charter_of(BeautifulSoup(html, "html.parser"))


def preprocess_html(html: str, *, strip_page_furniture: bool = False) -> PreprocessedHtml:
    """Lift the document title and subtitle out of the HTML body.

    ``.doc-title`` and ``.doc-subtitle`` are removed from the body and returned
    separately so they can be passed as pandoc metadata: this is what removes the
    duplicated title (``Title`` plus ``Heading1``) and gives the subtitle the
    native Word ``Subtitle`` style. Templates without those classes (the standard
    charter) are returned unchanged.

    Args:
        html: HTML source of the document.
        strip_page_furniture: Whether to also remove the decorative letterhead
            blocks (:data:`PAGE_FURNITURE_SELECTORS`). Pass True only when the
            reference document really reproduces them as a Word header or footer,
            otherwise the information is simply lost.

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

    stripped = _strip_page_furniture(soup) if strip_page_furniture else 0

    return PreprocessedHtml(
        html=str(soup),
        title=title or None,
        subtitle=subtitle or None,
        charter=_charter_of(soup),
        warnings=warnings,
        stripped_furniture=stripped,
    )


def _charter_of(soup: BeautifulSoup) -> str | None:
    """Return the ``data-doc-template`` value of a parsed document, or None."""
    charter_el = soup.select_one("[data-doc-template]")
    if charter_el is None:
        return None
    value = str(charter_el.get("data-doc-template", "")).strip()
    return value or None


def _strip_page_furniture(soup: BeautifulSoup) -> int:
    """Remove the decorative letterhead blocks, returning how many were removed."""
    removed = 0
    for selector in PAGE_FURNITURE_SELECTORS:
        for element in soup.select(selector):
            element.decompose()
            removed += 1
    return removed


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
            warnings.append(
                f"Image SVG detectee ({source}): pandoc ne peut pas la dimensionner "
                f"et Word ancien ne l'affiche pas. {SVG_ADVICE}"
            )
        elif source.lower().startswith("data:image/svg"):
            warnings.append(
                f"Image SVG en base64 detectee: pandoc ne peut pas la dimensionner "
                f"et Word ancien ne l'affiche pas. {SVG_ADVICE}"
            )
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
        return f"Charte '{charter}' inconnue: export avec les styles pandoc par defaut (chartes connues: perso, ei)."
    return (
        f"Charte '{charter}' non appliquee: generation du reference.docx impossible, "
        f"export avec les styles pandoc par defaut."
    )
