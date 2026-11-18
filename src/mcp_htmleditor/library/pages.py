"""Every page and text the web library mode adds (SPEC-0025, DEC-055): English constants, escaped output (DEC-029)."""

from __future__ import annotations

import html
import time
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

from .components import GOOGLE_MARK, LOGO, RIDGE, document
from .icons import icon
from .names import format_size

if TYPE_CHECKING:
    from .store import ActivityLine, FolderView, MemberView, PresentationView

PRODUCT_NAME: Final = "Slides"
SIGN_IN_LABEL: Final = "Sign in with Google"
ACCESS_DENIED_TEXT: Final = "Access denied."
SIGN_OUT_LABEL: Final = "Sign out"
THEME_LABEL: Final = "Switch theme"
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
REPLACE_LABEL: Final = "Replace"
DELETE_LABEL: Final = "Delete"
DELETE_QUESTION: Final = 'Delete "{name}"? This cannot be undone.'  # {name}: written by library.js
REPLACE_QUESTION: Final = 'A presentation named "{name}" already exists. Replace it?'  # {name}: written by library.js
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
    body = (
        '<div class="auth"><div class="auth-art">'
        f'<span class="brand" role="img" aria-label="{esc(PRODUCT_NAME)}">{LOGO}</span>'
        f'{RIDGE}</div><div class="auth-form"><div class="auth-box"><h1>{esc(PRODUCT_NAME)}</h1>{alert}'
        f'<a class="btn lg block" href="{SIGN_IN_START_PATH}?next={esc(destination)}">{GOOGLE_MARK}'
        f"{esc(SIGN_IN_LABEL)}</a></div></div></div>"
    )
    return document(esc(PRODUCT_NAME), body)


def access_denied() -> bytes:
    """The one refusal of a missing or forbidden target (DEC-023): the text and the ``Sign out`` form only."""
    body = f'<div class="center-note"><div class="card"><p>{esc(ACCESS_DENIED_TEXT)}</p>{_sign_out_form()}</div></div>'
    return document(esc(PRODUCT_NAME), body)


def library_unavailable() -> bytes:
    """The page while the stored library cannot be read (DEC-024): the message only, no name, no list, no form."""
    body = (
        f'<div class="center-note"><div class="card"><h1>{esc(PRODUCT_NAME)}</h1>'
        f'<p role="alert">{esc(LIBRARY_UNAVAILABLE)}</p></div></div>'
    )
    return document(esc(PRODUCT_NAME), body)


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


def deleted_line(name: str, folder: str) -> str:
    """The activity line of a presentation deletion (FR-NEW-049)."""
    return f'Deleted "{name}" from "{folder}"'


def replaced_line(name: str, folder: str) -> str:
    """The activity line of a replacement (FR-NEW-049)."""
    return f'Replaced "{name}" in "{folder}"'


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
    """The folders as a gallery in the given order, each a card with the person's role and its number of presentations;
    ``Administration`` for the administrator; ``You have no access to any folder yet.`` when there is none; the ``Sign
    out`` form (FR-NEW-015, FR-NEW-016)."""
    if folders:
        listing = f'<ul class="folders cards grid g3">{_folder_cards(folders)}</ul>'
    else:
        listing = f'<div class="card empty">{icon("folder")}<p>{esc(NO_FOLDER_YET)}</p></div>'
    hero = f'<div class="hero lib-hero"><h1>{esc(PRODUCT_NAME)}</h1>{RIDGE}</div>'
    return _app_page(f"{hero}{listing}", is_admin=is_admin)


