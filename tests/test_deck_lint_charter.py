"""Tests for the charter rules L007 to L011 of ``mcp-htmleditor lint`` (SPEC-0007 FR-NEW-012, FR-NEW-014, US-0043).

Fixtures come from ``deck_support`` (real bootstrap files). Expected lines are written by the tests themselves.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from mcp_htmleditor.deck import charter_rules

from .deck_support import (
    BOOTSTRAP,
    TINY_PNG,
    add_style,
    build_deck,
    deck_carbon,
    deck_ei,
    deck_med,
    doc_perso,
    inject_html,
    replace_in_slide,
    run_cli,
    set_total,
    write_deck,
)

OK = "lint: OK (0 errors, 0 warnings)"
SOURCE = '<p class="med-source"><span class="src-title">Titre</span> : Auteur A. 2024.</p>'
COMMENT = '<div class="med-comment w-50">'
REMOTE = "https://example.com/a.png"


def lint(tmp_path: Path, content: str, *flags: str) -> tuple[list[str], int]:
    """Write ``content``, run ``lint`` and return ``(stdout lines, exit code)``."""
    stdout, stderr, code = run_cli("lint", write_deck(tmp_path / "f.html", content), *flags)
    assert stderr == ""
    return stdout.splitlines(), code


def foreign(code_class: str, charter: str, slide: str = "slide-1") -> str:
    """Return the expected L007 line."""
    return f'error L007 {slide} class "{code_class}" belongs to another charter than {charter}'


def with_class(html: str, index: int, markup: str) -> str:
    """Append ``markup`` to the body of slide ``index``."""
    return inject_html(html, index, markup)


def test_deck_lint_charter_foreign_class_on_medical(tmp_path: Path) -> None:
    """E2E-021: a ``cds-tile`` div in slide-2 of DECK-MED is an error and the exit status is 1."""
    html = replace_in_slide(deck_med(), 2, '<ul class="med-list">', '<div class="cds-tile"></div><ul class="med-list">')
    lines, code = lint(tmp_path, html)
    assert lines == [foreign("cds-tile", "medical", "slide-2"), "lint: FAIL (1 error, 0 warnings)"]
    assert code == 1


def test_deck_lint_charter_missing_width_class(tmp_path: Path) -> None:
    """E2E-022: the second child of a ``.med-strip`` of slide-3 has no width class."""
    html = replace_in_slide(deck_med(), 3, COMMENT, '<div class="med-comment">')
    lines, code = lint(tmp_path, html)
    assert lines == [
        "error L008 slide-3 child of .med-strip has no w-* width class",
        "lint: FAIL (1 error, 0 warnings)",
    ]
    assert code == 1


def test_deck_lint_charter_warning_only_exits_zero(tmp_path: Path) -> None:
    """E2E-026: one remote image is a warning, the verdict is OK and the exit status 0."""
    lines, code = lint(tmp_path, with_class(deck_ei(), 2, f'<img src="{REMOTE}" alt="r">'))
    assert lines == [f"warning L010 slide-2 remote image {REMOTE} is not exported", "lint: OK (0 errors, 1 warning)"]
    assert code == 0


def test_deck_lint_charter_error_exit_and_json(tmp_path: Path) -> None:
    """E2E-026: a TOTAL of 7 fails with status 1; ``--json`` has a null slide for a whole file problem."""
    html = set_total(deck_ei(), 7)
    lines, code = lint(tmp_path, html)
    assert lines[-1] == "lint: FAIL (1 error, 0 warnings)"
    assert code == 1
    out, code = lint(tmp_path, html, "--json")
    assert code == 1
    assert json.loads(out[0])["problems"][0]["slide"] is None
    assert json.loads(out[0])["errors"] == 1
    assert out[0].startswith('{"problems":[{"code":"L002"')
    assert out[0].endswith('"errors":1,"warnings":0}')


def test_deck_lint_charter_image_without_source(tmp_path: Path) -> None:
    """E2E-035: an empty source on a content slide fails; the cover with a logo and no source passes."""
    html = replace_in_slide(deck_med(), 1, SOURCE, '<p class="med-source">  </p>')
    logo = f'<div class="med-logos"><img src="data:image/png;base64,{TINY_PNG}" alt="Logo"></div>'
    html = replace_in_slide(
        html, 0, '<div class="med-logos"><!-- <img src="data:image/png;base64,…" alt="Logo"> --></div>', logo
    )
    lines, code = lint(tmp_path, html)
    assert lines == ["error L009 slide-1 slide has an image and no source line", "lint: FAIL (1 error, 0 warnings)"]
    assert code == 1


def test_deck_lint_charter_palette_warning(tmp_path: Path) -> None:
    """E2E-037: one warning for #123456; the palette, white and grey colours are accepted."""
    html = add_style(deck_med(), 2, "color:#123456")
    html = add_style(html, 2, "color:#159984; background:#FFFFFF; border-color:#777777")
    lines, code = lint(tmp_path, html)
    assert lines == [
        "warning L011 slide-2 colour #123456 is not in the medical palette",
        "lint: OK (0 errors, 1 warning)",
    ]
    assert code == 0


