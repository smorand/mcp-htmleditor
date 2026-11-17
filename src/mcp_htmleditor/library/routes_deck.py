"""Content origin routes of one presentation: enter, shell, static files, deck frame, content, download, status
(SPEC-0025, DEC-037, DEC-038).

``GET /enter?t=<ticket>`` redeems the one time ticket ``/open/<pid>`` issued and sets the grant cookie scoped to
``/d/<pid>/``; every ``/d/<pid>/`` row is answered by the inherited editor method through the DEC-003 hooks once the
dispatcher resolved the grant, the presentation and the role. Any other path under ``/d/<pid>/`` (the DOCX export
and the files next to a deck included, DEC-044) is ``Access denied.`` for every role.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Callable
from typing import Final, Literal

from .access import Answer, Context, EditorAnswer, Permission, Role, Route, SetCookie, json_answer
from .signin import GRANT_COOKIE

SHELL_FRAME: Final = 'src="/content-frame"'
SHELL_DOWNLOAD: Final = 'href="/download"'
SHELL_SCRIPT_ANCHOR: Final = "<script src="
LIBRARY_SCRIPT: Final = '<script src="/static/editor-library.js"></script>'
READ_ONLY_STYLE: Final = (
    "<style>#edit-mode-btn,#undo-btn,#redo-btn,#requests-toggle,#ask-ai-btn,#notes-btn,#toolbar-slide-actions,"
    "#toolbar-doc-actions,#export-docx-btn,#requests-side,#ask-ai-panel,#notes-panel{display:none !important}</style>"
)
PID: Final = r"(?P<pid>[0-9a-f]{32})"
DENIED_CODE: Final = "denied"
DENIED_PAYLOAD: Final = {"error": "Access denied.", "code": DENIED_CODE}


def deck_path(presentation_id: str) -> str:
    """``/d/<pid>/``: the base of every route of a presentation and the ``Path`` of its grant cookie."""
    return f"/d/{presentation_id}/"


def denied() -> Answer:
    """The refusal of a deck route that is not a navigation: ``403 {"error": "Access denied.", "code": "denied"}``."""
    return json_answer(403, DENIED_PAYLOAD)


def enter(context: Context) -> Answer:
    """Redeem the ticket: the grant cookie and ``302 /d/<pid>/``, or ``302`` to the library home page."""
    grant = context.accounts.redeem_ticket(context.query.get("t", ""))
    if grant is None:
        return Answer(302, location=f"{context.library_origin}/")
    path = deck_path(grant.presentation_id)
    return Answer(302, location=path, cookies=(SetCookie(GRANT_COOKIE, grant.token, None, path=path),))


def library_shell(editor_html: str, presentation_id: str, library_origin: str, role: Role | None = None) -> str:
    """The shell of one presentation (DEC-038): ``editor.html`` with the frame and the download link under
    ``/d/<pid>`` and the meta and script of ``editor-library.js`` inserted before the first script."""
    base = f"/d/{presentation_id}"
    is_read_only = role is Role.RO
    config = json.dumps({"base": base, "readOnly": is_read_only, "library": library_origin}, separators=(",", ":"))
    meta = f"<meta name=\"editor-config\" content='{html.escape(config, quote=True)}'>{LIBRARY_SCRIPT}"
    if is_read_only:
        meta += READ_ONLY_STYLE
    shell = editor_html.replace(SHELL_FRAME, f'src="{base}/content-frame"', 1)
    shell = shell.replace(SHELL_DOWNLOAD, f'href="{base}/download"', 1)
    return shell.replace(SHELL_SCRIPT_ANCHOR, meta + SHELL_SCRIPT_ANCHOR, 1)


def inherited(
    route: Literal["content", "content-frame", "download", "save", "shell", "static", "status"],
    *,
    is_framed: bool = False,
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
    Route("content", "GET", re.compile(r"/static/[^/]+"), Permission.PUBLIC, inherited("static")),
    Route("content", "GET", _deck(""), Permission.VIEW, inherited("shell"), is_navigation=True),
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
    Route("content", "POST", _deck("content"), Permission.EDIT, inherited("save"), is_json=True),
    Route("content", "GET", _deck(".*"), Permission.VIEW, refuse),
    Route("content", "POST", _deck(".*"), Permission.VIEW, refuse),
)
