"""SPEC-0013 US-0073: the shared encodability predicate and the atomic writer refusal (BR-010, BR-017)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_htmleditor.fileio import WriteError, atomic_write
from mcp_htmleditor.textcheck import (
    UNENCODABLE_BIND_ADDRESS,
    UNENCODABLE_FILE_NAME,
    UNENCODABLE_TEXT,
    is_utf8_encodable,
    replace_unencodable,
)


@pytest.mark.parametrize(
    "text", ["", "abc", "\x00", "😀", "été", "\ud83d\ude00".encode("utf-16", "surrogatepass").decode("utf-16")]
)
def test_encodable_text(text: str) -> None:
    assert is_utf8_encodable(text) is True


@pytest.mark.parametrize("text", ["\ud800", "x\udc00", "a\udcff", "\ud83dX", "\udfff"])
def test_unencodable_text(text: str) -> None:
    assert is_utf8_encodable(text) is False


def test_replace_unencodable() -> None:
    assert replace_unencodable("a\ud800b\udcff") == "a\ufffdb\ufffd"
    assert replace_unencodable("été😀") == "été😀"


def test_messages() -> None:
    assert UNENCODABLE_TEXT == "Text cannot be encoded as UTF-8"
    assert UNENCODABLE_FILE_NAME == "File name cannot be encoded"
    assert UNENCODABLE_BIND_ADDRESS == "Bind address cannot be encoded"


def test_atomic_write_refuses_unencodable_text(tmp_path: Path) -> None:
    path = tmp_path / "f.html"
    with pytest.raises(WriteError) as raised:
        atomic_write(path, "x\ud800")
    assert raised.value.reason == "Text cannot be encoded as UTF-8"
    assert str(raised.value) == f"Cannot write {path}: Text cannot be encoded as UTF-8"
    assert list(tmp_path.iterdir()) == []


def test_atomic_write_keeps_existing_file_on_refusal(tmp_path: Path) -> None:
    path = tmp_path / "f.html"
    path.write_bytes(b"old")
    with pytest.raises(WriteError):
        atomic_write(path, "x\udc00", reason="browser-save")
    assert path.read_bytes() == b"old"
    assert [entry.name for entry in tmp_path.iterdir()] == ["f.html"]


def test_atomic_write_accepts_pair_and_nul(tmp_path: Path) -> None:
    path = tmp_path / "f.html"
    assert atomic_write(path, "<p>😀\x00</p>") is True
    assert path.read_bytes() == b"<p>\xf0\x9f\x98\x80\x00</p>"
