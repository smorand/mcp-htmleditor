"""US-0127, US-0129, US-0130: ``library/names.py`` (SPEC-0025, DEC-029, DEC-031): composed form, the unique key, the
folder order, the size text and the folder name rule."""

from __future__ import annotations

import random
import unicodedata

import pytest

from mcp_htmleditor.library import names
from mcp_htmleditor.library.names import NameRefused, check_folder_name, compose, name_key, order_key

CAFE_COMPOSED = "Caf\u00e9"
CAFE_DECOMPOSED = "Cafe\u0301"
RANDOM_NAMES = 100
RANDOM_SEED = 20261116
# Bases and combining marks whose composed and decomposed forms differ: a name drawn from them is rarely NFC already.
RANDOM_ALPHABET = "aAeEiIoOuUcCnNsSzZ\u0430\u0410\u0435\u0415 -0123456789\u00e9\u00c9\u00f1\u00e7\u0419"
RANDOM_MARKS = "\u0301\u0300\u0302\u0303\u0308\u0327\u030c\u0306"


E_ACUTE_DECOMPOSED = "e\u0301"


def sorted_names(*names: str) -> list[str]:
    return sorted(names, key=order_key)


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (("b", "10", "a", "2"), ["10", "2", "a", "b"]),  # digits before letters, compared character by character
        (
            ("zeta", "Alpha", "alpha", "Beta"),
            ["Alpha", "alpha", "Beta", "zeta"],
        ),  # case ignored, exact name breaks ties
        (("Zeta", "\u00c9t\u00e9", "\u00c9clair", "alpha"), ["alpha", "\u00c9clair", "\u00c9t\u00e9", "Zeta"]),
        (
            ("\u041a\u0430\u0440\u0434\u0438\u043e\u043b\u043e\u0433\u0438\u044f", "zulu", "2027"),
            ["2027", "zulu", "\u041a\u0430\u0440\u0434\u0438\u043e\u043b\u043e\u0433\u0438\u044f"],
        ),
        (
            ("\u0645\u0624\u062a\u0645\u0631", "\u041c\u043e\u0441\u043a\u0432\u0430", "omega"),
            ["omega", "\u041c\u043e\u0441\u043a\u0432\u0430", "\u0645\u0624\u062a\u0645\u0631"],
        ),
        (
            ("\u5fc3\u810f\u75c5\u5b66", "\u0642\u0644\u0628", "\u041a\u0430\u0440\u0434\u0438\u044f", "Z", "9"),
            ["9", "Z", "\u041a\u0430\u0440\u0434\u0438\u044f", "\u0642\u0644\u0628", "\u5fc3\u810f\u75c5\u5b66"],
        ),
    ],
)
def test_order_key_puts_digits_then_latin_then_other_alphabets(names: tuple[str, ...], expected: list[str]) -> None:
    """FR-NEW-015: accents removed, case ignored, compared by code point; Cyrillic before Arabic before Chinese."""
    assert sorted_names(*names) == expected
    assert sorted_names(*reversed(names)) == expected


def test_order_key_ignores_accents_and_case_but_keeps_the_exact_name() -> None:
    """\u00c9 sorts as e, between d and f; ``Cafe`` and ``Caf\u00e9`` share the first part and stay distinct."""
    assert order_key("\u00c9clair Study") == ("eclair study", "\u00c9clair Study")
    assert order_key("Pneumo \u00c9t\u00e9")[0] == "pneumo ete"
    assert sorted_names("f", "\u00c9clair", "d") == ["d", "\u00c9clair", "f"]
    assert order_key("Cafe")[0] == order_key(CAFE_COMPOSED)[0] == order_key(CAFE_DECOMPOSED)[0]
    assert order_key("Cafe") != order_key(CAFE_COMPOSED)


def test_order_key_keeps_letters_that_have_no_accent_to_remove() -> None:
    """Only combining marks go: a Cyrillic \u0419 decomposes to \u0418 plus a mark; \u00df and \u00f8 have no mark."""
    assert order_key("\u0419\u043e\u0433\u0430")[0] == "\u0438\u043e\u0433\u0430"
    assert order_key("Stra\u00dfe")[0] == "stra\u00dfe"  # lower(), never casefold(): \u00df is not ss
    assert order_key("\u00d8re")[0] == "\u00f8re"


def test_name_key_of_composed_and_decomposed_cafe_is_one_key() -> None:
    """DEC-029: NFC of the lower cased composed text; ``Cafe`` without accent is another name."""
    assert name_key(CAFE_COMPOSED) == name_key(CAFE_DECOMPOSED) == "caf\u00e9"
    assert name_key("CAF\u00c9") == name_key(CAFE_DECOMPOSED)
    assert name_key("Cafe") != name_key(CAFE_COMPOSED)
    assert name_key("STRASSE") != name_key("Stra\u00dfe")  # lower(), not casefold()
    assert compose(CAFE_DECOMPOSED) == CAFE_COMPOSED
    assert compose(CAFE_COMPOSED) == CAFE_COMPOSED


