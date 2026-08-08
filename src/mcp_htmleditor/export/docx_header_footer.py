"""Build the repeated Word header and footer parts of a reference DOCX.

An HTML document shows its letterhead once, at the top of the page flow: the
Euro-Information charter puts a blue rule, the logo, the brand mention and an
orange rule in a ``.ei-doc-head`` block, then a discreet ``.ei-doc-foot`` block
at the very end. Exported through pandoc those blocks become ordinary body
paragraphs, printed once, before the title. A Word document instead carries the
letterhead in ``word/header1.xml`` and ``word/footer1.xml``, parts that Word and
LibreOffice repeat on every page.

Pandoc cannot author those parts, but it does carry them over: it copies every
member of the ``--reference-doc`` archive it does not regenerate itself, reuses
the ``w:sectPr`` of the reference (hence its ``w:headerReference`` and
``w:footerReference``), keeps the relationships declared in
``word/_rels/document.xml.rels`` and emits a content-type override for each
``word/media/*`` entry it finds. Injecting the parts into the reference document
is therefore enough to obtain a real Word letterhead. Verified against pandoc
3.10; the relationship ids used here sit high on purpose, because pandoc
allocates its own ids above the highest one it finds.

The page geometry travels with the letterhead: a header only has room to breathe
if the top margin is wide enough, so a charter that declares a header also
declares its page size and margins (A4, mirroring the ``@page`` rule of the HTML
templates).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
PKG_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

HEADER_PART = "word/header1.xml"
FOOTER_PART = "word/footer1.xml"
HEADER_RELS_PART = "word/_rels/header1.xml.rels"
LOGO_PART = "word/media/header-logo.png"

HEADER_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"
FOOTER_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"

#: Relationship ids of the header and footer inside ``word/document.xml.rels``.
#: Pandoc renumbers its own parts above the highest id it finds, so these stay
#: free of collisions while leaving it a wide range.
HEADER_REL_ID = "rId990"
FOOTER_REL_ID = "rId991"
#: Relationship id of the logo inside ``word/_rels/header1.xml.rels``, a part
#: pandoc never rewrites, so a local id is enough.
LOGO_REL_ID = "rId1"

#: Fallback text width, used when a charter declares no page geometry.
DEFAULT_CONTENT_WIDTH_TWIPS = 9072

_EMU_PER_MM = 36000


@dataclass(frozen=True)
class RuleSpec:
    """A horizontal rule drawn as a paragraph border.

    Attributes:
        color: Hex RGB colour without ``#``.
        size_eighth_pt: Thickness in eighths of a point, as ``w:sz`` expects
            (36 renders like a 6px CSS border, 6 like a hairline).
    """

    color: str
    size_eighth_pt: int = 8


@dataclass(frozen=True)
class LogoSpec:
    """A PNG logo embedded in the Word header.

    The bytes travel as base64 so the whole charter stays JSON-serializable and
    can be fingerprinted for the reference document cache.

    Attributes:
        data_base64: PNG payload, base64 encoded, whitespace allowed.
        width_emu: Rendered width in English Metric Units (36000 per mm).
        height_emu: Rendered height in English Metric Units.
    """

    data_base64: str
    width_emu: int
    height_emu: int

    def to_bytes(self) -> bytes:
        """Return the decoded PNG payload."""
        return base64.b64decode("".join(self.data_base64.split()))


@dataclass(frozen=True)
class HeaderSpec:
    """The repeated Word header of a charter.

    The header is one paragraph: the logo on the left, a right tab stop, then the
    brand mention flush right, framed by up to two rules.

    Attributes:
        brand: Text placed flush right, empty for none.
        brand_color: Hex RGB colour of that text.
        brand_size_pt: Font size of that text, in points.
        brand_caps: Whether the text is forced to uppercase.
        logo: Logo placed flush left, or None.
        top_rule: Rule above the header line, or None.
        bottom_rule: Rule below the header line, or None.
    """

    brand: str = ""
    brand_color: str = "000000"
    brand_size_pt: float = 9
    brand_caps: bool = True
    logo: LogoSpec | None = None
    top_rule: RuleSpec | None = None
    bottom_rule: RuleSpec | None = None


@dataclass(frozen=True)
class FooterSpec:
    """The repeated Word footer of a charter.

    Two layouts: ``split`` puts the document title on the left and the page
    number flush right, ``center`` centres the page number alone.

    Attributes:
        layout: ``split`` or ``center``.
        page_label: Word placed before the page number, empty for none.
        color: Hex RGB colour of the footer text.
        size_pt: Font size of the footer text, in points.
        top_rule: Rule above the footer line, or None.
    """

    layout: str = "center"
    page_label: str = "Page"
    color: str = "666666"
    size_pt: float = 8
    top_rule: RuleSpec | None = None


@dataclass(frozen=True)
class PageSpec:
    """Page size and margins of a charter, in twentieths of a point.

    Attributes:
        width: Page width (11906 for A4 portrait).
        height: Page height (16838 for A4 portrait).
        top: Top margin; must leave room for the header.
        right: Right margin.
        bottom: Bottom margin; must leave room for the footer.
        left: Left margin.
        header: Distance from the top edge to the header.
        footer: Distance from the bottom edge to the footer.
    """

    width: int = 11906
    height: int = 16838
    top: int = 1701
    right: int = 1417
    bottom: int = 1418
    left: int = 1417
    header: int = 709
    footer: int = 709

    @property
    def content_width(self) -> int:
        """Return the usable text width, where the right tab stop belongs."""
        return self.width - self.left - self.right


def build_header_xml(spec: HeaderSpec, font: str, tab_twips: int) -> bytes:
    """Return the ``word/header1.xml`` part for a header specification.

    Args:
        spec: Header to render.
        font: Charter font family applied to the brand mention.
        tab_twips: Position of the right tab stop, normally the text width.

    Returns:
        The serialized header part.
    """
    run_props = _run_props(font, spec.brand_color, spec.brand_size_pt, caps=spec.brand_caps)
    content = ""
    if spec.logo is not None:
        content += _drawing(spec.logo)
    if spec.brand:
        content += f"<w:r>{run_props}<w:tab /><w:t>{escape(spec.brand)}</w:t></w:r>"
    paragraph_props = (
        f"<w:pPr>{_borders(top=spec.top_rule, bottom=spec.bottom_rule)}"
        f"{_tabs(tab_twips)}{_flat_spacing()}<w:rPr>{_inner(run_props)}</w:rPr></w:pPr>"
    )
    body = f"<w:p>{paragraph_props}{content}</w:p>"
    return _part("hdr", body, with_drawing_namespaces=spec.logo is not None)


def build_footer_xml(spec: FooterSpec, font: str, tab_twips: int) -> bytes:
    """Return the ``word/footer1.xml`` part for a footer specification.

    Args:
        spec: Footer to render.
        font: Charter font family applied to the footer text.
        tab_twips: Position of the right tab stop, normally the text width.

    Returns:
        The serialized footer part.
    """
    run_props = _run_props(font, spec.color, spec.size_pt)
    label = f"{escape(spec.page_label)} " if spec.page_label else ""
    is_split = spec.layout == "split"
    if is_split:
        # Title flush left, then a right tab stop carrying the page number.
        content = _title_field(run_props)
        content += f'<w:r>{run_props}<w:tab /><w:t xml:space="preserve">{label}</w:t></w:r>'
    else:
        content = f'<w:r>{run_props}<w:t xml:space="preserve">{label}</w:t></w:r>' if label else ""
    content += _page_field(run_props)
    alignment = "" if is_split else '<w:jc w:val="center" />'
    paragraph_props = (
        f"<w:pPr>{_borders(top=spec.top_rule)}{_tabs(tab_twips)}"
        f"{_flat_spacing()}{alignment}<w:rPr>{_inner(run_props)}</w:rPr></w:pPr>"
    )
    body = f"<w:p>{paragraph_props}{content}</w:p>"
    return _part("ftr", body, with_drawing_namespaces=False)


def build_header_rels_xml() -> bytes:
    """Return ``word/_rels/header1.xml.rels``, wiring the header to its logo."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<Relationships xmlns="{PKG_RELS_NS}">'
        f'<Relationship Id="{LOGO_REL_ID}" Type="{R_NS}/image" Target="media/header-logo.png" />'
        "</Relationships>"
    ).encode()


