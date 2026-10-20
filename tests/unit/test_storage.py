import os
import sqlite3

import pytest
from telethon.crypto import AuthKey
from telethon.sessions import MemorySession

from gramflux.backend import restore, snapshot
from gramflux.errors import SessionError
from gramflux.storage import MemoryStorage, SessionData, SQLiteStorage


@pytest.mark.parametrize("persistent", [False, True])
async def test_session_roundtrip(tmp_path, persistent):
    store = SQLiteStorage(tmp_path / "s.db") if persistent else MemoryStorage()
    await store.open()
    assert await store.load() is None
    session = MemorySession()
    session.set_dc(2, "149.154.167.51", 443)
    session.auth_key = AuthKey(os.urandom(256))
    original = snapshot(session)
    await store.save(original)
    await store.close()
    await store.open()
    saved = await store.load()
    assert saved == original
    other = MemorySession()
    restore(other, saved)
    assert other.auth_key.key == session.auth_key.key
    assert "payload=" not in repr(saved)
    await store.close()
    if persistent:
        assert (tmp_path / "s.db").stat().st_mode & 0o777 == 0o600


async def test_lock_and_release(tmp_path):
    first, second = SQLiteStorage(tmp_path / "s"), SQLiteStorage(tmp_path / "s")
    await first.open()
    with pytest.raises(SessionError):
        await second.open()
    await first.close()
    await second.open()
    await second.close()


async def test_foreign_database_is_not_modified(tmp_path):
    p = tmp_path / "foreign"
    with sqlite3.connect(p) as db:
        db.execute("CREATE TABLE sessions (secret TEXT)")
    store = SQLiteStorage(p)
    with pytest.raises(SessionError):
        await store.open()
    with sqlite3.connect(p) as db:
        assert db.execute("PRAGMA application_id").fetchone()[0] == 0
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [
            ("sessions",)
        ]


async def test_corrupt_and_symlink(tmp_path):
    p = tmp_path / "corrupt"
    p.write_bytes(b"not sqlite")
    with pytest.raises(SessionError):
        await SQLiteStorage(p).open()
    link = tmp_path / "link"
    link.symlink_to(p)
    with pytest.raises(SessionError):
        await SQLiteStorage(link).open()


@pytest.mark.parametrize("data", [b"{}", b'{"key":"secret"}', b"not json"])
def test_invalid_snapshot(data):
    with pytest.raises(SessionError):
        restore(MemorySession(), SessionData(data))


async def test_memory_store_ownership_and_lifecycle():
    store = MemoryStorage()
    with pytest.raises(SessionError):
        await store.load()
    await store.open()
    with pytest.raises(SessionError):
        await store.open()
    await store.save(SessionData(b"snapshot"))
    await store.close()
    with pytest.raises(SessionError):
        await store.save(SessionData(b"new"))
    await store.open()
    assert (await store.load()).payload == b"snapshot"
    await store.close()
