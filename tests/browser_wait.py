"""Bounded observation of asynchronous results in browser tests (SPEC-0014, BR-008 to BR-010).

A browser test never asserts an asynchronous result after a fixed delay. It observes the result
repeatedly, at most ``OBSERVE_INTERVAL_SECONDS`` apart, until it holds or ``OBSERVE_BOUND_SECONDS``
have passed since the call, and a failure reports the last observed value. The pause between two
observations is ``page.wait_for_timeout``, never ``time.sleep``: in the sync Playwright API route
handlers and events only run inside a Playwright call, so a ``time.sleep`` would freeze them.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

OBSERVE_INTERVAL_SECONDS = 0.1
OBSERVE_BOUND_SECONDS = 10.0
SETTLE_SECONDS = 1.0
LATE_SAVE_MS = 2000


def wait_until[T](
    page: Page, observe: Callable[[], T], holds: Callable[[T], bool], *, what: str, bound: float = OBSERVE_BOUND_SECONDS
) -> T:
    """Return the first observed value for which ``holds`` is true, else fail with the last one.

    Call it right after the action that triggers the result: the deadline starts at the call.
    """
    deadline = time.monotonic() + bound
    value = observe()
    while not holds(value):
        if time.monotonic() >= deadline:
            value = observe()
            if holds(value):
                return value
            raise AssertionError(f"{what} not reached within {bound:g} s, last value: {value!r}")
        page.wait_for_timeout(OBSERVE_INTERVAL_SECONDS * 1000)
        value = observe()
    return value


def wait_for_file(page: Page, path: Path, needle: str, *, bound: float = OBSERVE_BOUND_SECONDS) -> str:
    """Wait until the file at ``path`` contains ``needle``; return its text."""
    return wait_until(
        page,
        lambda: path.read_text(encoding="utf-8"),
        lambda text: needle in text,
        what=f"{path.name} containing {needle!r}",
        bound=bound,
    )


def wait_for_js(
    page: Page, expression: str, expected: object, *, what: str, bound: float = OBSERVE_BOUND_SECONDS
) -> object:
    """Wait until ``page.evaluate(expression)`` equals ``expected``; return the value."""
    return wait_until(page, lambda: page.evaluate(expression), lambda value: value == expected, what=what, bound=bound)


def settle(page: Page) -> None:
    """Let a possible side effect happen before an absence is asserted (BR-010)."""
    page.wait_for_timeout(SETTLE_SECONDS * 1000)


LATE_SAVE_SCRIPT = """
(() => {
  const send = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    const method = ((init && init.method) || 'GET').toUpperCase();
    if (method === 'POST' && url.pathname === '/content') {
      await new Promise(resolve => setTimeout(resolve, %d));
    }
    return send(input, init);
  };
})();
"""


def answer_saves_late(page: Page, delay_ms: int = LATE_SAVE_MS) -> None:
    """Make every ``POST /content`` round trip take ``delay_ms`` more, so its answer reaches the editor late (BR-011).

    The delay is in the page, before the request leaves: the file is written and the editor is
    answered ``delay_ms`` after the save started, and the editor's saves, which run one after the
    other, pile up behind it. Call it before ``page.goto``. A route handler cannot do this in the
    sync Playwright API: one that waits blocks the dispatcher, which stretches every
    ``wait_for_timeout`` of the test by the same delay and hides the latency from the test, and one
    that answers after ``route.fetch()`` has already written the file (see ``.agent_docs/testing.md``).
    """
    page.add_init_script(LATE_SAVE_SCRIPT % delay_ms)
