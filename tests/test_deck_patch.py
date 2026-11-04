"""Tests for ``mcp-htmleditor patch`` with ``set_text``, ``atomic_write`` and the path guard (SPEC-0007 US-0038)."""

from __future__ import annotations

import json
import os
import shutil
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from mcp_htmleditor.deck import DeckError
from mcp_htmleditor.deck.patch import apply_patch
from mcp_htmleditor.fileio import atomic_write

from .deck_support import (
    BOOTSTRAP,
    CARBON_TITLES,
    FIXED_TIME,
    assert_only_region_changed,
    build_deck,
    deck_carbon,
    deck_ei,
    doc_perso,
    run_cli,
    write_deck,
)

TITLE_2 = b'<h1 class="slide-h1" data-editable="text">Contexte</h1>'
TITLE_1 = b'<h1 class="slide-h1" data-editable="text">Sommaire</h1>'
SET_TITLE_2 = {"op": "set_text", "id": "slide-2", "selector": ".slide-h1", "text": "Contexte et enjeux"}
OK_CHANGED = '{"ok":true,"changed":true,"slides":8,"problems":[]}\n'
OK_UNCHANGED = '{"ok":true,"changed":false,"slides":8,"problems":[]}\n'
FIVE_OPERATIONS = (
    ("set_text", "id"),
    ("replace_slide", "id"),
    ("insert_slide", "after"),
    ("delete_slide", "id"),
    ("move_slide", "id"),
)


def patch(path: str, ops: object, *flags: str) -> tuple[str, str, int]:
    """Run ``patch`` with ``ops`` given on standard input."""
    return run_cli("patch", path, "--ops", "-", *flags, input=json.dumps(ops))


def failure(number: int, reason: str) -> str:
    """Return the standard error text of a failed operation."""
    return f"error: patch failed at operation {number}: {reason} (nothing written)\n"


def ei_file(tmp_path: Path) -> tuple[str, bytes]:
    """Write DECK-EI with a forced time and return its path and bytes."""
    path = write_deck(tmp_path / "ei.html", deck_ei())
    return path, Path(path).read_bytes()


def assert_untouched(path: str, before: bytes) -> None:
    """Assert the file has the same bytes and the forced modification time."""
    assert Path(path).read_bytes() == before
    assert Path(path).stat().st_mtime_ns == FIXED_TIME * 1_000_000_000


# E2E-004


def test_deck_patch_set_text_changes_only_the_title(tmp_path: Path) -> None:
    """E2E-004: the result is exact and only the content of the title element differs."""
    path, before = ei_file(tmp_path)
    assert patch(path, [SET_TITLE_2]) == (OK_CHANGED, "", 0)
    after = Path(path).read_bytes()
    assert_only_region_changed(before, after, TITLE_2)
    assert b'<h1 class="slide-h1" data-editable="text">Contexte et enjeux</h1>' in after


def test_deck_patch_two_operations_on_one_slide_both_apply(tmp_path: Path) -> None:
    """A second set_text on the same slide sees the first edit and lands on the right bytes."""
    path, before = ei_file(tmp_path)
    ops = [
        {"op": "set_text", "id": "slide-1", "selector": ".slide-eyebrow", "text": "Sujet"},
        {"op": "set_text", "id": "slide-1", "selector": ".slide-h1", "text": "Plan"},
        {"op": "set_text", "id": "slide-4", "selector": ".slide-h1", "text": "Cible"},
    ]
    assert patch(path, ops) == (OK_CHANGED, "", 0)
    after = Path(path).read_bytes().decode()
    assert '<div class="slide-eyebrow" data-editable="text">Sujet</div>' in after
    assert '<h1 class="slide-h1" data-editable="text">Plan</h1>' in after
    assert '<h1 class="slide-h1" data-editable="text">Cible</h1>' in after
    assert len(after) == len(before.decode()) + (len("Sujet") - len("Cat · Slide 02 / 08")) + (
        len("Plan") - len("Sommaire")
    ) + (len("Cible") - len("Architecture"))


# E2E-015


def test_deck_patch_unknown_operation(tmp_path: Path) -> None:
    """E2E-015: an unknown operation name fails and nothing is written."""
    path = write_deck(tmp_path / "carbon.html", deck_carbon())
    before = Path(path).read_bytes()
    assert patch(path, [{"op": "frobnicate"}]) == ("", failure(1, 'unknown operation "frobnicate"'), 1)
    assert_untouched(path, before)


# E2E-016


