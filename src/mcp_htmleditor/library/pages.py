"""Every page and text the web library mode adds (SPEC-0025, DEC-055): English constants, escaped output (DEC-029)."""

from __future__ import annotations

import html
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from .store import FolderView

PRODUCT_NAME: Final = "Slides"
SIGN_IN_LABEL: Final = "Sign in with Google"
ACCESS_DENIED_TEXT: Final = "Access denied."
SIGN_OUT_LABEL: Final = "Sign out"
SIGN_IN_UNAVAILABLE: Final = "Sign-in is unavailable. Try again later."
ROLE_LABELS: Final = {"RW": "Read and write", "RO": "Read only"}
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


def home_page(folders: Sequence[FolderView]) -> bytes:
    """The person's folders, each a link by id with the person's role, and the ``Sign out`` form."""
    rows = "".join(
        f'<li><a href="/f/{esc(folder.id)}">{esc(folder.name)}</a> <span>{esc(ROLE_LABELS[folder.role])}</span></li>'
        for folder in folders
    )
    return _page(f"<h1>{esc(PRODUCT_NAME)}</h1><ul>{rows}</ul>{_sign_out_form()}")


def _sign_out_form() -> str:
    return f'<form method="post" action="{SIGN_OUT_PATH}"><button type="submit">{esc(SIGN_OUT_LABEL)}</button></form>'


def _page(body: str) -> bytes:
    title = esc(PRODUCT_NAME)
    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{title}</title></head>'
        f"<body>{body}</body></html>"
    ).encode()
