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

A charter may also carry a repeated Word header and footer (logo, brand rule,
page number). Those live in their own archive parts, injected into the same
reference document; see :mod:`.docx_header_footer` for how pandoc carries them
over to the exported file.

Charter keys match the ``data-doc-template`` attribute of the document
``<article>``: ``perso``, ``ei``. A document without that attribute uses the
standard charter, which has no reference document: pandoc defaults apply.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ..config import reference_dir
from ..tracing import trace_span
from . import docx_header_footer as hf
from .docx_assets import EI_LOGO_PNG_BASE64

logger = logging.getLogger(__name__)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

STYLES_PART = "word/styles.xml"
DOCUMENT_PART = "word/document.xml"
DOCUMENT_RELS_PART = "word/_rels/document.xml.rels"
CONTENT_TYPES_PART = "[Content_Types].xml"

#: Version of the patching logic. Bump it when the generated XML changes, so
#: cached reference documents are rebuilt even if no charter was edited.
GENERATOR_VERSION = "3"

# Opening tag of the single w:sectPr of pandoc's default reference document,
# matched tolerantly (attributes, self-closing form).
_SECTPR_OPEN = re.compile(r"<w:sectPr\b[^>]*?(/?)>")
_SECTPR_START = "<w:sectPr>"
_SECTPR_CLOSE = "</w:sectPr>"

# Schema child order of w:style (CT_Style), truncated after w:tblStylePr.
_STYLE_ORDER: tuple[str, ...] = (
    "name",
    "aliases",
    "basedOn",
    "next",
    "link",
    "autoRedefine",
    "hidden",
    "uiPriority",
    "semiHidden",
    "unhideWhenUsed",
    "qFormat",
    "locked",
    "personal",
    "personalCompose",
    "personalReply",
    "rsid",
    "pPr",
    "rPr",
    "tblPr",
    "trPr",
    "tcPr",
    "tblStylePr",
)

# Schema child order of w:rPr (EG_RPrBase), limited to what we emit.
_RPR_ORDER: tuple[str, ...] = ("rFonts", "b", "bCs", "i", "iCs", "caps", "color", "sz", "szCs", "u")

# Schema child order of w:pPr (CT_PPr), limited to what we touch.
_PPR_ORDER: tuple[str, ...] = (
    "pStyle",
    "keepNext",
    "keepLines",
    "pageBreakBefore",
    "framePr",
    "widowControl",
    "numPr",
    "suppressLineNumbers",
    "pBdr",
    "shd",
    "tabs",
    "suppressAutoHyphens",
    "kinsoku",
    "wordWrap",
    "overflowPunct",
    "topLinePunct",
    "autoSpaceDE",
    "autoSpaceDN",
    "bidi",
    "adjustRightInd",
    "snapToGrid",
    "spacing",
    "ind",
    "contextualSpacing",
    "mirrorIndents",
    "suppressOverlap",
    "jc",
    "textDirection",
    "textAlignment",
    "textboxTightWrap",
    "outlineLvl",
    "divId",
    "cnfStyle",
    "rPr",
    "sectPr",
)

# Schema child order of w:tblStylePr (CT_TblStylePr).
_TBLSTYLEPR_ORDER: tuple[str, ...] = ("pPr", "rPr", "tblPr", "trPr", "tcPr")