@pytest.mark.parametrize(
    ("charter", "name"),
    [
        *[("medical", n) for n in ("cds-tile", "tag-blue", "stat-card", "ei-doc-head", "slide-inner", "slide-header")],
        *[("medical", n) for n in ("slide-footer", "slide-foot", "slide-foot-logo", "slide-foot-title")],
        *[("ei", n) for n in ("med-list", "stat-card", "cw-bar", "mention-pill", "slide-header", "slide-footer")],
        *[("carbon", n) for n in ("med-band", "slide-inner", "slide-foot", "slide-foot-logo", "slide-foot-title")],
        ("carbon", "slide-foot-page"),
        ("carbon", "slide-title-rule"),
    ],
)
def test_deck_lint_charter_foreign_class_tables(tmp_path: Path, charter: str, name: str) -> None:
    """Every prefix and every exact name of the three tables is flagged on its charter."""
    titles = ("A", "B", "C")
    lines, code = lint(tmp_path, with_class(build_deck(charter, titles), 1, f'<div class="{name}"></div>'))
    assert foreign(name, charter) in lines
    assert code == 1


@pytest.mark.parametrize(
    ("charter", "name"),
    [
        ("ei", "slide-foot-page"),
        ("ei", "slide-inner"),
        ("ei", "cds-tile"),
        ("ei", "slide-foot"),
        ("medical", "slide-foot-page"),
        ("medical", "med-list"),
        ("medical", "tagline"),
        ("medical", "cdsx"),
        ("carbon", "slide-header"),
        ("carbon", "slide-footer"),
        ("carbon", "cds-tile"),
        ("carbon", "stat-card"),
        ("carbon", "tag-blue"),
    ],
)
def test_deck_lint_charter_own_classes_pass(tmp_path: Path, charter: str, name: str) -> None:
    """Classes of the charter itself, and near misses of a prefix, are not flagged."""
    lines, code = lint(tmp_path, with_class(build_deck(charter, ("A", "B", "C")), 1, f'<div class="{name}"></div>'))
    assert not [line for line in lines if " L007 " in line]
    assert code == 0


def test_deck_lint_charter_foreign_class_once_per_slide_in_order(tmp_path: Path) -> None:
    """Two uses of a class give one problem; classes come in first occurrence order, per slide."""
    fragment = '<div class="tag-x cds-b"></div><div class="cds-b stat-a"></div><p class="tag-x"></p>'
    html = with_class(with_class(deck_med(), 1, fragment), 2, '<i class="cds-b"></i>')
    lines, _ = lint(tmp_path, html)
    assert lines[:-1] == [
        foreign("tag-x", "medical"),
        foreign("cds-b", "medical"),
        foreign("stat-a", "medical"),
        foreign("cds-b", "medical", "slide-2"),
    ]


def test_deck_lint_charter_class_on_the_slide_itself_and_odd_whitespace(tmp_path: Path) -> None:
    """The slide element is read; a ``class`` attribute with tabs and newlines is split on whitespace."""
    html = replace_in_slide(deck_med(), 2, '<article class="slide"', '<article class="slide\n\t cds-s  "')
    html = with_class(html, 2, '<div class="  a\n\tcds-t\r\n b "></div>')
    lines, _ = lint(tmp_path, html)
    assert lines[:-1] == [foreign("cds-s", "medical", "slide-2"), foreign("cds-t", "medical", "slide-2")]


def test_deck_lint_charter_class_case_is_exact(tmp_path: Path) -> None:
    """``CDS-tile`` is not ``cds-``: class names are compared as written."""
    lines, _ = lint(tmp_path, with_class(deck_med(), 1, '<div class="CDS-tile"></div>'))
    assert lines == [OK]


