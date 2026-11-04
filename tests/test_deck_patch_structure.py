"""Tests for ``insert_slide``, ``move_slide`` and ``replace_slide`` (SPEC-0007 US-0040).

Counters are checked with plain regexes written here, never with product code. Byte exactness is proved
by building the expected file again from the same literal builder (``hand``) with the new order.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from mcp_htmleditor.deck.patch import apply_patch
from mcp_htmleditor.deck.read import get_slide
from mcp_htmleditor.deck.renumber import renumber_edits

from .deck_support import (
    CARBON_TITLES,
    EI_TITLES,
    TINY_PNG,
    build_deck,
    deck_carbon,
    deck_ei,
    doc_perso,
    slide_html,
    write_deck,
)
from .test_deck_patch import assert_untouched, ei_file, failure, patch
from .test_deck_patch_delete import CARBON_FOOTER, EYEBROW, PAGE, TOTAL, carbon_file, run_ok

SLIDE_TAG = re.compile(r'<article\b[^>]*\bdata-type="slide"[^>]*>')
ATTRIBUTE = re.compile(r'([\w-]+)="([^"]*)"')
H1 = re.compile(r'<h1 class="slide-h1" data-editable="text">(.*?)</h1>', re.S)
SHAPE_REASON = 'slide html must have data-type="slide" and a data-id'
BIG = "A" * 1500
OK_NINE = '{"ok":true,"changed":true,"slides":9,"problems":[]}\n'


def slide_tags(text: str) -> list[dict[str, str]]:
    """Return the attributes of every slide start tag, in file order."""
    return [dict(ATTRIBUTE.findall(tag)) for tag in SLIDE_TAG.findall(text)]


def names_of(text: str) -> list[str]:
    """Return the raw entries of the ``slideNames`` list, one per line."""
    block = text[text.index("const slideNames = [") : text.index("];", text.index("const slideNames"))]
    return re.findall(r'^\s+(".*"),\s*$', block, flags=re.M)


def read(path: str) -> str:
    """Return the file text without newline translation."""
    return Path(path).read_bytes().decode("utf-8")


def eyebrows(text: str) -> list[str]:
    """Return the eyebrow texts."""
    return EYEBROW.findall(text)


# hand built deck: indentation of 4 spaces, an HTML comment between the second and the third slide

HEAD = (
    '<!DOCTYPE html>\n<html lang="en" data-doc-type="presentation">\n'
    '<head><meta charset="utf-8"><title>t</title></head>\n<body>\n  <div class="slide-frame">'
)
COMMENT = "<!-- between -->"


def hand_slide(index: int, title: str) -> str:
    """Return one slide of the hand built deck, with its leading line break and indentation."""
    active = " active" if index == 0 else ""
    return (
        f'\n    <article class="slide{active}" id="slide-{index}" data-type="slide" data-id="slide-{index}"'
        f' data-title="{title}">\n      <h1 class="slide-h1">{title}</h1>\n    </article>'
    )


def hand(items: list[str], eol: str = "\n") -> str:
    """Return the hand built deck: ``items`` are slide titles or the comment, ids and counters consistent."""
    titles = [item for item in items if item != COMMENT]
    body, number = "", 0
    for item in items:
        if item == COMMENT:
            body += f"\n    {item}"
        else:
            body += hand_slide(number, item)
            number += 1
    names = "".join(f'    "{title}",\n' for title in titles)
    tail = (
        f"\n  </div>\n  <script>\n  const TOTAL = {len(titles)};\n  const slideNames = [\n{names}  ];\n  </script>\n"
        "</body>\n</html>\n"
    )
    return (HEAD + body + tail).replace("\n", eol)


def hand_html(title: str, eol: str = "\n") -> str:
    """Return the slide an agent would insert in the hand built deck (id ``x``, to be renumbered)."""
    text = (
        f'<article class="slide" id="x" data-type="slide" data-id="x" data-title="{title}">\n'
        f'      <h1 class="slide-h1">{title}</h1>\n    </article>'
    )
    return text.replace("\n", eol)


HAND = ["A", "B", COMMENT, "C"]


def test_deck_patch_structure_hand_built_deck_is_consistent() -> None:
    """The builder yields a deck the renumbering pass leaves alone, so equality below proves exactness."""
    assert renumber_edits(hand(HAND)) == []
    assert renumber_edits(hand(["Été", "A", "B", COMMENT, "C"], "\r\n")) == []


# E2E-005


def test_deck_patch_structure_insert_in_the_middle_renumbers_everything(tmp_path: Path) -> None:
    """E2E-005: Budget after slide-4 of DECK-EI."""
    path, _ = ei_file(tmp_path)
    ops = [{"op": "insert_slide", "after": "slide-4", "html": slide_html("ei", "Budget")}]
    assert patch(path, ops) == (OK_NINE, "", 0)
    text = read(path)
    tags = slide_tags(text)
    assert len(tags) == 9
    assert (tags[5]["id"], tags[5]["data-id"], tags[5]["data-title"]) == ("slide-5", "slide-5", "Budget")
    assert [t["id"] for t in tags] == [f"slide-{i}" for i in range(9)]
    assert [t["data-id"] for t in tags] == [f"slide-{i}" for i in range(9)]
    assert [t["data-title"] for t in tags] == [*EI_TITLES[:5], "Budget", *EI_TITLES[5:]]
    expected = [f"Cat · Slide 0{n} / 09" for n in range(2, 6)] + ["Slide 06 / 09"]
    assert eyebrows(text) == expected + [f"Cat · Slide 0{n} / 09" for n in (7, 8)]
    assert PAGE.findall(text) == ["2", "3", "4", "5", "6", "7", "8"]  # Budget 6, Planning 7
    assert TOTAL.findall(text) == ["9"]
    names = names_of(text)
    assert len(names) == 9 and names[5] == '"Budget"' and names[6] == '"Planning"'
    assert tags[0]["class"] == "slide active" and "active" not in tags[5]["class"]


def test_deck_patch_structure_insert_dry_run_writes_nothing(tmp_path: Path) -> None:
    """A dry run reports the nine slides and writes nothing; ``apply_patch`` reports nine as well."""
    path, before = ei_file(tmp_path)
    ops = [{"op": "insert_slide", "after": "slide-4", "html": slide_html("ei", "Budget")}]
    result = patch(path, ops, "--dry-run")
    assert result == ('{"ok":true,"changed":true,"slides":9,"problems":[],"dry_run":true}\n', "", 0)
    assert_untouched(path, before)
    assert apply_patch(path, ops)["slides"] == 9


# E2E-007


def test_deck_patch_structure_move_carbon_slide(tmp_path: Path) -> None:
    """E2E-007: slide-4 after slide-0."""
    path, _ = carbon_file(tmp_path)
    text = run_ok(path, [{"op": "move_slide", "id": "slide-4", "after": "slide-0"}])
    tags = slide_tags(text)
    assert [t["data-title"] for t in tags] == ["Intro", "Fin", "Offre", "Chiffres", "Plan"]
    assert [t["id"] for t in tags] == [f"slide-{i}" for i in range(5)]
    assert [t["data-id"] for t in tags] == [f"slide-{i}" for i in range(5)]
    assert CARBON_FOOTER.findall(text) == [f"Slide {n} / 5" for n in range(1, 6)]
    assert eyebrows(text) == [f"Section · Slide 0{n} / 05" for n in range(1, 6)]
    assert names_of(text) == ['"Intro"', '"Fin"', '"Offre"', '"Chiffres"', '"Plan"']
    assert tags[0]["class"] == "slide active"


# E2E-008


def test_deck_patch_structure_replace_round_trip_keeps_the_image(tmp_path: Path) -> None:
    """E2E-008: get-slide output with a new title; the file differs from the original by the title only."""
    path, _ = ei_file(tmp_path)
    original = read(path)
    html = get_slide(path, "slide-3")
    assert "data:ref:img-1" in html and BIG not in html
    assert original.count(">Besoins</h1>") == 1
    edited = html.replace(">Besoins</h1>", ">Architecture cible</h1>")
    assert patch(path, [{"op": "replace_slide", "id": "slide-3", "html": edited}]) == (
        '{"ok":true,"changed":true,"slides":8,"problems":[]}\n',
        "",
        0,
    )
    text = read(path)
    assert text == original.replace(">Besoins</h1>", ">Architecture cible</h1>")
    assert text.count(f"data:image/png;base64,{BIG}") == 1


# E2E-014


def test_deck_patch_structure_mixed_operations_are_atomic(tmp_path: Path) -> None:
    """E2E-014: the second operation fails on an unknown id, nothing is written."""
    path, before = carbon_file(tmp_path)
    ops = [{"op": "delete_slide", "id": "slide-1"}, {"op": "move_slide", "id": "slide-2", "after": "slide-7"}]
    assert patch(path, ops) == ("", failure(2, 'unknown slide id "slide-7"'), 1)
    assert_untouched(path, before)


# E2E-017


@pytest.mark.parametrize("operation", ["replace_slide", "insert_slide"])
def test_deck_patch_structure_html_without_required_attributes(tmp_path: Path, operation: str) -> None:
    """E2E-017: ``<article><h1>x</h1></article>`` is refused by both operations."""
    path, before = ei_file(tmp_path)
    key = "id" if operation == "replace_slide" else "after"
    ops = [{"op": operation, key: "slide-2", "html": "<article><h1>x</h1></article>"}]
    assert patch(path, ops) == ("", failure(1, SHAPE_REASON), 1)
    assert_untouched(path, before)


@pytest.mark.parametrize(
    "html",
    [
        '<article data-type="slide"><h1>x</h1></article>',
        '<article data-type="slide" data-id=""></article>',
        '<article data-type="page" data-id="x"></article>',
        '<article data-id="x"></article>',
        "",
        "   \n",
        "just text",
        "<!-- only a comment -->",
        '<article data-type="slide" data-id="a"></article><article data-type="slide" data-id="b"></article>',
        'x<article data-type="slide" data-id="a"></article>',
        '<article data-type="slide" data-id="a"></article> tail',
        '<article data-type="slide" data-id="a"></article><!-- c --><p>y</p>',
        '<p><article data-type="slide" data-id="a"></article></p>',
        '<article data-type="slide" data-id="x" data-title="U"><p>hi',
        '<article data-type="slide" data-id="x" data-title="U"><p>hi</p>\n',
        '<article data-type="slide" data-id="x" data-title="U"></article></div>',
        '<article data-type="slide" data-id="x"></article><!-- open',
    ],
)
def test_deck_patch_structure_html_shape_is_checked(tmp_path: Path, html: str) -> None:
    """Zero or several top level elements, text around it, a missing or empty attribute: all refused."""
    path, before = ei_file(tmp_path)
    for ops in (
        [{"op": "replace_slide", "id": "slide-2", "html": html}],
        [{"op": "insert_slide", "after": "start", "html": html}],
    ):
        assert patch(path, ops) == ("", failure(1, SHAPE_REASON), 1)
    assert_untouched(path, before)


def test_deck_patch_structure_html_ignores_whitespace_and_comments_around_the_element(tmp_path: Path) -> None:
    """Comments and whitespace around the single element are accepted and written as given."""
    path, _ = ei_file(tmp_path)
    html = '\n<!-- c -->\n<article data-type="slide" data-id="v" data-title="V">v</article>\n<!-- d -->  \n'
    text = run_ok(path, [{"op": "insert_slide", "after": "slide-1", "html": html}])
    assert "\n<!-- c -->\n<article " in text and ">v</article>\n<!-- d -->  \n" in text
    assert [t["data-id"] for t in slide_tags(text)] == [f"slide-{i}" for i in range(9)]


def test_deck_patch_structure_html_accepts_nested_elements_single_quotes_and_a_trailing_comment(tmp_path: Path) -> None:
    """A closed element with children and single quoted attributes stays valid with comments after it."""
    path, _ = ei_file(tmp_path)
    html = "<article data-type='slide' data-id='v' data-title='V'><div><p>v</p></div></article><!-- d -->\n"
    text = run_ok(path, [{"op": "insert_slide", "after": "slide-1", "html": html}])
    assert "<div><p>v</p></div></article><!-- d -->\n" in text


# E2E-018


def test_deck_patch_structure_unknown_image_reference(tmp_path: Path) -> None:
    """E2E-018: slide-3 has one large image; the token 3 does not exist, an insert allows no token."""
    path, before = ei_file(tmp_path)
    replace = [
        {"op": "replace_slide", "id": "slide-3", "html": slide_html("ei", "T", extra='<img src="data:ref:img-3">')}
    ]
    assert patch(path, replace) == ("", failure(1, 'unknown image reference "data:ref:img-3"'), 1)
    insert = [
        {"op": "insert_slide", "after": "slide-2", "html": slide_html("ei", "T", extra='<img src="data:ref:img-1">')}
    ]
    assert patch(path, insert) == ("", failure(1, 'unknown image reference "data:ref:img-1"'), 1)
    assert_untouched(path, before)


@pytest.mark.parametrize("token", ["data:ref:img-0", "data:ref:img-007", "data:ref:img-2", "data:ref:img-99999999999"])
def test_deck_patch_structure_image_reference_names_the_token_as_written(tmp_path: Path, token: str) -> None:
    """N = 0 and N beyond the count are refused, the reason repeats the token as written."""
    path, before = ei_file(tmp_path)
    html = slide_html("ei", "T", extra=f'<img src="data:ref:img-1"><img src="{token}">')
    ops = [{"op": "replace_slide", "id": "slide-3", "html": html}]
    assert patch(path, ops) == ("", failure(1, f'unknown image reference "{token}"'), 1)
    assert_untouched(path, before)


def test_deck_patch_structure_insert_names_the_first_token_found(tmp_path: Path) -> None:
    """Whatever N, an insert refuses the first token of the html."""
    path, before = ei_file(tmp_path)
    html = slide_html("ei", "T", extra='<img src="data:ref:img-2"><img src="data:ref:img-1">')
    ops = [{"op": "insert_slide", "after": "start", "html": html}]
    assert patch(path, ops) == ("", failure(1, 'unknown image reference "data:ref:img-2"'), 1)
    assert_untouched(path, before)


@pytest.mark.parametrize(
    ("ops", "reason"),
    [
        (
            [{"op": "replace_slide", "id": "slide-9", "html": "<p>x</p>"}],
            'unknown slide id "slide-9"',
        ),
        (
            [{"op": "replace_slide", "id": "slide-3", "html": "<p>data:ref:img-1</p>"}],
            SHAPE_REASON,
        ),
        (
            [{"op": "insert_slide", "after": "slide-9", "html": "<p>data:ref:img-1</p>"}],
            'unknown slide id "slide-9"',
        ),
        (
            [{"op": "insert_slide", "after": "slide-1", "html": "<p>data:ref:img-1</p>"}],
            SHAPE_REASON,
        ),
        (
            [{"op": "move_slide", "id": "slide-9", "after": "slide-8"}],
            'unknown slide id "slide-9"',
        ),
        (
            [{"op": "move_slide", "id": "slide-1", "after": "slide-8"}],
            'unknown slide id "slide-8"',
        ),
    ],
)
def test_deck_patch_structure_checks_run_in_the_listed_order(
    tmp_path: Path, ops: list[dict[str, str]], reason: str
) -> None:
    """Unknown id, then html shape, then image reference; ``id`` before ``after``."""
    path, before = ei_file(tmp_path)
    assert patch(path, ops) == ("", failure(1, reason), 1)
    assert_untouched(path, before)


def test_deck_patch_structure_field_errors_come_before_semantics(tmp_path: Path) -> None:
    """A missing or non string field is a shape error of the operation."""
    path, before = ei_file(tmp_path)
    assert patch(path, [{"op": "insert_slide", "after": "slide-1"}]) == ("", failure(1, 'missing field "html"'), 1)
    assert patch(path, [{"op": "replace_slide", "id": "slide-1", "html": 3}]) == (
        "",
        failure(1, 'field "html" must be a string'),
        1,
    )
    assert patch(path, [{"op": "move_slide", "id": "slide-1", "after": None}]) == (
        "",
        failure(1, 'field "after" must be a string'),
        1,
    )
    assert_untouched(path, before)


# E2E-029


def test_deck_patch_structure_insert_at_start(tmp_path: Path) -> None:
    """E2E-029: a new first slide; accented title."""
    path, _ = carbon_file(tmp_path)
    text = run_ok(path, [{"op": "insert_slide", "after": "start", "html": slide_html("carbon", "Début")}])
    tags = slide_tags(text)
    assert [t["data-title"] for t in tags][:2] == ["Début", "Intro"]
    assert CARBON_FOOTER.findall(text)[:2] == ["Slide 1 / 6", "Slide 2 / 6"]
    assert tags[0]["class"] == "slide active" and tags[1]["class"] == "slide"
    assert names_of(text)[:2] == ['"Début"', '"Intro"']


def test_deck_patch_structure_insert_at_the_end(tmp_path: Path) -> None:
    """E2E-029: after the last slide."""
    path, _ = carbon_file(tmp_path)
    text = run_ok(path, [{"op": "insert_slide", "after": "slide-4", "html": slide_html("carbon", "Fin 2")}])
    assert [t["data-title"] for t in slide_tags(text)][-2:] == ["Fin", "Fin 2"]
    assert CARBON_FOOTER.findall(text)[-1] == "Slide 6 / 6"


def test_deck_patch_structure_move_to_start(tmp_path: Path) -> None:
    """E2E-029: moving slide-2 first."""
    path, _ = carbon_file(tmp_path)
    text = run_ok(path, [{"op": "move_slide", "id": "slide-2", "after": "start"}])
    assert [t["data-title"] for t in slide_tags(text)] == ["Chiffres", "Intro", "Offre", "Plan", "Fin"]
    assert slide_tags(text)[0]["class"] == "slide active"
    assert CARBON_FOOTER.findall(text) == [f"Slide {n} / 5" for n in range(1, 6)]


# E2E-030


def test_deck_patch_structure_special_characters_in_a_title(tmp_path: Path) -> None:
    """E2E-030: the attribute stays as written, the names list holds the decoded and escaped title."""
    path, _ = ei_file(tmp_path)
    attribute = "Café &amp; &quot;Co&quot; &lt;1&gt;"
    html = slide_html("ei", "Café", data_title=attribute)
    text = run_ok(path, [{"op": "insert_slide", "after": "slide-1", "html": html}])
    assert f'data-title="{attribute}"' in text
    assert '    "Café & \\"Co\\" <1>",\n' in text
    tags = slide_tags(text)
    assert len(tags) == 9
    assert all(t.get("data-type") == "slide" and t.get("data-id") and t.get("data-title") for t in tags)
    assert [t["id"] for t in tags] == [f"slide-{i}" for i in range(9)]
    assert [t["data-id"] for t in tags] == [f"slide-{i}" for i in range(9)]
    assert TOTAL.findall(text) == ["9"]
    assert len(names_of(text)) == 9
    expected = [("" if index == 2 else "Cat · ") + f"Slide {index + 1:02d} / 09" for index in range(1, 8)]
    assert eyebrows(text) == expected
    assert PAGE.findall(text) == [str(index + 1) for index in range(1, 8)]


# byte splice


@pytest.mark.parametrize("eol", ["\n", "\r\n"])
@pytest.mark.parametrize(
    ("op", "order"),
    [
        ({"op": "insert_slide", "after": "slide-0"}, ["A", "Été", "B", COMMENT, "C"]),
        ({"op": "insert_slide", "after": "slide-1"}, ["A", "B", "Été", COMMENT, "C"]),
        ({"op": "insert_slide", "after": "slide-2"}, ["A", "B", COMMENT, "C", "Été"]),
        ({"op": "insert_slide", "after": "start"}, ["Été", "A", "B", COMMENT, "C"]),
        ({"op": "move_slide", "id": "slide-2", "after": "slide-0"}, ["A", "C", "B", COMMENT]),
        ({"op": "move_slide", "id": "slide-0", "after": "slide-2"}, ["B", COMMENT, "C", "A"]),
        ({"op": "move_slide", "id": "slide-1", "after": "slide-2"}, ["A", COMMENT, "C", "B"]),
        ({"op": "move_slide", "id": "slide-2", "after": "start"}, ["C", "A", "B", COMMENT]),
        ({"op": "move_slide", "id": "slide-1", "after": "slide-0"}, HAND),
    ],
)
def test_deck_patch_structure_byte_splice(tmp_path: Path, eol: str, op: dict[str, str], order: list[str]) -> None:
    """Indentation, comment position and line ends come out exactly as the literal builder writes them."""
    path = write_deck(tmp_path / "hand.html", hand(HAND, eol))
    operation: dict[str, Any] = dict(op)
    if op["op"] == "insert_slide":
        operation["html"] = hand_html("Été", eol)
    assert patch(path, [operation])[1:] == ("", 0)
    assert read(path) == hand(order, eol)


def test_deck_patch_structure_insert_writes_the_line_break_and_indentation_of_the_reference(tmp_path: Path) -> None:
    """After slide 0: ``</article>`` newline, 4 spaces, the new slide; the comment stays after slide 1."""
    path = write_deck(tmp_path / "hand.html", hand(HAND))
    run_ok(path, [{"op": "insert_slide", "after": "slide-0", "html": hand_html("N")}])
    text = read(path)
    assert '    </article>\n    <article class="slide" id="slide-1"' in text
    assert text.index(COMMENT) > text.index('data-title="B"') and text.index(COMMENT) < text.index('data-title="C"')


def test_deck_patch_structure_insert_at_start_has_no_blank_line(tmp_path: Path) -> None:
    """One line break between the new slide and the old first one, the first one's indentation."""
    path = write_deck(tmp_path / "hand.html", hand(HAND))
    run_ok(path, [{"op": "insert_slide", "after": "start", "html": hand_html("N")}])
    text = read(path)
    assert '<div class="slide-frame">\n    <article class="slide active" id="slide-0"' in text
    assert "    </article>\n    <article" in text and "\n\n" not in text


