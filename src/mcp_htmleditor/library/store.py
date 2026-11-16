"""Library metadata in one SQLite file (SPEC-0025, DEC-025): the ``Database`` and the ``Library`` repository.

One connection per thread (``threading.local``), WAL, foreign keys on, 30 s busy timeout, writes under
``BEGIN IMMEDIATE``. The schema is the ordered ``MIGRATIONS`` tuple, applied by ``PRAGMA user_version``; each story
appends one entry and never edits an earlier one.
"""

from __future__ import annotations

import os
import re
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
FILES_DIRECTORY: Final = "files"
PRESENTATION_SUFFIX: Final = ".html"
ID_PATTERN: Final = re.compile(r"[0-9a-f]{32}")
SECONDS_PER_MINUTE: Final = 60

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
    # 2 (US-0129): presentations; the bytes live in files/<folder id>/<presentation id>.html
    """
    CREATE TABLE presentations(id TEXT PRIMARY KEY,
                               folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
                               name TEXT NOT NULL, name_key TEXT NOT NULL, created_at REAL NOT NULL,
                               UNIQUE (folder_id, name_key));
    """,
)


@dataclass(frozen=True, slots=True)
class FolderView:
    """One folder of the home page: its id, its name and the person's role in it."""

    id: str
    name: str
    role: Role


@dataclass(frozen=True, slots=True)
class PresentationView:
    """One row of a folder page: id, name (without ``.html``), and the file's ``st_mtime`` and size in bytes."""

    id: str
    name: str
    modified: float
    size: int


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
        self._files = database.path.parent / FILES_DIRECTORY

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

    def folder_name(self, folder_id: str) -> str | None:
        """The name of the folder, None when no folder has this id."""
        row = self._database.connection().execute("SELECT name FROM folders WHERE id = ?", (folder_id,)).fetchone()
        return str(row[0]) if row is not None else None

    def is_admin(self, email: str) -> bool:
        """True for the administrator's address in any letter case; a look alike address is another address."""
        return normalize_email(email) == ADMIN_EMAIL

    def presentation_path(self, folder_id: str, presentation_id: str) -> Path:
        """``files/<folder id>/<presentation id>.html``, built from two ids that each match ``^[0-9a-f]{32}$``
        (DEC-025); any other value raises ``ValueError`` before a path exists."""
        for value in (folder_id, presentation_id):
            if not ID_PATTERN.fullmatch(value):
                raise ValueError("not a library id")
        return self._files / folder_id / f"{presentation_id}{PRESENTATION_SUFFIX}"

    def presentations_in(self, folder_id: str) -> list[PresentationView]:
        """The presentations of a folder from one query and one ``stat`` each, newest minute first, then
        ``order_key`` (accents and case ignored, then the exact name, DEC-031); a missing file is an ``OSError``."""
        rows = (
            self._database.connection()
            .execute("SELECT id, name FROM presentations WHERE folder_id = ?", (folder_id,))
            .fetchall()
        )
        views = []
        for presentation_id, name in rows:
            status = self.presentation_path(folder_id, presentation_id).stat()
            views.append(PresentationView(presentation_id, name, status.st_mtime, status.st_size))
        return sorted(views, key=lambda view: (-(int(view.modified) // SECONDS_PER_MINUTE), order_key(view.name)))

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