def test_deck_lint_charter_width_class_per_child(tmp_path: Path) -> None:
    """Three children without a width class in one ``.med-strip`` give three problems."""
    strip = '<div class="med-strip"><b></b><i class="x"></i><u class="w-45"></u></div>'
    lines, _ = lint(tmp_path, with_class(deck_med(), 2, strip))
    expected = "error L008 slide-2 child of .med-strip has no w-* width class"
    assert lines[:-1] == [expected] * 3


def test_deck_lint_charter_width_classes(tmp_path: Path) -> None:
    """Every accepted width class passes on every flex row; the row class is named in the message."""
    widths = ("w-25", "w-30", "w-33", "w-40", "w-50", "w-60", "w-70")
    rows = ("med-strip", "med-split", "med-cols", "med-compare", "med-steps", "med-stats", "med-timeline")
    good = "".join(f'<div class="{r}">' + "".join(f'<p class="{w}"></p>' for w in widths) + "</div>" for r in rows)
    assert lint(tmp_path, with_class(deck_med(), 2, good))[0] == [OK]
    bad = '<div class="med-section-figs"><p></p></div><div class="med-split">text<p class="w-60"></p><p></p></div>'
    lines, _ = lint(tmp_path, with_class(deck_med(), 2, bad))
    assert lines[:-1] == [
        "error L008 slide-2 child of .med-section-figs has no w-* width class",
        "error L008 slide-2 child of .med-split has no w-* width class",
    ]


def test_deck_lint_charter_width_rows_only_on_medical(tmp_path: Path) -> None:
    """A ``med-strip`` in an Euro-Information deck is L007 only, never L008."""
    lines, _ = lint(tmp_path, with_class(deck_ei(), 1, '<div class="med-strip"><p></p></div>'))
    assert lines[:-1] == [foreign("med-strip", "ei")]


def test_deck_lint_charter_source_rules(tmp_path: Path) -> None:
    """A ``thanks`` slide passes, whitespace only fails (also a no break space), no image passes, text passes."""
    thanks = replace_in_slide(deck_med(), 1, 'data-slide-type="content"', 'data-slide-type="thanks"')
    thanks = replace_in_slide(thanks, 1, SOURCE, "")
    assert lint(tmp_path, thanks)[0] == [OK]
    blank = replace_in_slide(deck_med(), 1, SOURCE, '<p class="med-source"> \n\u00a0</p>')
    assert lint(tmp_path, blank)[0][0] == "error L009 slide-1 slide has an image and no source line"
    noimage = replace_in_slide(deck_med(), 1, SOURCE, "")
    noimage = replace_in_slide(noimage, 1, f'<img src="data:image/png;base64,{TINY_PNG}" alt="a">', "")
    assert lint(tmp_path, noimage)[0] == [OK]
    two = replace_in_slide(deck_med(), 1, SOURCE, f'<p class="med-source"></p>{SOURCE}')
    assert lint(tmp_path, two)[0] == [OK]


def test_deck_lint_charter_source_rule_is_medical_only(tmp_path: Path) -> None:
    """An image without a source line is not a problem in an Euro-Information deck."""
    assert lint(tmp_path, deck_ei())[0] == [OK]


@pytest.mark.parametrize("src", ["HTTP://x/a.png", "Https://x/a.png", "  https://x/a.png"])
def test_deck_lint_charter_remote_image_forms(tmp_path: Path, src: str) -> None:
    """The scheme is compared ignoring case; the url is shown as written, without the surrounding blanks."""
    lines, _ = lint(tmp_path, with_class(deck_ei(), 1, f'<img src="{src}" alt="r">'))
    assert lines[0] == f"warning L010 slide-1 remote image {src.strip()} is not exported"


def test_deck_lint_charter_local_images_are_not_remote(tmp_path: Path) -> None:
    """A data URI, a relative path, a protocol relative url, an img without src and a non img src are ignored."""
    fragment = (
        '<img src="data:image/png;base64,AAAA"><img src="media/a.png"><img src="//x/a.png"><img>'
        '<img src=""><script src="https://x/s.js"></script><a href="https://x/y.png">l</a>'
    )
    assert lint(tmp_path, with_class(deck_ei(), 1, fragment))[0] == [OK]


def test_deck_lint_charter_remote_image_one_problem_per_image(tmp_path: Path) -> None:
    """Two remote images give two warnings, even with the same url."""
    two = f'<img src="{REMOTE}"><img src="{REMOTE}">'
    lines, _ = lint(tmp_path, with_class(deck_ei(), 1, two))
    assert lines[:-1] == [f"warning L010 slide-1 remote image {REMOTE} is not exported"] * 2