def document_rels_entries(*, has_header: bool, has_footer: bool) -> str:
    """Return the ``Relationship`` elements to append to the document rels.

    Args:
        has_header: Whether a header part is injected.
        has_footer: Whether a footer part is injected.

    Returns:
        The concatenated XML elements, empty when nothing is injected.
    """
    entries = ""
    if has_header:
        entries += f'<Relationship Id="{HEADER_REL_ID}" Type="{R_NS}/header" Target="header1.xml" />'
    if has_footer:
        entries += f'<Relationship Id="{FOOTER_REL_ID}" Type="{R_NS}/footer" Target="footer1.xml" />'
    return entries


def content_type_entries(*, has_header: bool, has_footer: bool, has_logo: bool) -> str:
    """Return the ``[Content_Types].xml`` entries the injected parts need.

    Pandoc rebuilds this part and re-derives the media types itself, so these
    entries only matter for the reference document to be a valid DOCX on its own.

    Args:
        has_header: Whether a header part is injected.
        has_footer: Whether a footer part is injected.
        has_logo: Whether a PNG logo is injected.

    Returns:
        The concatenated XML elements, empty when nothing is injected.
    """
    entries = ""
    if has_logo:
        entries += '<Default Extension="png" ContentType="image/png" />'
    if has_header:
        entries += f'<Override PartName="/{HEADER_PART}" ContentType="{HEADER_CONTENT_TYPE}" />'
    if has_footer:
        entries += f'<Override PartName="/{FOOTER_PART}" ContentType="{FOOTER_CONTENT_TYPE}" />'
    return entries


