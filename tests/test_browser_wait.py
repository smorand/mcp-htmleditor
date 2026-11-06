"""Unit tests of ``tests/browser_wait.py``: the observation loop, without a browser."""

from __future__ import annotations

import time
from itertools import count
from pathlib import Path
from typing import cast

import pytest
from playwright.sync_api import Page

from tests.browser_wait import OBSERVE_INTERVAL_SECONDS, SETTLE_SECONDS, settle, wait_for_file, wait_for_js, wait_until


class StubPage:
    """Stands in for a Playwright page: records ``wait_for_timeout`` and really sleeps."""

    def __init__(self, evaluated: list[object] | None = None) -> None:
        self.waits: list[float] = []
        self.evaluated = evaluated or []

    def wait_for_timeout(self, timeout: float) -> None:
        self.waits.append(timeout)
        time.sleep(timeout / 1000)

    def evaluate(self, expression: str) -> object:
        return self.evaluated.pop(0)


def _page(stub: StubPage) -> Page:
    return cast(Page, stub)


def test_wait_until_returns_the_first_value_that_holds() -> None:
    stub = StubPage()
    values = count()

    result = wait_until(_page(stub), lambda: next(values), lambda value: value == 3, what="counter")

    assert result == 3
    assert stub.waits == [100.0, 100.0, 100.0]


def test_wait_until_does_not_wait_when_the_value_already_holds() -> None:
    stub = StubPage()

    assert wait_until(_page(stub), lambda: "ok", lambda value: value == "ok", what="value") == "ok"
    assert stub.waits == []


def test_wait_until_reports_what_and_the_last_value_at_the_bound() -> None:
    stub = StubPage()
    values = count()
    started = time.monotonic()

    with pytest.raises(AssertionError) as raised:
        wait_until(_page(stub), lambda: next(values), lambda value: False, what="never", bound=0.5)

    elapsed = time.monotonic() - started
    assert 0.5 <= elapsed <= 1.5
    message = str(raised.value)
    assert "never not reached within 0.5 s" in message
    last = len(stub.waits) + 1  # one observation per wait, plus the final one after the deadline
    assert f"last value: {last}" in message


def test_every_wait_is_at_most_the_observation_interval() -> None:
    stub = StubPage()

    with pytest.raises(AssertionError):
        wait_until(_page(stub), lambda: 0, lambda value: False, what="never", bound=0.4)

    assert stub.waits
    assert all(wait <= OBSERVE_INTERVAL_SECONDS * 1000 for wait in stub.waits)


def test_wait_for_file_returns_the_text_holding_the_needle(tmp_path: Path) -> None:
    target = tmp_path / "doc.html"
    target.write_text("<h1>Titre</h1>", encoding="utf-8")

    assert wait_for_file(_page(StubPage()), target, "Titre") == "<h1>Titre</h1>"


def test_wait_for_file_failure_names_the_file_and_shows_its_content(tmp_path: Path) -> None:
    target = tmp_path / "doc.html"
    target.write_text("<h1>Titre</h1>", encoding="utf-8")

    with pytest.raises(AssertionError) as raised:
        wait_for_file(_page(StubPage()), target, "Q", bound=0.3)

    assert "doc.html containing 'Q'" in str(raised.value)
    assert "<h1>Titre</h1>" in str(raised.value)


def test_wait_for_js_compares_the_evaluated_value() -> None:
    stub = StubPage(evaluated=["a", "b", "c"])

    assert wait_for_js(_page(stub), "1", "c", what="letter") == "c"
    assert stub.waits == [100.0, 100.0]


def test_settle_waits_the_settle_delay() -> None:
    stub = StubPage()
    stub.wait_for_timeout = stub.waits.append  # type: ignore[method-assign]  # no real sleep for 1 s

    settle(_page(stub))

    assert stub.waits == [SETTLE_SECONDS * 1000]
