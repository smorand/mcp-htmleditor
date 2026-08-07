"""Export HTML to DOCX using pandoc.

Delegates to pandoc, which maps semantic HTML tags to Word styles natively:
``<h1>``..``<h5>`` become the Word "Heading 1".."Heading 5" paragraph styles,
``<p>`` becomes body text, ``<table>`` a Word table, ``<ul>``/``<ol>`` list
paragraphs, and ``<sup>``/``<sub>`` superscript/subscript runs. Templates must
therefore use real semantic tags (not styled ``<div>``) for the mapping to work.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def to_docx(input_html: str, output_docx: str) -> None:
    """Convert an HTML file to DOCX using pandoc.

    The HTML input format is passed explicitly (``-f html``) so pandoc reliably
    maps ``<h1>``..``<h5>`` to Word Heading styles regardless of file extension.

    Args:
        input_html: Path to the source HTML file.
        output_docx: Path where the DOCX file will be written.

    Raises:
        subprocess.CalledProcessError: If pandoc exits with a non-zero code.
        FileNotFoundError: If pandoc is not available in PATH.
    """
    input_path = Path(input_html).resolve()
    output_path = Path(output_docx)

    subprocess.run(
        [
            "pandoc",
            "-f",
            "html",
            str(input_path),
            "-o",
            str(output_path),
            "--standalone",
        ],
        check=True,
    )