def admin_page(
    folders: Sequence[FolderView], activity: Sequence[ActivityLine], *, members: Mapping[str, Sequence[MemberView]]
) -> bytes:
    """``All folders``, the section ``Folders`` (each folder a card with its ``Delete folder`` button and its
    ``Members`` from ``members`` keyed by folder id, the field ``Folder name`` and the button ``Create folder``, an
    alert ``library.js`` fills with a refusal), the deletion prompt, the section ``Activity`` (the lines in the given
    order or ``No activity yet.``) and the ``Sign out`` form (FR-NEW-050, FR-NEW-067).

    Each alert carries the texts ``library.js`` shows for an answer that is not JSON (a refusal page, the unavailable
    page), so every text stays here.
    """
    rows = "".join(_admin_row(folder, members.get(folder.id, ())) for folder in folders)
    listing = f'<ul class="folders cards col">{rows}</ul>' if rows else ""
    create = (
        f'<form id="create-folder"><label for="folder-name">{esc(FOLDER_NAME_LABEL)}</label> '
        '<input class="input" id="folder-name" name="name" type="text" autocomplete="off"> '
        f'<button class="btn primary" type="submit">{icon("plus")}{esc(CREATE_FOLDER_LABEL)}</button></form>'
        f"{_alert('create-folder-alert')}"
    )
    lines = "".join(
        f'<li>{_time(line.at)} <span class="actor">{esc(line.actor)}</span> <span class="text">{esc(line.text)}</span>'
        "</li>"
        for line in activity
    )
    log = (
        f'<ol class="activity">{lines}</ol>'
        if lines
        else f'<div class="card empty">{icon("clock")}<p>{esc(NO_ACTIVITY_YET)}</p></div>'
    )
    body = (
        f'{_back_link()}<div class="page-head"><h1>{esc(ADMINISTRATION_LABEL)}</h1></div>'
        f'<section id="folders"><h2>{esc(FOLDERS_LABEL)}</h2>{listing}{create}{_delete_folder_dialog()}</section>'
        f'<section id="activity"><h2>{esc(ACTIVITY_LABEL)}</h2>{log}</section>'
    )
    return _app_page(body, is_admin=True)


def folder_page(
    name: str, presentations: Sequence[PresentationView], *, can_upload: bool = False, folder_id: str = ""
) -> bytes:
    """The folder name, ``All folders`` back to the home page, the presentations as a gallery in the given order
    (cover, name, date, size) or ``This folder has no presentations yet.``, and the ``Sign out`` form (FR-NEW-018,
    FR-NEW-019).

    The date is ``<time datetime="<UTC ISO>">`` holding the UTC text; ``library.js`` rewrites it in the browser's
    zone (DEC-031), so the server never guesses the person's zone.
    """
    cards = "".join(_presentation_card(presentation, can_upload) for presentation in presentations)
    if cards:
        listing = f'<ul class="presentations cards grid g3">{cards}</ul>'
    else:
        listing = f'<div class="card empty">{icon("layout")}<p>{esc(NO_PRESENTATION_YET)}</p></div>'
    head = f'{_back_link()}<div class="page-head"><h1>{esc(name)}</h1></div>'
    body = f"{head}{_upload_control(can_upload, folder_id)}{listing}"
    return _app_page(body)


def _folder_cards(folders: Sequence[FolderView]) -> str:
    """One card per folder: the folder tile, a link by id holding the name, the person's role and the count."""
    return "".join(
        '<li class="card hover folder-card">'
        f'<span class="tile">{icon("folder")}</span><div class="body">{_folder_link(folder)}</div></li>'
        for folder in folders
    )


def _folder_link(folder: FolderView) -> str:
    return (
        f'<span class="name"><a href="/f/{esc(folder.id)}">{esc(folder.name)}</a></span> '
        f'<span class="meta"><span class="badge primary">{esc(ROLE_LABELS[folder.role])}</span> '
        f"<span>{esc(presentation_count(folder.count))}</span></span>"
    )


def presentation_count(count: int) -> str:
    """``1 presentation`` or ``N presentations`` on a folder card."""
    return f"{count} presentation" if count == 1 else f"{count} presentations"


