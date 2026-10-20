"""Controlled backend tests; no claim of real Telegram interoperability."""

import asyncio
from types import SimpleNamespace

import pytest
from telethon import errors
from telethon.sessions import MemorySession
from telethon.tl import functions, types

from gramflux import Client, Config
from gramflux.errors import FloodWait, LifecycleError, PasswordRequired, UnsupportedFeature
from gramflux.storage import MemoryStorage


class Backend:
    def __init__(self):
        self.session = MemorySession()
        self.session.set_dc(2, "149.154.167.51", 443)
        self.connected = False
        self.handlers = []
        self.callback = None
        self.active = 0
        self.maximum = 0
        self.authorized = False
        self.codes = []

    def add_event_handler(self, handler, builder):
        self.handlers.append((handler, builder))

    def is_connected(self):
        return self.connected

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def is_user_authorized(self):
        return self.authorized

    async def get_me(self):
        return types.User(id=42) if self.authorized else None

    async def send_code_request(self, phone):
        self.codes.append(phone)
        return SimpleNamespace(phone_code_hash="PRIVATE")

    async def sign_in(self, **kwargs):
        if kwargs.get("code") == "2fa":
            raise errors.SessionPasswordNeededError(None)
        self.authorized = True
        return types.User(id=42)

    async def __call__(self, request):
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        try:
            if self.callback:
                return await self.callback(request)
            return request.id[0].user_id
        finally:
            self.active -= 1


def make(config=None, storage=None):
    backend = Backend()
    client = Client(storage, api_id=1234, api_hash="a" * 32, config=config, _backend=backend)
    return client, backend


def request(number):
    return functions.users.GetUsersRequest([types.InputUser(number, 0)])


async def test_lifecycle_and_auth_no_implicit_prompts(monkeypatch):
    client, backend = make()

    async def compute(*args):
        return object()

    monkeypatch.setattr("gramflux.client.disk", compute)

    async def password_response(req):
        if isinstance(req, functions.auth.CheckPasswordRequest):
            return SimpleNamespace(user=types.User(id=42))
        return object()

    async def on_login(user):
        backend.authorized = True
        return user

    backend.callback = password_response
    backend._on_login = on_login
    with pytest.raises(LifecycleError):
        await client.get_me()
    async with client:
        assert not await client.is_authorized()
        challenge = await client.request_login_code("+1234")
        assert "PRIVATE" not in repr(challenge) and "+1234" not in repr(challenge)
        with pytest.raises(PasswordRequired):
            await client.sign_in(challenge, "2fa")
        assert (await client.check_password("private")).id == 42
        assert (await client.get_me()).id == 42
        with pytest.raises(LifecycleError):
            await client.sign_in_bot("different-account-token")
    assert not backend.connected


async def test_out_of_order_and_isolated_cancellation():
    client, backend = make()
    gates = [asyncio.Event() for _ in range(3)]
    started = asyncio.Event()

    async def respond(req):
        number = req.id[0].user_id
        if backend.active == 3:
            started.set()
        await gates[number].wait()
        return number

    backend.callback = respond
    async with client:
        tasks = [asyncio.create_task(client.invoke(request(i))) for i in range(3)]
        await started.wait()
        gates[2].set()
        assert await tasks[2] == 2
        tasks[0].cancel()
        with pytest.raises(asyncio.CancelledError):
            await tasks[0]
        gates[1].set()
        assert await tasks[1] == 1
        assert not client._pending


async def test_deadline_includes_admission_and_shutdown_cancels():
    config = Config(request_timeout=0.05, max_concurrent_requests=1)
    client, backend = make(config)
    never = asyncio.Event()

    async def block(req):
        await never.wait()

    backend.callback = block
    await client.connect()
    tasks = [asyncio.create_task(client.invoke(request(i))) for i in range(2)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, TimeoutError) for r in results)
    assert backend.maximum == 1
    assert not client._pending
    pending = asyncio.create_task(client.invoke(request(1)))
    await asyncio.sleep(0.01)
    await client.disconnect()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert not backend.connected


async def test_flood_wait_no_automatic_retry():
    client, backend = make()
    calls = 0

    async def fail(req):
        nonlocal calls
        calls += 1
        raise errors.FloodWaitError(req, capture=17)

    backend.callback = fail
    async with client:
        with pytest.raises(FloodWait) as exc:
            await client.invoke(request(1))
        assert exc.value.seconds == 17
        assert calls == 1


async def test_independent_request_is_explicitly_unsupported():
    from gramflux.tl.generated.objects import UsersGetUsersRequest

    client, _ = make()
    async with client:
        with pytest.raises(UnsupportedFeature):
            await client.invoke(UsersGetUsersRequest(id=[]))
        with pytest.raises(TypeError):
            await client.invoke(types.InputPeerSelf())


async def test_connect_failure_releases_storage():
    storage = MemoryStorage()
    client, backend = make(storage=storage)

    async def fail():
        raise ConnectionError("controlled")

    backend.connect = fail
    with pytest.raises(ConnectionError):
        await client.connect()
    assert not client.connected
    assert client._dispatcher._task is None


async def test_auth_migration_is_bounded_and_opt_in():
    client, backend = make()
    calls = 0

    async def migrate(phone):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise errors.PhoneMigrateError(None, capture=2)
        return SimpleNamespace(phone_code_hash="PRIVATE")

    backend.send_code_request = migrate
    async with client:
        assert (await client.request_login_code("+123")).code_hash == "PRIVATE"
        assert calls == 2
    calls = 0

    async def forever(phone):
        nonlocal calls
        calls += 1
        raise errors.PhoneMigrateError(None, capture=2)

    from gramflux.errors import MigrationRequired

    backend.send_code_request = forever
    async with client:
        with pytest.raises(MigrationRequired):
            await client.request_login_code("+123")
        assert calls == 3


async def test_empty_code_cannot_implicitly_request_another():
    from gramflux import LoginChallenge
    from gramflux.errors import ConfigurationError

    client, backend = make()
    async with client:
        with pytest.raises(ConfigurationError):
            await client.sign_in(LoginChallenge("+123", "PRIVATE"), "")
        assert not backend.codes


async def test_auth_key_survives_new_client_instance():
    import os

    from telethon.crypto import AuthKey

    store = MemoryStorage()
    client, backend = make(storage=store)
    async with client:
        backend.session.auth_key = AuthKey(os.urandom(256))
        key = backend.session.auth_key.key
    another, other_backend = make(storage=store)
    async with another:
        assert other_backend.session.auth_key.key == key
