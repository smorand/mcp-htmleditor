"""Generate a pandoc ``--reference-doc`` DOCX that carries a document charter.

Pandoc styles every DOCX it produces from a reference document. Without one it
applies its built-in theme (serif font, teal headings, colourless tables), so the
whole HTML charter is lost and only the structure survives. This module builds
one reference DOCX per charter: it asks pandoc for its own default reference file
(``pandoc --print-default-data-file reference.docx``) and patches
``word/styles.xml`` in place. Only the charter traits change; every other pandoc
convention (list numbering, caption styles, table grid, language) is preserved.

Generated files are cached under ``~/.cache/mcp-htmleditor/reference`` (see
``config.reference_dir``), keyed by a fingerprint of the charter definition plus
the pandoc version, so editing a charter or upgrading pandoc regenerates them.

Charter keys match the ``data-doc-template`` attribute of the document
``<article>``: ``perso``, ``ei``. A document without that attribute uses the
standard charter, which has no reference document: pandoc defaults apply.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ..config import reference_dir

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

STYLES_PART = "word/styles.xml"

#: Version of the patching logic. Bump it when the generated XML changes, so
#: cached reference documents are rebuilt even if no charter was edited.
GENERATOR_VERSION = "2"

# Schema child order of w:style (CT_Style), truncated after w:tblStylePr.
_STYLE_ORDER: tuple[str, ...] = (
    "name", "aliases", "basedOn", "next", "link", "autoRedefine", "hidden",
    "uiPriority", "semiHidden", "unhideWhenUsed", "qFormat", "locked",
    "personal", "personalCompose", "personalReply", "rsid", "pPr", "rPr",
    "tblPr", "trPr", "tcPr", "tblStylePr",
)

# Schema child order of w:rPr (EG_RPrBase), limited to what we emit.
_RPR_ORDER: tuple[str, ...] = ("rFonts", "b", "bCs", "i", "iCs", "caps", "color", "sz", "szCs", "u")

# Schema child order of w:pPr (CT_PPr), limited to what we touch.
_PPR_ORDER: tuple[str, ...] = (
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
    "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs",
    "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
    "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
    "suppressOverlap", "jc", "textDirection", "textAlignment",
    "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr",
)

# Schema child order of w:tblStylePr (CT_TblStylePr).
_TBLSTYLEPR_ORDER: tuple[str, ...] = ("pPr", "rPr", "tblPr", "trPr", "tcPr")

# Schema child order of w:tcPr (CT_TcPrBase), limited to what we touch.
_TCPR_ORDER: tuple[str, ...] = (
    "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
    "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark",
)


@dataclass(frozen=True)
class StyleSpec:
    """Character and paragraph traits of one Word paragraph style.

    Attributes:
        size_pt: Font size in points (stored as half-points in the XML).
        color: Hex RGB colour without ``#`` (for example ``1155CC``), or None
            to inherit.
        bold: Whether the style is bold.
        italic: Whether the style is italic.
        underline: Whether the style carries a single underline.
        caps: Whether the style forces uppercase.
        align: Paragraph alignment (``center``, ``left``, ``both``), or None to
            keep the alignment inherited from the pandoc reference.
    """

    size_pt: float
    color: str | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    caps: bool = False
    align: str | None = None


@dataclass(frozen=True)
class TableSpec:
    """Header-row traits of the Word ``Table`` style used by pandoc.

    Attributes:
        header_fill: Hex RGB fill of the header row cells.
        header_color: Hex RGB colour of the header row text.
        header_bold: Whether the header row text is bold.
    """

    header_fill: str
    header_color: str = "FFFFFF"
    header_bold: bool = True


@dataclass(frozen=True)
class Charter:
    """A document charter expressed as Word styles.

    Attributes:
        key: Charter key, matching ``data-doc-template`` in the HTML.
        label: Human-readable name, used in CLI messages.
        font: Font family applied to the whole document.
        body_size_pt: Body text size in points.
        styles: Word style id (``Title``, ``Heading1``, ...) to its traits.
        table: Header-row traits of the table style, or None to keep pandoc's.
    """

    key: str
    label: str
    font: str
    body_size_pt: float
    styles: Mapping[str, StyleSpec] = field(default_factory=dict)
    table: TableSpec | None = None


PERSO = Charter(
    key="perso",
    label="Perso",
    font="Arial",
    body_size_pt=11,
    styles={
        "Title": StyleSpec(22, color="000000", bold=True, underline=True, align="center"),
        "Subtitle": StyleSpec(15, color="666666", align="center"),
        "Heading1": StyleSpec(18, color="000000", bold=True, underline=True),
        "Heading2": StyleSpec(16, color="1155CC"),
        "Heading3": StyleSpec(14, color="6D9EEB"),
        "Heading4": StyleSpec(12, color="B4A7D6"),
        "Heading5": StyleSpec(11, color="C27BA0"),
    },
    table=TableSpec(header_fill="1155CC"),
)

EI = Charter(
    key="ei",
    label="Euro-Information",
    font="Segoe UI",
    body_size_pt=11,
    styles={
        "Title": StyleSpec(24, color="003A8D", bold=True, align="left"),
        "Subtitle": StyleSpec(13, color="50565B", align="left"),
        "Heading1": StyleSpec(18, color="003A8D", bold=True),
        "Heading2": StyleSpec(15, color="284AAA"),
        "Heading3": StyleSpec(13, color="285C99"),
        "Heading4": StyleSpec(12, color="50565B"),
        "Heading5": StyleSpec(11, color="50565B", caps=True),
    },
    table=TableSpec(header_fill="003A8D"),
)

CHARTERS: Mapping[str, Charter] = {PERSO.key: PERSO, EI.key: EI}


def charter_keys() -> tuple[str, ...]:
    """Return the supported charter keys, in declaration order."""
    return tuple(CHARTERS)


def charter_for(key: str | None) -> Charter | None:
    """Return the charter matching a ``data-doc-template`` value.

    Args:
        key: Charter key read from the HTML, or None for the standard charter.

    Returns:
        The matching charter, or None when the key is absent or unknown; the
        caller then exports without a reference document.
    """
    if not key:
        return None
    return CHARTERS.get(key.strip().lower())


def reference_docx_for(key: str | None) -> Path | None:
    """Return a cached reference DOCX for a charter key, generating it if needed.

    Never raises: any failure (pandoc missing, unwritable cache, malformed
    styles part) yields None so the export can continue with pandoc defaults.

    Args:
        key: Charter key read from ``data-doc-template``.

    Returns:
        Path to the reference DOCX, or None when there is no charter to apply or
        when generation failed.
    """
    charter = charter_for(key)
    if charter is None:
        return None
    try:
        target = reference_dir() / f"{charter.key}-{_fingerprint(charter)}.docx"
        if target.is_file() and target.stat().st_size > 0:
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        # Per-process staging name: two concurrent exports must not clobber
        # each other's partially written archive.
        staging = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        build_reference_docx(charter, staging)
        staging.replace(target)
    except (OSError, subprocess.SubprocessError, ET.ParseError, KeyError):
        return None
    return target


def build_reference_docx(charter: Charter, destination: Path) -> None:
    """Build a reference DOCX for a charter at ``destination``.

    Args:
        charter: Charter to encode into ``word/styles.xml``.
        destination: Path of the DOCX to write (overwritten if present).

    Raises:
        FileNotFoundError: If pandoc is not available in PATH.
        subprocess.CalledProcessError: If pandoc fails to emit its default
            reference document.
        KeyError: If the default reference document has no styles part.
        ET.ParseError: If the styles part is not well-formed XML.
    """
    with tempfile.TemporaryDirectory(prefix="htmleditor-ref-") as tmp:
        base = Path(tmp) / "reference.docx"
        base.write_bytes(default_reference_bytes())
        with zipfile.ZipFile(base) as archive:
            styles = archive.read(STYLES_PART)
        patched = patch_styles_xml(styles, charter)
        _copy_zip_with_replacement(base, destination, STYLES_PART, patched)


def default_reference_bytes() -> bytes:
    """Return pandoc's own default ``reference.docx`` as bytes.

    Raises:
        FileNotFoundError: If pandoc is not available in PATH.
        subprocess.CalledProcessError: If pandoc exits with a non-zero code.
    """
    completed = subprocess.run(
        ["pandoc", "--print-default-data-file", "reference.docx"],
        capture_output=True,
        check=True,
    )
    return completed.stdout


def patch_styles_xml(styles_xml: bytes, charter: Charter) -> bytes:
    """Return ``word/styles.xml`` patched with a charter.

    The document defaults get the charter font and body size, each declared
    style gets its run properties and alignment, and the table style gets the
    charter header row. Styles absent from the reference document are skipped.

    Args:
        styles_xml: Raw content of the ``word/styles.xml`` part.
        charter: Charter to apply.

    Returns:
        The patched XML, serialized with its declaration.

    Raises:
        ET.ParseError: If the styles part is not well-formed XML.
    """
    ET.register_namespace("w", W_NS)
    ET.register_namespace("r", R_NS)
    root = ET.fromstring(styles_xml)
    _patch_document_defaults(root, charter)
    for style_id, spec in charter.styles.items():
        style = _find_style(root, style_id)
        if style is None:
            continue
        _apply_run_props(_child(style, "rPr", _STYLE_ORDER), charter.font, spec)
        if spec.align is not None:
            paragraph_props = _child(style, "pPr", _STYLE_ORDER)
            _set(_child(paragraph_props, "jc", _PPR_ORDER), val=spec.align)
    _patch_table_style(root, charter)
    serialized: bytes = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    return serialized


def _patch_document_defaults(root: ET.Element, charter: Charter) -> None:
    """Apply the charter font and body size to ``w:docDefaults``."""
    defaults = root.find(f"{{{W_NS}}}docDefaults/{{{W_NS}}}rPrDefault/{{{W_NS}}}rPr")
    if defaults is None:
        return
    _set_fonts(defaults, charter.font)
    half = _half_points(charter.body_size_pt)
    _set(_child(defaults, "sz", _RPR_ORDER), val=half)
    _set(_child(defaults, "szCs", _RPR_ORDER), val=half)


def _patch_table_style(root: ET.Element, charter: Charter) -> None:
    """Apply the charter header row to the pandoc ``Table`` style."""
    spec = charter.table
    style = _find_style(root, "Table")
    if spec is None or style is None:
        return
    first_row = _find_child(style, "tblStylePr", type_="firstRow")
    if first_row is None:
        first_row = _child(style, "tblStylePr", _STYLE_ORDER)
        _set(first_row, type="firstRow")
    run_props = _child(first_row, "rPr", _TBLSTYLEPR_ORDER)
    if spec.header_bold:
        _child(run_props, "b", _RPR_ORDER)
    _set(_child(run_props, "color", _RPR_ORDER), val=spec.header_color)
    cell_props = _child(first_row, "tcPr", _TBLSTYLEPR_ORDER)
    _set(_child(cell_props, "shd", _TCPR_ORDER), val="clear", color="auto", fill=spec.header_fill)


def _apply_run_props(run_props: ET.Element, font: str, spec: StyleSpec) -> None:
    """Replace the run properties of a style with the charter traits.

    The existing children are dropped first: pandoc's own heading styles carry
    theme fonts, theme colours and italics that would otherwise survive. Every
    toggle is then written explicitly, including when the charter turns it off,
    because Word styles inherit (pandoc bases ``Subtitle`` on ``Title``, so an
    implicit "no underline" would still come out underlined).
    """
    for existing in list(run_props):
        run_props.remove(existing)
    _set_fonts(run_props, font)
    _set(_child(run_props, "b", _RPR_ORDER), val=_toggle(spec.bold))
    _set(_child(run_props, "i", _RPR_ORDER), val=_toggle(spec.italic))
    _set(_child(run_props, "caps", _RPR_ORDER), val=_toggle(spec.caps))
    if spec.color:
        _set(_child(run_props, "color", _RPR_ORDER), val=spec.color)
    half = _half_points(spec.size_pt)
    _set(_child(run_props, "sz", _RPR_ORDER), val=half)
    _set(_child(run_props, "szCs", _RPR_ORDER), val=half)
    _set(_child(run_props, "u", _RPR_ORDER), val="single" if spec.underline else "none")


def _set_fonts(run_props: ET.Element, font: str) -> None:
    """Force an explicit font family, dropping any theme-based reference."""
    fonts = _child(run_props, "rFonts", _RPR_ORDER)
    for attribute in ("asciiTheme", "eastAsiaTheme", "hAnsiTheme", "cstheme"):
        fonts.attrib.pop(f"{{{W_NS}}}{attribute}", None)
    _set(fonts, ascii=font, hAnsi=font, cs=font)


def _find_style(root: ET.Element, style_id: str) -> ET.Element | None:
    """Return the ``w:style`` element with the given id, or None."""
    for style in root.findall(f"{{{W_NS}}}style"):
        if style.get(f"{{{W_NS}}}styleId") == style_id:
            return style
    return None


def _find_child(parent: ET.Element, tag: str, type_: str | None = None) -> ET.Element | None:
    """Return the first ``w:<tag>`` child, optionally filtered on its ``w:type``."""
    for child in parent.findall(f"{{{W_NS}}}{tag}"):
        if type_ is None or child.get(f"{{{W_NS}}}type") == type_:
            return child
    return None


def _child(parent: ET.Element, tag: str, order: Sequence[str]) -> ET.Element:
    """Return the ``w:<tag>`` child of ``parent``, creating it in schema order.

    Word rejects a styles part whose children are out of order, so a created
    child is inserted at the rank ``order`` gives it rather than appended.

    Args:
        parent: Element that owns the child.
        tag: Local name of the child, without the ``w:`` prefix.
        order: Local names of ``parent``'s children in schema order.

    Returns:
        The existing or newly created child element.
    """
    existing = _find_child(parent, tag)
    if existing is not None:
        return existing
    created = ET.Element(f"{{{W_NS}}}{tag}")
    rank = _rank(tag, order)
    for index, sibling in enumerate(parent):
        if _rank(_local_name(sibling), order) > rank:
            parent.insert(index, created)
            return created
    parent.append(created)
    return created


def _rank(tag: str, order: Sequence[str]) -> int:
    """Return the schema rank of a local name, unknown names sorting last."""
    return order.index(tag) if tag in order else len(order)


def _local_name(element: ET.Element) -> str:
    """Return the local name of an element, without its namespace."""
    tag = element.tag
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _set(element: ET.Element, **attributes: str) -> None:
    """Set ``w:``-namespaced attributes on an element."""
    for name, value in attributes.items():
        element.set(f"{{{W_NS}}}{name}", value)


def _toggle(enabled: bool) -> str:
    """Return the Word on/off value of a boolean run property."""
    return "1" if enabled else "0"


def _half_points(size_pt: float) -> str:
    """Convert a point size to the half-point string Word expects."""
    return str(round(size_pt * 2))


def _fingerprint(charter: Charter) -> str:
    """Return a short cache key covering the charter and the pandoc version."""
    charter_json = json.dumps(dataclasses.asdict(charter), sort_keys=True)
    payload = f"{GENERATOR_VERSION}|{charter_json}|{_pandoc_version()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _pandoc_version() -> str:
    """Return the first line of ``pandoc --version``, or an empty string."""
    try:
        completed = subprocess.run(["pandoc", "--version"], capture_output=True, check=True, text=True)
    except (OSError, subprocess.SubprocessError):
        return ""
    lines = completed.stdout.splitlines()
    return lines[0].strip() if lines else ""


def _copy_zip_with_replacement(source: Path, destination: Path, part: str, content: bytes) -> None:
    """Copy a DOCX archive, substituting one part and preserving every other entry.

    Args:
        source: Archive to copy.
        destination: Archive to write.
        part: Archive member to replace (for example ``word/styles.xml``).
        content: New content of that member.
    """
    with (
        zipfile.ZipFile(source) as reader,
        zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as writer,
    ):
        for item in reader.infolist():
            data = content if item.filename == part else reader.read(item.filename)
            writer.writestr(item, data)
