"""Roles, permissions and the route record of the web library mode (SPEC-0025, DEC-006, DEC-021)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any, Final, Literal

from .pages import HTML_CONTENT_TYPE

if TYPE_CHECKING:
    from .signin import Accounts, Session
    from .store import Library

ADMIN_EMAIL: Final = "seb.morand@gmail.com"
JSON_CONTENT_TYPE: Final = "application/json"


class Role(StrEnum):
    ADMIN = "Admin"
    RW = "RW"
    RO = "RO"


class Permission(Enum):
    PUBLIC = "public"
    SIGNED_IN = "signed_in"
    VIEW = "view"
    EDIT = "edit"
    ADMINISTER = "administer"


_ROLES_BY_PERMISSION: Final[dict[Permission, frozenset[Role]]] = {
    Permission.VIEW: frozenset({Role.RO, Role.RW, Role.ADMIN}),
    Permission.EDIT: frozenset({Role.RW, Role.ADMIN}),
    Permission.ADMINISTER: frozenset({Role.ADMIN}),
}


@dataclass(frozen=True, slots=True)
class SetCookie:
    """A cookie an answer sets: base name (``lib``, ``lib-b``, ``d``), value, ``Max-Age`` (None: a browser session
    cookie) and ``Path``.

    The dispatcher turns the base name into the origin's name (on https ``__Host-`` for ``Path=/``, ``__Secure-``
    for a narrower path such as a grant's ``/d/<pid>/``) and adds the attributes.
    """

    base: str
    value: str
    max_age: int | None
    path: str = "/"


@dataclass(frozen=True, slots=True)
class Context:
    """What the dispatcher hands a route handler once the route is authorized.

    ``folder_id`` is the ``fid`` of the route's pattern, or the folder of its presentation ``pid`` (None for a route
    that names neither, or an unknown presentation) and ``role`` the person's role in it (Admin for the administrator
    whatever the route), both already checked by ``authorize`` (DEC-021). ``payload`` is the JSON object of a JSON
    route, read after ``authorize`` (DEC-019); empty otherwise. ``session`` is the live session of a library origin
    request, None on the content origin, where the person comes from a grant.
    """

    person_email: str | None
    query: Mapping[str, str]  # first value of each query parameter
    session_token: str | None
    browser_id: str | None
    accounts: Accounts
    library: Library
    folder_id: str | None = None
    role: Role | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    session: Session | None = None
    presentation_id: str | None = None
    library_origin: str = ""
    content_origin: str = ""


@dataclass(frozen=True, slots=True)
class Answer:
    """What a route handler returns; the dispatcher writes it with the protection headers."""

    status: int
    body: bytes = b""
    location: str | None = None
    cookies: tuple[SetCookie, ...] = ()
    content_type: str = HTML_CONTENT_TYPE


@dataclass(frozen=True, slots=True)
class EditorAnswer:
    """A deck route answered by the inherited editor method of that name through the DEC-003 hooks; ``is_framed``
    lets the content origin frame the answer (``X-Frame-Options: SAMEORIGIN``, ``frame-ancestors 'self'``)."""

    route: Literal["content", "content-frame", "download", "save", "shell", "static", "status"]
    is_framed: bool = False


@dataclass(frozen=True, slots=True)
class Route:
    """One row of the table every later route joins: matched on origin, method and ``pattern.fullmatch(path)``.

    A pattern naming a folder captures its id as the group ``fid``; the dispatcher reads the role there. A route with
    ``is_json`` takes a JSON object body: ``Content-Type: application/json`` is required with the ``Origin`` (DEC-022)
    and the body is read only once the permission holds. A content origin pattern captures the presentation id as
    ``pid``; ``is_navigation`` marks the routes a browser navigates to (the deck frame, the download), which send a
    refused person back to ``/open/<pid>`` instead of answering JSON (DEC-040).
    """

    origin: Literal["library", "content"]
    method: str
    pattern: re.Pattern[str]
    permission: Permission
    handler: Callable[[Context], Answer | EditorAnswer]
    is_json: bool = False
    is_navigation: bool = False


def json_answer(status: int, payload: Mapping[str, Any]) -> Answer:
    """A JSON answer (the JSON policy applies: it is not a page)."""
    return Answer(status, json.dumps(payload).encode(), content_type=JSON_CONTENT_TYPE)


def authorize(role: Role | None, permission: Permission) -> bool:
    """``role`` is None for a person with a session but no role on the target."""
    if permission in {Permission.PUBLIC, Permission.SIGNED_IN}:
        return True
    return role in _ROLES_BY_PERMISSION[permission]