@pytest.mark.parametrize("folder", ["bootstrap", "reference"])
@pytest.mark.parametrize("flags", [(), ("--dry-run",)])
def test_deck_patch_refuses_a_template_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, folder: str, flags: tuple[str, ...]
) -> None:
    """E2E-016: a path under templates/bootstrap or templates/reference is refused, dry run or not."""
    target = tmp_path / "templates" / folder / "x.html"
    target.parent.mkdir(parents=True)
    shutil.copy(BOOTSTRAP / "slides-empty.html", target)
    monkeypatch.chdir(tmp_path)
    given = f"templates/{folder}/x.html"
    before = target.read_bytes()
    ops = [{"op": "set_text", "id": "slide-0", "selector": "h1", "text": "x"}]
    assert patch(given, ops, *flags) == ("", f"error: Refusing to modify a template: {given}\n", 1)
    assert target.read_bytes() == before


def test_deck_patch_refuses_a_symlink_into_a_template(tmp_path: Path) -> None:
    """The guard resolves symlinks: a link outside templates/ that points inside is refused."""
    target = tmp_path / "templates" / "reference" / "x.html"
    target.parent.mkdir(parents=True)
    shutil.copy(BOOTSTRAP / "slides-empty.html", target)
    link = tmp_path / "link.html"
    link.symlink_to(target)
    stdout, stderr, code = patch(str(link), [])
    assert (stdout, stderr, code) == ("", f"error: Refusing to modify a template: {link}\n", 1)


def test_deck_patch_template_guard_ignores_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A case variant of the template folders is refused whatever the filesystem (macOS is case insensitive).

    The path need not exist: the guard runs before the file check, so the test is deterministic on
    case sensitive and case insensitive filesystems alike.
    """
    monkeypatch.chdir(tmp_path)
    given = "d/repo/TEMPLATES/BOOTSTRAP/x.html"
    assert patch(given, []) == ("", f"error: Refusing to modify a template: {given}\n", 1)


def test_deck_patch_template_guard_comes_before_the_file_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing file under templates/bootstrap is refused as a template, not reported missing."""
    monkeypatch.chdir(tmp_path)
    assert run_cli("patch", "templates/bootstrap/ghost.html", "--ops", "nope.json") == (
        "",
        "error: Refusing to modify a template: templates/bootstrap/ghost.html\n",
        1,
    )


# E2E-033


def test_deck_patch_escapes_text_and_is_idempotent(tmp_path: Path) -> None:
    """E2E-033: the text is escaped, a second identical run writes nothing."""
    path, before = ei_file(tmp_path)
    ops = [{"op": "set_text", "id": "slide-2", "selector": ".slide-h1", "text": "R&D <b>x</b>"}]
    assert patch(path, ops) == (OK_CHANGED, "", 0)
    after = Path(path).read_bytes()
    assert b'data-editable="text">R&amp;D &lt;b&gt;x&lt;/b&gt;</h1>' in after
    assert_only_region_changed(before, after, TITLE_2)
    os.utime(path, (FIXED_TIME, FIXED_TIME))
    assert patch(path, ops) == (OK_UNCHANGED, "", 0)
    assert_untouched(path, after)


# E2E-040


def test_deck_patch_missing_field_and_non_json(tmp_path: Path) -> None:
    """E2E-040: a missing field names the field; text that is not JSON is an invalid operations error."""
    path, before = ei_file(tmp_path)
    ops = [{"op": "set_text", "id": "slide-1", "selector": ".slide-h1"}]
    assert patch(path, ops) == ("", failure(1, 'missing field "text"'), 1)
    stdout, stderr, code = run_cli("patch", path, "--ops", "-", input="not json")
    assert (stdout, code) == ("", 1)
    assert stderr.startswith("error: Invalid operations JSON: ")
    assert len(stderr) > len("error: Invalid operations JSON: \n")
    assert_untouched(path, before)


# atomic_write


def test_deck_patch_atomic_write_replaces_content_and_keeps_mode(tmp_path: Path) -> None:
    """The content is replaced and a 0o640 file stays 0o640, with no temp file left."""
    target = tmp_path / "f.html"
    target.write_bytes(b"old")
    target.chmod(0o640)
    atomic_write(target, b"new")
    assert target.read_bytes() == b"new"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert [p.name for p in tmp_path.iterdir()] == ["f.html"]


def test_deck_patch_atomic_write_follows_a_symlink(tmp_path: Path) -> None:
    """The target of a symlink is replaced and the link stays a link."""
    target = tmp_path / "real.html"
    target.write_bytes(b"old")
    link = tmp_path / "link.html"
    link.symlink_to(target)
    atomic_write(link, b"new")
    assert link.is_symlink()
    assert target.read_bytes() == b"new"