def test_deck_lint_charter_remote_image_outside_every_slide(tmp_path: Path) -> None:
    """In a presentation an image outside the slides is reported with slide ``-``, before the slide problems."""
    html = with_class(deck_ei(), 1, f'<img src="{REMOTE}">')
    at = html.rindex("</body>")
    html = html[:at] + '<img src="http://x/out.png">' + html[at:]
    lines, _ = lint(tmp_path, html)
    assert lines[:-1] == [
        "warning L010 - remote image http://x/out.png is not exported",
        f"warning L010 slide-1 remote image {REMOTE} is not exported",
    ]


def test_deck_lint_charter_document_gets_l010_only(tmp_path: Path) -> None:
    """DOC-PERSO: one L010 line with slide ``-``, no other code, and the OK verdict with one warning."""
    html = doc_perso().replace(
        '<h1 class="doc-h1">Risques</h1>', f'<h1 class="doc-h1">Risques</h1><img src="{REMOTE}">'
    )
    html = html.replace('<h2 class="doc-h2">', '<h2 class="doc-h2 cds-tile" style="color:#123456">')
    lines, code = lint(tmp_path, html)
    assert lines == [f"warning L010 - remote image {REMOTE} is not exported", "lint: OK (0 errors, 1 warning)"]
    assert code == 0


@pytest.mark.parametrize("name", ["mail-empty.html", "website-empty.html"])
def test_deck_lint_charter_mail_and_website_get_l010_only(tmp_path: Path, name: str) -> None:
    """A mail and a website are checked by L010 only."""
    text = (
        (BOOTSTRAP / name).read_text(encoding="utf-8").replace("</body>", f'<img src="{REMOTE}" class="cds-x"></body>')
    )
    lines, code = lint(tmp_path, text)
    assert lines == [f"warning L010 - remote image {REMOTE} is not exported", "lint: OK (0 errors, 1 warning)"]
    assert code == 0


def test_deck_lint_charter_colour_forms(tmp_path: Path) -> None:
    """``#ABC`` is expanded for the comparison and shown as written; letter case is ignored."""
    lines, _ = lint(tmp_path, add_style(deck_ei(), 1, "color:#ABC"))
    assert lines[0] == "warning L011 slide-1 colour #ABC is not in the ei palette"
    assert lint(tmp_path, add_style(deck_ei(), 1, "color:#fbae40; background:#003a8d"))[0] == [OK]
    assert lint(tmp_path, add_style(deck_ei(), 1, "color:#000; background:#fff; border-color:#808080"))[0] == [OK]
    assert lint(tmp_path, add_style(deck_ei(), 1, "color:#808081"))[0][0].endswith(
        "colour #808081 is not in the ei palette"
    )


def test_deck_lint_charter_colour_ignored_forms(tmp_path: Path) -> None:
    """``rgb()``, ``var()``, names, 4 and 8 digit hex, url() and comments are ignored."""
    style = (
        "color:rgb(1,2,3); background:var(--x); border-color:red; outline-color:#abcd; fill:#12345678;"
        " background-image:url(data:image/png;base64,#123456); mask:url('#abc'); /* #765432 */ stroke:#003A8D"
    )
    assert lint(tmp_path, add_style(deck_ei(), 1, style))[0] == [OK]


def test_deck_lint_charter_colour_once_per_slide(tmp_path: Path) -> None:
    """The same colour on two elements, or written two ways, gives one warning; slides count apart."""
    html = add_style(deck_ei(), 1, "color:#123456")
    html = add_style(html, 1, "color:#123456; background:#112233")
    html = add_style(html, 2, "color:#123456")
    lines, _ = lint(tmp_path, html)
    assert lines == [
        "warning L011 slide-1 colour #123456 is not in the ei palette",
        "warning L011 slide-1 colour #112233 is not in the ei palette",
        "warning L011 slide-2 colour #123456 is not in the ei palette",
        "lint: OK (0 errors, 3 warnings)",
    ]


def test_deck_lint_charter_colour_equivalent_spellings_are_one_colour(tmp_path: Path) -> None:
    """``#AABBCC`` and ``#abc`` are the same colour: the first spelling is shown, once."""
    html = add_style(deck_ei(), 1, "color:#AABBCC; background:#abc")
    lines, _ = lint(tmp_path, html)
    assert lines == ["warning L011 slide-1 colour #AABBCC is not in the ei palette", "lint: OK (0 errors, 1 warning)"]


