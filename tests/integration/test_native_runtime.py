"""Native runtime operations serialize real own-schema requests at the sender seam."""

import asyncio

import pytest

from gramflux import Client, Config, filters
from gramflux.backend import NativeBackend, rpc_error
from gramflux.errors import SerializationError
from gramflux.mtproto.updates import UpdateEngine
from gramflux.raw import LAYER, functions, types
from gramflux.tl import Codec


def user():
    return types.User(id=9, self=True, access_hash=100)


def message(ident, peer=12):
    return types.Message(
        id=ident, peer_id=types.PeerUser(user_id=peer), message="server text", date=100, out=True
    )


class SenderDouble:
    def __init__(self, respond):
        self.calls = []
        self.codec = Codec()
        self.respond = respond
        self.disconnected = asyncio.get_running_loop().create_future()
        self.error = None
        self.offered = []
        self.closed = False

    async def invoke(self, request, **kwargs):
        self.codec.encode(request)  # detect invalid fields, flags and wire-level constructor use
        self.calls.append(request)
        while request.definition.result == "X":
            request = request.query
        return await self.respond(request)

    def _offer(self, value):
        self.offered.append(value)

    async def close(self):
        self.closed = True


def runtime(respond):
    backend = NativeBackend(1234, "a" * 32, Config())
    backend.sender = SenderDouble(respond)
    return backend


async def test_initialization_wraps_exact_own_layer_once_then_direct_calls():
    async def respond(request):
        return [user()]

    backend = runtime(respond)
    assert (await backend.get_me()).id == 9
    assert (await backend.get_me()).id == 9
    first, second = backend.sender.calls
    assert isinstance(first, functions.InvokeWithLayerRequest) and first.layer == LAYER == 225
    assert isinstance(first.query, functions.InitConnectionRequest)
    assert first.query.api_id == 1234
    assert isinstance(second, functions.users.GetUsersRequest)


async def test_initialization_rpc_authorization_rejection_does_not_renegotiate_every_call():
    async def respond(request):
        raise rpc_error(401, "AUTH_KEY_UNREGISTERED")

    backend = runtime(respond)
    assert await backend.get_me() is None
    assert await backend.get_me() is None
    assert isinstance(backend.sender.calls[1], functions.users.GetUsersRequest)


async def test_code_signin_and_bot_authorization_are_real_serializable_methods():
    async def respond(request):
        if isinstance(request, functions.auth.SendCodeRequest):
            assert request.phone_number == "+10000000000" and request.api_id == 1234
            return types.auth.SentCode(
                type=types.auth.SentCodeTypeApp(length=5), phone_code_hash="synthetic-hash"
            )
        if isinstance(request, functions.updates.GetStateRequest):
            return types.updates.State(pts=10, qts=0, date=100, seq=1, unread_count=0)
        assert isinstance(
            request, (functions.auth.SignInRequest, functions.auth.ImportBotAuthorizationRequest)
        )
        if isinstance(request, functions.auth.ImportBotAuthorizationRequest):
            assert request.flags == 0
        return types.auth.Authorization(user=user())

    backend = runtime(respond)
    assert (await backend.send_code_request("+10000000000")).phone_code_hash == "synthetic-hash"
    assert (
        await backend.sign_in(phone="+10000000000", code="12345", phone_code_hash="synthetic-hash")
    ).id == 9
    assert backend.session.states[0].pts == 10 and backend._authorized.is_set()
    assert (await backend.sign_in(bot_token="synthetic-token")).id == 9


async def test_send_correlates_random_id_and_chat_instead_of_first_update():
    async def respond(request):
        assert isinstance(request, functions.messages.SendMessageRequest)
        assert request.message == "literal **text**"
        return types.Updates(
            updates=[
                types.UpdateNewMessage(message=message(5, 99), pts=11, pts_count=1),
                types.UpdateNewMessage(message=message(6), pts=12, pts_count=1),
                types.UpdateMessageID(id=7, random_id=request.random_id),
                types.UpdateNewMessage(message=message(7), pts=13, pts_count=1),
            ],
            users=[user()],
            chats=[],
            date=100,
            seq=2,
        )

    backend = runtime(respond)
    result = await backend.send_message(
        types.InputPeerUser(user_id=12, access_hash=8), "literal **text**", reply_to=3
    )
    assert result.id == 7
    raw = backend.sender.calls[0].query.query
    assert raw.reply_to.reply_to_msg_id == 3
    assert len(backend.sender.offered) == 1


async def test_short_sent_response_normalizes_actual_server_fields_and_reaches_update_pipeline():
    async def respond(request):
        return types.UpdateShortSentMessage(id=10, pts=11, pts_count=1, date=101, out=True)

    backend = runtime(respond)
    result = await backend.send_message(types.InputPeerUser(user_id=12, access_hash=8), "text")
    assert result.id == 10 and result.message == "text" and result.chat_id == 12
    offered = backend.sender.offered[0]
    assert isinstance(offered, types.UpdateShort)
    assert offered.update.pts == 11 and offered.update.message.id == 10