# Schema child order of w:tcPr (CT_TcPrBase), limited to what we touch.
_TCPR_ORDER: tuple[str, ...] = (
    "cnfStyle",
    "tcW",
    "gridSpan",
    "hMerge",
    "vMerge",
    "tcBorders",
    "shd",
    "noWrap",
    "tcMar",
    "textDirection",
    "tcFitText",
    "vAlign",
    "hideMark",
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
        header: Repeated Word header, or None for none.
        footer: Repeated Word footer, or None for none.
        page: Page size and margins, or None to keep the reader defaults. A
            charter with a header needs one: the header is drawn inside the top
            margin, which must be widened to make room for it.
    """

    key: str
    label: str
    font: str
    body_size_pt: float
    styles: Mapping[str, StyleSpec] = field(default_factory=dict)
    table: TableSpec | None = None
    header: hf.HeaderSpec | None = None
    footer: hf.FooterSpec | None = None
    page: hf.PageSpec | None = None

    @property
    def has_page_furniture(self) -> bool:
        """Whether the charter provides a repeated Word header or footer."""
        return self.header is not None or self.footer is not None


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
    # The HTML charter has no letterhead, so only a discreet centred page number.
    footer=hf.FooterSpec(layout="center", color="666666", size_pt=9),
    page=hf.PageSpec(top=1134, bottom=1418, left=1417, right=1417),
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
    # Mirrors .ei-doc-head: blue rule, logo, brand mention, orange rule.
    header=hf.HeaderSpec(
        brand="Euro-Information",
        brand_color="003A8D",
        brand_size_pt=9,
        brand_caps=True,
        logo=hf.LogoSpec(
            data_base64=EI_LOGO_PNG_BASE64,
            width_emu=hf.millimetres_to_emu(11.9),
            height_emu=hf.millimetres_to_emu(11.0),
        ),
        top_rule=hf.RuleSpec(color="003A8D", size_eighth_pt=36),
        bottom_rule=hf.RuleSpec(color="FBAE40", size_eighth_pt=12),
    ),
    # Mirrors .ei-doc-foot: hairline, document title left, page number right.
    footer=hf.FooterSpec(
        layout="split",
        color="8A9099",
        size_pt=9,
        top_rule=hf.RuleSpec(color="DBE3F0", size_eighth_pt=6),
    ),
    # Top margin much wider than the HTML @page rule: the header lives inside
    # it (12.5 mm offset, about 13 mm of letterhead), so 33 mm leaves the body a
    # visible gap below the orange rule on continuation pages.
    page=hf.PageSpec(top=1871, bottom=1418, left=1417, right=1417),
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


def has_page_furniture(key: str | None) -> bool:
    """Whether the charter of a key ships a repeated Word header or footer.

    Callers use this to decide whether the decorative HTML blocks may be dropped
    from the exported body: removing them is only safe when Word reproduces them.

    Args:
        key: Charter key read from ``data-doc-template``.

    Returns:
        True when the charter exists and declares a header or a footer.
    """
    charter = charter_for(key)
    return charter is not None and charter.has_page_furniture


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
        with trace_span("export.reference_docx", {"export.charter": charter.key, "file.path": str(target)}):
            build_reference_docx(charter, staging)
            staging.replace(target)
    except (OSError, subprocess.SubprocessError, ET.ParseError, KeyError, ValueError) as exc:
        logger.warning("Reference docx generation failed for charter %s: %s", charter.key, exc)
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
        ValueError: If the default reference document has no section properties
            to hang the header and footer references on.
    """
    with tempfile.TemporaryDirectory(prefix="htmleditor-ref-") as tmp:
        base = Path(tmp) / "reference.docx"
        base.write_bytes(default_reference_bytes())
        with zipfile.ZipFile(base) as archive:
            replacements = {STYLES_PART: patch_styles_xml(archive.read(STYLES_PART), charter)}
            if charter.has_page_furniture or charter.page is not None:
                replacements[DOCUMENT_PART] = patch_document_xml(archive.read(DOCUMENT_PART), charter)
                replacements[DOCUMENT_RELS_PART] = patch_document_rels_xml(archive.read(DOCUMENT_RELS_PART), charter)
                replacements[CONTENT_TYPES_PART] = patch_content_types_xml(archive.read(CONTENT_TYPES_PART), charter)
        _copy_zip(base, destination, replacements, page_furniture_parts(charter))


def default_reference_bytes() -> bytes:
    """Return pandoc's own default ``reference.docx`` as bytes.

    Raises:
        FileNotFoundError: If pandoc is not available in PATH.
        subprocess.CalledProcessError: If pandoc exits with a non-zero code.
    """
    with trace_span("tool.pandoc", {"tool.operation": "print-default-reference"}) as span:
        # Fixed argument list, no shell. pandoc is resolved from PATH on purpose:
        # it is an external, user installed requirement, not a bundled binary.
        completed = subprocess.run(
            ["pandoc", "--print-default-data-file", "reference.docx"],  # noqa: S607
            capture_output=True,
            check=True,
        )
        span.set_attribute("file.size", len(completed.stdout))
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


def patch_document_xml(document_xml: bytes, charter: Charter) -> bytes:
    """Return ``word/document.xml`` with the header, footer and page geometry.

    The header and footer references and the page geometry are written into the
    single ``w:sectPr`` of the reference document, in schema order: the
    references first, then the existing ``w:footnotePr``, then ``w:pgSz`` and
    ``w:pgMar`` last. Pandoc reuses that ``w:sectPr`` verbatim for the document
    it produces, which is what makes the letterhead repeat on every page.

    Args:
        document_xml: Raw content of the ``word/document.xml`` part.
        charter: Charter to apply.

    Returns:
        The patched XML.

    Raises:
        ValueError: If the part declares no section properties.
    """
    text = document_xml.decode("utf-8")
    opening = _SECTPR_OPEN.search(text)
    if opening is None:
        raise ValueError("reference document has no w:sectPr to attach a header to")
    if opening.group(1):
        # Self-closing form: expand it first so children can be inserted.
        text = f"{text[: opening.start()]}{_SECTPR_START}{_SECTPR_CLOSE}{text[opening.end() :]}"
        insert_at = opening.start() + len(_SECTPR_START)
    else:
        insert_at = opening.end()
    references = hf.sectpr_references(
        has_header=charter.header is not None,
        has_footer=charter.footer is not None,
    )
    text = f"{text[:insert_at]}{references}{text[insert_at:]}"
    page = "" if charter.page is None else hf.sectpr_page(charter.page)
    if page:
        close = text.index(_SECTPR_CLOSE, insert_at)
        text = f"{text[:close]}{page}{text[close:]}"
    return text.encode("utf-8")


def patch_document_rels_xml(rels_xml: bytes, charter: Charter) -> bytes:
    """Return ``word/_rels/document.xml.rels`` with the header and footer relations.

    Args:
        rels_xml: Raw content of the relationships part.
        charter: Charter to apply.

    Returns:
        The patched XML.

    Raises:
        ValueError: If the part is not a relationships document.
    """
    entries = hf.document_rels_entries(
        has_header=charter.header is not None,
        has_footer=charter.footer is not None,
    )
    return _insert_before_close(rels_xml, "</Relationships>", entries)


def patch_content_types_xml(content_types_xml: bytes, charter: Charter) -> bytes:
    """Return ``[Content_Types].xml`` declaring the injected parts.

    Pandoc rebuilds this part for the exported document, deriving media types on
    its own; the declarations matter so the reference document is a valid DOCX in
    its own right and can be opened for inspection.

    Args:
        content_types_xml: Raw content of the content types part.
        charter: Charter to apply.

    Returns:
        The patched XML.

    Raises:
        ValueError: If the part is not a content types document.
    """
    entries = hf.content_type_entries(
        has_header=charter.header is not None,
        has_footer=charter.footer is not None,
        has_logo=charter.header is not None and charter.header.logo is not None,
    )
    return _insert_before_close(content_types_xml, "</Types>", entries)


def page_furniture_parts(charter: Charter) -> dict[str, bytes]:
    """Return the archive members carrying the header, footer and logo.

    Args:
        charter: Charter to render.

    Returns:
        Archive member name to content; empty when the charter has no header and
        no footer.
    """
    tab = hf.DEFAULT_CONTENT_WIDTH_TWIPS if charter.page is None else charter.page.content_width
    parts: dict[str, bytes] = {}
    if charter.header is not None:
        parts[hf.HEADER_PART] = hf.build_header_xml(charter.header, charter.font, tab)
        if charter.header.logo is not None:
            parts[hf.HEADER_RELS_PART] = hf.build_header_rels_xml()
            parts[hf.LOGO_PART] = charter.header.logo.to_bytes()
    if charter.footer is not None:
        parts[hf.FOOTER_PART] = hf.build_footer_xml(charter.footer, charter.font, tab)
    return parts


def _insert_before_close(xml: bytes, closing_tag: str, entries: str) -> bytes:
    """Return ``xml`` with ``entries`` spliced in just before ``closing_tag``.

    Raises:
        ValueError: If the closing tag is absent.
    """
    if not entries:
        return xml
    text = xml.decode("utf-8")
    if closing_tag not in text:
        raise ValueError(f"reference document part has no {closing_tag}")
    return text.replace(closing_tag, f"{entries}{closing_tag}", 1).encode("utf-8")


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
        # Fixed argument list, no shell; pandoc resolved from PATH (see above).
        completed = subprocess.run(
            ["pandoc", "--version"],  # noqa: S607
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("pandoc version unavailable: %s", exc)
        return ""
    lines = completed.stdout.splitlines()
    return lines[0].strip() if lines else ""


def _copy_zip(
    source: Path,
    destination: Path,
    replacements: Mapping[str, bytes],
    additions: Mapping[str, bytes],
) -> None:
    """Copy a DOCX archive, substituting some parts and appending new ones.

    Every member not named in ``replacements`` is copied byte for byte, which is
    what keeps the pandoc conventions (numbering, theme, settings) intact.

    Args:
        source: Archive to copy.
        destination: Archive to write.
        replacements: Member name to new content, for members already present.
        additions: Member name to content, for members to create.
    """
    with (
        zipfile.ZipFile(source) as reader,
        zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as writer,
    ):
        for item in reader.infolist():
            data = replacements.get(item.filename)
            writer.writestr(item, reader.read(item.filename) if data is None else data)
        for name, content in additions.items():
            writer.writestr(name, content)