def test_deck_patch_structure_move_keeps_the_indentation_of_the_moved_slide(tmp_path: Path) -> None:
    """The moved range carries its own leading whitespace; insert uses the reference's."""
    c_line = '\n    <article class="slide" id="slide-{i}" data-type="slide" data-id="slide-{i}" data-title="C"'
    tabbed = '\n\t<article class="slide" id="slide-{i}" data-type="slide" data-id="slide-{i}" data-title="C"'
    source = hand(HAND).replace(c_line.format(i=2), tabbed.format(i=2))
    path = write_deck(tmp_path / "hand.html", source)
    run_ok(path, [{"op": "move_slide", "id": "slide-2", "after": "slide-0"}])
    assert read(path) == hand(["A", "C", "B", COMMENT]).replace(c_line.format(i=1), tabbed.format(i=1))


def test_deck_patch_structure_insert_in_a_crlf_deck_is_crlf_only(tmp_path: Path) -> None:
    """A real fixture with CRLF line ends: no bare line feed is introduced anywhere."""
    path = write_deck(tmp_path / "ei.html", deck_ei().replace("\n", "\r\n"))
    html = slide_html("ei", "Budget").replace("\n", "\r\n")
    assert patch(path, [{"op": "insert_slide", "after": "slide-4", "html": html}])[1:] == ("", 0)
    text = read(path)
    assert re.search(r"(?<!\r)\n", text) is None
    assert len(slide_tags(text)) == 9 and '    "Budget",\r\n' in text


