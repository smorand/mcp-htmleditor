"""Roles, permissions and the route record of the web library mode (SPEC-0025, DEC-006, DEC-021)."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Final, Literal

from .pages import HTML_CONTENT_TYPE

if TYPE_CHECKING:
    from .signin import Accounts
    from .store import Library

ADMIN_EMAIL: Final = "seb.morand@gmail.com"


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
    """A cookie an answer sets: base name (``lib``, ``lib-b``), value, ``Max-Age`` (None: a browser session cookie).

    The dispatcher turns the base name into the origin's name (``__Host-`` on https) and adds the attributes.
    """

    base: str
    value: str
    max_age: int | None


@dataclass(frozen=True, slots=True)
class Context:
    """What the dispatcher hands a route handler once the route is authorized."""

    person_email: str | None
    query: Mapping[str, str]  # first value of each query parameter
    session_token: str | None
    browser_id: str | None
    accounts: Accounts
    library: Library


@dataclass(frozen=True, slots=True)
class Answer:
    """What a route handler returns; the dispatcher writes it with the protection headers."""

    status: int
    body: bytes = b""
    location: str | None = None
    cookies: tuple[SetCookie, ...] = ()
    content_type: str = HTML_CONTENT_TYPE


@dataclass(frozen=True, slots=True)
class Route:
    """One row of the table every later route joins: matched on origin, method and ``pattern.fullmatch(path)``."""

    origin: Literal["library", "content"]
    method: str
    pattern: re.Pattern[str]
    permission: Permission
    handler: Callable[[Context], Answer]


def authorize(role: Role | None, permission: Permission) -> bool:
    """``role`` is None for a person with a session but no role on the target."""
    if permission in {Permission.PUBLIC, Permission.SIGNED_IN}:
        return True
    return role in _ROLES_BY_PERMISSION[permission]
