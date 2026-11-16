"""US-0127: ``library/names.py`` (SPEC-0025, DEC-029): composed form, the unique key and the folder order."""

from __future__ import annotations

import random
import unicodedata

import pytest

from mcp_htmleditor.library.names import compose, name_key, order_key

CAFE_COMPOSED = "Caf\u00e9"
CAFE_DECOMPOSED = "Cafe\u0301"
RANDOM_NAMES = 100
RANDOM_SEED = 20261116
# Bases and combining marks whose composed and decomposed forms differ: a name drawn from them is rarely NFC already.
RANDOM_ALPHABET = "aAeEiIoOuUcCnNsSzZ\u0430\u0410\u0435\u0415 -0123456789\u00e9\u00c9\u00f1\u00e7\u0419"
RANDOM_MARKS = "\u0301\u0300\u0302\u0303\u0308\u0327\u030c\u0306"


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