def test_deck_patch_structure_insert_at_start_of_an_inline_slide(tmp_path: Path) -> None:
    """A first slide with no line break before it: the new slide takes that (empty) leading text."""
    old = '<article class="slide active" id="slide-0" data-type="slide" data-id="slide-0" data-title="A">a</article>'
    new = '<article class="slide" id="x" data-type="slide" data-id="x" data-title="N">n</article>'
    page = '<html data-doc-type="presentation"><body><div>{}</div></body></html>'
    path = write_deck(tmp_path / "inline.html", page.format(old))
    run_ok(path, [{"op": "insert_slide", "after": "start", "html": new}])
    old_after = old.replace("slide active", "slide").replace("slide-0", "slide-1")
    new_after = new.replace('"x"', '"slide-0"').replace('class="slide"', 'class="slide active"')
    assert read(path) == page.format(new_after + "\n" + old_after)


# operations on ids


def test_deck_patch_structure_move_after_itself_changes_nothing(tmp_path: Path) -> None:
    """``after`` equal to the moved slide: nothing changes, file and time untouched."""
    path, before = ei_file(tmp_path)
    ops = [{"op": "move_slide", "id": "slide-3", "after": "slide-3"}]
    assert patch(path, ops) == ('{"ok":true,"changed":false,"slides":8,"problems":[]}\n', "", 0)
    assert_untouched(path, before)


