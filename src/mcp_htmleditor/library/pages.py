"""Every page and text the web library mode adds (SPEC-0025, DEC-055): English constants, escaped output (DEC-029)."""

from __future__ import annotations

import html
import time
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

from .names import format_size

if TYPE_CHECKING:
    from .store import ActivityLine, FolderView, MemberView, PresentationView

PRODUCT_NAME: Final = "Slides"
SIGN_IN_LABEL: Final = "Sign in with Google"
ACCESS_DENIED_TEXT: Final = "Access denied."
SIGN_OUT_LABEL: Final = "Sign out"
SIGN_IN_UNAVAILABLE: Final = "Sign-in is unavailable. Try again later."
ADMIN_LABEL: Final = "Admin"
ADMINISTRATION_LABEL: Final = "Administration"
NO_FOLDER_YET: Final = "You have no access to any folder yet."
LIBRARY_UNAVAILABLE: Final = "The library is unavailable. Try again later."
NO_PRESENTATION_YET: Final = "This folder has no presentations yet."
ALL_FOLDERS_LABEL: Final = "All folders"
FOLDERS_LABEL: Final = "Folders"
ACTIVITY_LABEL: Final = "Activity"
FOLDER_NAME_LABEL: Final = "Folder name"
CREATE_FOLDER_LABEL: Final = "Create folder"
NO_ACTIVITY_YET: Final = "No activity yet."
DELETE_FOLDER_LABEL: Final = "Delete folder"
DELETE_FOLDER_PROMPT: Final = "Type the folder name to confirm."
CANCEL_LABEL: Final = "Cancel"
NAME_MISMATCH: Final = "The name does not match. Nothing was deleted."
FOLDER_NAME_REFUSED: Final = "Folder names use 1 to 60 letters, digits, spaces or hyphens."
UPLOAD_LABEL: Final = "Upload"
ONLY_HTML: Final = "Only .html files are accepted."
UPLOAD_FAILED: Final = "The upload failed. Nothing was changed."
FILE_NAME_REFUSED: Final = "This file name is not allowed."
TOO_LARGE: Final = "The file is larger than 25 MB."
MEMBERS_LABEL: Final = "Members"
EMAIL_ADDRESS_LABEL: Final = "Email address"
ROLE_LABEL: Final = "Role"
ADD_MEMBER_LABEL: Final = "Add member"
REMOVE_LABEL: Final = "Remove"
INVALID_EMAIL: Final = "This is not a valid email address."
INVALID_ROLE: Final = "This is not a valid role."
SESSION_EXPIRED: Final = "Your session has expired. Sign in again to save."
EXPORT_FAILED: Final = "Export failed"  # a failure without an operating system reason (DEC-042)
INVALID_REQUEST_BODY: Final = "Invalid request body"
REQUEST_TOO_LARGE: Final = "Request too large"
MONTHS: Final = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
ROLE_LABELS: Final = {"Admin": ADMIN_LABEL, "RW": "Read and write", "RO": "Read only"}  # keyed by ``Role`` value
MEMBER_ROLES: Final = ("RW", "RO")  # the only roles a member can be given, in the order of the choosers (FR-NEW-012)
ADMINISTRATION_PATH: Final = "/admin"
STYLESHEET_PATH: Final = "/lib/library.css"
SCRIPT_PATH: Final = "/lib/library.js"
HOME_PATH: Final = "/"
SIGN_IN_START_PATH: Final = "/auth/start"
SIGN_OUT_PATH: Final = "/auth/logout"
HTML_CONTENT_TYPE: Final = "text/html; charset=utf-8"


def esc(text: str) -> str:
    """Every dynamic string of every page goes through this (FR-NEW-053)."""
    return html.escape(text, quote=True)


