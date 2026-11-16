"""Content origin routes of one presentation: enter, deck frame, content, download, status (SPEC-0025, DEC-037).

``GET /enter?t=<ticket>`` redeems the one time ticket ``/open/<pid>`` issued and sets the grant cookie scoped to
``/d/<pid>/``; every ``/d/<pid>/`` row is answered by the inherited editor method through the DEC-003 hooks once the
dispatcher resolved the grant, the presentation and the role. Any other path under ``/d/<pid>/`` (the DOCX export
and the files next to a deck included, DEC-044) is ``Access denied.`` for every role.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Final, Literal

from .access import Answer, Context, EditorAnswer, Permission, Route, SetCookie, json_answer
from .signin import GRANT_COOKIE

PID: Final = r"(?P<pid>[0-9a-f]{32})"
DENIED_CODE: Final = "denied"


def deck_path(presentation_id: str) -> str:
    """``/d/<pid>/``: the base of every route of a presentation and the ``Path`` of its grant cookie."""
    return f"/d/{presentation_id}/"


def denied() -> Answer:
    """The refusal of a deck route that is not a navigation: ``403 {"error": "Access denied.", "code": "denied"}``."""
    return json_answer(403, {"error": "Access denied.", "code": DENIED_CODE})


def enter(context: Context) -> Answer:
    """Redeem the ticket: the grant cookie and ``302 /d/<pid>/``, or ``302`` to the library home page."""
    grant = context.accounts.redeem_ticket(context.query.get("t", ""))
    if grant is None:
        return Answer(302, location=f"{context.library_origin}/")
    path = deck_path(grant.presentation_id)
    return Answer(302, location=path, cookies=(SetCookie(GRANT_COOKIE, grant.token, None, path=path),))


def inherited(
    route: Literal["content", "content-frame", "download", "status"], *, is_framed: bool = False
) -> Callable[[Context], EditorAnswer]:
    """The handler of a route the editor already answers (DEC-003)."""

    def answer(_context: Context) -> EditorAnswer:
        return EditorAnswer(route, is_framed=is_framed)

    return answer


def refuse(_context: Context) -> Answer:
    """Any other path under ``/d/<pid>/``, whatever the role."""
    return denied()


def _deck(route: str) -> re.Pattern[str]:
    return re.compile(f"/d/{PID}/{route}")


ROUTES: tuple[Route, ...] = (
    Route("content", "GET", re.compile(r"/enter"), Permission.PUBLIC, enter),
    Route(
        "content",
        "GET",
        _deck("content-frame"),
        Permission.VIEW,
        inherited("content-frame", is_framed=True),
        is_navigation=True,
    ),
    Route("content", "GET", _deck("status"), Permission.VIEW, inherited("status")),
    Route("content", "GET", _deck("content"), Permission.VIEW, inherited("content")),
    Route("content", "GET", _deck("download"), Permission.VIEW, inherited("download"), is_navigation=True),
    Route("content", "GET", _deck(".*"), Permission.VIEW, refuse),
    Route("content", "POST", _deck(".*"), Permission.VIEW, refuse),
)