def test_deck_patch_structure_move_first_slide_to_start_changes_nothing(tmp_path: Path) -> None:
    """The first slide moved to the start stays where it is."""
    path, before = ei_file(tmp_path)
    assert patch(path, [{"op": "move_slide", "id": "slide-0", "after": "start"}])[1:] == ("", 0)
    assert_untouched(path, before)


def test_deck_patch_structure_delete_then_replace_is_unknown(tmp_path: Path) -> None:
    """A slide deleted earlier in the patch cannot be designated."""
    path, before = ei_file(tmp_path)
    ops = [{"op": "delete_slide", "id": "slide-1"}, {"op": "replace_slide", "id": "slide-1", "html": "<p>x</p>"}]
    assert patch(path, ops) == ("", failure(2, 'unknown slide id "slide-1"'), 1)
    ops = [{"op": "delete_slide", "id": "slide-1"}, {"op": "insert_slide", "after": "slide-1", "html": "<p>x</p>"}]
    assert patch(path, ops) == ("", failure(2, 'unknown slide id "slide-1"'), 1)
    ops = [{"op": "delete_slide", "id": "slide-1"}, {"op": "move_slide", "id": "slide-2", "after": "slide-1"}]
    assert patch(path, ops) == ("", failure(2, 'unknown slide id "slide-1"'), 1)
    assert_untouched(path, before)


