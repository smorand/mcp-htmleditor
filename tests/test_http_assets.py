"""Preservation of the template asset attributes when rebuilding a document.

`<html data-asset-*="data:...">` carries the fallback data URIs that
`resolveTemplateAssets()` (static/editor.js) uses when the document has no slide
to copy an asset from. Losing them on a save would silently break the footer logo
of every slide inserted afterwards.
"""

from __future__ import annotations

from pathlib import Path

from mcp_htmleditor.http_server import _rebuild_full_html


def test_rebuild_preserves_data_asset_attributes(tmp_path: Path) -> None:
    src = tmp_path / "pres.html"
    src.write_text(
        '<!DOCTYPE html>\n<html lang="fr" data-doc-type="presentation"'
        ' data-asset-chevrons="data:image/png;base64,AAA"'
        ' data-asset-cover="data:image/jpeg;base64,BBB">\n'
        "<head><title>x</title></head>\n<body><article>a</article></body>\n</html>\n",
        encoding="utf-8",
    )

    out = _rebuild_full_html("<article>b</article>", str(src))

    assert 'lang="fr"' in out
    assert 'data-doc-type="presentation"' in out
    assert 'data-asset-chevrons="data:image/png;base64,AAA"' in out
    assert 'data-asset-cover="data:image/jpeg;base64,BBB"' in out


def test_rebuild_without_asset_attributes_stays_clean(tmp_path: Path) -> None:
    src = tmp_path / "doc.html"
    src.write_text(
        '<!DOCTYPE html>\n<html lang="fr" data-doc-type="document">\n'
        "<head><title>x</title></head>\n<body><article>a</article></body>\n</html>\n",
        encoding="utf-8",
    )

    out = _rebuild_full_html("<article>b</article>", str(src))

    assert "data-asset-" not in out
    assert out.count("<html") == 1
