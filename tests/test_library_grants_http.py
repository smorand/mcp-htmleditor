"""US-0137: a grant follows a newer session of its address after the session ended by time (DEC-037)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from tests import library_support
from tests.library_support import CARDIOLOGY, CAROL, DAN, HEART_FAILURE, FakeGoogle, RunningLibrary, signed_in

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

SESSION_SECONDS = 2_592_000
DAY = 86_400
MODIFIED = datetime(2026, 11, 10, 9, 15, tzinfo=UTC)


def setup(library_server: START, fake_google: FakeGoogle):
    running = library_server(fake_google)
    ids = running.builder.standard()
    heart = running.builder.presentation(ids[CARDIOLOGY], HEART_FAILURE, size=4_096, modified=MODIFIED)
    dan = signed_in(running, fake_google, DAN)
    dan.open_presentation(heart.id)
    return running, heart, dan


def test_a_grant_follows_a_newer_session_of_its_address_within_a_day(
    library_server: START, fake_google: FakeGoogle
) -> None:
    running, heart, dan = setup(library_server, fake_google)
    running.clock.advance(SESSION_SECONDS + 1)
    assert dan.deck(heart.id, "status", x_editor="1").status == 401

    signed_in(running, fake_google, DAN)

    assert dan.deck(heart.id, "status", x_editor="1").status == 200
    assert dan.deck(heart.id, "status", x_editor="1").status == 200  # the rebound grant stays live


def test_a_grant_does_not_follow_a_session_of_another_address_or_after_a_day(
    library_server: START, fake_google: FakeGoogle
) -> None:
    running, heart, dan = setup(library_server, fake_google)
    running.clock.advance(SESSION_SECONDS + 1)
    signed_in(running, fake_google, CAROL)
    assert dan.deck(heart.id, "status", x_editor="1").status == 401

    running.clock.advance(DAY)
    signed_in(running, fake_google, DAN)

    reply = dan.deck(heart.id, "status", x_editor="1")
    assert reply.status == 401
    assert reply.json()["code"] == "session_expired"


def test_a_grant_ended_by_sign_out_never_revives(library_server: START, fake_google: FakeGoogle) -> None:
    running, heart, dan = setup(library_server, fake_google)
    dan.sign_out()
    signed_in(running, fake_google, DAN)

    assert dan.deck(heart.id, "status", x_editor="1").status == 401