def test_deck_patch_structure_moved_slide_is_still_designated_by_its_original_id(tmp_path: Path) -> None:
    """After moving slide-4 to index 1, ``set_text`` on slide-4 edits ``Fin``, not the slide now at index 4."""
    path, _ = carbon_file(tmp_path)
    ops = [
        {"op": "move_slide", "id": "slide-4", "after": "slide-0"},
        {"op": "set_text", "id": "slide-4", "selector": ".slide-h1", "text": "Final"},
    ]
    text = run_ok(path, ops)
    assert [t["data-title"] for t in slide_tags(text)] == ["Intro", "Fin", "Offre", "Chiffres", "Plan"]
    assert H1.findall(text) == [
        "<strong>Intro</strong>",
        "Final",
        "<strong>Offre</strong>",
        "<strong>Chiffres</strong>",
        "<strong>Plan</strong>",
    ]


def test_deck_patch_structure_replaced_and_inserted_slides_chain(tmp_path: Path) -> None:
    """A replaced slide keeps its original id for later operations; an inserted one cannot be designated."""
    path, _ = ei_file(tmp_path)
    ops = [
        {"op": "replace_slide", "id": "slide-2", "html": slide_html("ei", "Neuf")},
        {"op": "move_slide", "id": "slide-2", "after": "slide-6"},
        {"op": "set_text", "id": "slide-2", "selector": ".slide-h1", "text": "Neuf bis"},
    ]
    text = run_ok(path, ops)
    titles = [t["data-title"] for t in slide_tags(text)]
    assert titles == ["Couverture", "Sommaire", "Besoins", "Architecture", "Planning", "Risques", "Neuf", "Merci"]
    assert "Neuf bis" in H1.findall(text)
    assert patch(
        path,
        [
            {"op": "insert_slide", "after": "slide-1", "html": slide_html("ei", "Z")},
            {"op": "move_slide", "id": "x", "after": "slide-0"},
        ],
    )[1] == failure(2, 'unknown slide id "x"')


