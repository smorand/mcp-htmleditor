"""Export HTML to DOCX using pandoc.

Simple V1: delegates entirely to pandoc which handles HTML→DOCX very well.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def to_docx(input_html: str, output_docx: str) -> None:
    """Convert an HTML file to DOCX using pandoc.

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
            str(input_path),
            "-o",
            str(output_path),
            "--standalone",
        ],
        check=True,
    )