def test_name_key_is_the_same_for_a_name_and_its_composed_form() -> None:
    """Property style: 100 random names mixing composed letters and combining marks."""
    generator = random.Random(RANDOM_SEED)  # noqa: S311 - a reproducible test sample, not a secret
    decomposed_seen = 0
    for _ in range(RANDOM_NAMES):
        name = "".join(
            generator.choice(RANDOM_ALPHABET) + (generator.choice(RANDOM_MARKS) if generator.random() < 0.4 else "")
            for _ in range(generator.randint(1, 12))
        )
        decomposed_seen += unicodedata.normalize("NFC", name) != name
        assert name_key(name) == name_key(compose(name)), ascii(name)
        assert unicodedata.is_normalized("NFC", name_key(name)), ascii(name)
        assert name_key(name) == name_key(unicodedata.normalize("NFD", name)), ascii(name)
    assert decomposed_seen > RANDOM_NAMES // 4  # the loop exercised names that are not already composed


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, "0 bytes"),
        (1, "1 byte"),
        (900, "900 bytes"),
        (1_023, "1023 bytes"),
        (1_024, "1.0 KB"),
        (1_075, "1.0 KB"),  # 1.0498: below the half
        (1_076, "1.1 KB"),  # 1.0508: rounded half up from the exact value
        (1_280, "1.3 KB"),  # exactly 1.25: half up, where round() would give 1.2
        (1_048_575, "1024.0 KB"),  # one byte short of 1 MB stays in KB
        (1_048_576, "1.0 MB"),
        (26_214_400, "25.0 MB"),
    ],
)
def test_format_size_chooses_the_unit_from_the_exact_byte_count(count: int, expected: str) -> None:
    """FR-NEW-018, DEC-031: bytes below 1 024, then KB, then MB, one decimal rounded half up from the exact value."""
    assert names.format_size(count) == expected


@pytest.mark.parametrize(
    ("raw", "kept"),
    [
        ("  Oncology 2030  ", "Oncology 2030"),  # E2E-091: trimmed before it is checked and kept
        ("B" * 60, "B" * 60),  # E2E-096: exactly 60
        ("-", "-"),  # E2E-096: a single hyphen
        ("\u041a\u0430\u0440\u0434\u0438\u043e\u043b\u043e\u0433\u0438\u044f 2027", None),  # E2E-097 Cyrillic
        ("\u0623\u0645\u0631\u0627\u0636 \u0627\u0644\u0631\u0626\u0629", None),  # E2E-097 Arabic
        ("\u5fc3\u81d3\u75c5\u5b66", None),  # E2E-097 Chinese
        ("Pneumo E\u0301te\u0301", "Pneumo \u00c9t\u00e9"),  # E2E-163: brought to its composed form
        (E_ACUTE_DECOMPOSED * 60, "\u00e9" * 60),  # E2E-163: 120 code points, 60 once composed
        ("Study \u0663\u0660", None),  # decimal digits of another script (Nd)
        ("Pneumo  \u00c9t\u00e9", None),  # inner spaces are kept as typed
    ],
)
def test_check_folder_name_accepts_letters_of_any_alphabet_digits_spaces_and_hyphens(
    raw: str, kept: str | None
) -> None:
    """FR-NEW-040, FR-NEW-041, DEC-029: the trimmed composed name comes back (``None``: the name as given)."""
    assert check_folder_name(raw) == (kept if kept is not None else raw)


@pytest.mark.parametrize(
    "raw",
    [
        "",  # E2E-093
        "   ",  # E2E-093: blank once trimmed
        "A" * 61,  # E2E-094
        E_ACUTE_DECOMPOSED * 61,  # E2E-163: 61 once composed
        "Pneumo \U0001fac1",  # E2E-095: emoji
        "Cardio/Rhythm",  # E2E-095
        "Cardio_2027",  # E2E-095
        "R&D",  # E2E-095
        "Study.2027",  # E2E-095
        "..",
        "Cardio\u20132027",  # an en dash is not the plain hyphen
        "Cardio\u00a02027",  # a no break space inside is not the space
        "Cardio\t2027",
        "Folder \u2167",  # a Roman numeral letter is Nl, not a decimal digit
        "<script>",
        "\u0301",  # a lone combining mark
        "A\ufe0f",  # a variation selector is a mark but not an accent
        "1\ufe0f\u20e3",  # a keycap emoji
        " \u0301A",  # a mark after a space
    ],
)
def test_check_folder_name_refuses_everything_else(raw: str) -> None:
    """FR-NEW-041: empty, over 60 composed characters, or a character outside ``L*``, ``M*``, ``Nd``, space, hyphen."""
    with pytest.raises(NameRefused):
        check_folder_name(raw)
