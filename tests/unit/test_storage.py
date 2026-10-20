import os
import sqlite3

import pytest

from gramflux.backend import Key as AuthKey
from gramflux.backend import NativeSession as MemorySession
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
        assert (tmp_path / "s.db").stat().st_mode & 511 == 384


async def test_lock_and_release(tmp_path):
    first, second = (SQLiteStorage(tmp_path / "s"), SQLiteStorage(tmp_path / "s"))
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


async def test_open_only_never_creates_missing_file(tmp_path):
    from gramflux import Session
    from gramflux.errors import SessionNotFound

    store = Session.open(tmp_path / "missing")._storage()
    with pytest.raises(SessionNotFound):
        await store.open()
    assert not list(tmp_path.iterdir())


async def test_create_is_exclusive_and_existing_data_is_preserved(tmp_path):
    from gramflux import Session
    from gramflux.errors import SessionAlreadyExists

    path = tmp_path / "account.session"
    store = Session.create(path)._storage()
    await store.open()
    await store.save(SessionData(b"private-snapshot"))
    await store.close()
    original = path.read_bytes()
    with pytest.raises(SessionAlreadyExists):
        await Session.create(path)._storage().open()
    assert path.read_bytes() == original
    reader = Session.open(path)._storage()
    await reader.open()
    assert (await reader.load()).payload == b"private-snapshot"
    await reader.close()
    await store.open()
    assert (await store.load()).payload == b"private-snapshot"
    await store.close()


async def test_exclusive_creators_cannot_race(tmp_path):
    import asyncio

    from gramflux.errors import SessionAlreadyExists

    path = tmp_path / "account.session"
    a, b = (SQLiteStorage(path, mode="create"), SQLiteStorage(path, mode="create"))
    outcomes = await asyncio.gather(a.open(), b.open(), return_exceptions=True)
    assert sum(isinstance(result, SessionAlreadyExists) for result in outcomes) == 1
    assert sum(result is None for result in outcomes) == 1
    await a.close()
    await b.close()


async def test_open_does_not_initialize_an_empty_existing_file(tmp_path):
    path = tmp_path / "empty"
    path.touch()
    with pytest.raises(SessionError):
        await SQLiteStorage(path, mode="open").open()
    assert path.read_bytes() == b""


@pytest.mark.parametrize("name", ["", " ", ".", "/"])
def test_session_names_must_identify_a_file(name):
    from gramflux import Session
    from gramflux.errors import ConfigurationError

    with pytest.raises(ConfigurationError):
        Session.create(name)


async def test_open_does_not_recreate_file_removed_before_sqlite_connect(tmp_path, monkeypatch):
    path = tmp_path / "race.session"
    writer = SQLiteStorage(path, mode="create")
    await writer.open()
    await writer.close()
    original_connect = sqlite3.connect

    def removed_before_connect(*args, **kwargs):
        path.unlink()
        return original_connect(*args, **kwargs)

    monkeypatch.setattr("gramflux.storage.sqlite3.connect", removed_before_connect)
    with pytest.raises(SessionError):
        await SQLiteStorage(path, mode="open").open()
    assert not path.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_salt", True),
        ("native_salt", 2**64),
        ("native_time_offset", float("inf")),
        ("native_time_offset", True),
    ],
)
def test_invalid_native_metadata_is_validated_before_session_mutation(field, value):
    import json

    from gramflux.backend import Key, NativeSession, restore, snapshot
    from gramflux.errors import SessionError
    from gramflux.storage import SessionData

    source = NativeSession()
    source.auth_key = Key(bytes(range(256)))
    data = json.loads(snapshot(source).payload)
    data[field] = value
    target = NativeSession(dc_id=5, server_address="91.108.56.130")
    target.auth_key = Key(bytes(reversed(range(256))))
    before = snapshot(target).payload
    with pytest.raises(SessionError):
        restore(target, SessionData(json.dumps(data).encode()))
    assert snapshot(target).payload == before