def sign_in_page(destination: str, message: str | None) -> bytes:
    """The only page a visitor sees: one link, ``Sign in with Google``, keeping the wanted address as ``next``."""
    alert = f'<p role="alert">{esc(message)}</p>' if message is not None else ""
    return _page(
        f'<h1>{esc(PRODUCT_NAME)}</h1>{alert}<p><a href="{SIGN_IN_START_PATH}?next={esc(destination)}">'
        f"{esc(SIGN_IN_LABEL)}</a></p>"
    )


def access_denied() -> bytes:
    """The one refusal of a missing or forbidden target (DEC-023): the text and the ``Sign out`` form only."""
    return _page(f"<p>{esc(ACCESS_DENIED_TEXT)}</p>{_sign_out_form()}")


def library_unavailable() -> bytes:
    """The page while the stored library cannot be read (DEC-024): the message only, no name, no list, no form."""
    return _page(f'<h1>{esc(PRODUCT_NAME)}</h1><p role="alert">{esc(LIBRARY_UNAVAILABLE)}</p>')


def folder_exists(name: str) -> str:
    """The refusal of a duplicate folder name, ``name`` as the administrator typed it, trimmed (FR-NEW-042)."""
    return f'A folder named "{name}" already exists.'


def created_folder_line(name: str) -> str:
    """The activity line of a folder creation (FR-NEW-049)."""
    return f'Created folder "{name}"'


def deleted_folder_line(name: str) -> str:
    """The activity line of a folder deletion (FR-NEW-049)."""
    return f'Deleted folder "{name}"'


def uploaded_line(name: str, folder: str) -> str:
    """The activity line of an upload (FR-NEW-049)."""
    return f'Uploaded "{name}" in "{folder}"'


def uploaded_message(name: str) -> str:
    """What the person sees after a successful upload (FR-NEW-028)."""
    return f"Uploaded {name}."


def added_member_line(email: str, role: str, folder: str) -> str:
    """The activity line of a new member (FR-NEW-049)."""
    return f'Added {email} as {role} to "{folder}"'


def changed_member_line(email: str, role: str, folder: str) -> str:
    """The activity line of a member given the other role (FR-NEW-049)."""
    return f'Changed {email} to {role} in "{folder}"'


def removed_member_line(email: str, folder: str) -> str:
    """The activity line of a removed member (FR-NEW-049)."""
    return f'Removed {email} from "{folder}"'


def member_role_label(email: str) -> str:
    """The name of a member's role chooser (DEC-053); ``Role`` alone names the chooser of the add form."""
    return f"{ROLE_LABEL} of {email}"


def home_page(folders: Sequence[FolderView], *, is_admin: bool) -> bytes:
    """The folders in the given order, each a link by id with the person's role; ``Administration`` for the
    administrator; ``You have no access to any folder yet.`` when there is none; the ``Sign out`` form."""
    administration = f'<nav><a href="{ADMINISTRATION_PATH}">{esc(ADMINISTRATION_LABEL)}</a></nav>' if is_admin else ""
    rows = _folder_rows(folders)
    listing = f'<ul class="folders">{rows}</ul>' if rows else f"<p>{esc(NO_FOLDER_YET)}</p>"
    return _page(f"<h1>{esc(PRODUCT_NAME)}</h1>{administration}{listing}{_sign_out_form()}")