def test_deck_lint_charter_style_blocks_are_not_scanned(tmp_path: Path) -> None:
    """A ``<style>`` block inside a slide and one outside carry foreign colours without a warning."""
    html = with_class(deck_ei(), 1, "<style>.x { color:#123456 }</style>")
    assert lint(tmp_path, html)[0] == [OK]


def test_deck_lint_charter_colour_on_the_slide_element(tmp_path: Path) -> None:
    """The ``style`` of the slide element itself is read."""
    html = replace_in_slide(deck_ei(), 3, '<article class="slide"', '<article style="color:#123456" class="slide"')
    assert lint(tmp_path, html)[0][0] == "warning L011 slide-3 colour #123456 is not in the ei palette"


@pytest.mark.parametrize(
    ("charter", "colour", "other"),
    [("carbon", "#0F62FE", "#003A8D"), ("medical", "#159984", "#0F62FE"), ("ei", "#003A8D", "#159984")],
)
def test_deck_lint_charter_palette_follows_the_charter(tmp_path: Path, charter: str, colour: str, other: str) -> None:
    """A colour of the charter passes; the colour of another charter is flagged with the charter name."""
    base = build_deck(charter, ("A", "B", "C"))
    assert lint(tmp_path, add_style(base, 1, f"color:{colour}"))[0] == [OK]
    lines, _ = lint(tmp_path, add_style(base, 1, f"color:{other}"))
    assert lines[0] == f"warning L011 slide-1 colour {other} is not in the {charter} palette"


def test_deck_lint_charter_order_inside_a_slide(tmp_path: Path) -> None:
    """Inside one slide the problems come by code: L007, L008, L009, L010, L011."""
    html = replace_in_slide(deck_med(), 1, SOURCE, "")
    html = replace_in_slide(html, 1, COMMENT, '<div class="med-comment cds-z" style="color:#123456">')
    html = with_class(html, 1, f'<img src="{REMOTE}">')
    lines, _ = lint(tmp_path, html)
    codes = [line.split()[1] for line in lines[:-1]]
    assert codes == ["L007", "L008", "L009", "L010", "L011"]


@pytest.mark.parametrize("maker", [deck_ei, deck_carbon, deck_med])
def test_deck_lint_charter_clean_decks_stay_clean(tmp_path: Path, maker: Callable[[], str]) -> None:
    """E2E-009 non regression: DECK-EI, DECK-CARBON and DECK-MED report nothing with every rule active."""
    assert lint(tmp_path, maker())[0] == [OK]


@pytest.mark.parametrize("charter", ["ei", "carbon", "medical"])
def test_deck_lint_charter_real_bootstrap_covers_have_no_charter_problem(tmp_path: Path, charter: str) -> None:
    """DEC-017: the real bootstrap cover of each charter has no foreign class, no colour and no remote image."""
    lines, _ = lint(tmp_path, build_deck(charter, ("Seul",)))
    assert not [line for line in lines if any(f" {c} " in line for c in ("L007", "L008", "L009", "L010", "L011"))]


def test_deck_lint_charter_rule_functions() -> None:
    """The contract functions return the documented tuples."""
    soup = BeautifulSoup(
        '<article class="cds-a" data-slide-type="content"><div class="med-strip"><p></p></div>'
        '<img src="http://h/i.png"><b style="color:#123456"></b></article>',
        "html.parser",
    )
    slide = soup.find("article")
    assert slide is not None
    assert charter_rules.foreign_class_problems(slide, "medical") == [
        ("L007", 'class "cds-a" belongs to another charter than medical')
    ]
    assert charter_rules.charter_problems(slide, "medical") == [
        ("L007", "error", 'class "cds-a" belongs to another charter than medical'),
        ("L008", "error", "child of .med-strip has no w-* width class"),
        ("L009", "error", "slide has an image and no source line"),
        ("L011", "warning", "colour #123456 is not in the medical palette"),
    ]
    assert charter_rules.remote_image_problems(slide) == ["remote image http://h/i.png is not exported"]
    assert charter_rules.charter_problems(slide, "unknown") == []


def test_deck_lint_charter_palettes_live_in_one_module() -> None:
    """The palettes are written in ``charter_rules.py`` only."""
    folder = Path(charter_rules.__file__).parent
    holders = [p.name for p in folder.glob("*.py") if "#003A8D" in p.read_text(encoding="utf-8")]
    assert holders == ["charter_rules.py"]