def test_deck_patch_atomic_write_new_file_uses_the_umask(tmp_path: Path) -> None:
    """A new file gets 0o666 minus the process umask."""
    umask = os.umask(0o027)
    try:
        atomic_write(tmp_path / "new.html", b"x")
    finally:
        os.umask(umask)
    assert (tmp_path / "new.html").read_bytes() == b"x"
    assert stat.S_IMODE((tmp_path / "new.html").stat().st_mode) == 0o666 & ~0o027


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_deck_patch_atomic_write_read_only_directory(tmp_path: Path) -> None:
    """A directory that refuses a new file gives a DeckError and leaves nothing behind."""
    target = tmp_path / "f.html"
    target.write_bytes(b"old")
    tmp_path.chmod(0o500)
    try:
        with pytest.raises(DeckError, match=r"^Cannot write .*f\.html: "):
            atomic_write(target, b"new")
    finally:
        tmp_path.chmod(0o700)
    assert [p.name for p in tmp_path.iterdir()] == ["f.html"]
    assert target.read_bytes() == b"old"


def test_deck_patch_atomic_write_failure_leaves_the_original_intact(tmp_path: Path) -> None:
    """A failure at the last step keeps the original bytes and removes the temp file."""
    target = tmp_path / "f.html"
    target.write_bytes(b"old")
    with (
        mock.patch.object(Path, "replace", side_effect=OSError(28, "No space left on device")),
        pytest.raises(DeckError, match=r"^Cannot write .*f\.html: No space left on device$"),
    ):
        atomic_write(target, b"new")
    assert [p.name for p in tmp_path.iterdir()] == ["f.html"]
    assert target.read_bytes() == b"old"


def test_deck_patch_atomic_write_records_a_span(tmp_path: Path) -> None:
    """A file.write span carries the path and the size."""
    recorded: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def fake_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[None]:
        recorded.append((name, dict(attributes or {})))
        yield

    target = tmp_path / "f.html"
    with mock.patch("mcp_htmleditor.fileio.trace_span", fake_span):
        atomic_write(target, b"12345")
    assert recorded == [("file.write", {"file.path": str(target.resolve()), "file.size": 5})]


# set_text semantics


@pytest.mark.parametrize(
    ("text", "written"),
    [
        ("a&b", "a&amp;b"),
        ("<i>", "&lt;i&gt;"),
        ("\"q\" 's'", "\"q\" 's'"),
        ("é", "é"),
        ("", ""),
    ],
)
def test_deck_patch_set_text_escaping_table(tmp_path: Path, text: str, written: str) -> None:
    """Only & < > are escaped; quotes and non ASCII stay literal; empty text leaves an empty element."""
    path, _ = ei_file(tmp_path)
    ops = [{"op": "set_text", "id": "slide-1", "selector": ".slide-h1", "text": text}]
    assert patch(path, ops) == (OK_CHANGED, "", 0)
    assert f'<h1 class="slide-h1" data-editable="text">{written}</h1>' in Path(path).read_bytes().decode()


def test_deck_patch_set_text_selector_hits_the_slide_element_itself(tmp_path: Path) -> None:
    """The slide element is a candidate: ``article`` replaces everything inside the slide."""
    path = write_deck(tmp_path / "carbon.html", deck_carbon())
    ops = [{"op": "set_text", "id": "slide-1", "selector": "article", "text": "X"}]
    assert patch(path, ops) == ('{"ok":true,"changed":true,"slides":5,"problems":[]}\n', "", 0)
    after = Path(path).read_text(encoding="utf-8")
    assert 'data-title="Offre">X</article>' in after
    assert '<article class="slide" id="slide-2"' in after


def test_deck_patch_set_text_first_match_in_document_order(tmp_path: Path) -> None:
    """The eyebrow comes before the title in the file, so it is the first ``[data-editable]``."""
    path, before = ei_file(tmp_path)
    ops = [{"op": "set_text", "id": "slide-2", "selector": "[data-editable]", "text": "Eyebrow"}]
    assert patch(path, ops) == (OK_CHANGED, "", 0)
    after = Path(path).read_bytes()
    assert_only_region_changed(
        before, after, b'<div class="slide-eyebrow" data-editable="text">Cat \xc2\xb7 Slide 03 / 08</div>'
    )


