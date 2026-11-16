"""Roles, permissions and the route record of the web library mode (SPEC-0025, DEC-006, DEC-021)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Final, Literal

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
class Route:
    """One row of the table every later route joins; ``handler`` names a ``LibraryHandler`` method."""

    origin: Literal["library", "content"]
    method: str
    pattern: re.Pattern[str]
    permission: Permission
    handler: str


def authorize(role: Role | None, permission: Permission) -> bool:
    """``role`` is None for a person with a session but no role on the target."""
    if permission in {Permission.PUBLIC, Permission.SIGNED_IN}:
        return True
    return role in _ROLES_BY_PERMISSION[permission]
