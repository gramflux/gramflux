"""Actual SQLite and process termination; Telegram backend is controlled, not live."""

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from gramflux import Client, LoginPrompts, Session
from gramflux.backend import restore, snapshot
from gramflux.errors import AuthenticationError, LifecycleError, SessionError
from gramflux.login_state import PendingLogin
from gramflux.raw import functions, types
from gramflux.storage import SessionData
from tests.integration.test_client import Backend

REPOSITORY = Path(__file__).resolve().parents[2]


async def crash_after_checkpoint(path, stage):
    script = """
import asyncio, os, sys
from gramflux import Client, Session
from gramflux.backend import Key
from gramflux.errors import PasswordRequired
from tests.integration.test_client import Backend
async def main():
    backend = Backend()
    backend.session.auth_key = Key(bytes(range(256)))  # Public synthetic test key.
    client = Client(Session.create(sys.argv[1]), api_id=1234, api_hash="a"*32, _backend=backend)
    await client.connect()
    await client.request_login_code("+1234")
    if sys.argv[2] == "password":
        try:
            await client.sign_in(code="2fa")
        except PasswordRequired:
            pass
    os._exit(0)  # Deliberately bypass disconnect, finally and interpreter shutdown.
asyncio.run(main())
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        script,
        str(path),
        stage,
        cwd=REPOSITORY,
    )
    assert await asyncio.wait_for(process.wait(), 15) == 0


def reopen(path):
    backend = Backend()
    client = Client(
        Session.open(path, require_authorized=False),
        api_id=1234,
        api_hash="a" * 32,
        _backend=backend,
    )
    return client, backend


async def test_code_checkpoint_survives_process_death_without_disconnect(tmp_path):
    path = tmp_path / "login.session"
    await crash_after_checkpoint(path, "code")
    client, backend = reopen(path)
    original = backend.sign_in
    seen = []

    async def submit(**kwargs):
        seen.append(kwargs)
        return await original(**kwargs)

    backend.sign_in = submit
    async with client:
        assert backend.session.auth_key.key == bytes(range(256))
        assert client.login_stage == "code"
        assert client.login_challenge.phone == "+1234"
        assert "PRIVATE" not in repr(client.login_challenge)
        assert (await client.sign_in(code="12345")).id == 42
        assert client.login_stage is None
        assert backend.codes == []
    assert seen == [{"phone": "+1234", "code": "12345", "phone_code_hash": "PRIVATE"}]
    client, _ = reopen(path)
    async with client:
        assert client.login_stage is None
        data = await client._storage.load()
        assert b"12345" not in data.payload
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


async def test_password_checkpoint_survives_process_death_and_retries(tmp_path, monkeypatch):
    path = tmp_path / "password.session"
    await crash_after_checkpoint(path, "password")
    client, backend = reopen(path)
    attempts = []

    async def compute(function, parameters, password):
        attempts.append(password)
        if password == "wrong-secret":
            raise AuthenticationError(400, "PASSWORD_HASH_INVALID")
        return object()

    async def respond(request):
        if isinstance(request, functions.auth.CheckPasswordRequest):
            return SimpleNamespace(user=types.User(id=42))
        return object()

    async def on_login(user):
        backend.authorized = True
        return user

    monkeypatch.setattr("gramflux.client.disk", compute)
    backend.callback, backend._on_login = respond, on_login
    async with client:
        assert backend.session.auth_key.key == bytes(range(256))
        assert client.login_stage == "password" and client.login_challenge is None
        with pytest.raises(AuthenticationError, match="PASSWORD_HASH_INVALID"):
            await client.check_password("wrong-secret")
        assert client.login_stage == "password"
        data = await client._storage.load()
        assert b"wrong-secret" not in data.payload and b"PRIVATE" not in data.payload

        async def unexpected(prompt):
            pytest.fail("password resume must not request phone or code")

        async def password(prompt):
            return "correct-secret"

        user = await client.login(
            prompts=LoginPrompts(
                phone=unexpected,
                code=unexpected,
                password=password,
            )
        )
        assert user.id == 42
        assert client.login_stage is None
        assert backend.codes == []
    assert attempts == ["wrong-secret", "correct-secret"]


async def test_interactive_login_reuses_saved_challenge(tmp_path):
    path = tmp_path / "interactive.session"
    await crash_after_checkpoint(path, "code")
    client, backend = reopen(path)

    async def unexpected(prompt):
        pytest.fail("resuming a saved code must not ask for the phone or password")

    async def code(prompt):
        return "12345"

    async with client:
        user = await client.login(
            prompts=LoginPrompts(phone=unexpected, code=code, password=unexpected)
        )
        assert user.id == 42 and backend.codes == []


@pytest.mark.parametrize("name,kept", [("PHONE_CODE_INVALID", True), ("PHONE_CODE_EXPIRED", False)])
async def test_invalid_code_keeps_challenge_but_expired_code_clears_it(tmp_path, name, kept):
    client, backend = reopen_created(tmp_path / "invalid.session")

    async def invalid(**kwargs):
        raise AuthenticationError(400, name)

    async with client:
        await client.request_login_code("+1234")
        backend.sign_in = invalid
        with pytest.raises(AuthenticationError):
            await client.sign_in(code="secret-code")
        assert (client.login_challenge is not None) == kept
        payload = (await client._storage.load()).payload
        assert b"secret-code" not in payload
        assert (json.loads(payload)["pending_login"] is not None) == kept


def reopen_created(path):
    backend = Backend()
    return Client(Session.create(path), api_id=1234, api_hash="a" * 32, _backend=backend), backend


async def test_missing_pending_challenge_is_explicit():
    client = Client(api_id=1234, api_hash="a" * 32, _backend=Backend())
    async with client:
        with pytest.raises(LifecycleError, match="no pending code challenge"):
            await client.sign_in(code="12345")


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"stage": "other", "phone": None, "code_hash": None},
        {"stage": "code", "phone": "+123", "code_hash": ""},
        {"stage": "password", "phone": "+123", "code_hash": "secret"},
    ],
)
def test_invalid_pending_metadata_does_not_mutate_native_session(bad):
    backend = Backend()
    data = json.loads(snapshot(backend.session).payload)
    data["dc"] = 4
    data["pending_login"] = bad
    with pytest.raises(SessionError):
        restore(backend.session, SessionData(json.dumps(data).encode()))
    assert backend.session.dc_id == 2


def test_old_snapshots_without_login_state_remain_compatible():
    backend = Backend()
    payload = json.loads(snapshot(backend.session).payload)
    payload.pop("pending_login")
    assert restore(backend.session, SessionData(json.dumps(payload).encode())) is None
    assert "secret" not in repr(PendingLogin("code", "+secret", "secret"))