def test_deck_patch_set_text_selector_errors(tmp_path: Path) -> None:
    """No match, invalid selector and a void element each give one failure and no write."""
    content = build_deck(
        "carbon", CARBON_TITLES, mutate=lambda t: t.replace("<p>Texte de Offre.</p>", "<p>Texte de Offre.<br></p>")
    )
    path = write_deck(tmp_path / "carbon.html", content)
    before = Path(path).read_bytes()

    def one(selector: str) -> tuple[str, str, int]:
        return patch(path, [{"op": "set_text", "id": "slide-1", "selector": selector, "text": "x"}])

    assert one(".nope") == ("", failure(1, 'selector ".nope" matches no element in slide "slide-1"'), 1)
    assert one(":::") == ("", failure(1, 'invalid selector ":::"'), 1)
    assert one("br") == ("", failure(1, 'element matched by selector "br" has no content'), 1)
    assert_untouched(path, before)


def test_deck_patch_unknown_slide_id(tmp_path: Path) -> None:
    """A set_text on an id the file does not hold names the id."""
    path, before = ei_file(tmp_path)
    ops = [{"op": "set_text", "id": "slide-9", "selector": "h1", "text": "x"}]
    assert patch(path, ops) == ("", failure(1, 'unknown slide id "slide-9"'), 1)
    assert_untouched(path, before)


# validation


def test_deck_patch_invalid_shapes(tmp_path: Path) -> None:
    """A non list, a non object and a non string field each give their own message."""
    path, before = ei_file(tmp_path)
    assert patch(path, {}) == ("", "error: Invalid operations JSON: expected a list\n", 1)
    assert patch(path, [3]) == ("", failure(1, "operation must be an object"), 1)
    bad_id = [{"op": "set_text", "id": 5, "selector": "p", "text": "x"}]
    assert patch(path, bad_id) == ("", failure(1, 'field "id" must be a string'), 1)
    assert patch(path, [{"op": 7}]) == ("", failure(1, 'field "op" must be a string'), 1)
    assert_untouched(path, before)


@pytest.mark.parametrize(("name", "first_field"), FIVE_OPERATIONS)
def test_deck_patch_every_operation_name_is_parsed(tmp_path: Path, name: str, first_field: str) -> None:
    """All five operation names are known: each reports its own first missing field."""
    path, before = ei_file(tmp_path)
    assert patch(path, [{"op": name}]) == ("", failure(1, f'missing field "{first_field}"'), 1)
    assert_untouched(path, before)


def test_deck_patch_validates_every_operation_before_writing(tmp_path: Path) -> None:
    """A valid set_text followed by a bad operation 2 writes nothing."""
    path, before = ei_file(tmp_path)
    ops = [SET_TITLE_2, {"op": "move_slide", "id": "slide-1"}]
    assert patch(path, ops) == ("", failure(2, 'missing field "after"'), 1)
    assert_untouched(path, before)


def test_deck_patch_operations_are_checked_in_order_semantic_before_later_shape(tmp_path: Path) -> None:
    """An unknown slide id in operation 1 is reported before the unknown operation 2."""
    path, before = ei_file(tmp_path)
    ops = [{"op": "set_text", "id": "slide-9", "selector": "p", "text": "a"}, {"op": "bogus"}]
    assert patch(path, ops) == ("", failure(1, 'unknown slide id "slide-9"'), 1)
    assert_untouched(path, before)


def test_deck_patch_a_document_reports_the_presentation_before_a_later_shape_error(tmp_path: Path) -> None:
    """On a file with no slide, operation 1 needs a presentation before operation 2 is parsed."""
    path = write_deck(tmp_path / "doc.html", doc_perso())
    before = Path(path).read_bytes()
    ops = [{"op": "delete_slide", "id": "slide-1"}, {"op": "bogus"}]
    assert patch(path, ops) == ("", failure(1, 'operation "delete_slide" needs a presentation'), 1)
    assert_untouched(path, before)


@pytest.mark.parametrize(
    "operation",
    [
        {"op": "replace_slide", "id": "slide-1", "html": "<article></article>"},
        {"op": "insert_slide", "after": "slide-1", "html": "<article></article>"},
        {"op": "move_slide", "id": "slide-1", "after": "slide-2"},
    ],
)
def test_deck_patch_structure_operations_are_not_supported_yet(tmp_path: Path, operation: dict[str, str]) -> None:
    """A valid structural operation fails for now, after an earlier set_text, and writes nothing."""
    path, before = ei_file(tmp_path)
    reason = f'operation "{operation["op"]}" is not supported yet'
    assert patch(path, [SET_TITLE_2, operation]) == ("", failure(2, reason), 1)
    assert_untouched(path, before)


def test_deck_patch_structure_operation_with_unknown_id(tmp_path: Path) -> None:
    """A structural operation naming an unknown slide id reports the id first."""
    path, _ = ei_file(tmp_path)
    assert patch(path, [{"op": "delete_slide", "id": "slide-9"}]) == ("", failure(1, 'unknown slide id "slide-9"'), 1)