def sectpr_references(*, has_header: bool, has_footer: bool) -> str:
    """Return the ``w:sectPr`` reference children, which come first in schema order.

    Args:
        has_header: Whether a header part is injected.
        has_footer: Whether a footer part is injected.

    Returns:
        The concatenated XML elements, empty when nothing is injected.
    """
    references = ""
    if has_header:
        references += f'<w:headerReference w:type="default" r:id="{HEADER_REL_ID}" />'
    if has_footer:
        references += f'<w:footerReference w:type="default" r:id="{FOOTER_REL_ID}" />'
    return references


def sectpr_page(page: PageSpec) -> str:
    """Return the ``w:pgSz`` and ``w:pgMar`` children of a ``w:sectPr``.

    They come last among the children this module writes, as the schema requires
    them after ``w:footnotePr``.

    Args:
        page: Page geometry to encode.

    Returns:
        The concatenated XML elements.
    """
    return (
        f'<w:pgSz w:w="{page.width}" w:h="{page.height}" />'
        f'<w:pgMar w:top="{page.top}" w:right="{page.right}" w:bottom="{page.bottom}" '
        f'w:left="{page.left}" w:header="{page.header}" w:footer="{page.footer}" w:gutter="0" />'
    )


def _part(tag: str, body: str, *, with_drawing_namespaces: bool) -> bytes:
    """Wrap header or footer content in its root element.

    Args:
        tag: ``hdr`` or ``ftr``.
        body: Inner XML.
        with_drawing_namespaces: Whether the drawing namespaces must be declared,
            which is only needed when a logo is embedded.

    Returns:
        The serialized part.
    """
    namespaces = f'xmlns:w="{W_NS}" xmlns:r="{R_NS}"'
    if with_drawing_namespaces:
        namespaces += f' xmlns:wp="{WP_NS}" xmlns:a="{A_NS}" xmlns:pic="{PIC_NS}"'
    return (f'<?xml version="1.0" encoding="UTF-8"?><w:{tag} {namespaces}>{body}</w:{tag}>').encode()


def _run_props(font: str, color: str, size_pt: float, *, caps: bool = False) -> str:
    """Return a ``w:rPr`` element carrying the font, colour, size and caps."""
    half = round(size_pt * 2)
    caps_xml = '<w:caps w:val="1" />' if caps else ""
    family = _attribute(font)
    return (
        "<w:rPr>"
        f'<w:rFonts w:ascii="{family}" w:hAnsi="{family}" w:cs="{family}" />'
        f"{caps_xml}"
        f'<w:color w:val="{color}" />'
        f'<w:sz w:val="{half}" /><w:szCs w:val="{half}" />'
        "</w:rPr>"
    )


