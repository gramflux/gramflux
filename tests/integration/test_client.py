"""Controlled backend tests; no claim of real Telegram interoperability."""

import asyncio
from types import SimpleNamespace

import pytest

from gramflux import Client, Config
from gramflux.backend import NativeSession as MemorySession
from gramflux.backend import rpc_error
from gramflux.errors import FloodWait, LifecycleError, PasswordRequired
from gramflux.raw import functions, types
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
            raise rpc_error(401, "SESSION_PASSWORD_NEEDED")
        self.authorized = True
        return types.User(id=42)

    async def __call__(self, request):
        if isinstance(request, functions.updates.GetStateRequest):
            if not self.authorized:
                raise rpc_error(401, "AUTH_KEY_UNREGISTERED")
            return object()
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
    return (client, backend)


def request(number):
    return functions.users.GetUsersRequest(id=[types.InputUser(user_id=number, access_hash=0)])


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


async def test_deadline_includes_admission():
    config = Config(request_timeout=0.05, max_concurrent_requests=1)
    client, backend = make(config)
    never = asyncio.Event()

    async def block(req):
        await never.wait()

    backend.callback = block
    async with client:
        tasks = [asyncio.create_task(client.invoke(request(i))) for i in range(2)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert all(isinstance(r, TimeoutError) for r in results)
        assert backend.maximum == 1
        assert not client._pending


async def test_shutdown_cancels_admitted_request():
    client, backend = make(Config(request_timeout=5, max_concurrent_requests=1))
    entered = asyncio.Event()
    never = asyncio.Event()

    async def block(req):
        entered.set()
        await never.wait()

    backend.callback = block
    await client.connect()
    pending = asyncio.create_task(client.invoke(request(1)))
    async with asyncio.timeout(5):
        await entered.wait()
        await client.disconnect()
        with pytest.raises(asyncio.CancelledError):
            await pending
    assert not backend.connected
    assert not client._pending


async def test_flood_wait_no_automatic_retry():
    client, backend = make()
    calls = 0

    async def fail(req):
        nonlocal calls
        calls += 1
        raise rpc_error(420, f"FLOOD_WAIT_{17}")

    backend.callback = fail
    async with client:
        with pytest.raises(FloodWait) as exc:
            await client.invoke(request(1))
        assert exc.value.seconds == 17
        assert calls == 1


async def test_native_generated_request_is_accepted_and_nonmethod_rejected():
    from gramflux.tl.generated.objects import UsersGetUsersRequest

    client, _ = make()
    async with client:
        backend = client._backend

        async def respond(request):
            return []

        backend.callback = respond
        assert await client.invoke(UsersGetUsersRequest(id=[])) == []
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
            error = rpc_error(303, "PHONE_MIGRATE_2")
            error.retry_ready = True  # emulate the native runtime completing a DC switch
            raise error
        return SimpleNamespace(phone_code_hash="PRIVATE")

    backend.send_code_request = migrate
    async with client:
        assert (await client.request_login_code("+123")).code_hash == "PRIVATE"
        assert calls == 2
    calls = 0

    async def forever(phone):
        nonlocal calls
        calls += 1
        error = rpc_error(303, "PHONE_MIGRATE_2")
        error.retry_ready = True
        raise error

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

    from gramflux.backend import Key as AuthKey

    store = MemoryStorage()
    client, backend = make(storage=store)
    async with client:
        backend.session.auth_key = AuthKey(os.urandom(256))
        key = backend.session.auth_key.key
    another, other_backend = make(storage=store)
    async with another:
        assert other_backend.session.auth_key.key == key


async def test_named_session_modes_and_authorization_check(tmp_path):
    from gramflux import Session
    from gramflux.backend import Key as AuthKey
    from gramflux.errors import AuthenticationRequired, SessionAlreadyExists, SessionNotFound

    def named(session, *, authorized=False):
        backend = Backend()
        backend.authorized = authorized
        backend.session.auth_key = AuthKey(bytes(range(256)))
        client = Client(session, api_id=1234, api_hash="a" * 32, _backend=backend)
        return (client, backend)

    name = tmp_path / "account"
    missing, _ = named(Session.open(name))
    with pytest.raises(SessionNotFound):
        await missing.connect()
    assert not list(tmp_path.iterdir())
    created, _ = named(Session.create(name), authorized=True)
    async with created:
        assert (await created.get_me()).id == 42
    before = name.with_suffix(".session").read_bytes()
    duplicate, _ = named(Session.create(name))
    with pytest.raises(SessionAlreadyExists):
        await duplicate.connect()
    reopened, _ = named(Session.open(name), authorized=True)
    async with reopened:
        assert await reopened.is_authorized()
    revoked, backend = named(Session.open(name))
    with pytest.raises(AuthenticationRequired, match="not authorized"):
        await revoked.connect()
    assert not backend.connected
    assert not revoked.connected
    assert revoked._dispatcher._task is None
    assert name.with_suffix(".session").read_bytes() == before
    resumed, _ = named(Session.open(name, require_authorized=False))
    async with resumed:
        assert not await resumed.is_authorized()


async def test_unfinished_saved_session_requires_explicit_resume(tmp_path):
    from gramflux import Session
    from gramflux.errors import AuthenticationRequired

    name = tmp_path / "unfinished"
    backend = Backend()
    async with Client(Session.create(name), api_id=1234, api_hash="a" * 32, _backend=backend):
        assert backend.session.auth_key is None
    reader = Backend()
    client = Client(Session.open(name), api_id=1234, api_hash="a" * 32, _backend=reader)
    with pytest.raises(AuthenticationRequired, match="require_authorized=False"):
        await client.connect()
    assert not reader.connected


async def test_temporary_sessions_do_not_share_or_write_keys(tmp_path, monkeypatch):
    from gramflux import Session
    from gramflux.backend import Key as AuthKey

    monkeypatch.chdir(tmp_path)
    backend = Backend()
    async with Client(Session.temporary(), api_id=1234, api_hash="a" * 32, _backend=backend):
        backend.session.auth_key = AuthKey(bytes(range(256)))
    next_backend = Backend()
    async with Client(Session.temporary(), api_id=1234, api_hash="a" * 32, _backend=next_backend):
        assert next_backend.session.auth_key is None
    assert not list(tmp_path.iterdir())


def scripted_prompts(*, phones=(), codes=(), passwords=()):
    from gramflux import LoginPrompts

    phone_iter, code_iter, password_iter = (iter(phones), iter(codes), iter(passwords))
    messages = []

    async def phone(_):
        return next(phone_iter)

    async def code(_):
        return next(code_iter)

    async def password(_):
        return next(password_iter)

    return (
        LoginPrompts(phone=phone, code=code, password=password, notify=messages.append),
        messages,
    )


async def test_interactive_wrong_code_reprompts_without_resending():
    client, backend = make()
    calls = []

    async def sign_in(**kwargs):
        calls.append(kwargs["code"])
        if kwargs["code"] != "correct":
            raise rpc_error(400, "PHONE_CODE_INVALID")
        backend.authorized = True
        return types.User(id=42)

    backend.sign_in = sign_in
    prompts, messages = scripted_prompts(phones=["+12345"], codes=["bad", "correct"])
    async with client:
        assert (await client.login(prompts=prompts)).id == 42
    assert len(backend.codes) == 1
    assert calls == ["bad", "correct"]
    assert len(messages) == 1
    assert "bad" not in "".join(messages)


async def test_interactive_password_reprompts_and_does_not_resend_code(monkeypatch):
    client, backend = make()
    checks = 0
    prompts, messages = scripted_prompts(
        phones=["+12345"], codes=["2fa"], passwords=["wrong", "correct"]
    )

    async def compute(*args):
        return object()

    monkeypatch.setattr("gramflux.client.disk", compute)

    async def respond(req):
        nonlocal checks
        if isinstance(req, functions.auth.CheckPasswordRequest):
            checks += 1
            if checks == 1:
                raise rpc_error(400, "PASSWORD_HASH_INVALID")
            return SimpleNamespace(user=types.User(id=42))
        return object()

    async def on_login(user):
        backend.authorized = True
        return user

    backend.callback = respond
    backend._on_login = on_login
    async with client:
        assert (await client.login(prompts=prompts)).id == 42
    assert checks == 2
    assert len(backend.codes) == 1
    assert messages == ["Incorrect or empty password. Please try again."]


async def test_login_code_expiry_refreshes_within_attempt_budget():
    client, backend = make()
    attempts = 0

    async def sign_in(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise rpc_error(400, "PHONE_CODE_EXPIRED")
        return types.User(id=42)

    backend.sign_in = sign_in
    prompts, messages = scripted_prompts(codes=["old", "new"])
    async with client:
        assert (await client.login(phone="+12345", prompts=prompts)).id == 42
    assert len(backend.codes) == 2
    assert attempts == 2
    assert messages == ["Login code expired. Requesting a new code."]


async def test_login_is_idempotent_for_saved_authorization():
    client, backend = make()
    backend.authorized = True
    prompts, _ = scripted_prompts()
    async with client:
        assert (await client.login(prompts=prompts)).id == 42
    assert not backend.codes


@pytest.mark.parametrize("failure", ["code", "password", "phone"])
async def test_interactive_failures_have_bounded_attempts(failure):
    from gramflux.errors import LoginAttemptsExceeded

    client, backend = make()
    count = 0

    async def reject(**kwargs):
        nonlocal count
        count += 1
        raise rpc_error(400, "PHONE_CODE_INVALID")

    if failure == "phone":

        async def invalid_phone(phone):
            nonlocal count
            count += 1
            raise rpc_error(400, "PHONE_NUMBER_INVALID")

        backend.send_code_request = invalid_phone
        prompts, _ = scripted_prompts(phones=["bad", "bad"])
    elif failure == "password":

        async def require_password(phone):
            raise rpc_error(401, "SESSION_PASSWORD_NEEDED")

        backend.send_code_request = require_password

        async def invalid_password(password):
            from gramflux.errors import AuthenticationError

            nonlocal count
            count += 1
            raise AuthenticationError(400, "PASSWORD_HASH_INVALID")

        client.check_password = invalid_password
        prompts, _ = scripted_prompts(phones=["+12345"], passwords=["bad", "bad"])
    else:
        backend.sign_in = reject
        prompts, _ = scripted_prompts(phones=["+12345"], codes=["bad", "bad"])
    async with client:
        with pytest.raises(LoginAttemptsExceeded) as exc:
            await client.login(max_attempts=2, prompts=prompts)
        assert exc.value.stage == failure
        assert exc.value.attempts == 2
    assert count == 2


@pytest.mark.parametrize("kind", ["flood", "connection", "cancel", "banned"])
async def test_interactive_does_not_retry_network_flood_or_fatal_errors(kind):
    from gramflux.errors import AuthenticationError, TransportError

    client, backend = make()
    count = 0

    async def fail(**kwargs):
        nonlocal count
        count += 1
        if kind == "flood":
            raise rpc_error(420, f"FLOOD_WAIT_{60}")
        if kind == "connection":
            raise ConnectionError("offline")
        if kind == "cancel":
            raise asyncio.CancelledError
        raise rpc_error(400, "PHONE_NUMBER_BANNED")

    backend.sign_in = fail
    prompts, _ = scripted_prompts(phones=["+12345"], codes=["x", "x", "x"])
    expected = {
        "flood": FloodWait,
        "connection": TransportError,
        "cancel": asyncio.CancelledError,
        "banned": AuthenticationError,
    }[kind]
    async with client:
        with pytest.raises(expected):
            await client.login(prompts=prompts)
    assert count == 1


async def test_empty_input_never_sends_or_resends_code():
    from gramflux.errors import LoginAttemptsExceeded

    client, backend = make()
    prompts, _ = scripted_prompts(phones=["", "+12345"], codes=["", ""])
    async with client:
        with pytest.raises(LoginAttemptsExceeded) as exc:
            await client.login(max_attempts=2, prompts=prompts)
        assert exc.value.stage == "code"
    assert backend.codes == ["+12345"]


async def test_login_prompt_cancellation_releases_lock():
    client, _ = make()
    prompts, _ = scripted_prompts()
    from gramflux import LoginPrompts

    async def cancel(_):
        raise asyncio.CancelledError

    async with client:
        with pytest.raises(asyncio.CancelledError):
            await client.login(prompts=LoginPrompts(phone=cancel))
        assert not client._auth_lock.locked()


@pytest.mark.parametrize(
    "kwargs",
    [{"max_attempts": 0}, {"max_attempts": True}, {"phone": "+12345", "bot_token": "secret"}],
)
async def test_login_options_validate_before_prompts(kwargs):
    from gramflux.errors import ConfigurationError

    client, _ = make()
    prompts, _ = scripted_prompts()
    async with client:
        with pytest.raises(ConfigurationError):
            await client.login(prompts=prompts, **kwargs)


async def test_bare_client_path_is_open_only(tmp_path):
    from gramflux.errors import SessionNotFound

    client = Client(tmp_path / "missing", api_id=1234, api_hash="a" * 32, _backend=Backend())
    with pytest.raises(SessionNotFound):
        await client.connect()
    assert not list(tmp_path.iterdir())


async def test_concurrent_login_prompts_only_once():
    from gramflux import LoginPrompts

    client, backend = make()
    started, release = (asyncio.Event(), asyncio.Event())
    phone_calls = 0

    async def phone(_):
        nonlocal phone_calls
        phone_calls += 1
        started.set()
        await release.wait()
        return "+12345"

    async def code(_):
        return "correct"

    prompts = LoginPrompts(phone=phone, code=code)
    async with client:
        first = asyncio.create_task(client.login(prompts=prompts))
        await started.wait()
        second = asyncio.create_task(client.login(prompts=prompts))
        await asyncio.sleep(0)
        assert not second.done()
        release.set()
        results = await asyncio.gather(first, second)
        assert [user.id for user in results] == [42, 42]
    assert phone_calls == 1
    assert backend.codes == ["+12345"]


async def test_login_bot_token_does_not_fall_back_to_phone():
    client, backend = make()
    prompts, _ = scripted_prompts()
    async with client:
        assert (await client.login(bot_token="synthetic-token", prompts=prompts)).id == 42
    assert not backend.codes


async def test_migration_without_completed_dc_switch_is_not_blindly_retried():
    from gramflux.errors import MigrationRequired

    client, backend = make()
    calls = 0

    async def migrate(phone):
        nonlocal calls
        calls += 1
        raise rpc_error(303, "PHONE_MIGRATE_2")

    backend.send_code_request = migrate
    async with client:
        with pytest.raises(MigrationRequired):
            await client.request_login_code("+123")
    assert calls == 1
