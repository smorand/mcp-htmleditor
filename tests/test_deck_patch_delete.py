"""Tests for ``delete_slide``, the renumbering pass and the dry run (SPEC-0007 US-0039).

Counters are checked with plain regexes written here, never with product code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from mcp_htmleditor.deck import DeckError
from mcp_htmleditor.deck.patch import apply_patch
from mcp_htmleditor.deck.renumber import renumber_edits

from .deck_support import (
    build_deck,
    deck_carbon,
    deck_ei,
    deck_med,
    doc_perso,
    run_cli,
    write_deck,
)
from .test_deck_patch import assert_untouched, ei_file, failure, patch

DELETE_1 = {"op": "delete_slide", "id": "slide-1"}
SLIDE_TAG = re.compile(
    r'<article class="([^"]*)" id="([^"]*)" data-type="slide" data-id="([^"]*)"[^>]*?data-title="([^"]*)">'
)
EYEBROW = re.compile(r'slide-eyebrow" data-editable="text">([^<]*)<')
CARBON_FOOTER = re.compile(r'slide-footer-right">([^<]*)<')
PAGE = re.compile(r'slide-foot-page">([^<]*)<')
TOTAL = re.compile(r"const TOTAL = (\d+);")
NAMES = re.compile(r"const slideNames = \[\n((?:\s+\"[^\"]*\",\n)*)  \];")
OK_DRY = '{"ok":true,"changed":true,"slides":4,"problems":[],"dry_run":true}\n'


def carbon_file(tmp_path: Path, text: str | None = None) -> tuple[str, bytes]:
    """Write DECK-CARBON (or ``text``) with a forced time and return its path and bytes."""
    path = write_deck(tmp_path / "carbon.html", text if text is not None else deck_carbon())
    return path, Path(path).read_bytes()


def run_ok(path: str, ops: list[dict[str, str]]) -> str:
    """Patch through the CLI, assert success and return the file text."""
    out, err, code = patch(path, ops)
    assert (err, code) == ("", 0), err
    assert json.loads(out)["ok"] is True
    return Path(path).read_text(encoding="utf-8")


def slides_of(text: str) -> list[tuple[str, str, str, str]]:
    """Return ``(class, id, data-id, title)`` of every slide tag."""
    return SLIDE_TAG.findall(text)


def mask(text: str) -> str:
    """Hide every counter so two texts can be compared outside them."""
    text = re.sub(r'slide-\d+(?=")', "slide-#", text)
    text = re.sub(r"Slide \d+ / \d+", "Slide # / #", text)
    text = re.sub(r'slide-foot-page">\d+<', 'slide-foot-page">#<', text)
    text = re.sub(r"const TOTAL = \d+;", "const TOTAL = #;", text)
    return re.sub(r"const slideNames = \[.*?\];", "NAMES", text, flags=re.S)


# E2E-006


def test_deck_patch_delete_carbon_renumbers_everything(tmp_path: Path) -> None:
    """E2E-006: 4 slides, ids, footers and eyebrows follow the new positions."""
    path, _ = carbon_file(tmp_path)
    text = run_ok(path, [DELETE_1])
    assert [(s[3]) for s in slides_of(text)] == ["Intro", "Chiffres", "Plan", "Fin"]
    assert [s[1] for s in slides_of(text)] == [f"slide-{i}" for i in range(4)]
    assert [s[2] for s in slides_of(text)] == [f"slide-{i}" for i in range(4)]
    assert CARBON_FOOTER.findall(text) == [f"Slide {n} / 4" for n in range(1, 5)]
    assert EYEBROW.findall(text) == [f"Section · Slide 0{n} / 04" for n in range(1, 5)]
    assert TOTAL.findall(text) == ["4"]


def test_deck_patch_delete_carbon_names_list_layout(tmp_path: Path) -> None:
    """The names list keeps the indentation of the first entry and a trailing comma."""
    path, _ = carbon_file(tmp_path)
    text = run_ok(path, [DELETE_1])
    assert 'const slideNames = [\n    "Intro",\n    "Chiffres",\n    "Plan",\n    "Fin",\n  ];' in text
    assert "slideNames.forEach" in text


def test_deck_patch_delete_ei_renumbers_pages_and_keeps_section(tmp_path: Path) -> None:
    """Euro-Information: page element and eyebrow follow; the section slide gets no page."""
    path, _ = ei_file(tmp_path)
    text = run_ok(path, [DELETE_1])
    tags = slides_of(text)
    assert len(tags) == 7 and tags[1][3] == "Contexte" and tags[1][1] == "slide-1"
    assert EYEBROW.findall(text) == [f"Cat · Slide 0{n} / 07" for n in range(2, 7)]
    assert PAGE.findall(text) == [str(n) for n in range(2, 7)]
    assert TOTAL.findall(text) == ["7"]
    assert len(PAGE.findall(text)) == 5  # slides 1 to 5 carry a foot, the section slide none


def test_deck_patch_delete_medical_renumbers_and_keeps_accents(tmp_path: Path) -> None:
    """Medical: foot page and eyebrow follow; accented titles stay as is."""
    path = write_deck(tmp_path / "med.html", deck_med())
    text = run_ok(path, [{"op": "delete_slide", "id": "slide-2"}])
    assert len(slides_of(text)) == 5
    assert PAGE.findall(text) == ["2", "3", "4", "5"]
    assert EYEBROW.findall(text) == [f"Cat · Slide 0{n} / 05" for n in range(2, 6)]
    assert '    "Résultats",\n' in text and TOTAL.findall(text) == ["5"]


def test_deck_patch_delete_first_slide_moves_active(tmp_path: Path) -> None:
    """Deleting the first slide makes the new first slide the active one."""
    path, _ = carbon_file(tmp_path)
    text = run_ok(path, [{"op": "delete_slide", "id": "slide-0"}])
    assert [s[0] for s in slides_of(text)] == ["slide active", "slide", "slide", "slide"]


def test_deck_patch_delete_active_class_keeps_other_classes(tmp_path: Path) -> None:
    """``active`` ends on the first slide only; another class on a later slide stays."""
    text = deck_carbon().replace(
        '<article class="slide" id="slide-2"', '<article class="slide active extra" id="slide-2"'
    )
    path, _ = carbon_file(tmp_path, text)
    result = run_ok(path, [{"op": "delete_slide", "id": "slide-4"}])
    assert [s[0] for s in slides_of(result)] == ["slide active", "slide", "slide extra", "slide"]


def test_deck_patch_delete_missing_ids_are_added(tmp_path: Path) -> None:
    """A slide with no ``id`` and no ``data-id`` gets both, appended before the ``>``."""
    text = deck_carbon().replace(' id="slide-2" data-type="slide" data-id="slide-2"', ' data-type="slide"')
    path, _ = carbon_file(tmp_path, text)
    result = run_ok(path, [{"op": "delete_slide", "id": "slide-4"}])
    assert '<article class="slide" data-type="slide" data-title="Chiffres" id="slide-2" data-id="slide-2">' in result


def test_deck_patch_delete_escapes_names(tmp_path: Path) -> None:
    """Entities are decoded, then quotes and backslashes are escaped in the names list."""
    text = deck_carbon().replace('data-title="Offre"', 'data-title="A &quot;b&quot; \\ c"')
    path, _ = carbon_file(tmp_path, text)
    result = run_ok(path, [{"op": "delete_slide", "id": "slide-4"}])
    assert '    "A \\"b\\" \\\\ c",\n' in result


def test_deck_patch_delete_creates_no_constant(tmp_path: Path) -> None:
    """A script with no total and no names list gets none."""
    text = re.sub(r"const slideNames = \[.*?\];", "", deck_carbon().replace("const TOTAL = 5;", ""), flags=re.S)
    path, _ = carbon_file(tmp_path, text)
    result = run_ok(path, [DELETE_1])
    assert "const TOTAL" not in result and "const slideNames" not in result
    assert len(slides_of(result)) == 4


def test_deck_patch_delete_keeps_crlf(tmp_path: Path) -> None:
    """A CRLF file keeps CRLF everywhere, including in the rewritten names list."""
    path, _ = carbon_file(tmp_path, deck_carbon().replace("\n", "\r\n"))
    data = Path(path).read_bytes()
    assert run_cli("patch", path, "--ops", "-", input=json.dumps([DELETE_1]))[2] == 0
    result = Path(path).read_bytes()
    assert result != data and b"\n" in result
    assert result.count(b"\n") == result.count(b"\r\n")
    assert TOTAL.findall(result.decode()) == ["4"]
    assert b'  "Chiffres",\r\n' in result


def test_deck_patch_delete_leaves_other_bytes_alone(tmp_path: Path) -> None:
    """Outside the removed slide and the counters, every byte stays, comments included."""
    marker = '</article>\n    <article class="slide" id="slide-2"'
    text = deck_carbon().replace(marker, '</article>\n    <!-- séparateur -->\n    <article class="slide" id="slide-2"')
    path, _ = carbon_file(tmp_path, text)
    result = run_ok(path, [DELETE_1])
    start = text.index('\n    <article class="slide" id="slide-1"')
    end = text.index("</article>", start) + len("</article>")
    assert mask(result) == mask(text[:start] + text[end:])
    assert "<!-- séparateur -->" in result


def test_deck_patch_delete_last_slide_keeps_the_tail(tmp_path: Path) -> None:
    """Deleting the last slide leaves the text that followed it (``</article>`` then ``</div>``) intact."""
    path, before = ei_file(tmp_path)
    text = before.decode()
    result = run_ok(path, [{"op": "delete_slide", "id": "slide-7"}])
    start = text.index('\n    <article class="slide" id="slide-7"')
    end = text.index("</article>", start) + len("</article>")
    assert mask(result) == mask(text[:start] + text[end:])
    assert "</article>\n\n  </div>" in result


def test_deck_patch_delete_set_text_alone_does_not_renumber(tmp_path: Path) -> None:
    """Counters inconsistent on purpose stay so when no structural operation runs."""
    text = deck_carbon().replace("Slide 02 / 05", "Slide 02 / 09")
    path, _ = carbon_file(tmp_path, text)
    result = run_ok(path, [{"op": "set_text", "id": "slide-1", "selector": ".slide-h1", "text": "X"}])
    assert "Slide 02 / 09" in result
    assert result == text.replace('data-editable="text"><strong>Offre</strong>', 'data-editable="text">X')


def test_deck_patch_delete_is_idempotent() -> None:
    """A consistent file yields no edit, before and after a delete."""
    for text in (deck_ei(), deck_carbon(), deck_med()):
        assert renumber_edits(text) == []


def test_deck_patch_delete_then_renumber_is_stable(tmp_path: Path) -> None:
    """The result of a delete is already consistent."""
    path, _ = carbon_file(tmp_path)
    assert renumber_edits(run_ok(path, [DELETE_1])) == []


def test_deck_patch_delete_engine_finds_edits_in_an_inconsistent_file(tmp_path: Path) -> None:
    """The renumbering engine finds edits in an inconsistent file."""
    assert renumber_edits(deck_carbon().replace("Slide 02 / 05", "Slide 02 / 09")) != []


# E2E-013


def test_deck_patch_delete_unknown_id_writes_nothing(tmp_path: Path) -> None:
    """E2E-013: the second operation fails, the file is untouched, also in a dry run."""
    path, before = ei_file(tmp_path)
    ops = [
        {"op": "set_text", "id": "slide-1", "selector": ".slide-h1", "text": "A"},
        {"op": "delete_slide", "id": "slide-9"},
    ]
    reason = 'unknown slide id "slide-9"'
    assert patch(path, ops) == ("", failure(2, reason), 1)
    assert_untouched(path, before)
    assert patch(path, ops, "--dry-run") == ("", failure(2, reason), 1)
    assert_untouched(path, before)
    for dry_run in (False, True):
        with pytest.raises(
            DeckError, match=r'^patch failed at operation 2: unknown slide id "slide-9" \(nothing written\)$'
        ):
            apply_patch(path, ops, dry_run=dry_run)
    nope = [{"op": "set_text", "id": "slide-1", "selector": ".nope", "text": "A"}]
    assert patch(path, nope)[1] == failure(1, 'selector ".nope" matches no element in slide "slide-1"')
    assert_untouched(path, before)


def test_deck_patch_delete_twice_the_same_id_fails(tmp_path: Path) -> None:
    """The second delete of the same id reports an unknown id and nothing is written."""
    path, before = carbon_file(tmp_path)
    assert patch(path, [DELETE_1, DELETE_1]) == ("", failure(2, 'unknown slide id "slide-1"'), 1)
    assert_untouched(path, before)


def test_deck_patch_delete_needs_a_presentation(tmp_path: Path) -> None:
    """A document has no slides: the operation is refused before any other check."""
    path, before = carbon_file(tmp_path, doc_perso())
    assert patch(path, [DELETE_1])[1] == failure(1, 'operation "delete_slide" needs a presentation')
    assert_untouched(path, before)


# E2E-019


def test_deck_patch_delete_last_slide_is_protected(tmp_path: Path) -> None:
    """E2E-019: a one slide deck cannot lose its slide."""
    path, before = carbon_file(tmp_path, build_deck("carbon", ("Seul",)))
    assert patch(path, [{"op": "delete_slide", "id": "slide-0"}]) == ("", failure(1, "cannot delete the last slide"), 1)
    assert_untouched(path, before)


def test_deck_patch_delete_unknown_id_wins_over_last_slide(tmp_path: Path) -> None:
    """On a one slide deck an unknown id is reported as unknown, not as the last slide."""
    path, _ = carbon_file(tmp_path, build_deck("carbon", ("Seul",)))
    assert patch(path, [DELETE_1])[1] == failure(1, 'unknown slide id "slide-1"')


def test_deck_patch_delete_last_slide_after_an_earlier_delete(tmp_path: Path) -> None:
    """The protection counts the working copy: two slides, two deletes."""
    path, before = carbon_file(tmp_path, build_deck("carbon", ("A", "B")))
    ops = [{"op": "delete_slide", "id": "slide-0"}, {"op": "delete_slide", "id": "slide-1"}]
    assert patch(path, ops)[1] == failure(2, "cannot delete the last slide")
    assert_untouched(path, before)


# E2E-032


def test_deck_patch_delete_dry_run_writes_nothing(tmp_path: Path) -> None:
    """E2E-032: the result announces the change, the file keeps bytes and mtime."""
    path, before = carbon_file(tmp_path)
    assert patch(path, [DELETE_1], "--dry-run") == (OK_DRY, "", 0)
    assert_untouched(path, before)
    assert apply_patch(path, [DELETE_1], dry_run=True) == json.loads(OK_DRY)
    assert_untouched(path, before)


def test_deck_patch_delete_dry_run_result_is_the_real_one_plus_flag(tmp_path: Path) -> None:
    """A real run gives the same result without ``dry_run``."""
    path, _ = carbon_file(tmp_path)
    real = apply_patch(path, [DELETE_1])
    assert real == {k: v for k, v in json.loads(OK_DRY).items() if k != "dry_run"}
    assert len(slides_of(Path(path).read_text(encoding="utf-8"))) == 4


def test_deck_patch_delete_handles_quote_styles_and_odd_titles(tmp_path: Path) -> None:
    """Single quoted and unquoted attributes are rewritten, a title holding ``];`` and ``</`` is safe."""
    text = deck_carbon().replace(' id="slide-2" data-type="slide"', " id=slide-2 data-type='slide'")
    text = text.replace('data-title="Plan"', 'data-title="a]; b &lt;/script&gt;"')
    path, _ = carbon_file(tmp_path, text)
    result = run_ok(path, [{"op": "delete_slide", "id": "slide-4"}])
    assert '<article class="slide" id="slide-2" data-type=\'slide\'' in result
    assert '    "a]; b <\\/script>",\n' in result
    assert TOTAL.findall(result) == ["4"] and len(NAMES.findall(result)) == 1
