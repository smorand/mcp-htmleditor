"""Library origin routes: sign in, sign out, home page (SPEC-0025, DEC-012 to DEC-017, DEC-021)."""

from __future__ import annotations

import logging
import re
from typing import Final

from . import pages
from .access import Answer, Context, Permission, Route, SetCookie
from .signin import BROWSER_COOKIE, SESSION_COOKIE, SESSION_SECONDS, SignInUnavailable, safe_destination

logger = logging.getLogger(__name__)

CONSENT_CANCELLED: Final = "access_denied"


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
    """The person's folders; an account with no role anywhere gets the ``Access denied.`` page."""
    folders = context.library.folders_for(context.person_email) if context.person_email else []
    if not folders:
        return Answer(403, pages.access_denied())
    return Answer(200, pages.home_page(folders))


ROUTES: tuple[Route, ...] = (
    Route("library", "GET", re.compile(r"/auth/start"), Permission.PUBLIC, sign_in_start),
    Route("library", "GET", re.compile(r"/auth/callback"), Permission.PUBLIC, sign_in_callback),
    Route("library", "POST", re.compile(r"/auth/logout"), Permission.SIGNED_IN, sign_out),
    Route("library", "GET", re.compile(r"/"), Permission.SIGNED_IN, home),
)
