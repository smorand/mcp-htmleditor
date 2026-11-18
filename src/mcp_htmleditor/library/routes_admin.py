"""Library origin routes of the administration: the page, folder creation and deletion, members (SPEC-0025, DEC-019,
DEC-021, DEC-023, DEC-026, DEC-030).

Every row is ``ADMINISTER``: the dispatcher refuses anyone but the administrator before a body is read or a name is
checked (so a RW member who posts the role ``Admin`` gets ``Access denied.``); the handlers only validate the payload
and act. Member routes check the folder, then the address, then the role (DEC-019).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Final

from . import pages
from .access import Answer, Context, Permission, Role, Route, json_answer
from .names import NameRefused, check_email, check_folder_name
from .store import FolderMissing, NameMismatch, NameTaken

logger = logging.getLogger(__name__)

FOLDER_PATH: Final = r"/api/folders/(?P<fid>[0-9a-f]{32})"


def administration(context: Context) -> Answer:
    """The administration page: every folder in home page order, the 500 newest activity lines."""
    library = context.library
    folders = library.folders_for(context.person_email or "")
    return Answer(200, pages.admin_page(folders, library.activity(), members=library.members_by_folder()))


def create_folder(context: Context) -> Answer:
    """``{"name": str}``: ``201 {"ok": true, "id"}``, or ``400`` with the name rule or the duplicate message."""
    raw = context.payload.get("name")
    if not isinstance(raw, str):
        return _refused(pages.INVALID_REQUEST_BODY)
    try:
        name = check_folder_name(raw)
    except NameRefused:
        logger.warning("Refused POST /api/folders: folder name")
        return _refused(pages.FOLDER_NAME_REFUSED)
    try:
        folder_id = context.library.create_folder(name, context.person_email or "")
    except NameTaken:
        logger.warning("Refused POST /api/folders: duplicate folder name")
        return _refused(pages.folder_exists(name))
    logger.info("Created a folder")
    return json_answer(201, {"ok": True, "id": folder_id})


def delete_folder(context: Context) -> Answer:
    """``{"confirm": str}``: ``200 {"ok": true}`` once the folder, its presentations with their history and requests,
    and its members are gone; ``400`` with the mismatch text and nothing deleted; ``Access denied.`` for no folder."""
    confirm = context.payload.get("confirm")
    if not isinstance(confirm, str):
        return _refused(pages.INVALID_REQUEST_BODY)
    try:
        context.library.delete_folder(context.folder_id or "", confirm, context.person_email or "")
    except FolderMissing:
        return Answer(403, pages.access_denied())
    except NameMismatch:
        logger.warning("Refused POST /api/folders/<fid>/delete: name mismatch")
        return _refused(pages.NAME_MISMATCH)
    logger.info("Deleted a folder")
    return json_answer(200, {"ok": True})


def set_member(context: Context) -> Answer:
    """``{"email": str, "role": "RW" or "RO"}``: ``200 {"ok": true}`` once the address has that role in the folder
    (added, changed, or already so); ``400`` with the address or the role text and nothing changed; ``Access denied.``
    for no folder (FR-NEW-045, FR-NEW-046, FR-NEW-012)."""
    library = context.library
    folder_id = context.folder_id or ""
    if library.folder_name(folder_id) is None:
        return Answer(403, pages.access_denied())
    email = _checked_email(context.payload.get("email"))
    if email is None:
        logger.warning("Refused POST /api/folders/<fid>/members: email address")
        return _refused(pages.INVALID_EMAIL)
    role = context.payload.get("role")
    if not isinstance(role, str) or role not in pages.MEMBER_ROLES:
        logger.warning("Refused POST /api/folders/<fid>/members: role")
        return _refused(pages.INVALID_ROLE)
    try:
        library.set_member(folder_id, email, Role(role), context.person_email or "")
    except FolderMissing:  # deleted between the two reads
        return Answer(403, pages.access_denied())
    logger.info("Set a member role")
    return json_answer(200, {"ok": True})


def remove_member(context: Context) -> Answer:
    """``{"email": str}``: ``200 {"ok": true}`` once the address is no member of the folder (removed, or never
    listed); ``400`` with the address text; ``Access denied.`` for no folder (FR-NEW-047)."""
    library = context.library
    folder_id = context.folder_id or ""
    if library.folder_name(folder_id) is None:
        return Answer(403, pages.access_denied())
    email = _checked_email(context.payload.get("email"))
    if email is None:
        logger.warning("Refused POST /api/folders/<fid>/members/remove: email address")
        return _refused(pages.INVALID_EMAIL)
    try:
        library.remove_member(folder_id, email, context.person_email or "")
    except FolderMissing:
        return Answer(403, pages.access_denied())
    logger.info("Removed a member")
    return json_answer(200, {"ok": True})


def _checked_email(raw: Any) -> str | None:
    """The trimmed lower case address, None for anything that is not one valid address (a value that is no string
    included)."""
    if not isinstance(raw, str):
        return None
    try:
        return check_email(raw)
    except NameRefused:
        return None


def _refused(error: str) -> Answer:
    return json_answer(400, {"ok": False, "error": error})


ROUTES: tuple[Route, ...] = (
    Route("library", "GET", re.compile(r"/admin"), Permission.ADMINISTER, administration),
    Route("library", "POST", re.compile(r"/api/folders"), Permission.ADMINISTER, create_folder, is_json=True),
    Route("library", "POST", re.compile(f"{FOLDER_PATH}/delete"), Permission.ADMINISTER, delete_folder, is_json=True),
    Route("library", "POST", re.compile(f"{FOLDER_PATH}/members"), Permission.ADMINISTER, set_member, is_json=True),
    Route(
        "library",
        "POST",
        re.compile(f"{FOLDER_PATH}/members/remove"),
        Permission.ADMINISTER,
        remove_member,
        is_json=True,
    ),
)