def _attribute(value: str) -> str:
    """Return a string escaped for use inside a double-quoted XML attribute."""
    return escape(value, {'"': "&quot;"})


def _inner(run_props: str) -> str:
    """Return the children of a ``w:rPr`` element, for reuse as a paragraph mark."""
    return run_props[len("<w:rPr>") : -len("</w:rPr>")]


def _borders(top: RuleSpec | None = None, bottom: RuleSpec | None = None) -> str:
    """Return a ``w:pBdr`` element for the requested rules, or an empty string."""
    parts = ""
    if top is not None:
        parts += f'<w:top w:val="single" w:sz="{top.size_eighth_pt}" w:space="1" w:color="{top.color}" />'
    if bottom is not None:
        parts += f'<w:bottom w:val="single" w:sz="{bottom.size_eighth_pt}" w:space="4" w:color="{bottom.color}" />'
    return f"<w:pBdr>{parts}</w:pBdr>" if parts else ""


def _tabs(position: int) -> str:
    """Return a ``w:tabs`` element with a single right tab stop."""
    return f'<w:tabs><w:tab w:val="right" w:pos="{position}" /></w:tabs>'


def _flat_spacing() -> str:
    """Return a ``w:spacing`` element cancelling the inherited paragraph spacing."""
    return '<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto" />'


def _page_field(run_props: str) -> str:
    """Return the runs of a dynamic ``PAGE`` field, with a cached result of 1."""
    return _field(run_props, " PAGE ", "1")


def _title_field(run_props: str) -> str:
    """Return the runs of a dynamic ``TITLE`` field, showing the document title.

    Pandoc writes the document title into ``docProps/core.xml``, which is what
    Word and LibreOffice read to resolve this field, so the footer follows the
    real title instead of a value frozen in the charter.
    """
    return _field(run_props, " TITLE ", "")


def _field(run_props: str, instruction: str, cached: str) -> str:
    """Return the five runs of a Word field.

    The explicit ``fldChar`` form is used rather than ``w:fldSimple`` so that
    every run, including the cached result, carries the footer run properties;
    with ``w:fldSimple`` LibreOffice re-renders the recomputed value with the
    paragraph defaults and the page number comes out at the wrong size.

    Args:
        run_props: ``w:rPr`` element applied to every run.
        instruction: Field code, spaces included (for example ``" PAGE "``).
        cached: Value shown until the reader recomputes the field.

    Returns:
        The concatenated runs.
    """
    result = f'<w:r>{run_props}<w:t xml:space="preserve">{escape(cached)}</w:t></w:r>' if cached else ""
    return (
        f'<w:r>{run_props}<w:fldChar w:fldCharType="begin" /></w:r>'
        f'<w:r>{run_props}<w:instrText xml:space="preserve">{escape(instruction)}</w:instrText></w:r>'
        f'<w:r>{run_props}<w:fldChar w:fldCharType="separate" /></w:r>'
        f"{result}"
        f'<w:r>{run_props}<w:fldChar w:fldCharType="end" /></w:r>'
    )


def _drawing(logo: LogoSpec) -> str:
    """Return the run holding the header logo as an inline DrawingML picture."""
    extent = f'cx="{logo.width_emu}" cy="{logo.height_emu}"'
    return (
        "<w:r><w:drawing>"
        '<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f"<wp:extent {extent} />"
        '<wp:docPr id="900" name="Logo" descr="Logo" />'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1" /></wp:cNvGraphicFramePr>'
        f'<a:graphic><a:graphicData uri="{PIC_NS}"><pic:pic>'
        '<pic:nvPicPr><pic:cNvPr id="0" name="Logo" /><pic:cNvPicPr /></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{LOGO_REL_ID}" /><a:stretch><a:fillRect /></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0" /><a:ext {extent} /></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst /></a:prstGeom></pic:spPr>'
        "</pic:pic></a:graphicData></a:graphic>"
        "</wp:inline></w:drawing></w:r>"
    )


def millimetres_to_emu(millimetres: float) -> int:
    """Convert millimetres to English Metric Units, the DrawingML length unit."""
    return round(millimetres * _EMU_PER_MM)
