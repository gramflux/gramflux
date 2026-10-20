"""Async session stores. A session is an authentication credential, not a cache."""

import asyncio
import os
import sqlite3
import stat
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Literal, Protocol

from .errors import ConfigurationError, SessionAlreadyExists, SessionError, SessionNotFound

APP_ID = 0x47524A54


@dataclass(frozen=True, slots=True)
class SessionData:
    payload: bytes = field(repr=False)


class Storage(Protocol):
    async def open(self) -> None: ...
    async def load(self) -> SessionData | None: ...
    async def save(self, data: SessionData) -> None: ...
    async def close(self) -> None: ...


class MemoryStorage:
    """Reusable in-process session storage; never writes to disk."""

    def __init__(self) -> None:
        self._data: SessionData | None = None
        self._opened = False

    async def open(self) -> None:
        if self._opened:
            raise SessionError("memory session storage is already in use")
        self._opened = True

    async def load(self) -> SessionData | None:
        if not self._opened:
            raise SessionError("session storage is not open")
        return self._data

    async def save(self, data: SessionData) -> None:
        if not self._opened:
            raise SessionError("session storage is not open")
        if len(data.payload) > 1024 * 1024:
            raise SessionError("invalid session snapshot")
        self._data = data

    async def close(self) -> None:
        """Retain the snapshot so the same store can be reused."""
        self._opened = False


class SQLiteStorage:
    """Single-owner SQLite store with atomic snapshots and advisory file locking.

    All SQLite work runs in a worker thread. Locks are released by the OS on
    process death. Unsupported lock platforms fail explicitly. Files are not
    compatible with other libraries' session formats. Parent must already exist.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        mode: Literal["open", "create", "open_or_create"] = "open_or_create",
    ) -> None:
        if mode not in {"open", "create", "open_or_create"}:
            raise ConfigurationError("unknown session file mode")
        self.path = Path(path).absolute()
        self.mode = mode
        self._created = False
        self._handle: BinaryIO | None = None
        self._guard = asyncio.Lock()

    async def _run(self, operation: str, data: SessionData | None = None) -> SessionData | None:
        # Shield + join prevents cancellation from leaving an untracked worker
        # using a database after the lifetime lock was released.
        task = asyncio.create_task(asyncio.to_thread(self._sync, operation, data))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            finally:
                raise

    def _sync(self, operation: str, data: SessionData | None) -> SessionData | None:
        try:
            if operation == "open":
                flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
                creating = self.mode == "create" and not self._created
                if self.mode == "open_or_create" or creating:
                    flags |= os.O_CREAT
                if creating:
                    flags |= os.O_EXCL
                fd = os.open(self.path, flags, 0o600)
                handle = os.fdopen(fd, "r+b")
                try:
                    if not stat.S_ISREG(os.fstat(fd).st_mode):
                        raise SessionError("session must be a regular file")
                    if os.name == "posix":
                        import fcntl

                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        os.fchmod(fd, 0o600)
                    else:
                        raise SessionError("persistent storage currently requires POSIX file locks")
                    self._handle = handle
                except BaseException:
                    handle.close()
                    raise
            if operation == "close":
                if self._handle is not None:
                    self._handle.close()
                    self._handle = None
                return None
            if self._handle is None:
                raise SessionError("session storage is not open")
            # File creation belongs exclusively to the os.open policy above.
            # SQLite's default connection would recreate a file removed between
            # acquiring our handle and opening the database.
            with (
                closing(
                    sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5)
                ) as db,
                db,
            ):
                app_id = db.execute("PRAGMA application_id").fetchone()[0]
                version = db.execute("PRAGMA user_version").fetchone()[0]
                tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if (
                    operation == "open"
                    and (
                        self.mode == "open_or_create" or not self._created and self.mode == "create"
                    )
                    and app_id == 0
                    and version == 0
                    and not tables
                ):
                    db.execute("BEGIN IMMEDIATE")
                    db.execute(f"PRAGMA application_id={APP_ID}")
                    db.execute("PRAGMA user_version=1")
                    db.execute(
                        "CREATE TABLE session (id INTEGER PRIMARY KEY CHECK(id=1), "
                        "payload BLOB NOT NULL)"
                    )
                elif app_id != APP_ID or version != 1:
                    raise SessionError("unrecognized session format or unsupported schema version")
                if operation == "load":
                    row = db.execute("SELECT payload FROM session WHERE id=1").fetchone()
                    if row is None:
                        return None
                    if not isinstance(row[0], bytes) or len(row[0]) > 1024 * 1024:
                        raise SessionError("invalid session snapshot")
                    return SessionData(row[0])
                if operation == "save":
                    if data is None or len(data.payload) > 1024 * 1024:
                        raise SessionError("invalid session snapshot")
                    db.execute(
                        "INSERT INTO session VALUES (1, ?) "
                        "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                        (data.payload,),
                    )
            if operation == "open" and self.mode == "create":
                self._created = True
            return None
        except FileExistsError:
            raise SessionAlreadyExists(
                "Session already exists; use Session.open(name) to reuse it, or "
                "Session.open(name, require_authorized=False) to resume an unfinished login"
            ) from None
        except FileNotFoundError:
            raise SessionNotFound(
                "Session file or parent directory does not exist; "
                "use Session.create(name) for a new session in an existing directory"
            ) from None
        except (OSError, sqlite3.Error) as exc:
            raise SessionError("session I/O failed, is corrupt, or is already in use") from exc

    async def open(self) -> None:
        async with self._guard:
            if self._handle is not None:
                raise SessionError("session storage is already open")
            try:
                await self._run("open")
            except BaseException:
                await self._run("close")
                raise

    async def load(self) -> SessionData | None:
        async with self._guard:
            return await self._run("load")

    async def save(self, data: SessionData) -> None:
        async with self._guard:
            await self._run("save", data)

    async def close(self) -> None:
        async with self._guard:
            await self._run("close")