# images


def test_deck_patch_structure_replace_restores_every_reference(tmp_path: Path) -> None:
    """Two references to the same image are both restored."""
    path, _ = ei_file(tmp_path)
    extra = '<img src="data:ref:img-1" alt="a"><img src="data:ref:img-1" alt="b">'
    text = run_ok(path, [{"op": "replace_slide", "id": "slide-3", "html": slide_html("ei", "Dos", extra=extra)}])
    assert text.count(f'src="data:image/png;base64,{BIG}"') == 2
    assert "data:ref:" not in text


def test_deck_patch_structure_replace_restores_by_order_and_skips_small_images(tmp_path: Path) -> None:
    """Token N is the Nth large image; a small one is not counted; the order can be swapped."""

    def add_images(text: str) -> str:
        small = f'<img src="data:image/png;base64,{TINY_PNG}" alt="t">'
        second = f'<img src="data:image/png;base64,{"B" * 1200}" alt="b2">'
        return text.replace('alt="big">', f'alt="big">{second}', 1).replace(
            "<p>Texte de Besoins.</p>", f"<p>Texte de Besoins.</p>{small}", 1
        )

    path = write_deck(
        tmp_path / "two.html", build_deck("ei", EI_TITLES, image_chars=1500, image_slide=3, mutate=add_images)
    )
    assert "B" * 1200 in read(path)
    html = slide_html("ei", "Swap", extra='<img src="data:ref:img-2"><img src="data:ref:img-1">')
    text = run_ok(path, [{"op": "replace_slide", "id": "slide-3", "html": html}])
    assert text.index("B" * 1200) < text.index(BIG)
    assert "data:ref:" not in text


