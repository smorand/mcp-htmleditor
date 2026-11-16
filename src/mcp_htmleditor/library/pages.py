"""Every page and text the web library mode adds (SPEC-0025, DEC-055): English constants, escaped output (DEC-029)."""

from __future__ import annotations

import html
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

from .names import format_size

if TYPE_CHECKING:
    from .store import ActivityLine, FolderView, PresentationView

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
FOLDER_NAME_REFUSED: Final = "Folder names use 1 to 60 letters, digits, spaces or hyphens."
INVALID_REQUEST_BODY: Final = "Invalid request body"
REQUEST_TOO_LARGE: Final = "Request too large"
MONTHS: Final = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
ROLE_LABELS: Final = {"Admin": ADMIN_LABEL, "RW": "Read and write", "RO": "Read only"}  # keyed by ``Role`` value
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


def home_page(folders: Sequence[FolderView], *, is_admin: bool) -> bytes:
    """The folders in the given order, each a link by id with the person's role; ``Administration`` for the
    administrator; ``You have no access to any folder yet.`` when there is none; the ``Sign out`` form."""
    administration = f'<nav><a href="{ADMINISTRATION_PATH}">{esc(ADMINISTRATION_LABEL)}</a></nav>' if is_admin else ""
    rows = _folder_rows(folders)
    listing = f'<ul class="folders">{rows}</ul>' if rows else f"<p>{esc(NO_FOLDER_YET)}</p>"
    return _page(f"<h1>{esc(PRODUCT_NAME)}</h1>{administration}{listing}{_sign_out_form()}")


def admin_page(folders: Sequence[FolderView], activity: Sequence[ActivityLine]) -> bytes:
    """``All folders``, the section ``Folders`` (the folders as on the home page, the field ``Folder name`` and the
    button ``Create folder``, an alert ``library.js`` fills with a refusal), the section ``Activity`` (the lines in
    the given order or ``No activity yet.``) and the ``Sign out`` form (FR-NEW-050, FR-NEW-067).

    The alert carries the texts ``library.js`` shows for an answer that is not JSON (a refusal page, the unavailable
    page), so every text stays here.
    """
    rows = _folder_rows(folders)
    listing = f'<ul class="folders">{rows}</ul>' if rows else ""
    create = (
        f'<form id="create-folder"><label for="folder-name">{esc(FOLDER_NAME_LABEL)}</label> '
        '<input id="folder-name" name="name" type="text" autocomplete="off"> '
        f'<button type="submit">{esc(CREATE_FOLDER_LABEL)}</button></form>'
        f'<p role="alert" id="create-folder-alert" data-denied="{esc(ACCESS_DENIED_TEXT)}" '
        f'data-unavailable="{esc(LIBRARY_UNAVAILABLE)}" hidden></p>'
    )
    lines = "".join(
        f'<li>{_time(line.at)} <span class="actor">{esc(line.actor)}</span> <span class="text">{esc(line.text)}</span>'
        "</li>"
        for line in activity
    )
    log = f'<ol class="activity">{lines}</ol>' if lines else f"<p>{esc(NO_ACTIVITY_YET)}</p>"
    return _page(
        f"{_back_link()}<h1>{esc(ADMINISTRATION_LABEL)}</h1>"
        f'<section id="folders"><h2>{esc(FOLDERS_LABEL)}</h2>{listing}{create}</section>'
        f'<section id="activity"><h2>{esc(ACTIVITY_LABEL)}</h2>{log}</section>{_sign_out_form()}'
    )


def folder_page(name: str, presentations: Sequence[PresentationView]) -> bytes:
    """The folder name, ``All folders`` back to the home page, the rows in the given order (name, date, size) or
    ``This folder has no presentations yet.``, and the ``Sign out`` form (FR-NEW-018, FR-NEW-019).

    The date is ``<time datetime="<UTC ISO>">`` holding the UTC text; ``library.js`` rewrites it in the browser's
    zone (DEC-031), so the server never guesses the person's zone.
    """
    rows = "".join(
        f'<li><span class="name">{esc(presentation.name)}</span> {_time(presentation.modified)} '
        f'<span class="size">{esc(format_size(presentation.size))}</span></li>'
        for presentation in presentations
    )
    listing = f'<ul class="presentations">{rows}</ul>' if rows else f"<p>{esc(NO_PRESENTATION_YET)}</p>"
    return _page(f"{_back_link()}<h1>{esc(name)}</h1>{listing}{_sign_out_form()}")


def _folder_rows(folders: Sequence[FolderView]) -> str:
    """One row per folder: a link by id holding the name, then the person's role."""
    return "".join(
        f'<li><a href="/f/{esc(folder.id)}">{esc(folder.name)}</a> <span>{esc(ROLE_LABELS[folder.role])}</span></li>'
        for folder in folders
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
