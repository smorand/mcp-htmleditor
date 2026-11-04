"""Tests for ``mcp-htmleditor lint`` and the structure rules L001 to L006 (SPEC-0007 FR-NEW-012, FR-NEW-013, US-0042).

Fixtures come from ``deck_support`` (real bootstrap files). Expected counters are written by the tests
themselves, never taken from the renumber code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from .deck_support import (
    BOOTSTRAP,
    BOOTSTRAP_FILES,
    build_deck,
    deck_carbon,
    deck_ei,
    doc_perso,
    drop_attr,
    inject_html,
    run_cli,
    set_names_len,
    set_total,
    slide_html,
    write_deck,
)

OK = "lint: OK (0 errors, 0 warnings)"


def lint(tmp_path: Path, content: str, *flags: str, name: str = "f.html") -> tuple[list[str], str, int]:
    """Write ``content``, run ``lint`` and return ``(stdout lines, stderr, exit code)``."""
    stdout, stderr, code = run_cli("lint", write_deck(tmp_path / name, content), *flags)
    return stdout.splitlines(), stderr, code


def names_source(html: str, source: str) -> str:
    """Return ``html`` with the whole ``slideNames`` statement replaced by ``source``."""
    return re.sub(r"const slideNames = \[.*?\];", lambda _: f"const slideNames = {source};", html, flags=re.S)


def test_deck_lint_clean_deck(tmp_path: Path) -> None:
    """E2E-009: DECK-EI prints exactly the OK verdict and exits 0."""
    stdout, stderr, code = run_cli("lint", write_deck(tmp_path / "f.html", deck_ei()))
    assert (stdout, stderr, code) == (OK + "\n", "", 0)


def test_deck_lint_total_wrong(tmp_path: Path) -> None:
    """E2E-020: a TOTAL of 7 on 8 slides is the single error and the exit status is 1."""
    lines, _, code = lint(tmp_path, set_total(deck_ei(), 7))
    assert lines == ["error L002 - TOTAL is 7 but the file has 8 slides", "lint: FAIL (1 error, 0 warnings)"]
    assert code == 1


def test_deck_lint_template_text_left(tmp_path: Path) -> None:
    """E2E-023: ``Contenu de la slide`` left on slide-4 is reported with its slide id."""
    lines, _, code = lint(tmp_path, inject_html(deck_ei(), 4, "<p>Contenu de la slide…</p>"))
    assert lines == ['error L006 slide-4 template text left: "Contenu de la slide"', "lint: FAIL (1 error, 0 warnings)"]
    assert code == 1


def test_deck_lint_missing_attribute(tmp_path: Path) -> None:
    """E2E-024: slide-5 without data-title."""
    lines, _, _ = lint(tmp_path, drop_attr(deck_ei(), 5, "data-title"))
    assert lines == ["error L001 slide-5 missing attribute data-title", "lint: FAIL (1 error, 0 warnings)"]


def test_deck_lint_missing_attributes_in_order(tmp_path: Path) -> None:
    """One problem per missing attribute: data-type, then data-id, then data-title.

    A slide without ``data-type`` is only found through the ``article.slide`` fallback, which applies
    when no slide carries the attribute, so every slide of a two slide deck loses it.
    """
    html = build_deck("ei", ("A", "B"))
    for attr in ("data-title", "data-id", "data-type"):
        html = drop_attr(drop_attr(html, 1, attr), 0, attr)
    lines, _, _ = lint(tmp_path, html)
    assert lines[:6] == [
        f"error L001 slide-{i} missing attribute {name}"
        for i in (0, 1)
        for name in ("data-type", "data-id", "data-title")
    ]


def test_deck_lint_wrong_counters(tmp_path: Path) -> None:
    """E2E-025: eyebrow then page counter of slide-2."""
    html = deck_ei().replace("Cat · Slide 03 / 08", "Cat · Slide 05 / 08")
    html = html.replace('<span class="slide-foot-page">3</span>', '<span class="slide-foot-page">5</span>')
    lines, _, _ = lint(tmp_path, html)
    assert lines == [
        'error L005 slide-2 eyebrow counter says "Slide 05 / 08", expected "Slide 03 / 08"',
        'error L005 slide-2 page counter says "5", expected "3"',
        "lint: FAIL (2 errors, 0 warnings)",
    ]


def test_deck_lint_names_list_length(tmp_path: Path) -> None:
    """E2E-038: 7 slide names for 8 slides."""
    lines, _, _ = lint(tmp_path, set_names_len(deck_ei(), 7))
    assert lines[0] == "error L003 - slideNames has 7 entries but the file has 8 slides"


def test_deck_lint_ids_out_of_order_and_duplicate(tmp_path: Path) -> None:
    """E2E-039: the third slide is slide-5; two slides named slide-3 give the duplicate."""
    html = deck_ei().replace(
        'id="slide-2" data-type="slide" data-id="slide-2"', 'id="slide-5" data-type="slide" data-id="slide-5"'
    )
    lines, _, _ = lint(tmp_path, html)
    assert 'error L004 slide-5 expected id "slide-2" but found "slide-5"' in lines
    both = deck_ei().replace(
        'id="slide-4" data-type="slide" data-id="slide-4"', 'id="slide-3" data-type="slide" data-id="slide-3"'
    )
    lines, _, _ = lint(tmp_path, both)
    assert 'error L004 slide-3 duplicate id "slide-3"' in lines
    assert not any("expected id" in line for line in lines)


def test_deck_lint_document_is_clean_and_slide_operations_fail(tmp_path: Path) -> None:
    """E2E-041: a document fails patch and get-slide, and lints clean."""
    path = write_deck(tmp_path / "doc.html", doc_perso())
    ops = tmp_path / "ops.json"
    ops.write_text(json.dumps([{"op": "delete_slide", "id": "slide-0"}]), encoding="utf-8")
    _, stderr, code = run_cli("patch", path, "--ops", str(ops))
    assert code == 1
    assert 'patch failed at operation 1: operation "delete_slide" needs a presentation (nothing written)' in stderr
    _, stderr, code = run_cli("get-slide", path, "slide-0")
    assert (stderr, code) == (f"error: get_slide needs a presentation: {path}\n", 1)
    stdout, stderr, code = run_cli("lint", path)
    assert (stdout, stderr, code) == (OK + "\n", "", 0)


def test_lint_clean_after_special_title_insert(tmp_path: Path) -> None:
    """A slide inserted with a title full of entities leaves the deck lint clean (E2E-030 clause)."""
    path = write_deck(tmp_path / "f.html", deck_ei())
    title = "Café &amp; &quot;Co&quot; &lt;1&gt;"
    ops = [{"op": "insert_slide", "after": "slide-1", "html": slide_html("ei", "Cafe", data_title=title)}]
    ops_path = tmp_path / "ops.json"
    ops_path.write_text(json.dumps(ops), encoding="utf-8")
    _, stderr, code = run_cli("patch", path, "--ops", str(ops_path))
    assert (stderr, code) == ("", 0)
    stdout, _, code = run_cli("lint", path)
    assert (stdout, code) == (OK + "\n", 0)


def test_deck_lint_report_format() -> None:
    """The verdict line: plural forms, OK or FAIL, and ``-`` for a whole file problem."""
    from mcp_htmleditor.deck.lint import Problem, format_report

    def err(slide: str | None = None) -> Problem:
        return Problem("L002", "error", None if slide is None else 0, slide, "m")

    def warn() -> Problem:
        return Problem("L010", "warning", 0, "slide-0", "w")

    assert format_report([]) == [OK]
    assert format_report([err()]) == ["error L002 - m", "lint: FAIL (1 error, 0 warnings)"]
    assert format_report([err(), err("slide-0"), warn()])[-1] == "lint: FAIL (2 errors, 1 warning)"
    assert format_report([warn(), warn()]) == ["warning L010 slide-0 w"] * 2 + ["lint: OK (0 errors, 2 warnings)"]


def test_deck_lint_ordering(tmp_path: Path) -> None:
    """Whole file first, then slide by slide, then by code."""
    html = inject_html(deck_ei(), 4, "<p>Contenu de la slide</p>")
    html = drop_attr(set_total(html, 7), 4, "data-title")
    html = drop_attr(html, 1, "data-title")
    lines, _, _ = lint(tmp_path, html)
    assert lines[:4] == [
        "error L002 - TOTAL is 7 but the file has 8 slides",
        "error L001 slide-1 missing attribute data-title",
        "error L001 slide-4 missing attribute data-title",
        'error L006 slide-4 template text left: "Contenu de la slide"',
    ]


def test_deck_lint_counter_before_template_text_on_one_slide(tmp_path: Path) -> None:
    """Within a slide L005 comes before L006."""
    html = inject_html(deck_ei(), 2, "<p>Titre de la présentation</p>").replace("Slide 03 / 08", "Slide 04 / 08")
    lines, _, _ = lint(tmp_path, html)
    assert [line.split()[1] for line in lines[:-1]] == ["L005", "L006"]


@pytest.mark.parametrize(
    ("source", "count"),
    [
        ("[\"a\", 'b', `c`]", 3),
        ('["a\\"b", "c]"]', 2),
        ('[["x","y"], "z"]', 2),
        ('["a",\n"b",\n"c",\n]', 3),
        ('["a", "b", "c"]', 3),
        ("[]", 0),
        ('["a", 4 / 2, "b"]', 2),
        ('["a", // "x", "y"\n "b" /* "z" */]', 2),
        ('["it\'s", \'say "hi"\', `a ] b`]', 3),
    ],
)
def test_deck_lint_names_literal_scanner(tmp_path: Path, source: str, count: int) -> None:
    """The literal counter skips escapes, quotes of the three kinds, brackets in strings and nesting."""
    lines, _, _ = lint(tmp_path, names_source(deck_ei(), source))
    assert lines[0] == f"error L003 - slideNames has {count} entries but the file has 8 slides"


def test_deck_lint_names_same_length_is_clean(tmp_path: Path) -> None:
    """Eight literals, in any quoting, are not a problem."""
    source = "[" + ", ".join(['"a"', "'b'", "`c`", '"d]"', '"e\\""', '"f"', '"g"', '"h"']) + "]"
    lines, _, _ = lint(tmp_path, names_source(deck_ei(), source))
    assert lines == [OK]


def test_deck_lint_absent_total_and_names_are_not_problems(tmp_path: Path) -> None:
    """No TOTAL and no slideNames: neither L002 nor L003."""
    html = re.sub(r"const TOTAL = \d+;", "", deck_ei())
    html = re.sub(r"const slideNames = \[.*?\];", "", html, flags=re.S)
    assert "const TOTAL" not in html
    lines, _, _ = lint(tmp_path, html)
    assert lines == [OK]


def test_deck_lint_duplicate_only_for_the_later_slide(tmp_path: Path) -> None:
    """ids slide-0, slide-1, slide-1: the third slide only."""
    html = build_deck("ei", ("A", "B", "C"))
    html = html.replace(
        'id="slide-2" data-type="slide" data-id="slide-2"', 'id="slide-1" data-type="slide" data-id="slide-1"'
    )
    lines, _, _ = lint(tmp_path, html)
    l004 = [line for line in lines if " L004 " in line]
    assert l004 == ['error L004 slide-1 duplicate id "slide-1"']


def test_deck_lint_slide_without_id_is_l001_only(tmp_path: Path) -> None:
    """No data-id and no id: L001 under ``slide-<index>``, no L004."""
    html = deck_ei().replace('id="slide-3" data-type="slide" data-id="slide-3"', 'data-type="slide"')
    lines, _, _ = lint(tmp_path, html)
    assert "error L001 slide-3 missing attribute data-id" in lines
    assert not any(" L004 " in line for line in lines)


def test_deck_lint_id_attribute_is_the_fallback(tmp_path: Path) -> None:
    """A slide with ``id`` but no ``data-id``: L001 for data-id, the id is still compared by L004."""
    html = deck_ei().replace('id="slide-3" data-type="slide" data-id="slide-3"', 'id="slide-9" data-type="slide"')
    lines, _, _ = lint(tmp_path, html)
    assert 'error L004 slide-9 expected id "slide-3" but found "slide-9"' in lines
    assert "error L001 slide-9 missing attribute data-id" in lines


def test_deck_lint_carbon_footer_counter(tmp_path: Path) -> None:
    """L005 Carbon: the footer says ``Slide 5 / 9`` on index 2 of a 9 slide deck."""
    html = build_deck("carbon", tuple(f"T{i}" for i in range(9)))
    html = html.replace("Slide 3 / 9", "Slide 5 / 9")
    lines, _, _ = lint(tmp_path, html)
    assert 'error L005 slide-2 footer counter says "Slide 5 / 9", expected "Slide 3 / 9"' in lines


def test_deck_lint_carbon_ignores_the_ei_page_element(tmp_path: Path) -> None:
    """A Carbon deck is checked on its footer only; an EI deck on its page element only."""
    html = deck_carbon().replace("</article>", '<span class="slide-foot-page">99</span></article>')
    lines, _, _ = lint(tmp_path, html)
    assert not any(" L005 " in line for line in lines)
    ei = deck_ei().replace("</article>", '<span class="slide-footer-right">Slide 9 / 9</span></article>')
    lines, _, _ = lint(tmp_path, ei)
    assert lines == [OK]


def test_deck_lint_absent_counters_are_not_problems(tmp_path: Path) -> None:
    """An eyebrow without pattern, an empty page element and the section slide give no L005."""
    html = (
        deck_ei()
        .replace("Cat · Slide 02 / 08", "Sommaire")
        .replace('<span class="slide-foot-page">4</span>', '<span class="slide-foot-page"></span>')
    )
    lines, _, _ = lint(tmp_path, html)
    assert lines == [OK]


def test_deck_lint_eyebrow_counter_is_rewritten_by_pattern_only(tmp_path: Path) -> None:
    """A wrong total in the eyebrow is reported with the text as written."""
    lines, _, _ = lint(tmp_path, deck_ei().replace("Cat · Slide 04 / 08", "Cat · Slide 4 / 9"))
    assert lines[0] == 'error L005 slide-3 eyebrow counter says "Slide 4 / 9", expected "Slide 04 / 08"'


def test_deck_lint_eyebrow_template_text(tmp_path: Path) -> None:
    """``Section · Slide 01 / 01``: fine on the only slide of a one slide deck, a problem elsewhere."""
    one = build_deck("carbon", ("Seul",))
    assert 'template text left: "Section · Slide 01 / 01"' not in "\n".join(lint(tmp_path, one)[0])
    five = deck_carbon().replace("Section · Slide 01 / 05", "Section · Slide 01 / 01")
    lines, _, _ = lint(tmp_path, five)
    assert 'error L006 slide-0 template text left: "Section · Slide 01 / 01"' in lines
    second = deck_carbon().replace("Section · Slide 02 / 05", "Section · Slide 01 / 01")
    assert 'error L006 slide-1 template text left: "Section · Slide 01 / 01"' in lint(tmp_path, second)[0]


def test_deck_lint_template_title_text(tmp_path: Path) -> None:
    """``Titre de la présentation`` in a slide body, once per slide even if repeated."""
    html = inject_html(deck_ei(), 2, "<p>Titre de la présentation</p><p>Titre de la présentation</p>")
    lines, _, _ = lint(tmp_path, html)
    assert lines.count('error L006 slide-2 template text left: "Titre de la présentation"') == 1


def test_deck_lint_template_text_in_script_style_or_comment_is_ignored(tmp_path: Path) -> None:
    """Scripts, styles and comments are not slide text."""
    fragment = (
        "<script>var a='Contenu de la slide'</script><style>/* Contenu de la slide */</style>"
        "<!-- Contenu de la slide -->"
    )
    lines, _, _ = lint(tmp_path, inject_html(deck_ei(), 4, fragment))
    assert lines == [OK]


def test_deck_lint_template_text_across_whitespace_and_nbsp(tmp_path: Path) -> None:
    """Line breaks or non breaking spaces inside the phrase do not hide it."""
    lines, _, _ = lint(tmp_path, inject_html(deck_ei(), 4, "<p>Contenu de\n  la\u00a0slide</p>"))
    assert 'error L006 slide-4 template text left: "Contenu de la slide"' in lines


def test_deck_lint_json_mode(tmp_path: Path) -> None:
    """``--json`` prints only the compact JSON, ``ensure_ascii`` false."""
    stdout, stderr, code = run_cli("lint", write_deck(tmp_path / "f.html", deck_ei()), "--json")
    assert (stdout, stderr, code) == ('{"problems":[],"errors":0,"warnings":0}\n', "", 0)


def test_deck_lint_json_with_problems_exits_1(tmp_path: Path) -> None:
    """Problems are listed with a null slide for the whole file; exit 1; non ASCII kept."""
    html = set_total(inject_html(deck_ei(), 4, "<p>Titre de la présentation</p>"), 7)
    stdout, _, code = run_cli("lint", write_deck(tmp_path / "f.html", html), "--json")
    assert code == 1
    assert stdout.count("\n") == 1
    assert json.loads(stdout) == {
        "problems": [
            {"code": "L002", "severity": "error", "slide": None, "message": "TOTAL is 7 but the file has 8 slides"},
            {
                "code": "L006",
                "severity": "error",
                "slide": "slide-4",
                "message": 'template text left: "Titre de la présentation"',
            },
        ],
        "errors": 2,
        "warnings": 0,
    }
    assert "présentation" in stdout
    assert ", " not in stdout


def test_deck_lint_file_not_found(tmp_path: Path) -> None:
    """A missing file: message on stderr, empty stdout, exit 1."""
    stdout, stderr, code = run_cli("lint", str(tmp_path / "ghost.html"))
    assert (stdout, stderr, code) == ("", f"error: File not found: {tmp_path / 'ghost.html'}\n", 1)


def test_deck_lint_crlf_deck_is_clean(tmp_path: Path) -> None:
    """A deck saved with CRLF line ends lints like the LF one."""
    path = tmp_path / "crlf.html"
    path.write_bytes(deck_ei().replace("\n", "\r\n").encode("utf-8"))
    stdout, stderr, code = run_cli("lint", str(path))
    assert (stdout, stderr, code) == (OK + "\n", "", 0)


def test_deck_lint_nonpresentations_return_no_problem(tmp_path: Path) -> None:
    """A mail and a website are not presentations: nothing to report here."""
    for key in ("doc-perso",):
        text = (BOOTSTRAP / BOOTSTRAP_FILES[key]).read_text(encoding="utf-8")
        assert lint(tmp_path, set_total(text, 3))[0] == [OK]
    for name in ("mail-empty.html", "website-empty.html"):
        assert lint(tmp_path, (BOOTSTRAP / name).read_text(encoding="utf-8"))[2] == 0


@pytest.mark.parametrize("key", ["ei", "carbon", "medical"])
def test_deck_lint_real_bootstrap_files_never_crash(tmp_path: Path, key: str) -> None:
    """The shipped one slide bootstraps give a report, never a traceback."""
    text = (BOOTSTRAP / BOOTSTRAP_FILES[key]).read_text(encoding="utf-8")
    lines, stderr, code = lint(tmp_path, text)
    assert stderr == ""
    assert lines[-1].startswith("lint: ")
    assert code == (1 if lines[-1].startswith("lint: FAIL") else 0)


def test_deck_lint_warnings_alone_do_not_fail() -> None:
    """Exit status follows errors only: a report with warnings only is OK."""
    from mcp_htmleditor.deck.lint import Problem, format_report

    assert format_report([Problem("L010", "warning", 0, "slide-0", "w")])[-1] == "lint: OK (0 errors, 1 warning)"


def test_deck_lint_file_returns_the_json_form(tmp_path: Path) -> None:
    """``lint_file`` gives the object the tool of a later story returns."""
    from mcp_htmleditor.deck.lint import lint_file

    path = write_deck(tmp_path / "f.html", set_total(deck_ei(), 7))
    assert lint_file(path) == {
        "problems": [
            {"code": "L002", "severity": "error", "slide": None, "message": "TOTAL is 7 but the file has 8 slides"}
        ],
        "errors": 1,
        "warnings": 0,
    }