def admin_page(
    folders: Sequence[FolderView], activity: Sequence[ActivityLine], *, members: Mapping[str, Sequence[MemberView]]
) -> bytes:
    """``All folders``, the section ``Folders`` (the folders as on the home page, each with a ``Delete folder``
    button and its ``Members`` from ``members`` keyed by folder id, the field ``Folder name`` and the button ``Create
    folder``, an alert ``library.js`` fills with a refusal),
    the deletion prompt, the section ``Activity`` (the lines in the given order or ``No activity yet.``) and the
    ``Sign out`` form (FR-NEW-050, FR-NEW-067).

    Each alert carries the texts ``library.js`` shows for an answer that is not JSON (a refusal page, the unavailable
    page), so every text stays here.
    """
    rows = "".join(_admin_row(folder, members.get(folder.id, ())) for folder in folders)
    listing = f'<ul class="folders">{rows}</ul>' if rows else ""
    create = (
        f'<form id="create-folder"><label for="folder-name">{esc(FOLDER_NAME_LABEL)}</label> '
        '<input id="folder-name" name="name" type="text" autocomplete="off"> '
        f'<button type="submit">{esc(CREATE_FOLDER_LABEL)}</button></form>{_alert("create-folder-alert")}'
    )
    lines = "".join(
        f'<li>{_time(line.at)} <span class="actor">{esc(line.actor)}</span> <span class="text">{esc(line.text)}</span>'
        "</li>"
        for line in activity
    )
    log = f'<ol class="activity">{lines}</ol>' if lines else f"<p>{esc(NO_ACTIVITY_YET)}</p>"
    return _page(
        f"{_back_link()}<h1>{esc(ADMINISTRATION_LABEL)}</h1>"
        f'<section id="folders"><h2>{esc(FOLDERS_LABEL)}</h2>{listing}{create}{_delete_folder_dialog()}</section>'
        f'<section id="activity"><h2>{esc(ACTIVITY_LABEL)}</h2>{log}</section>{_sign_out_form()}'
    )


def folder_page(
    name: str, presentations: Sequence[PresentationView], *, can_upload: bool = False, folder_id: str = ""
) -> bytes:
    """The folder name, ``All folders`` back to the home page, the rows in the given order (name, date, size) or
    ``This folder has no presentations yet.``, and the ``Sign out`` form (FR-NEW-018, FR-NEW-019).

    The date is ``<time datetime="<UTC ISO>">`` holding the UTC text; ``library.js`` rewrites it in the browser's
    zone (DEC-031), so the server never guesses the person's zone.
    """
    rows = "".join(
        f'<li><span class="name"><a href="/open/{esc(presentation.id)}">{esc(presentation.name)}</a></span> '
        f"{_time(presentation.modified)} "
        f'<span class="size">{esc(format_size(presentation.size))}</span></li>'
        for presentation in presentations
    )
    listing = f'<ul class="presentations">{rows}</ul>' if rows else f"<p>{esc(NO_PRESENTATION_YET)}</p>"
    return _page(
        f"{_back_link()}<h1>{esc(name)}</h1>{_upload_control(can_upload, folder_id)}{listing}{_sign_out_form()}"
    )


def _folder_rows(folders: Sequence[FolderView]) -> str:
    """One row per folder: a link by id holding the name, then the person's role."""
    return "".join(f"<li>{_folder_link(folder)}</li>" for folder in folders)


def _folder_link(folder: FolderView) -> str:
    return f'<a href="/f/{esc(folder.id)}">{esc(folder.name)}</a> <span>{esc(ROLE_LABELS[folder.role])}</span>'


def _admin_row(folder: FolderView, members: Sequence[MemberView]) -> str:
    """A folder row of the administration: the link and role, ``Delete folder``, then its ``Members`` section (the
    members in the given order, each with its role chooser and ``Remove``, then the add form and its alert)."""
    folder_id = esc(folder.id)
    rows = "".join(
        f'<li><span class="email">{esc(member.email)}</span> '
        f'<select class="member-role" aria-label="{esc(member_role_label(member.email))}" data-folder-id="{folder_id}"'
        f' data-email="{esc(member.email)}">{_role_options(member.role)}</select> '
        f'<button type="button" class="remove-member" data-folder-id="{folder_id}" data-email="{esc(member.email)}">'
        f"{esc(REMOVE_LABEL)}</button></li>"
        for member in members
    )
    add = (
        f'<form class="add-member" data-folder-id="{folder_id}">'
        f'<label for="member-email-{folder_id}">{esc(EMAIL_ADDRESS_LABEL)}</label> '
        f'<input id="member-email-{folder_id}" name="email" type="text" autocomplete="off"> '
        f'<label for="member-role-{folder_id}">{esc(ROLE_LABEL)}</label> '
        f'<select id="member-role-{folder_id}" name="role">{_role_options(None)}</select> '
        f'<button type="submit">{esc(ADD_MEMBER_LABEL)}</button></form>'
    )
    return (
        f'<li>{_folder_link(folder)} <button type="button" class="delete-folder" data-folder-id="{folder_id}">'
        f'{esc(DELETE_FOLDER_LABEL)}</button><section class="members" id="members-{folder_id}">'
        f'<h3>{esc(MEMBERS_LABEL)}</h3><ul class="members">{rows}</ul>{add}{_alert(f"members-alert-{folder_id}")}'
        "</section></li>"
    )


