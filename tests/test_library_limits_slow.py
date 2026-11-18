"""US-0143: a slow link still completes an upload within 2 minutes (SPEC-0025, E2E-076).

About 25 seconds, so it carries the ``slow`` marker and ``make check`` deselects it; run it with
``make test ARGS='-m slow -k library_limits_slow'``. Nothing is patched: a real 25 MB body goes out at 10 megabits per
second over a raw socket while another person browses her folder and the page times are measured.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import pytest

from tests import library_support
from tests.library_support import (
    CARDIOLOGY,
    DAN,
    LAMYA,
    WCBIP,
    FakeGoogle,
    RunningLibrary,
    UploadPlan,
    signed_in,
    valid_deck,
)

pytestmark = pytest.mark.slow

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

BIG = 26_214_400
TEN_MEGABIT = 1_250_000
TWO_MINUTES = 120.0
NOTICEABLE = 1.0  # seconds: a folder page of the quiet person must answer faster than this while the upload runs


def test_library_limits_slow_a_slow_link_still_completes_within_two_minutes(
    library_server: START, fake_google: FakeGoogle
) -> None:
    running = library_server(fake_google)
    ids = running.builder.standard()
    running.builder.standard_presentations(ids)
    dan = signed_in(running, fake_google, DAN)
    lamya = signed_in(running, fake_google, LAMYA)
    started = time.monotonic()
    results = []
    sender = threading.Thread(
        target=lambda: results.append(
            dan.upload_streaming(
                ids[CARDIOLOGY], "Slow Deck.html", valid_deck(3, BIG), UploadPlan(BIG, bytes_per_second=TEN_MEGABIT)
            )
        )
    )
    sender.start()
    slowest = 0.0
    while sender.is_alive():
        begun = time.monotonic()
        assert lamya.open(f"/f/{ids[WCBIP]}").status == 200
        slowest = max(slowest, time.monotonic() - begun)
        time.sleep(1.0)
    sender.join()

    (streamed,) = results
    assert streamed.reply is not None
    assert streamed.reply.json()["message"] == "Uploaded Slow Deck."
    assert time.monotonic() - started < TWO_MINUTES
    assert slowest < NOTICEABLE, slowest
