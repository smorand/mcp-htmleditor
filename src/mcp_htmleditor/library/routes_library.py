"""Library origin routes: public files, sign in, sign out, home and folder pages (SPEC-0025, DEC-011 to DEC-021)."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Final

from . import pages
from .access import Answer, Context, Permission, Route, SetCookie
from .signin import BROWSER_COOKIE, SESSION_COOKIE, SESSION_SECONDS, SignInUnavailable, safe_destination

logger = logging.getLogger(__name__)

CONSENT_CANCELLED: Final = "access_denied"
STATIC_DIR: Final = Path(__file__).resolve().parent.parent / "static"
NOT_FOUND_BODY: Final = json.dumps({"error": "Not found"}).encode()
JSON_CONTENT_TYPE: Final = "application/json"


def static_file(name: str, media_type: str) -> Callable[[Context], Answer]:
    """The handler of one public file of ``static/`` (DEC-011); ``404`` JSON while the file is not shipped."""

    def serve(_context: Context) -> Answer:
        path = STATIC_DIR / name
        if not path.is_file():
            logger.warning("Refused GET /lib/%s: not served", name)
            return Answer(404, NOT_FOUND_BODY, content_type=JSON_CONTENT_TYPE)
        return Answer(200, path.read_bytes(), content_type=media_type)

    return serve


def sign_in_start(context: Context) -> Answer:
    """``302`` to Google; the browser id cookie is set when the browser had none (DEC-013)."""
    destination = safe_destination(context.query.get("next"))
    try:
        url, browser_id = context.accounts.begin_login(context.browser_id, destination)
    except SignInUnavailable as exc:
        logger.warning("Sign in refused: %s", exc)
        return Answer(200, pages.sign_in_page(destination, pages.SIGN_IN_UNAVAILABLE))
    cookies = () if browser_id == context.browser_id else (SetCookie(BROWSER_COOKIE, browser_id, None),)
    return Answer(302, location=url, cookies=cookies)


def sign_in_callback(context: Context) -> Answer:
    """Google's answer: a session and ``303`` to the stored destination, or the sign in page (DEC-016)."""
    error, state, code = (context.query.get(name) for name in ("error", "state", "code"))
    if error == CONSENT_CANCELLED:
        return Answer(200, pages.sign_in_page("/", None))
    try:
        if error is not None or not state or not code:
            raise SignInUnavailable("Google reported a failure" if error is not None else "incomplete answer")
        new = context.accounts.finish_login(state, code, context.browser_id)
    except SignInUnavailable as exc:
        logger.warning("Sign in refused: %s", exc)
        return Answer(200, pages.sign_in_page("/", pages.SIGN_IN_UNAVAILABLE))
    return Answer(303, location=new.destination, cookies=(SetCookie(SESSION_COOKIE, new.token, SESSION_SECONDS),))


def sign_out(context: Context) -> Answer:
    """End this browser's session (the row is deleted), clear both cookies, ``303 /`` (DEC-017)."""
    if context.session_token is not None:
        context.accounts.end_session(context.session_token)
    cleared = (SetCookie(SESSION_COOKIE, "", 0), SetCookie(BROWSER_COOKIE, "", 0))
    return Answer(303, location="/", cookies=cleared)


def home(context: Context) -> Answer:
    """The person's folders (every folder for the administrator, who also gets ``Administration``); an account
    with no role anywhere gets the ``Access denied.`` page (FR-NEW-003, FR-NEW-016)."""
    email = context.person_email or ""
    is_admin = context.library.is_admin(email)
    folders = context.library.folders_for(email)
    if not folders and not is_admin:
        return Answer(403, pages.access_denied())
    return Answer(200, pages.home_page(folders, is_admin=is_admin))


def folder(context: Context) -> Answer:
    """The folder page (``VIEW`` already authorized on ``fid``); a folder that does not exist, which the
    administrator's role does not rule out, is the same ``Access denied.`` as a forbidden one (DEC-023)."""
    folder_id = context.folder_id or ""
    name = context.library.folder_name(folder_id)
    if name is None:
        return Answer(403, pages.access_denied())
    return Answer(200, pages.folder_page(name, context.library.presentations_in(folder_id)))


ROUTES: tuple[Route, ...] = (
    Route(
        "library", "GET", re.compile(r"/lib/library\.css"), Permission.PUBLIC, static_file("library.css", "text/css")
    ),
    Route(
        "library",
        "GET",
        re.compile(r"/lib/library\.js"),
        Permission.PUBLIC,
        static_file("library.js", "application/javascript"),
    ),
    Route("library", "GET", re.compile(r"/auth/start"), Permission.PUBLIC, sign_in_start),
    Route("library", "GET", re.compile(r"/auth/callback"), Permission.PUBLIC, sign_in_callback),
    Route("library", "POST", re.compile(r"/auth/logout"), Permission.SIGNED_IN, sign_out),
    Route("library", "GET", re.compile(r"/"), Permission.SIGNED_IN, home),
    Route("library", "GET", re.compile(r"/f/(?P<fid>[0-9a-f]{32})"), Permission.VIEW, folder),
)