def _role_options(selected: str | None) -> str:
    """The two roles a member can be given; ``selected`` marks the member's current one."""
    return "".join(
        f'<option value="{role}"{" selected" if role == selected else ""}>{esc(ROLE_LABELS[role])}</option>'
        for role in MEMBER_ROLES
    )


def _alert(alert_id: str) -> str:
    """A hidden alert ``library.js`` fills with a refusal, holding the texts of the answers that are not JSON."""
    return (
        f'<p role="alert" id="{alert_id}" data-denied="{esc(ACCESS_DENIED_TEXT)}" '
        f'data-unavailable="{esc(LIBRARY_UNAVAILABLE)}" hidden></p>'
    )


def _upload_control(can_upload: bool, folder_id: str) -> str:
    """``Upload`` for a person who can edit: a labelled file field (``library.js`` sends the chosen file at once) and
    the status area that shows the message or the progress (FR-NEW-067)."""
    if not can_upload:
        return ""
    return (
        f'<section id="upload" data-folder-id="{esc(folder_id)}"><label for="upload-file">{esc(UPLOAD_LABEL)}</label> '
        '<input id="upload-file" type="file" accept=".html,text/html" aria-label="Upload">'
        f'<p role="status" id="upload-status" data-denied="{esc(ACCESS_DENIED_TEXT)}" '
        f'data-failed="{esc(UPLOAD_FAILED)}"></p></section>'
    )


def _delete_folder_dialog() -> str:
    """The prompt of ``Delete folder``: the field labelled ``Type the folder name to confirm.``, ``Delete folder``
    and ``Cancel``, and its alert; ``library.js`` opens it for the folder of the pressed button."""
    return (
        '<dialog id="delete-folder"><form id="delete-folder-form">'
        f'<p><label for="delete-folder-name">{esc(DELETE_FOLDER_PROMPT)}</label></p>'
        '<p><input id="delete-folder-name" name="confirm" type="text" autocomplete="off"></p>'
        f"{_alert('delete-folder-alert')}"
        f'<p><button type="submit">{esc(DELETE_FOLDER_LABEL)}</button> '
        f'<button type="button" id="delete-folder-cancel">{esc(CANCEL_LABEL)}</button></p></form></dialog>'
    )


def _back_link() -> str:
    return f'<nav><a href="{HOME_PATH}">{esc(ALL_FOLDERS_LABEL)}</a></nav>'


def _time(modified: float) -> str:
    """``<time>`` of a modified time: UTC ISO 8601 to the second, the text ``D Mon YYYY HH:MM`` in UTC."""
    utc = time.gmtime(modified)
    text = f"{utc.tm_mday} {MONTHS[utc.tm_mon - 1]} {utc.tm_year} {utc.tm_hour:02d}:{utc.tm_min:02d}"
    return f'<time datetime="{time.strftime("%Y-%m-%dT%H:%M:%SZ", utc)}">{text}</time>'


def _sign_out_form() -> str:
    return f'<form method="post" action="{SIGN_OUT_PATH}"><button type="submit">{esc(SIGN_OUT_LABEL)}</button></form>'


def _page(body: str) -> bytes:
    title = esc(PRODUCT_NAME)
    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>'
        f'<link rel="stylesheet" href="{STYLESHEET_PATH}"><script src="{SCRIPT_PATH}" defer></script></head>'
        f"<body>{body}</body></html>"
    ).encode()