def test_deck_patch_a_document_needs_a_presentation(tmp_path: Path) -> None:
    """Any of the operations on a file with no slide fails with the presentation message."""
    path = write_deck(tmp_path / "doc.html", doc_perso())
    before = Path(path).read_bytes()
    assert patch(path, [{"op": "delete_slide", "id": "slide-1"}]) == (
        "",
        failure(1, 'operation "delete_slide" needs a presentation'),
        1,
    )
    set_text = [{"op": "set_text", "id": "a", "selector": "h1", "text": "x"}]
    assert patch(path, set_text) == ("", failure(1, 'operation "set_text" needs a presentation'), 1)
    assert patch(path, []) == ('{"ok":true,"changed":false,"slides":0,"problems":[]}\n', "", 0)
    assert_untouched(path, before)


def test_deck_patch_empty_list_changes_nothing(tmp_path: Path) -> None:
    """An empty list reports the slide count and leaves file and time alone."""
    path, before = ei_file(tmp_path)
    assert patch(path, []) == (OK_UNCHANGED, "", 0)
    assert_untouched(path, before)


# check order, dry run, callback


def test_deck_patch_missing_file_is_reported_before_the_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither the file nor the operations file exists: the file is reported."""
    monkeypatch.chdir(tmp_path)
    assert run_cli("patch", "ghost.html", "--ops", "ops.json") == ("", "error: File not found: ghost.html\n", 1)


def test_deck_patch_unreadable_operations_file(tmp_path: Path) -> None:
    """An operations file that does not exist gives one error line once the file is found."""
    path, _ = ei_file(tmp_path)
    _, stderr, code = run_cli("patch", path, "--ops", str(tmp_path / "ops.json"))
    assert code == 1
    assert stderr.startswith("error: Cannot read ")


def test_deck_patch_reads_operations_from_a_file(tmp_path: Path) -> None:
    """``--ops PATH`` reads the file."""
    path, _ = ei_file(tmp_path)
    ops_file = tmp_path / "ops.json"
    ops_file.write_text(json.dumps([SET_TITLE_2]), encoding="utf-8")
    assert run_cli("patch", path, "--ops", str(ops_file)) == (OK_CHANGED, "", 0)


def test_deck_patch_dry_run_writes_nothing(tmp_path: Path) -> None:
    """A dry run reports the change with ``dry_run`` last and leaves bytes and time alone."""
    path, before = ei_file(tmp_path)
    expected = '{"ok":true,"changed":true,"slides":8,"problems":[],"dry_run":true}\n'
    assert patch(path, [SET_TITLE_2], "--dry-run") == (expected, "", 0)
    assert_untouched(path, before)


def test_deck_patch_callback_surrounds_the_real_write(tmp_path: Path) -> None:
    """The flag goes True then False around a write, never on a dry run, never when nothing changed."""
    path, _ = ei_file(tmp_path)
    calls: list[bool] = []
    apply_patch(path, [SET_TITLE_2], dry_run=True, set_update_flag=calls.append)
    assert calls == []
    apply_patch(path, [], set_update_flag=calls.append)
    assert calls == []
    result = apply_patch(path, [SET_TITLE_2], set_update_flag=calls.append)
    assert result == {"ok": True, "changed": True, "slides": 8, "problems": []}
    assert calls == [True, False]
    calls.clear()
    apply_patch(path, [SET_TITLE_2], set_update_flag=calls.append)
    assert calls == []


def test_deck_patch_callback_is_released_when_the_write_fails(tmp_path: Path) -> None:
    """A failing write still puts the flag back to False."""
    path, _ = ei_file(tmp_path)
    calls: list[bool] = []
    with (
        mock.patch("mcp_htmleditor.deck.patch.atomic_write", side_effect=DeckError("Cannot write x: boom")),
        pytest.raises(DeckError, match="boom"),
    ):
        apply_patch(path, [SET_TITLE_2], set_update_flag=calls.append)
    assert calls == [True, False]


# bytes


def test_deck_patch_crlf_and_bom_are_kept(tmp_path: Path) -> None:
    """A CRLF copy keeps every CRLF outside the title and a BOM stays first."""
    path = tmp_path / "crlf.html"
    before = ("\ufeff" + deck_ei().replace("\n", "\r\n")).encode()
    path.write_bytes(before)
    assert patch(str(path), [SET_TITLE_2]) == (OK_CHANGED, "", 0)
    after = path.read_bytes()
    assert after.startswith(b"\xef\xbb\xbf")
    assert after.count(b"\n") == after.count(b"\r\n") == before.count(b"\r\n")
    assert_only_region_changed(before, after, TITLE_2)
