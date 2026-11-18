"""Library metadata in one SQLite file (SPEC-0025, DEC-025): the ``Database`` and the ``Library`` repository.

One connection per thread (``threading.local``), WAL, foreign keys on, 30 s busy timeout, writes under
``BEGIN IMMEDIATE``. The schema is the ordered ``MIGRATIONS`` tuple, applied by ``PRAGMA user_version``; each story
appends one entry and never edits an earlier one.
"""

from __future__ import annotations

import logging
import math
import os
import re
import secrets
import shutil
import sqlite3
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

from ..fileio import atomic_write
from ..request_store import RequestStore
from ..tracing import trace_span
from . import pages
from .access import ADMIN_EMAIL, Role
from .covers import Cover, first_cover
from .names import compose, name_key, order_key

if TYPE_CHECKING:
    from .seed import SeedPresentation

logger = logging.getLogger(__name__)

DIRECTORY_MODE: Final = 0o700
FILE_MODE: Final = 0o600
BUSY_TIMEOUT_MS: Final = 30_000
FILES_DIRECTORY: Final = "files"
PRESENTATION_SUFFIX: Final = ".html"
ID_PATTERN: Final = re.compile(r"[0-9a-f]{32}")
SECONDS_PER_MINUTE: Final = 60
COVERS_KEPT: Final = 64  # cover pictures kept in memory
ACTIVITY_KEPT: Final = 500  # the newest lines shown and kept (FR-NEW-050)
ID_BYTES: Final = 16  # a folder id is 32 hex digits

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
    # 3 (US-0130): the activity list, one row per successful action, the 500 newest kept
    """
    CREATE TABLE activity(id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, actor TEXT NOT NULL,
                          text TEXT NOT NULL);
    """,
    # 4 (US-0133): one time tickets and per presentation grants, both gone with their session (DEC-037); no foreign
    # key to presentations: a grant for a deleted presentation answers Access denied
    """
    CREATE TABLE tickets(ticket_hash TEXT PRIMARY KEY,
                         session_id_hash TEXT NOT NULL REFERENCES sessions(id_hash) ON DELETE CASCADE,
                         presentation_id TEXT NOT NULL, created_at REAL NOT NULL);
    CREATE TABLE grants(token_hash TEXT PRIMARY KEY,
                        session_id_hash TEXT NOT NULL REFERENCES sessions(id_hash) ON DELETE CASCADE,
                        presentation_id TEXT NOT NULL, created_at REAL NOT NULL);
    """,
)


class NameTaken(Exception):  # noqa: N818 - a domain outcome, not an error of the program
    """A folder whose name is the same without regard to case already exists (the ``name_key`` constraint)."""


class NameMismatch(Exception):  # noqa: N818 - a domain outcome, not an error of the program
    """The retyped name, composed, differs from the folder name in some character (FR-NEW-044)."""


class FolderMissing(Exception):  # noqa: N818 - a domain outcome, not an error of the program
    """No folder has this id."""


class PresentationMissing(Exception):  # noqa: N818 - a domain outcome, not an error of the program
    """No presentation has this id (never existed, or already deleted)."""


@dataclass(frozen=True, slots=True)
class Added:
    """The outcome of a stored upload: the new presentation's id and name."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Collision:
    """The outcome of an upload whose name is taken in the folder: the existing name, as stored."""

    existing_name: str


@dataclass(frozen=True, slots=True)
class Replaced:
    """The outcome of a replacement: the existing presentation keeps its id and its name."""

    id: str
    name: str


Outcome = Added | Collision | Replaced


@dataclass(frozen=True, slots=True)
class FolderView:
    """One folder of the home page: its id, its name and the person's role in it."""

    id: str
    name: str
    role: Role
    count: int = 0


@dataclass(frozen=True, slots=True)
class MemberView:
    """One member of a folder on the administration page: the stored lower case address and its role (RW or RO)."""

    email: str
    role: Role


@dataclass(frozen=True, slots=True)
class ActivityLine:
    """One line of the activity list: when (``at``, the injected clock), who (lower case address), what."""

    at: float
    actor: str
    text: str


