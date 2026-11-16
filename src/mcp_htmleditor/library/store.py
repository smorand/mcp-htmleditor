"""Library metadata in one SQLite file (SPEC-0025, DEC-025): the ``Database`` and the ``Library`` repository.

One connection per thread (``threading.local``), WAL, foreign keys on, 30 s busy timeout, writes under
``BEGIN IMMEDIATE``. The schema is the ordered ``MIGRATIONS`` tuple, applied by ``PRAGMA user_version``; each story
appends one entry and never edits an earlier one.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Final

from .access import ADMIN_EMAIL, Role
from .names import order_key

DIRECTORY_MODE: Final = 0o700
FILE_MODE: Final = 0o600
BUSY_TIMEOUT_MS: Final = 30_000

MIGRATIONS: Final[tuple[str, ...]] = (
    # 1 (US-0126): folders, members, login attempts, sessions
    """
    CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE folders(id TEXT PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE,
                         created_at REAL NOT NULL);
    CREATE TABLE members(folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE, email TEXT NOT NULL,
                         role TEXT NOT NULL CHECK (role IN ('RW','RO')), PRIMARY KEY (folder_id, email));
    CREATE INDEX members_email ON members(email);
    CREATE TABLE logins(state_hash TEXT PRIMARY KEY, nonce TEXT NOT NULL, verifier TEXT NOT NULL,
                        destination TEXT NOT NULL, browser_hash TEXT NOT NULL, created_at REAL NOT NULL);
    CREATE TABLE sessions(id_hash TEXT PRIMARY KEY, email TEXT NOT NULL, created_at REAL NOT NULL,
                          expires_at REAL NOT NULL);
    """,
)


@dataclass(frozen=True, slots=True)
class FolderView:
    """One folder of the home page: its id, its name and the person's role in it."""

    id: str
    name: str
    role: Role


class Database:
    """The library database file; created ``0600`` in a ``0700`` directory, migrated at construction."""

    # Test seam (DEC-032, like ``fileio.replace_file``): called before every new connection, a test sets it to raise
    # ``sqlite3.OperationalError`` to simulate an unreadable library. Production never sets it.
    connect_hook: ClassVar[Callable[[], None] | None] = None

    def __init__(self, path: Path) -> None:
        self.path = path
        self._local = threading.local()
        path.parent.mkdir(mode=DIRECTORY_MODE, parents=True, exist_ok=True)
        os.close(os.open(path, os.O_CREAT | os.O_WRONLY, FILE_MODE))  # SQLite gives its WAL files the same mode
        try:
            self.migrate()
        finally:
            self.release()

    def connect(self) -> sqlite3.Connection:
        """A new configured connection; one that fails while being configured (a file that is not a database) is
        closed before the error goes up, so nothing of it stays open or cached."""
        if Database.connect_hook is not None:
            Database.connect_hook()
        connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        except sqlite3.Error:
            connection.close()
            raise
        return connection

    def connection(self) -> sqlite3.Connection:
        """This thread's connection, opened on first use."""
        connection: sqlite3.Connection | None = getattr(self._local, "connection", None)
        if connection is None:
            connection = self._local.connection = self.connect()
        return connection

    def migrate(self) -> None:
        """Apply every migration above ``PRAGMA user_version``, each with its version bump, in one transaction."""
        with self.transaction(immediate=True) as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
                for statement in filter(str.strip, script.split(";")):
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version = {number}")

    def release(self) -> None:
        """Close this thread's connection (the handler calls it when its connection ends)."""
        connection: sqlite3.Connection | None = getattr(self._local, "connection", None)
        if connection is not None:
            self._local.connection = None
            connection.close()

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        """``BEGIN`` (``BEGIN IMMEDIATE`` for writes), then commit, or roll back on any exception."""
        connection = self.connection()
        connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        try:
            yield connection
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        connection.execute("COMMIT")


class Library:
    """Folders and members; roles are read from ``members`` on every call, never cached (DEC-018).

    The administrator is decided here and nowhere else: ``is_admin`` compares the normalized address with
    ``ADMIN_EMAIL``, and ``role_in`` and ``folders_for`` ask it before any member row (FR-NEW-011, FR-NEW-014).
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def folders_for(self, email: str) -> list[FolderView]:
        """The folders ``email`` can open with its role, in ``order_key`` order: every folder (Admin) for the
        administrator, the member rows for anyone else."""
        if self.is_admin(email):
            rows = self._database.connection().execute("SELECT id, name, ? FROM folders", (Role.ADMIN.value,))
        else:
            rows = self._database.connection().execute(
                "SELECT folders.id, folders.name, members.role FROM members JOIN folders ON folders.id ="
                " members.folder_id WHERE members.email = ?",
                (normalize_email(email),),
            )
        views = [FolderView(id=row[0], name=row[1], role=Role(row[2])) for row in rows.fetchall()]
        return sorted(views, key=lambda view: order_key(view.name))

    def is_admin(self, email: str) -> bool:
        """True for the administrator's address in any letter case; a look alike address is another address."""
        return normalize_email(email) == ADMIN_EMAIL

    def role_in(self, email: str, folder_id: str) -> Role | None:
        """Admin first whatever the member rows hold, else the member row of that folder, else None."""
        if self.is_admin(email):
            return Role.ADMIN
        row = (
            self._database.connection()
            .execute("SELECT role FROM members WHERE folder_id = ? AND email = ?", (folder_id, normalize_email(email)))
            .fetchone()
        )
        return Role(row[0]) if row is not None else None


def normalize_email(email: str) -> str:
    """The stored form of an address: trimmed and lower cased, nothing else (no dot removal, no domain rewriting)."""
    return email.strip().lower()