def _presentation_card(presentation: PresentationView, can_delete: bool) -> str:
    """One card: the cover of the deck (its first picture, else the ridge), the name as the link that opens it, the
    date and the size, and ``Delete`` for a person who can edit. A cover that does not exist is hidden by
    ``library.js``; the ridge under it stays."""
    pid = esc(presentation.id)
    return (
        '<li class="card hover pres-card">'
        f'<div class="cover">{RIDGE}<img src="/cover/{pid}" alt="" loading="lazy"></div>'
        f'<div class="body"><span class="name"><a href="/open/{pid}">{esc(presentation.name)}</a></span>'
        f'<span class="meta">{_time(presentation.modified)} '
        f'<span class="size">{esc(format_size(presentation.size))}</span></span></div>'
        f'<div class="actions">{_delete_button(presentation, can_delete)}</div></li>'
    )


def _admin_row(folder: FolderView, members: Sequence[MemberView]) -> str:
    """A folder card of the administration: the link and role, ``Delete folder``, then its ``Members`` section (the
    members in the given order, each with its role chooser and ``Remove``, then the add form and its alert)."""
    folder_id = esc(folder.id)
    rows = "".join(
        f'<li><span class="email">{esc(member.email)}</span> '
        f'<select class="select member-role" aria-label="{esc(member_role_label(member.email))}" '
        f'data-folder-id="{folder_id}" data-email="{esc(member.email)}">{_role_options(member.role)}</select> '
        f'<button type="button" class="btn sm remove-member" data-folder-id="{folder_id}" '
        f'data-email="{esc(member.email)}">{esc(REMOVE_LABEL)}</button></li>'
        for member in members
    )
    add = (
        f'<form class="add-member" data-folder-id="{folder_id}">'
        f'<label for="member-email-{folder_id}">{esc(EMAIL_ADDRESS_LABEL)}</label> '
        f'<input class="input" id="member-email-{folder_id}" name="email" type="text" autocomplete="off"> '
        f'<label for="member-role-{folder_id}">{esc(ROLE_LABEL)}</label> '
        f'<select class="select" id="member-role-{folder_id}" name="role">{_role_options(None)}</select> '
        f'<button type="submit" class="btn primary">{icon("user")}{esc(ADD_MEMBER_LABEL)}</button></form>'
    )
    return (
        f'<li class="card admin-folder"><a class="name" href="/f/{folder_id}">{esc(folder.name)}</a> '
        f'<span class="badge primary">{esc(ROLE_LABELS[folder.role])}</span> '
        f'<button type="button" class="btn sm danger-text delete-folder" data-folder-id="{folder_id}">'
        f'{icon("trash", "sm")}{esc(DELETE_FOLDER_LABEL)}</button><section class="members" id="members-{folder_id}">'
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


def _delete_button(presentation: PresentationView, can_delete: bool) -> str:
    """``Delete`` on the card of a person who can edit; ``library.js`` asks the question and sends the request."""
    if not can_delete:
        return ""
    return (
        f'<button type="button" class="btn sm ghost danger-text delete-presentation" '
        f'data-presentation-id="{esc(presentation.id)}" data-name="{esc(presentation.name)}">'
        f"{icon('trash', 'sm')}{esc(DELETE_LABEL)}</button>"
    )


def _upload_control(can_upload: bool, folder_id: str) -> str:
    """``Upload`` for a person who can edit: a file field behind a primary button (``library.js`` sends the chosen file
    at once) and the status area that shows the message or the progress (FR-NEW-067)."""
    if not can_upload:
        return ""
    return (
        f'<section id="upload" class="upload-box" data-folder-id="{esc(folder_id)}">'
        '<input id="upload-file" class="sr-only" type="file" accept=".html,text/html" aria-label="Upload">'
        f'<label class="btn primary" for="upload-file">{icon("upload")}{esc(UPLOAD_LABEL)}</label>'
        f'<p role="status" id="upload-status" data-denied="{esc(ACCESS_DENIED_TEXT)}" '
        f'data-failed="{esc(UPLOAD_FAILED)}" data-only-html="{esc(ONLY_HTML)}" '
        f'data-too-large="{esc(TOO_LARGE)}"></p>{_confirm_dialog()}</section>'
    )


def _confirm_dialog() -> str:
    """The one question dialog of the folder page, for a name collision (``Replace`` and ``Cancel``, FR-NEW-033) and for
    a deletion (``Delete`` and ``Cancel``, FR-NEW-039); ``library.js`` writes the name into the question with
    ``textContent`` and the labels of the two buttons from these attributes."""
    return (
        '<dialog id="confirm-dialog" aria-labelledby="confirm-question"><form method="dialog">'
        f'<p id="confirm-question" data-replace="{esc(REPLACE_QUESTION)}" data-delete="{esc(DELETE_QUESTION)}"></p>'
        f'<div class="modal-f"><button type="button" class="btn primary" id="confirm-yes" '
        f'data-replace="{esc(REPLACE_LABEL)}" data-delete="{esc(DELETE_LABEL)}">{esc(REPLACE_LABEL)}</button>'
        f'<button type="button" class="btn" id="confirm-no">{esc(CANCEL_LABEL)}</button></div></form></dialog>'
    )


def _delete_folder_dialog() -> str:
    """The prompt of ``Delete folder``: the field labelled ``Type the folder name to confirm.``, ``Delete folder``
    and ``Cancel``, and its alert; ``library.js`` opens it for the folder of the pressed button."""
    return (
        '<dialog id="delete-folder"><form id="delete-folder-form">'
        f'<label for="delete-folder-name">{esc(DELETE_FOLDER_PROMPT)}</label>'
        '<input class="input" id="delete-folder-name" name="confirm" type="text" autocomplete="off">'
        f"{_alert('delete-folder-alert')}"
        f'<div class="modal-f"><button type="submit" class="btn danger">{esc(DELETE_FOLDER_LABEL)}</button>'
        f'<button type="button" class="btn" id="delete-folder-cancel">{esc(CANCEL_LABEL)}</button>'
        "</div></form></dialog>"
    )


def _back_link() -> str:
    return f'<nav class="crumbs"><a href="{HOME_PATH}">{icon("chevron-left", "sm")}{esc(ALL_FOLDERS_LABEL)}</a></nav>'


def _time(modified: float) -> str:
    """``<time>`` of a modified time: UTC ISO 8601 to the second, the text ``D Mon YYYY HH:MM`` in UTC."""
    utc = time.gmtime(modified)
    text = f"{utc.tm_mday} {MONTHS[utc.tm_mon - 1]} {utc.tm_year} {utc.tm_hour:02d}:{utc.tm_min:02d}"
    return f'<time datetime="{time.strftime("%Y-%m-%dT%H:%M:%SZ", utc)}">{text}</time>'


def _sign_out_form() -> str:
    return (
        f'<form method="post" action="{SIGN_OUT_PATH}"><button type="submit" class="btn sm">'
        f"{icon('logout', 'sm')}{esc(SIGN_OUT_LABEL)}</button></form>"
    )


def _bar(*, is_admin: bool) -> str:
    """The bar of every signed in page: the logo, ``Administration`` for the administrator, the theme button and the
    ``Sign out`` form. Its texts come after the page's own for a reader of the page text (see ``visible_texts``)."""
    administration = (
        f'<a class="btn sm ghost" href="{ADMINISTRATION_PATH}">{icon("shield", "sm")}{esc(ADMINISTRATION_LABEL)}</a>'
        if is_admin
        else ""
    )
    theme = (
        f'<button type="button" class="btn icon sm ghost theme" data-theme-toggle aria-label="{esc(THEME_LABEL)}">'
        f"{icon('moon').replace('ico', 'ico ico-moon', 1)}{icon('sun').replace('ico', 'ico ico-sun', 1)}</button>"
    )
    return (
        f'<header class="lib-bar"><span class="brand" role="img" aria-label="{esc(PRODUCT_NAME)}">{LOGO}</span>'
        f'<span class="grow"></span>{administration}{theme}{_sign_out_form()}</header>'
    )


def _app_page(body: str, *, is_admin: bool = False) -> bytes:
    return document(esc(PRODUCT_NAME), f'{_bar(is_admin=is_admin)}<main class="lib-main">{body}</main>')