@dataclass(frozen=True, slots=True)
class PresentationView:
    """One row of a folder page: id, name (without ``.html``), and the file's ``st_mtime`` and size in bytes."""

    id: str
    name: str
    modified: float
    size: int


@dataclass(frozen=True, slots=True)
class PresentationRow:
    """A stored presentation: its id, its folder's id and its name (without ``.html``)."""

    id: str
    folder_id: str
    name: str


@dataclass(frozen=True, slots=True)
class InventoryRow:
    """One stored presentation for the operator: folder name, presentation name, stored file and its size."""

    folder: str
    presentation: str
    path: Path
    bytes: int


def read_inventory(connection: sqlite3.Connection, files_dir: Path) -> list[InventoryRow]:
    """Every presentation of the library with its stored file, by folder name then presentation name (character
    code order, like the operator's tools); one query and one ``stat`` each, nothing is written (DEC-051)."""
    rows = connection.execute(
        "SELECT folders.name, presentations.name, folders.id, presentations.id FROM presentations"
        " JOIN folders ON folders.id = presentations.folder_id ORDER BY folders.name, presentations.name"
    ).fetchall()
    found = []
    for folder, presentation, folder_id, presentation_id in rows:
        if not (ID_PATTERN.fullmatch(folder_id) and ID_PATTERN.fullmatch(presentation_id)):
            continue  # a damaged row never becomes a path
        path = files_dir / folder_id / f"{presentation_id}{PRESENTATION_SUFFIX}"
        found.append(InventoryRow(str(folder), str(presentation), path, path.stat().st_size if path.is_file() else 0))
    return found


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
    """Folders, members and the activity list; roles are read from ``members`` on every call, never cached (DEC-018).

    The administrator is decided here and nowhere else: ``is_admin`` compares the normalized address with
    ``ADMIN_EMAIL``, and ``role_in`` and ``folders_for`` ask it before any member row (FR-NEW-011, FR-NEW-014).
    Every successful action writes its activity line in its own transaction (``record``, DEC-030); ``clock`` dates
    rows and lines.
    """

    def __init__(self, database: Database, clock: Callable[[], float], *, state_dir: Path) -> None:
        self._database = database
        self._clock = clock
        self._files = database.path.parent / FILES_DIRECTORY
        self._records = RequestStore(state_dir)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._covers: dict[str, tuple[tuple[int, int], Cover | None]] = {}

    def add_presentation(self, folder_id: str, name: str, data: bytes, actor: str, *, replace: bool = False) -> Outcome:
        """Store ``data`` as the presentation ``name`` of the folder and write its line ``Uploaded "<name>" in
        "<folder>"`` (FR-NEW-028, FR-NEW-049, DEC-027, DEC-054).

        ``name`` is checked and composed already. The bytes are written first, to a new random id, outside any
        transaction (a slow write never holds the database); then one ``BEGIN IMMEDIATE`` looks the name key up and
        inserts the row and the line. A taken name removes the new file and returns ``Collision``; any failure
        removes it too and the exception goes on, so a failed upload leaves nothing. ``FolderMissing`` when the
        folder is gone. Time O(n) in the size of the file for the write.

        With ``replace`` and a name key that exists, the presentation is replaced instead (DEC-027, DEC-035): under
        its lock, ``atomic_write(..., reason="replace")`` swaps the bytes in one step and keeps the previous ones in the
        history, then a short transaction writes ``Replaced "<name>" in "<folder>"`` (only when the bytes changed). The
        presentation keeps its id, its name, its requests and its suggestions. A name that vanished meanwhile is added.
        """
        if replace and (replaced := self._replace_presentation(folder_id, name, data, actor)) is not None:
            return replaced
        presentation_id = secrets.token_hex(ID_BYTES)
        path = self.presentation_path(folder_id, presentation_id)
        with trace_span("library.upload", {"file.size": len(data)}):
            path.parent.mkdir(mode=DIRECTORY_MODE, parents=True, exist_ok=True)
            atomic_write(path, data)
            path.chmod(FILE_MODE)
            try:
                with self._database.transaction(immediate=True) as connection:
                    folder_name = _folder_name_in(connection, folder_id)
                    taken = connection.execute(
                        "SELECT name FROM presentations WHERE folder_id = ? AND name_key = ?",
                        (folder_id, name_key(name)),
                    ).fetchone()
                    if taken is None:
                        connection.execute(
                            "INSERT INTO presentations(id, folder_id, name, name_key, created_at)"
                            " VALUES (?, ?, ?, ?, ?)",
                            (presentation_id, folder_id, name, name_key(name), self._clock()),
                        )
                        self.record(connection, actor, pages.uploaded_line(name, folder_name))
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        if taken is not None:
            path.unlink(missing_ok=True)
            return Collision(str(taken[0]))
        return Added(presentation_id, name)

    def _replace_presentation(self, folder_id: str, name: str, data: bytes, actor: str) -> Replaced | None:
        """The replacement of the presentation of this name key, None when no presentation has it."""
        key = name_key(name)
        found = (
            self._database.connection()
            .execute("SELECT id, name FROM presentations WHERE folder_id = ? AND name_key = ?", (folder_id, key))
            .fetchone()
        )
        if found is None:
            return None
        presentation_id, existing = str(found[0]), str(found[1])
        with self.lock_for(presentation_id), trace_span("library.replace", {"file.size": len(data)}):
            if self.presentation(presentation_id) is None:  # deleted while this upload waited for the lock
                return None
            changed = atomic_write(self.presentation_path(folder_id, presentation_id), data, reason="replace")
            if changed:
                with self._database.transaction(immediate=True) as connection:
                    folder_name = _folder_name_in(connection, folder_id)
                    self.record(connection, actor, pages.replaced_line(existing, folder_name))
        return Replaced(presentation_id, existing)

    def inventory(self) -> list[InventoryRow]:
        """The stored presentations for the operator (``library-list``)."""
        return read_inventory(self._database.connection(), self._files)

    def is_seeded(self) -> bool:
        """Whether the initial content was created (or decided) already: ``meta('seeded')`` exists."""
        row = self._database.connection().execute("SELECT 1 FROM meta WHERE key = 'seeded'").fetchone()
        return row is not None

    def seed_initial_content(
        self,
        folder: str,
        members: Sequence[tuple[str, str]],
        presentations: Sequence[SeedPresentation],
        clock: Callable[[], float],
    ) -> bool:
        """Create the folder, its members and its presentations from verified files, and remember it (DEC-036).

        One ``BEGIN IMMEDIATE`` transaction: the flag is looked up again (another process may have won), the rows are
        inserted, each source file is copied byte for byte to its new path and given its modified time, then
        ``meta('seeded')`` is written; no activity line. Any failure removes the copied files and rolls back.
        """
        folder_id = secrets.token_hex(ID_BYTES)
        copied: list[Path] = []
        try:
            with self._database.transaction(immediate=True) as connection:
                if connection.execute("SELECT 1 FROM meta WHERE key = 'seeded'").fetchone() is not None:
                    return False
                connection.execute(
                    "INSERT INTO folders(id, name, name_key, created_at) VALUES (?, ?, ?, ?)",
                    (folder_id, folder, name_key(folder), self._clock()),
                )
                connection.executemany(
                    "INSERT INTO members(folder_id, email, role) VALUES (?, ?, ?)",
                    [(folder_id, normalize_email(email), role) for email, role in members],
                )
                for presentation in presentations:
                    presentation_id = secrets.token_hex(ID_BYTES)
                    path = self.presentation_path(folder_id, presentation_id)
                    path.parent.mkdir(mode=DIRECTORY_MODE, parents=True, exist_ok=True)
                    shutil.copyfile(presentation.source, path)
                    copied.append(path)
                    path.chmod(FILE_MODE)
                    os.utime(path, (presentation.modified, presentation.modified))
                    connection.execute(
                        "INSERT INTO presentations(id, folder_id, name, name_key, created_at) VALUES (?, ?, ?, ?, ?)",
                        (presentation_id, folder_id, presentation.name, name_key(presentation.name), self._clock()),
                    )
                connection.execute("INSERT INTO meta(key, value) VALUES ('seeded', ?)", (str(clock()),))
        except BaseException:
            for path in copied:
                path.unlink(missing_ok=True)
            _remove_directory(self._files / folder_id)
            raise
        return True

    def cover(self, presentation_id: str) -> Cover | None:
        """The cover of a presentation (``covers.first_cover``), cached by file modified time and size: a deck is read
        and scanned once until it changes. At most ``COVERS_KEPT`` entries are kept (the oldest goes first)."""
        row = self.presentation(presentation_id)
        if row is None:
            return None
        path = self.presentation_path(row.folder_id, presentation_id)
        try:
            status = path.stat()
        except OSError:
            return None
        stamp = (status.st_mtime_ns, status.st_size)
        with self._locks_guard:
            kept = self._covers.get(presentation_id)
        if kept is not None and kept[0] == stamp:
            return kept[1]
        try:
            cover = first_cover(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            cover = None
        with self._locks_guard:
            self._covers[presentation_id] = (stamp, cover)
            while len(self._covers) > COVERS_KEPT:
                self._covers.pop(next(iter(self._covers)))
        return cover

    def lock_for(self, presentation_id: str) -> threading.Lock:
        """The one lock of a presentation (created on first use): a save, a replacement and a deletion hold it."""
        with self._locks_guard:
            return self._locks.setdefault(presentation_id, threading.Lock())

    def activity(self) -> list[ActivityLine]:
        """The 500 newest lines, newest first (FR-NEW-050)."""
        rows = self._database.connection().execute(
            "SELECT at, actor, text FROM activity ORDER BY id DESC LIMIT ?", (ACTIVITY_KEPT,)
        )
        return [ActivityLine(at=row[0], actor=row[1], text=row[2]) for row in rows.fetchall()]

    def create_folder(self, name: str, actor: str) -> str:
        """Add an empty folder without any member and its line ``Created folder "<name>"``; returns its id.

        ``name`` is already checked (``names.check_folder_name``); ``NameTaken`` when its ``name_key`` exists, in
        which case nothing is written (the transaction rolls back).
        """
        folder_id = secrets.token_hex(ID_BYTES)
        try:
            with self._database.transaction(immediate=True) as connection:
                connection.execute(
                    "INSERT INTO folders(id, name, name_key, created_at) VALUES (?, ?, ?, ?)",
                    (folder_id, name, name_key(name), self._clock()),
                )
                self.record(connection, actor, pages.created_folder_line(name))
        except sqlite3.IntegrityError as exc:
            raise NameTaken from exc
        return folder_id

    def delete_folder(self, folder_id: str, confirm: str, actor: str) -> None:
        """Delete the folder when ``compose(confirm)`` equals its name character by character (FR-NEW-043).

        One ``BEGIN IMMEDIATE`` transaction checks the name, collects the presentation ids, writes the line
        ``Deleted folder "<name>"`` and deletes the folder row (members and presentations cascade); only then, the
        rows gone, ``files/<folder id>/`` and the state directory of each presentation (history, requests, AI
        suggestions) are removed (DEC-026). A directory that cannot be removed is a warning, never an error: nothing
        reaches it any more and ids are never reused. ``FolderMissing`` or ``NameMismatch`` write nothing.
        """
        if not ID_PATTERN.fullmatch(folder_id):  # no folder has it, and it never becomes a path
            raise FolderMissing
        with self._database.transaction(immediate=True) as connection:
            name = _folder_name_in(connection, folder_id)
            if compose(confirm) != name:
                raise NameMismatch
            presentation_ids = [
                found[0]
                for found in connection.execute("SELECT id FROM presentations WHERE folder_id = ?", (folder_id,))
            ]
            self.record(connection, actor, pages.deleted_folder_line(name))
            connection.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        with trace_span("library.delete_folder", {"presentations": len(presentation_ids)}):
            record_dirs = [self._record_dir(folder_id, presentation_id) for presentation_id in presentation_ids]
            for directory in (self._files / folder_id, *filter(None, record_dirs)):
                _remove_directory(directory)

    def delete_presentation(self, presentation_id: str, actor: str) -> None:
        """Delete the presentation for good (FR-NEW-039, DEC-026, DEC-028): under its lock, one ``BEGIN IMMEDIATE``
        transaction writes the line ``Deleted "<name>" from "<folder>"`` and deletes the row; only then the file and
        the state directory of the presentation (history, requests, AI suggestions) are removed. A directory that
        cannot be removed is a warning, never an error: nothing reaches it any more and ids are never reused. A save
        that lost the race finds the row gone and creates nothing. ``PresentationMissing`` writes nothing.
        """
        if not ID_PATTERN.fullmatch(presentation_id):  # no presentation has it, and it never becomes a path
            raise PresentationMissing
        with self.lock_for(presentation_id), trace_span("library.delete_presentation", {}):
            with self._database.transaction(immediate=True) as connection:
                row = connection.execute(
                    "SELECT folder_id, name FROM presentations WHERE id = ?", (presentation_id,)
                ).fetchone()
                if row is None:
                    raise PresentationMissing
                folder_id, name = str(row[0]), str(row[1])
                self.record(connection, actor, pages.deleted_line(name, _folder_name_in(connection, folder_id)))
                connection.execute("DELETE FROM presentations WHERE id = ?", (presentation_id,))
            record_dir = self._record_dir(folder_id, presentation_id)
            try:
                self.presentation_path(folder_id, presentation_id).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Could not remove the file of a deleted presentation: %s", type(exc).__name__)
            if record_dir is not None:
                _remove_directory(record_dir)
        with self._locks_guard:
            self._locks.pop(presentation_id, None)  # a waiter holds the lock object and finds the row gone

    def folders_for(self, email: str) -> list[FolderView]:
        """The folders ``email`` can open with its role, in ``order_key`` order: every folder (Admin) for the
        administrator, the member rows for anyone else."""
        if self.is_admin(email):
            rows = self._database.connection().execute(
                "SELECT id, name, ?, (SELECT COUNT(*) FROM presentations WHERE folder_id = folders.id) FROM folders",
                (Role.ADMIN.value,),
            )
        else:
            rows = self._database.connection().execute(
                "SELECT folders.id, folders.name, members.role,"
                " (SELECT COUNT(*) FROM presentations WHERE folder_id = folders.id)"
                " FROM members JOIN folders ON folders.id = members.folder_id WHERE members.email = ?",
                (normalize_email(email),),
            )
        views = [FolderView(id=row[0], name=row[1], role=Role(row[2]), count=row[3]) for row in rows.fetchall()]
        return sorted(views, key=lambda view: order_key(view.name))

    def folder_name(self, folder_id: str) -> str | None:
        """The name of the folder, None when no folder has this id."""
        row = self._database.connection().execute("SELECT name FROM folders WHERE id = ?", (folder_id,)).fetchone()
        return str(row[0]) if row is not None else None

    def is_admin(self, email: str) -> bool:
        """True for the administrator's address in any letter case; a look alike address is another address."""
        return normalize_email(email) == ADMIN_EMAIL

    def members_by_folder(self) -> dict[str, list[MemberView]]:
        """The members of every folder from one query, each folder's list in address order by code point (SQLite's
        ``BINARY`` collation compares the UTF-8 bytes, the same order); a folder without member has no key."""
        rows = self._database.connection().execute("SELECT folder_id, email, role FROM members ORDER BY email")
        listing: dict[str, list[MemberView]] = {}
        for folder_id, email, role in rows:
            listing.setdefault(folder_id, []).append(MemberView(email, Role(role)))
        return listing

    def presentation(self, presentation_id: str) -> PresentationRow | None:
        """The presentation of this id, None when none has it (a malformed id is never looked up)."""
        if not ID_PATTERN.fullmatch(presentation_id):
            return None
        row = (
            self._database.connection()
            .execute("SELECT folder_id, name FROM presentations WHERE id = ?", (presentation_id,))
            .fetchone()
        )
        return PresentationRow(presentation_id, str(row[0]), str(row[1])) if row is not None else None

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
            try:
                path = self.presentation_path(folder_id, presentation_id)
            except ValueError as exc:  # a damaged row: the library cannot be read, like a missing file (FR-NEW-062)
                raise sqlite3.DatabaseError("malformed presentation id") from exc
            status = path.stat()
            views.append(PresentationView(presentation_id, name, status.st_mtime, status.st_size))
        return sorted(
            views, key=lambda view: (-(math.floor(view.modified) // SECONDS_PER_MINUTE), order_key(view.name))
        )

    def record(self, connection: sqlite3.Connection, actor: str, text: str) -> None:
        """Add an activity line inside the caller's transaction, then drop the lines older than the 500 newest
        (DEC-030); only a successful action calls it, never a refusal, a sign in or a stored change (FR-NEW-051)."""
        connection.execute(
            "INSERT INTO activity(at, actor, text) VALUES (?, ?, ?)", (self._clock(), normalize_email(actor), text)
        )
        connection.execute("DELETE FROM activity WHERE id <= (SELECT MAX(id) FROM activity) - ?", (ACTIVITY_KEPT,))

    def _record_dir(self, folder_id: str, presentation_id: str) -> Path | None:
        """``<state_dir>/files/<key>`` of a presentation, the key of its resolved path (history, requests, AI
        suggestions); None for a malformed id, which no path is ever built from."""
        try:
            path = self.presentation_path(folder_id, presentation_id)
        except ValueError:
            logger.warning("Skipped a malformed presentation id of a deleted folder")
            return None
        return self._records.record_dir(path).parent

    def remove_member(self, folder_id: str, email: str, actor: str) -> None:
        """Delete the member row and write ``Removed <email> from "<folder>"``; an address that is not listed changes
        nothing and writes no line; ``FolderMissing`` for no folder (FR-NEW-047, FR-NEW-049)."""
        with self._database.transaction(immediate=True) as connection:
            name = _folder_name_in(connection, folder_id)
            removed = connection.execute(
                "DELETE FROM members WHERE folder_id = ? AND email = ?", (folder_id, email)
            ).rowcount
            if removed:
                self.record(connection, actor, pages.removed_member_line(email, name))

    def role_in(self, email: str, folder_id: str | None) -> Role | None:
        """Admin first whatever the member rows hold and whatever the route (a route naming no folder has
        ``folder_id`` None), else the member row of that folder, else None."""
        if self.is_admin(email):
            return Role.ADMIN
        if folder_id is None:
            return None
        row = (
            self._database.connection()
            .execute("SELECT role FROM members WHERE folder_id = ? AND email = ?", (folder_id, normalize_email(email)))
            .fetchone()
        )
        return Role(row[0]) if row is not None else None

    def set_member(self, folder_id: str, email: str, role: Role, actor: str) -> None:
        """Give ``email`` (already checked, lower case) the role RW or RO in the folder: one row per address and
        folder (upsert on the primary key). A new row writes ``Added <email> as <role> to "<folder>"``, another role
        ``Changed <email> to <role> in "<folder>"``, the same role nothing at all; ``FolderMissing`` for no folder.
        The table's ``CHECK`` refuses any other role (FR-NEW-012, FR-NEW-045)."""
        with self._database.transaction(immediate=True) as connection:
            name = _folder_name_in(connection, folder_id)
            row = connection.execute(
                "SELECT role FROM members WHERE folder_id = ? AND email = ?", (folder_id, email)
            ).fetchone()
            if row is not None and row[0] == role.value:
                return
            connection.execute(
                "INSERT INTO members(folder_id, email, role) VALUES (?, ?, ?)"
                " ON CONFLICT(folder_id, email) DO UPDATE SET role = excluded.role",
                (folder_id, email, role.value),
            )
            if row is None:
                line = pages.added_member_line(email, role.value, name)
            else:
                line = pages.changed_member_line(email, role.value, name)
            self.record(connection, actor, line)


def _folder_name_in(connection: sqlite3.Connection, folder_id: str) -> str:
    """The folder's name read inside the caller's write transaction, so it cannot vanish before the commit;
    ``FolderMissing`` when no folder has this id."""
    row = connection.execute("SELECT name FROM folders WHERE id = ?", (folder_id,)).fetchone()
    if row is None:
        raise FolderMissing
    return str(row[0])


def _remove_directory(directory: Path) -> None:
    """``shutil.rmtree`` of a directory of a deleted folder; already absent is fine, any other failure a warning."""
    try:
        shutil.rmtree(directory)
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning("Could not remove a directory of a deleted folder: %s", type(exc).__name__)


def normalize_email(email: str) -> str:
    """The stored form of an address: trimmed and lower cased, nothing else (no dot removal, no domain rewriting)."""
    return email.strip().lower()
