"""US-0149: the closing journeys that cross several features of the web library mode (SPEC-0025).

Spec tests: E2E-001, E2E-108, E2E-114, E2E-138. Nothing here is new product code: a journey that fails shows a defect of
an earlier story. The second channel is the operator view of the database (sessions, activity), never only a page.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from tests import library_support
from tests.library_support import (
    ADMIN,
    CARDIOLOGY,
    DAN,
    LAMYA,
    PNEUMO,
    WCBIP,
    FakeGoogle,
    LibraryReply,
    RunningLibrary,
    signed_in,
    valid_deck,
    visible_texts,
)

library_server = library_support.library_server
fake_google = library_support.fake_google
START = Callable[..., RunningLibrary]

QUARTERLY = "Quarterly Review"
ONCOLOGY = "Oncology 2030"
SIGN_IN = "Sign in with Google"
PRODUCT = "Slides"
FORBIDDEN_TEXTS = ("Access denied.", "Sign-in is unavailable. Try again later.")


def lines_of(running: RunningLibrary, google: FakeGoogle) -> list[tuple[str, str]]:
    """``(actor, text)`` of the activity list as the administrator reads it, newest first."""
    page = signed_in(running, google, ADMIN).open("/admin")
    return [(actor, text) for _when, actor, text in page.activity_lines()]


def test_e2e_001_a_member_signs_in_and_signs_out(library_server: START, fake_google: FakeGoogle) -> None:
    running = library_server(fake_google)
    folder = running.builder.folder(WCBIP)
    running.builder.member(folder, LAMYA, "RW")
    browser = running.browser()
    seen: list[LibraryReply] = []

    seen.append(browser.open("/"))
    assert visible_texts(seen[-1]) == [PRODUCT, SIGN_IN]
    seen.append(browser.sign_in(fake_google, None))  # she cancels the Google consent first: the sign in page again
    assert visible_texts(seen[-1]) == [PRODUCT, SIGN_IN]
    assert running.stored.sessions() == []
    home = browser.sign_in(fake_google, "Lamya.Chrif@Gmail.COM")
    seen.append(home)

    texts = visible_texts(home)
    assert texts == [PRODUCT, WCBIP, "Read and write", "Sign out"]
    assert "Administration" not in home.text
    assert not [reply for reply in fake_google.received if "password" in reply.path.lower()]
    assert browser.upload(folder, f"{QUARTERLY}.html", valid_deck()).status == 201
    assert lines_of(running, fake_google) == [(LAMYA, f'Uploaded "{QUARTERLY}" in "{WCBIP}"')]  # lower case actor
    seen.append(browser.sign_out())
    assert visible_texts(seen[-1]) == [PRODUCT, SIGN_IN]
    again = browser.open("/")
    seen.append(again)

    assert visible_texts(again) == [PRODUCT, SIGN_IN]
    assert WCBIP not in again.text
    for reply in seen:
        assert not any(text in reply.text for text in FORBIDDEN_TEXTS)
    assert browser.sign_in(fake_google, LAMYA).status == 200  # a second attempt after the cancel succeeds


def test_e2e_108_the_administrator_adds_a_member(library_server: START, fake_google: FakeGoogle) -> None:
    running = library_server(fake_google)
    ids = running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)
    dan = signed_in(running, fake_google, DAN)
    assert not [row for row in dan.open("/").folder_rows() if row[1] == PNEUMO]

    assert admin.add_member(ids[PNEUMO], DAN, "RW").status == 200

    home = dan.open("/")
    assert (ids[PNEUMO], PNEUMO, "Read and write") in home.folder_rows()
    assert 'for="upload-file"' in dan.open(f"/f/{ids[PNEUMO]}").text
    assert (f'Added {DAN} as RW to "{PNEUMO}"') in [text for _a, text in lines_of(running, fake_google)]
    assert admin.add_member(ids[PNEUMO], DAN, "RW").status == 200  # again: one entry, no new line
    assert admin.open("/admin").member_rows(ids[PNEUMO]) == [(DAN, "Read and write")]
    assert [text for _a, text in lines_of(running, fake_google)].count(f'Added {DAN} as RW to "{PNEUMO}"') == 1


def test_e2e_114_the_administrators_own_address_can_be_listed(library_server: START, fake_google: FakeGoogle) -> None:
    running = library_server(fake_google)
    ids = running.builder.standard()
    admin = signed_in(running, fake_google, ADMIN)

    assert admin.add_member(ids[PNEUMO], ADMIN, "RO").status == 200

    assert admin.open("/admin").member_rows(ids[PNEUMO]) == [(ADMIN, "Read only")]
    assert (ids[PNEUMO], PNEUMO, "Admin") in admin.open("/").folder_rows()
    assert admin.upload(ids[PNEUMO], f"{QUARTERLY}.html", valid_deck()).status == 201


def test_e2e_138_the_activity_list_records_every_kind_of_successful_action(
    library_server: START, fake_google: FakeGoogle
) -> None:
    running = library_server(fake_google)
    ids = running.builder.standard()
    dan = signed_in(running, fake_google, DAN)
    admin = signed_in(running, fake_google, ADMIN)

    assert dan.upload(ids[CARDIOLOGY], f"{QUARTERLY}.html", valid_deck(2)).status == 201
    assert dan.upload(ids[CARDIOLOGY], f"{QUARTERLY}.html", valid_deck(3), replace=True).status == 201
    listing = admin.open(f"/f/{ids[CARDIOLOGY]}").text
    found = re.search(r'/open/([0-9a-f]{32})">Quarterly Review<', listing)
    assert found is not None
    presentation_id = found[1]
    assert dan.delete_presentation(presentation_id).status == 200
    created = admin.post_json("/api/folders", {"name": ONCOLOGY})
    assert created.status == 201
    folder = next(row[0] for row in admin.open("/").folder_rows() if row[1] == ONCOLOGY)
    assert admin.add_member(folder, DAN, "RW").status == 200
    assert admin.add_member(folder, DAN, "RO").status == 200
    assert admin.remove_member(folder, DAN).status == 200
    assert admin.post_json(f"/api/folders/{folder}/delete", {"confirm": ONCOLOGY}).status == 200

    assert lines_of(running, fake_google) == [
        (ADMIN, f'Deleted folder "{ONCOLOGY}"'),
        (ADMIN, f'Removed {DAN} from "{ONCOLOGY}"'),
        (ADMIN, f'Changed {DAN} to RO in "{ONCOLOGY}"'),
        (ADMIN, f'Added {DAN} as RW to "{ONCOLOGY}"'),
        (ADMIN, f'Created folder "{ONCOLOGY}"'),
        (DAN, f'Deleted "{QUARTERLY}" from "{CARDIOLOGY}"'),
        (DAN, f'Replaced "{QUARTERLY}" in "{CARDIOLOGY}"'),
        (DAN, f'Uploaded "{QUARTERLY}" in "{CARDIOLOGY}"'),
    ]
