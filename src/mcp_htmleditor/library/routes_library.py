"""Library origin routes: public files, sign in, sign out, home and folder pages, opening a presentation (SPEC-0025,
DEC-011 to DEC-021, DEC-037)."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Final

from ..fileio import WriteError
from . import pages, uploads
from .access import JSON_CONTENT_TYPE, Answer, Context, Permission, Role, Route, SetCookie, authorize, json_answer
from .names import NameRefused, check_file_name
from .signin import BROWSER_COOKIE, SESSION_COOKIE, SESSION_SECONDS, SignInUnavailable, safe_destination
from .store import Collision, Replaced

logger = logging.getLogger(__name__)

CONSENT_CANCELLED: Final = "access_denied"
STATIC_DIR: Final = Path(__file__).resolve().parent.parent / "static"
NOT_FOUND_BODY: Final = json.dumps({"error": "Not found"}).encode()


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
    can_upload = context.role in {Role.ADMIN, Role.RW}
    return Answer(
        200,
        pages.folder_page(
            name, context.library.presentations_in(folder_id), can_upload=can_upload, folder_id=folder_id
        ),
    )


def _refuse(status: int, text: str) -> Answer:
    return json_answer(status, {"ok": False, "error": text})


def upload_presentation(context: Context) -> Answer:
    """``POST /api/folders/<fid>/presentations``: the checks in the order of FR-NEW-028, the body read only once the
    right, the extension, the name and the size hold (DEC-033). ``201`` with the message, ``400`` with the first
    problem, ``409`` with the colliding name, ``403`` ``Access denied.`` for a folder that does not exist."""
    folder_id = context.folder_id or ""
    if context.library.folder_name(folder_id) is None or context.read_body is None:
        return Answer(403, pages.access_denied())
    stem = _checked_stem(context)
    if isinstance(stem, Answer):
        return stem
    data = _read_upload(context)
    if isinstance(data, Answer):
        return data
    role = context.library.role_in(context.person_email or "", folder_id)  # the right may have ended meanwhile
    if not authorize(role, Permission.EDIT):
        logger.warning("Refused an upload at its end: no right")
        return Answer(403, pages.access_denied())
    return _store_upload(context, folder_id, stem, data)


def _store_upload(context: Context, folder_id: str, stem: str, data: bytes) -> Answer:
    """The validity check, then the store: ``201``, the first problem, the collision or a failed upload."""
    try:
        uploads.check_validity(data)
        replace = context.headers.get(uploads.REPLACE_HEADER) == "1"
        outcome = context.library.add_presentation(folder_id, stem, data, context.person_email or "", replace=replace)
    except uploads.UploadRefused as exc:
        return _refuse(400, str(exc))
    except (OSError, WriteError) as exc:
        logger.error("Upload failed: %s", type(exc).__name__)
        return _refuse(500, pages.UPLOAD_FAILED)
    if isinstance(outcome, Collision):
        return json_answer(409, {"ok": False, "collision": outcome.existing_name})
    logger.info("%s a presentation of %d bytes", "Replaced" if isinstance(outcome, Replaced) else "Uploaded", len(data))
    return json_answer(201, {"ok": True, "name": outcome.name, "message": pages.uploaded_message(outcome.name)})


def _checked_stem(context: Context) -> str | Answer:
    """The composed name without ``.html``, or the refusal of the extension and the name checks."""
    name = uploads.file_name(context.headers.get(uploads.NAME_HEADER, ""))
    if name is None:
        return _refuse(400, pages.FILE_NAME_REFUSED)
    if not name.lower().endswith(uploads.EXTENSION):
        return _refuse(400, pages.ONLY_HTML)
    try:
        return check_file_name(name)
    except NameRefused:
        return _refuse(400, pages.FILE_NAME_REFUSED)


def _read_upload(context: Context) -> bytes | Answer:
    """The size check, then the body: exactly the declared bytes, or a chunked body stopped at 26 214 401 bytes; a
    short body is a failed upload and a fifth concurrent upload is refused (DEC-033)."""
    try:
        if context.headers.get(uploads.ENCODING_HEADER) == "chunked":
            return _read_chunked(context)
        length = uploads.declared_length(context.headers.get(uploads.LENGTH_HEADER))
        if length > uploads.MAX_BYTES:
            return _refuse(413, pages.TOO_LARGE)
        read_body = context.read_body
        data = read_body(length) if read_body is not None else b""
    except uploads.UploadRefused as exc:
        return _refuse(400, str(exc))
    except uploads.UploadBusy:
        return _refuse(503, pages.UPLOAD_FAILED)
    return data if len(data) == length else _refuse(400, pages.UPLOAD_FAILED)


def _read_chunked(context: Context) -> bytes | Answer:
    read_chunked = context.read_chunked
    data = read_chunked(uploads.MAX_BYTES + 1) if read_chunked is not None else b""
    return _refuse(413, pages.TOO_LARGE) if len(data) > uploads.MAX_BYTES else data


def open_presentation(context: Context) -> Answer:
    """``VIEW`` already authorized on the presentation's folder: a one time ticket and ``302`` to ``/enter`` on the
    content origin; a presentation that does not exist, which the administrator's role does not rule out, is the
    same ``Access denied.`` as a forbidden one (DEC-023, DEC-037)."""
    presentation_id = context.presentation_id or ""
    if context.session is None or context.library.presentation(presentation_id) is None:
        return Answer(403, pages.access_denied())
    ticket = context.accounts.issue_ticket(context.session, presentation_id)
    return Answer(302, location=f"{context.content_origin}/enter?t={ticket}")


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
    Route("library", "GET", re.compile(r"/open/(?P<pid>[0-9a-f]{32})"), Permission.VIEW, open_presentation),
    Route(
        "library",
        "POST",
        re.compile(r"/api/folders/(?P<fid>[0-9a-f]{32})/presentations"),
        Permission.EDIT,
        upload_presentation,
        is_upload=True,
    ),
)