def test_deck_patch_structure_replace_reads_the_current_text_of_the_working_copy(tmp_path: Path) -> None:
    """A second replace of the same slide still finds the image the first one restored."""
    path, _ = ei_file(tmp_path)
    one = slide_html("ei", "Un", extra='<img src="data:ref:img-1">')
    two = slide_html("ei", "Deux", extra='<img src="data:ref:img-1">')
    text = run_ok(
        path,
        [{"op": "replace_slide", "id": "slide-3", "html": one}, {"op": "replace_slide", "id": "slide-3", "html": two}],
    )
    assert text.count(BIG) == 1 and "Deux" in text


def test_deck_patch_structure_replace_without_image_removes_it(tmp_path: Path) -> None:
    """A replacement with no reference drops the large image and raises no error."""
    path, _ = ei_file(tmp_path)
    text = run_ok(path, [{"op": "replace_slide", "id": "slide-3", "html": slide_html("ei", "Sans image")}])
    assert BIG not in text and "Sans image" in text


def test_deck_patch_structure_insert_has_no_image_restore_even_for_a_plain_data_address(tmp_path: Path) -> None:
    """A real image handed to ``insert_slide`` is written as is."""
    path, _ = ei_file(tmp_path)
    extra = f'<img src="data:image/png;base64,{TINY_PNG}">'
    text = run_ok(path, [{"op": "insert_slide", "after": "slide-0", "html": slide_html("ei", "Img", extra=extra)}])
    assert text.count(f'src="data:image/png;base64,{TINY_PNG}"') == 1 + deck_ei().count(
        f'src="data:image/png;base64,{TINY_PNG}"'
    )


