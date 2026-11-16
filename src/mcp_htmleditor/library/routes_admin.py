"""Library origin routes of the administration: the page, folder creation and deletion (SPEC-0025, DEC-019, DEC-021,
DEC-023, DEC-026, DEC-030).

Every row is ``ADMINISTER``: the dispatcher refuses anyone but the administrator before a body is read or a name is
checked; the handlers only validate the payload and act.
"""

from __future__ import annotations

import logging
import re

from . import pages
from .access import Answer, Context, Permission, Route, json_answer
from .names import NameRefused, check_folder_name
from .store import FolderMissing, NameMismatch, NameTaken

logger = logging.getLogger(__name__)


def administration(context: Context) -> Answer:
    """The administration page: every folder in home page order, the 500 newest activity lines."""
    library = context.library
    return Answer(200, pages.admin_page(library.folders_for(context.person_email or ""), library.activity()))


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


def _refused(error: str) -> Answer:
    return json_answer(400, {"ok": False, "error": error})


ROUTES: tuple[Route, ...] = (
    Route("library", "GET", re.compile(r"/admin"), Permission.ADMINISTER, administration),
    Route("library", "POST", re.compile(r"/api/folders"), Permission.ADMINISTER, create_folder, is_json=True),
    Route(
        "library",
        "POST",
        re.compile(r"/api/folders/(?P<fid>[0-9a-f]{32})/delete"),
        Permission.ADMINISTER,
        delete_folder,
        is_json=True,
    ),
)