async def test_ambiguous_message_update_result_is_not_fabricated_as_success():
    async def respond(request):
        return types.Updates(
            updates=[
                types.UpdateNewMessage(message=message(1), pts=11, pts_count=1),
                types.UpdateNewMessage(message=message(2), pts=12, pts_count=1),
            ],
            users=[],
            chats=[],
            date=100,
            seq=2,
        )

    backend = runtime(respond)
    with pytest.raises(SerializationError):
        await backend.send_message(types.InputPeerUser(user_id=12, access_hash=8), "text")


async def test_rpc_entity_results_feed_native_recovery_cache_without_overwriting_full_hash():
    async def respond(request):
        return [types.User(id=12, access_hash=50)]

    backend = runtime(respond)
    await backend(functions.users.GetUsersRequest(id=[types.InputUser(user_id=12, access_hash=50)]))
    assert backend.entities[12].access_hash == 50
    backend.sender.respond = lambda request: None
    from gramflux.peer_utils import ingest_entities

    ingest_entities(backend.entities, [types.User(id=12, min=True, access_hash=0)])
    assert backend.entities[12].access_hash == 50


async def test_handler_ack_boundary_does_not_commit_cancelled_message_on_shutdown():
    backend = NativeBackend(1234, "a" * 32, Config())
    # This test injects lifecycle I/O only; it exercises the actual native UpdateEngine,
    # Client event boundary and stop order without making a network connection.
    backend.session.states[0] = types.updates.State(pts=10, qts=0, date=100, seq=1, unread_count=0)
    backend.connect = lambda: asyncio.sleep(0)
    backend.is_connected = lambda: True

    async def disconnect():
        await backend.stop_updates()

    backend.disconnect = disconnect
    client = Client(api_id=1234, api_hash="a" * 32, _backend=backend)
    entered = asyncio.Event()

    @client.on_message(filters.all_messages)
    async def callback(event):
        entered.set()
        await asyncio.Event().wait()

    async with client:
        engine = UpdateEngine(backend)
        value = types.Updates(
            updates=[types.UpdateNewMessage(message=message(1), pts=11, pts_count=1)],
            users=[],
            chats=[],
            date=101,
            seq=2,
        )
        backend.update_task = asyncio.create_task(engine.process(value))
        await entered.wait()
    assert backend.session.states[0].pts == 10
    assert backend.session.states[0].seq == 1
    assert backend.update_task is None


@pytest.mark.parametrize(
    "name",
    [
        "CONNECTION_NOT_INITED",
        "CONNECTION_LAYER_INVALID",
        "API_ID_INVALID",
        "CONNECTION_API_ID_INVALID",
        "CONNECTION_LANG_PACK_INVALID",
        "INTERNAL",
    ],
)
async def test_rejected_initialization_is_not_cached_or_automatically_replayed(name):
    attempts = 0

    async def respond(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise rpc_error(500 if name == "INTERNAL" else 400, name)
        return [user()]

    backend = runtime(respond)
    from gramflux.errors import RPCError

    with pytest.raises(RPCError):
        await backend.get_me()
    assert attempts == 1 and not backend._initialized
    assert (await backend.get_me()).id == 9
    assert all(isinstance(call, functions.InvokeWithLayerRequest) for call in backend.sender.calls)


async def test_failed_native_setup_closes_started_sender(monkeypatch):
    from gramflux import backend as module
    from gramflux.backend import Key
    from gramflux.errors import RPCError

    connections = []

    class ConnectionDouble:
        def __init__(self, *args, **kwargs):
            self.closed = False
            connections.append(self)

        async def connect(self):
            return None

        async def close(self):
            self.closed = True

    async def respond(request):
        raise rpc_error(400, "API_ID_INVALID")

    sender = SenderDouble(respond)
    sender.start = lambda: None
    monkeypatch.setattr(module, "Connection", ConnectionDouble)
    monkeypatch.setattr(module, "Sender", lambda *args, **kwargs: sender)
    backend = NativeBackend(1234, "a" * 32, Config())
    backend.session.auth_key = Key(bytes(256))
    with pytest.raises(RPCError):
        await backend.connect()
    assert sender.closed and connections[0].closed
    assert backend.sender is None
    assert backend.update_task is backend.heartbeat_task is None


async def test_lost_api_initialization_rewraps_next_request_without_replaying_failed_one():
    from gramflux.errors import RPCError

    attempts = 0

    async def respond(request):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise rpc_error(400, "CONNECTION_NOT_INITED")
        return [user()]

    backend = runtime(respond)
    assert (await backend.get_me()).id == 9
    with pytest.raises(RPCError):
        await backend.get_me()
    assert attempts == 2 and not backend._initialized
    assert (await backend.get_me()).id == 9
    first, rejected, next_request = backend.sender.calls
    assert isinstance(first, functions.InvokeWithLayerRequest)
    assert isinstance(rejected, functions.users.GetUsersRequest)
    assert isinstance(next_request, functions.InvokeWithLayerRequest)
