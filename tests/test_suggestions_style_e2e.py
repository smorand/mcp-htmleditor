"""SPEC-0032 (US-0170): the AI suggestions block of the requests panel looks like the requests above it.

E2E-001 to E2E-005, read on computed styles in a real headless Chromium against a real editor server.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page

from tests.browser_wait import wait_until
from tests.conftest import ServedDeck, needs_chromium
from tests.test_review_apply_e2e import _open, _row, _write_review, s1
from tests.test_review_write import suggestion

STYLE = """([selector, props]) => {
  const el = document.querySelector(selector);
  const css = getComputedStyle(el);
  const out = {};
  props.forEach(p => { out[p] = css.getPropertyValue(p); });
  return out;
}"""
RECT = """(selector) => { const r = document.querySelector(selector).getBoundingClientRect();
  return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width}; }"""


def _style(page: Page, selector: str, *props: str) -> dict[str, str]:
    return dict(page.evaluate(STYLE, [selector, list(props)]))


def _rect(page: Page, selector: str) -> dict[str, float]:
    return {key: float(value) for key, value in page.evaluate(RECT, selector).items()}


def _two(page: Page, deck: ServedDeck) -> list[dict[str, Any]]:
    _open(page, deck, "AI suggestions (0)")
    items = [s1(), suggestion(2, slide="slide-2")]
    _write_review(deck, items)
    wait_until(
        page,
        lambda: page.locator("#suggestions-list li").count(),
        lambda count: count == 2,
        what="the two suggestions shown",
    )
    return items


@needs_chromium
def test_e2e_001_the_heading_matches_the_requests_heading(page: Page, served_deck: ServedDeck) -> None:
    _two(page, served_deck)

    heading = _style(page, "#suggestions-heading", "font-size", "font-weight", "color")
    requests = _style(page, "#requests-heading", "font-size", "font-weight", "color")

    assert heading == requests == {"font-size": "12px", "font-weight": "600", "color": "rgb(244, 244, 244)"}
    gap = _rect(page, "#suggestions-heading")["top"] - _rect(page, "#requests-list")["bottom"]
    assert gap >= 16


@needs_chromium
def test_e2e_002_a_suggestion_is_a_card_like_a_request(page: Page, served_deck: ServedDeck) -> None:
    items = _two(page, served_deck)
    row = f'#suggestions-list li[data-suggestion-id="{items[0]["id"]}"]'

    card = _style(page, row, "background-color", "border-top-width", "border-top-color", "padding")
    title = _style(page, f"{row} .suggestion-title", "color", "font-weight")
    why = _style(page, f"{row} .suggestion-why", "color")

    assert card == {
        "background-color": "rgb(38, 38, 38)",
        "border-top-width": "1px",
        "border-top-color": "rgb(57, 57, 57)",
        "padding": "6px 8px",
    }
    assert title == {"color": "rgb(244, 244, 244)", "font-weight": "600"}
    assert why == {"color": "rgb(198, 198, 198)"}
    assert _rect(page, f"{row} button")["left"] == _rect(page, f"{row} .suggestion-title")["left"]
    first = _rect(page, "#suggestions-list li:nth-child(1)")
    second = _rect(page, "#suggestions-list li:nth-child(2)")
    assert second["top"] - first["bottom"] == 6


@needs_chromium
def test_e2e_003_long_text_stays_inside_the_panel(page: Page, served_deck: ServedDeck) -> None:
    _open(page, served_deck, "AI suggestions (0)")
    long = suggestion(1, slide="slide-1")
    long["title"] = "T" * 60
    long["why"] = "why " * 75
    _write_review(served_deck, [long])
    wait_until(page, lambda: page.locator("#suggestions-list li").count(), lambda n: n == 1, what="the suggestion")

    card = _rect(page, "#suggestions-list li")
    panel = page.evaluate(
        "() => { const p = document.getElementById('requests-side');"
        " return {scroll: p.scrollWidth, client: p.clientWidth, right: p.getBoundingClientRect().right}; }"
    )

    assert card["right"] <= panel["right"]
    assert panel["scroll"] <= panel["client"]


@needs_chromium
def test_e2e_004_the_apply_button_is_blue_on_the_dark_panel(page: Page, served_deck: ServedDeck) -> None:
    items = _two(page, served_deck)

    button = _style(
        page, f'#suggestions-list li[data-suggestion-id="{items[0]["id"]}"] button', "background-color", "color"
    )

    assert button == {"background-color": "rgb(15, 98, 254)", "color": "rgb(255, 255, 255)"}


@needs_chromium
def test_e2e_005_an_applied_suggestion_is_inactive(page: Page, served_deck: ServedDeck) -> None:
    items = _two(page, served_deck)
    button = _row(page, items[0]["id"]).locator("button.suggestion-apply")
    selector = f'#suggestions-list li[data-suggestion-id="{items[0]["id"]}"] button'

    button.click()
    wait_until(page, button.inner_text, lambda text: text == "Applied", what="the button applied")

    assert button.is_disabled()
    assert _style(page, selector, "background-color", "color", "cursor") == {
        "background-color": "rgb(57, 57, 57)",
        "color": "rgb(141, 141, 141)",
        "cursor": "default",
    }