# idempotence


@pytest.mark.parametrize(
    ("maker", "slide"),
    [(deck_ei, "slide-3"), (deck_ei, "slide-2"), (deck_ei, "slide-7"), (deck_carbon, "slide-2")],
)
def test_deck_patch_structure_get_slide_then_replace_changes_nothing(tmp_path: Path, maker: Any, slide: str) -> None:
    """A consistent file, a slide read and written back: ``changed`` false, bytes and time untouched."""
    path = write_deck(tmp_path / "d.html", maker())
    before = Path(path).read_bytes()
    html = get_slide(path, slide)
    ops = [{"op": "replace_slide", "id": slide, "html": html}]
    assert json.loads(patch(path, ops)[0])["changed"] is False
    assert_untouched(path, before)


def test_deck_patch_structure_second_application_is_a_no_op(tmp_path: Path) -> None:
    """The same structural patch applied twice through ``apply_patch``: the second one changes nothing."""
    path, _ = ei_file(tmp_path)
    html = get_slide(path, "slide-3").replace(">Besoins</h1>", ">Cible</h1>")
    ops = [
        {"op": "replace_slide", "id": "slide-3", "html": html},
        {"op": "move_slide", "id": "slide-3", "after": "slide-3"},
    ]
    assert apply_patch(path, ops)["changed"] is True
    after = Path(path).read_bytes()
    assert apply_patch(path, ops)["changed"] is False
    assert Path(path).read_bytes() == after


# documents


@pytest.mark.parametrize(
    "operation",
    [
        {"op": "set_text", "id": "a", "selector": "h1", "text": "x"},
        {"op": "replace_slide", "id": "a", "html": "<p>x</p>"},
        {"op": "insert_slide", "after": "start", "html": "<p>x</p>"},
        {"op": "delete_slide", "id": "a"},
        {"op": "move_slide", "id": "a", "after": "start"},
    ],
)
def test_deck_patch_structure_a_document_needs_a_presentation(tmp_path: Path, operation: dict[str, str]) -> None:
    """The five operations on a file with no slide give the presentation reason, before any semantic check."""
    path = write_deck(tmp_path / "doc.html", doc_perso())
    before = Path(path).read_bytes()
    reason = f'operation "{operation["op"]}" needs a presentation'
    assert patch(path, [operation]) == ("", failure(1, reason), 1)
    assert_untouched(path, before)


def test_deck_patch_structure_fixtures_are_the_expected_ones() -> None:
    """Guard of the shared fixtures this file relies on."""
    assert len(CARBON_TITLES) == 5 and len(EI_TITLES) == 8 and BIG in deck_ei()
