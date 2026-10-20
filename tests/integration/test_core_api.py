"""Deterministic raw-API integration boundaries, not live-account verification."""

import io
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from gramflux import Client, Session, filters
from gramflux.backend import NativeSession as MemorySession
from gramflux.backend import rpc_error
from gramflux.errors import ConfigurationError, FloodWait, PaginationError, PeerNotFound
from gramflux.raw import functions as f
from gramflux.raw import types as t
from tests.native_fixtures import fixture_field, native_date

NOW = datetime(2026, 10, 20, tzinfo=UTC)


def message(ident, peer=12, *, text="synthetic text", date=NOW):
    return t.Message(
        id=ident, peer_id=t.PeerUser(user_id=peer), message=text, date=native_date(date)
    )


def user(ident=12):
    return t.User(
        id=ident, access_hash=ident * 100, first_name=f"User {ident}", username=f"user_{ident}"
    )


def row(ident=12, top=10, *, pinned=False):
    return t.Dialog(
        peer=t.PeerUser(user_id=ident),
        top_message=top,
        read_inbox_max_id=0,
        read_outbox_max_id=0,
        unread_count=2,
        unread_mentions_count=0,
        unread_reactions_count=0,
        unread_poll_votes_count=0,
        notify_settings=t.PeerNotifySettings(),
        pinned=pinned,
    )


def state():
    return t.updates.State(pts=0, qts=0, date=native_date(NOW), seq=0, unread_count=0)


def pinned(*rows):
    return t.messages.PeerDialogs(
        dialogs=list(rows),
        messages=[message(r.top_message, r.peer.user_id) for r in rows],
        chats=[],
        users=[user(r.peer.user_id) for r in rows],
        state=state(),
    )


def history_slice(*rows):
    return t.messages.MessagesSlice(count=1000, messages=list(rows), topics=[], chats=[], users=[])


class Backend:
    def __init__(self, respond):
        self.session = MemorySession()
        self.session.set_dc(2, "149.154.167.51", 443)
        self.connected = False
        self.respond = respond
        self.calls = []
        self.sent = []
        self.media = []
        self.handlers = []

    def add_event_handler(self, callback, builder):
        self.handlers.append((callback, builder))

    def is_connected(self):
        return self.connected

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def get_me(self):
        return user(1)

    async def __call__(self, request):
        self.calls.append(request)
        return await self.respond(request)

    async def send_message(self, peer, text, **kwargs):
        self.sent.append((peer, text, kwargs))
        return message(100, text=text)

    async def send_file(self, peer, file, **kwargs):
        self.media.append((peer, file, kwargs))
        return message(101)


def make(respond):
    backend = Backend(respond)
    client = Client(Session.temporary(), api_id=1234, api_hash="a" * 32, _backend=backend)
    return (client, backend)


async def test_history_is_lazy_handles_short_slices_and_progresses_offsets():
    responses = iter(
        [history_slice(message(9)), history_slice(message(8), message(7)), history_slice()]
    )

    async def respond(request):
        assert isinstance(request, f.messages.GetHistoryRequest)
        return next(responses)

    client, backend = make(respond)
    async with client:
        stream = client.iter_history(t.InputPeerUser(user_id=12, access_hash=1200), page_size=10)
        assert not backend.calls
        assert (await anext(stream)).id == 9
        assert len(backend.calls) == 1
        rest = [m.id async for m in stream]
        assert rest == [8, 7]
    assert [r.offset_id for r in backend.calls] == [0, 9, 7]


async def test_history_overlap_and_finite_limit_do_not_prefetch():
    responses = iter([history_slice(message(9), message(8)), history_slice(message(8), message(7))])

    async def respond(request):
        return next(responses)

    client, backend = make(respond)
    async with client:
        values = [
            m.id
            async for m in client.iter_history(
                t.InputPeerUser(user_id=12, access_hash=1200), limit=3, page_size=2
            )
        ]
    assert values == [9, 8, 7]
    assert [r.limit for r in backend.calls] == [2, 1]


async def test_history_repeated_cursor_is_an_error_not_an_infinite_loop():

    async def respond(request):
        return history_slice(message(9))

    client, backend = make(respond)
    async with client:
        with pytest.raises(PaginationError, match="cursor"):
            await client.get_history(t.InputPeerUser(user_id=12, access_hash=1200), limit=3)
    assert len(backend.calls) == 2


async def test_search_uses_explicit_peer_and_sender():

    async def respond(request):
        assert isinstance(request, f.messages.SearchRequest)
        assert request.q == "needle" and request.from_id.user_id == 14
        return t.messages.Messages(messages=[message(9)], topics=[], chats=[], users=[])

    client, _ = make(respond)
    async with client:
        values = await client.search_messages(
            t.InputPeerUser(user_id=12, access_hash=1200),
            "needle",
            sender=t.InputPeerUser(user_id=14, access_hash=1400),
        )
    assert [m.id for m in values] == [9]


@pytest.mark.parametrize("method", ["get_history", "get_dialogs", "get_members"])
async def test_collected_results_require_finite_limit(method):

    async def forbidden(request):
        raise AssertionError("no network")

    client, _ = make(forbidden)
    async with client:
        with pytest.raises(ConfigurationError):
            if method == "get_dialogs":
                await client.get_dialogs(limit=None)
            else:
                await getattr(client, method)("me", limit=None)


async def test_zero_limit_performs_no_network_or_peer_resolution():

    async def forbidden(request):
        raise AssertionError("no network")

    client, backend = make(forbidden)
    async with client:
        assert await client.get_history(999, limit=0) == []
        assert await client.get_dialogs(limit=0) == []
        assert await client.get_members(999, limit=0) == []
    assert backend.calls == []


async def test_pinned_dialogs_are_not_lost_with_page_size_one():

    async def respond(request):
        if isinstance(request, f.messages.GetPinnedDialogsRequest):
            return pinned(row(12, pinned=True), row(13, pinned=True))
        assert request.exclude_pinned and request.folder_id == 0
        return t.messages.Dialogs(
            dialogs=[row(14)], messages=[message(10, 14)], chats=[], users=[user(14)]
        )

    client, backend = make(respond)
    async with client:
        result = [d async for d in client.iter_dialogs(page_size=1)]
    assert [d.id for d in result] == [12, 13, 14]
    assert result[0].name == "User 12" and result[0].pinned
    assert "synthetic text" not in repr(result[0])
    assert len(backend.calls) == 2


async def test_dialog_cursor_carries_date_id_and_peer_access_hash():
    calls = 0

    async def respond(request):
        nonlocal calls
        if isinstance(request, f.messages.GetPinnedDialogsRequest):
            return pinned()
        calls += 1
        if calls == 1:
            return t.messages.DialogsSlice(
                count=3, dialogs=[row(12, 9)], messages=[message(9)], chats=[], users=[user(12)]
            )
        assert request.offset_date == native_date(NOW) and request.offset_id == 9
        assert request.offset_peer.user_id == 12 and request.offset_peer.access_hash == 1200
        return t.messages.Dialogs(
            dialogs=[row(13, 8)], messages=[message(8, 13)], chats=[], users=[user(13)]
        )

    client, _ = make(respond)
    async with client:
        assert [d.id for d in await client.get_dialogs()] == [12, 13]


async def test_dialog_missing_cursor_message_is_reported():

    async def respond(request):
        if isinstance(request, f.messages.GetPinnedDialogsRequest):
            return pinned()
        return t.messages.DialogsSlice(
            count=2, dialogs=[row()], messages=[], chats=[], users=[user()]
        )

    client, _ = make(respond)
    async with client:
        with pytest.raises(PaginationError, match="cursor"):
            await client.get_dialogs()


async def test_get_messages_keeps_order_duplicates_and_scope():

    async def respond(request):
        return t.messages.Messages(
            messages=[message(9), message(7, 99), t.MessageEmpty(id=8, peer_id=None)],
            topics=[],
            chats=[],
            users=[],
        )

    client, _ = make(respond)
    async with client:
        result = await client.get_messages(
            t.InputPeerUser(user_id=12, access_hash=1200), [9, 7, 8, 9]
        )
    assert [m.id if m else None for m in result] == [9, None, None, 9]


async def test_private_chat_deletion_validates_all_ids_before_mutating():

    async def respond(request):
        assert isinstance(request, f.messages.GetMessagesRequest)
        return t.messages.Messages(
            messages=[message(9), message(7, 99)], topics=[], chats=[], users=[]
        )

    client, backend = make(respond)
    async with client:
        with pytest.raises(PeerNotFound, match="other-chat"):
            await client.delete_messages(
                t.InputPeerUser(user_id=12, access_hash=1200), [9, 7], revoke=True
            )
    assert not any(isinstance(r, f.messages.DeleteMessagesRequest) for r in backend.calls)


async def test_channel_deletion_routes_and_batches_without_guessing_scope():

    async def respond(request):
        assert isinstance(request, f.channels.DeleteMessagesRequest)
        assert request.channel.channel_id == 50
        return t.messages.AffectedMessages(pts=1, pts_count=1)

    client, backend = make(respond)
    async with client:
        await client.delete_messages(
            t.InputPeerChannel(channel_id=50, access_hash=5000), list(range(1, 202)), revoke=True
        )
    assert [len(r.id) for r in backend.calls] == [100, 100, 1]


async def test_forward_binds_source_destination_and_random_ids(monkeypatch):
    ids = iter([100, 101])
    monkeypatch.setattr("gramflux.messages.secrets.randbits", lambda bits: next(ids))

    async def respond(request):
        assert request.from_peer.user_id == 12 and request.to_peer.user_id == 13
        assert request.id == [8, 9] and request.random_id == [100, 101]
        assert request.silent and request.drop_author
        return t.Updates(updates=[], users=[], chats=[], date=native_date(NOW), seq=1)

    client, backend = make(respond)
    async with client:
        assert (
            len(
                await client.forward_messages(
                    t.InputPeerUser(user_id=13, access_hash=1300),
                    t.InputPeerUser(user_id=12, access_hash=1200),
                    [8, 9],
                    silent=True,
                    drop_author=True,
                )
            )
            == 1
        )
    assert len(backend.calls) == 1


async def test_raw_mutations_and_read_receipts_use_correct_requests():

    async def respond(request):
        return True

    client, backend = make(respond)
    async with client:
        channel = t.InputPeerChannel(channel_id=50, access_hash=5000)
        await client.edit_message(channel, 8, "**literal**", link_preview=False)
        await client.pin_message(channel, 8)
        await client.unpin_message(channel, 8)
        await client.read_history(channel, max_id=8)
        await client.read_history(t.InputPeerUser(user_id=12, access_hash=1200), max_id=9)
    edit, pin, unpin, channel_read, user_read = backend.calls
    assert edit.message == "**literal**" and edit.entities == [] and edit.no_webpage
    assert pin.silent and unpin.unpin
    assert isinstance(channel_read, f.channels.ReadHistoryRequest)
    assert isinstance(user_read, f.messages.ReadHistoryRequest)


async def test_message_reply_parameters_are_literal_and_validated_before_send():

    async def forbidden(request):
        raise AssertionError("no raw network needed")

    client, backend = make(forbidden)
    async with client:
        await client.send_message("me", "**literal**", reply_to=7, silent=True, link_preview=False)
        with pytest.raises(ConfigurationError):
            await client.send_message("me", "invalid", reply_to=True)
    assert len(backend.sent) == 1
    assert backend.sent[0][2] == {
        "parse_mode": None,
        "reply_to": 7,
        "silent": True,
        "link_preview": False,
    }


async def test_upload_send_document_and_photo_use_streaming_pipeline():

    async def respond(request):
        assert isinstance(request, f.upload.SaveFilePartRequest)
        return True

    client, backend = make(respond)
    async with client:
        await client.send_document(
            "me", io.BytesIO(b"document"), name="file.bin", caption="literal", reply_to=7
        )
        await client.send_photo("me", io.BytesIO(b"photo bytes"))
    assert backend.media[0][2]["force_document"]
    assert backend.media[0][2]["reply_to"] == 7
    assert isinstance(backend.media[1][1], t.InputMediaUploadedPhoto)


async def test_members_channel_pages_are_demand_driven():

    async def respond(request):
        ident = 12 + request.offset
        rows = (
            []
            if request.offset >= 2
            else [t.ChannelParticipant(user_id=ident, date=native_date(NOW))]
        )
        return t.channels.ChannelParticipants(
            count=2, participants=rows, chats=[], users=[user(ident)]
        )

    client, backend = make(respond)
    async with client:
        result = [
            m
            async for m in client.iter_members(
                t.InputPeerChannel(channel_id=50, access_hash=5000), page_size=10
            )
        ]
    assert [m.id for m in result] == [12, 13]
    assert [r.offset for r in backend.calls] == [0, 1]
    assert all(m.role == "member" for m in result)


async def test_mutation_flood_is_not_automatically_retried():

    async def respond(request):
        raise rpc_error(420, f"FLOOD_WAIT_{33}")

    client, backend = make(respond)
    async with client:
        with pytest.raises(FloodWait) as error:
            await client.edit_message(t.InputPeerUser(user_id=12, access_hash=1200), 8, "text")
        assert error.value.seconds == 33
    assert len(backend.calls) == 1


async def test_peer_cache_reuse_after_client_restart(tmp_path):
    from gramflux.backend import Key as AuthKey
    from gramflux.storage import SQLiteStorage

    path = tmp_path / "account.sqlite"

    async def respond(request):
        if isinstance(request, f.contacts.ResolveUsernameRequest):
            return t.contacts.ResolvedPeer(peer=t.PeerUser(user_id=12), chats=[], users=[user()])
        return state()

    first, _ = make(respond)
    first._storage = SQLiteStorage(path)
    first._backend.session.auth_key = AuthKey(bytes(range(256)))
    async with first:
        assert (await first.resolve_peer("user_12")).access_hash == 1200
    second_backend = Backend(respond)
    second = Client(Session.open(path), api_id=1234, api_hash="a" * 32, _backend=second_backend)
    async with second:
        assert (await second.resolve_peer(12)).access_hash == 1200
        await second.send_message(12, "after restart")
    assert not any(isinstance(r, f.contacts.ResolveUsernameRequest) for r in second_backend.calls)


async def test_client_event_context_reply_and_handler_removal():

    async def forbidden(request):
        raise AssertionError("reply should use the known input peer")

    client, backend = make(forbidden)
    seen = []

    @client.on_message(filters.command("start") & filters.private, priority=-1)
    async def handler(event):
        seen.append(event.chat_type)
        await event.reply("reply", silent=True)

    async with client:
        incoming = message(9, text="/start")
        await client._receive(
            SimpleNamespace(
                message=incoming,
                _entities={12: user()},
                is_private=True,
                is_group=False,
                is_channel=False,
            )
        )
        await client._dispatcher.join()
        assert client.off_message(handler) == 1
    assert seen == ["private"]
    assert backend.sent[0][2]["reply_to"] == 9
    assert backend.sent[0][2]["silent"]


async def test_basic_group_member_list_and_search():

    async def respond(request):
        assert isinstance(request, f.messages.GetFullChatRequest)
        participants = t.ChatParticipants(
            chat_id=7,
            participants=[t.ChatParticipant(user_id=12, inviter_id=1, date=native_date(NOW))],
            version=1,
        )
        full = t.ChatFull(
            id=7, about="about", participants=participants, notify_settings=t.PeerNotifySettings()
        )
        return t.messages.ChatFull(full_chat=full, chats=[], users=[user()])

    client, _ = make(respond)
    async with client:
        values = await client.get_members(-7, query="USER 12")
    assert len(values) == 1 and values[0].id == 12
    assert values[0].user.username == "user_12"


async def test_join_leave_and_invite_are_explicit_mutations():

    async def respond(request):
        return t.Updates(updates=[], users=[], chats=[], date=native_date(NOW), seq=1)

    client, backend = make(respond)
    async with client:
        target = t.InputPeerChannel(channel_id=50, access_hash=5000)
        await client.join_chat(target)
        await client.leave_chat(target)
        await client.leave_chat(-7)
        await client.import_invite("synthetic_hash")
    assert [type(r) for r in backend.calls] == [
        f.channels.JoinChannelRequest,
        f.channels.LeaveChannelRequest,
        f.messages.DeleteChatUserRequest,
        f.messages.ImportChatInviteRequest,
    ]


async def test_entities_contacts_and_blocking_use_raw_api():

    async def respond(request):
        if isinstance(request, f.users.GetUsersRequest):
            return [user()]
        if isinstance(request, f.contacts.GetContactsRequest):
            return t.contacts.Contacts(contacts=[], saved_count=1, users=[user()])
        if isinstance(request, f.messages.GetChatsRequest):
            return t.messages.Chats(chats=[t.ChatForbidden(id=7, title="Group")])
        return True

    client, backend = make(respond)
    async with client:
        assert (await client.get_user(t.InputPeerUser(user_id=12, access_hash=1200))).id == 12
        assert (await client.get_chat(-7)).title == "Group"
        assert [u.id for u in await client.get_contacts()] == [12]
        assert await client.block_user(12)
        assert await client.unblock_user(12)
    assert isinstance(backend.calls[-2], f.contacts.BlockRequest)
    assert isinstance(backend.calls[-1], f.contacts.UnblockRequest)


async def test_logout_clears_persisted_authorization_and_peers():
    import json

    from gramflux.backend import Key as AuthKey
    from gramflux.errors import LifecycleError
    from gramflux.storage import MemoryStorage

    async def respond(request):
        assert isinstance(request, f.auth.LogOutRequest)
        return t.auth.LoggedOut()

    client, backend = make(respond)
    store = MemoryStorage()
    client._storage = store
    backend.session.auth_key = AuthKey(bytes(range(256)))
    await client.connect()
    client._peers.cache.ingest(user())
    await client.log_out()
    assert not client.connected and (not backend.connected)
    await store.open()
    saved = json.loads((await store.load()).payload)
    await store.close()
    assert saved["key"] is None and saved["peers"] == [] and (saved["states"] == [])
    with pytest.raises(LifecycleError, match="new Client"):
        await client.connect()


async def test_failed_logout_does_not_discard_local_authorization():
    from gramflux.backend import Key as AuthKey

    async def respond(request):
        raise rpc_error(420, f"FLOOD_WAIT_{15}")

    client, backend = make(respond)
    backend.session.auth_key = AuthKey(bytes(range(256)))
    async with client:
        with pytest.raises(FloodWait):
            await client.log_out()
        assert client.connected and backend.session.auth_key is not None


async def test_channel_delete_requires_explicit_revoke_consent():

    async def forbidden(request):
        raise AssertionError("no deletion should be sent")

    client, backend = make(forbidden)
    async with client:
        with pytest.raises(ConfigurationError, match="revoke=True"):
            await client.delete_messages(t.InputPeerChannel(channel_id=50, access_hash=5000), 8)
    assert not backend.calls


async def test_unexpected_logout_response_does_not_destroy_saved_state():
    from gramflux.errors import SerializationError

    async def respond(request):
        return False

    client, _ = make(respond)
    async with client:
        with pytest.raises(SerializationError):
            await client.log_out()
        assert client.connected


async def test_history_cancellation_isolated_and_frees_pending_requests():
    import asyncio

    started = asyncio.Event()
    never = asyncio.Event()

    async def respond(request):
        started.set()
        await never.wait()

    client, backend = make(respond)
    async with client:
        task = asyncio.create_task(
            client.get_history(t.InputPeerUser(user_id=12, access_hash=1200))
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not client._pending
        assert client.connected and backend.connected


async def test_startup_updates_are_dispatched_only_after_client_is_ready():
    import asyncio

    async def forbidden(request):
        raise AssertionError("peer should already be cached from the incoming event")

    client, backend = make(forbidden)
    ready = []

    @client.on_message()
    async def handler(event):
        ready.append(client.connected)
        await event.reply("startup reply")

    async def connect():
        backend.connected = True
        await client._receive(
            SimpleNamespace(message=message(9), _entities={12: user()}, is_private=True)
        )
        await asyncio.sleep(0)
        assert ready == []

    backend.connect = connect
    async with client:
        await client._dispatcher.join()
    assert ready == [True]
    assert len(backend.sent) == 1


async def test_public_file_ranges_raw_and_media_to_stream():
    payload = bytes(range(256)) * 60
    requests = []

    async def respond(request):
        assert isinstance(request, f.upload.GetFileRequest)
        requests.append(request)
        return t.upload.File(
            type=t.storage.FileUnknown(),
            mtime=0,
            bytes=payload[request.offset : request.offset + request.limit],
        )

    client, backend = make(respond)
    document = t.Document(
        id=4,
        access_hash=5,
        file_reference=b"reference",
        date=native_date(NOW),
        mime_type="application/octet-stream",
        size=len(payload),
        dc_id=2,
        attributes=[],
    )
    media_message = t.Message(
        id=1,
        peer_id=t.PeerUser(user_id=12),
        media=t.MessageMediaDocument(document=document),
        date=fixture_field("int"),
        message=fixture_field("string"),
    )
    async with client:
        stream = client.iter_download_media(
            media_message, offset=4090, length=30, request_size=4096
        )
        assert not requests
        assert b"".join([part async for part in stream]) == payload[4090:4120]
        assert len(requests) == 2
        assert isinstance(requests[0].location, t.InputDocumentFileLocation)
        target = io.BytesIO()
        assert (
            await client.download_media(
                media_message, target, offset=23, length=100, request_size=4096
            )
            is None
        )
        assert target.getvalue() == payload[23:123]
        assert not target.closed
        result = [
            part
            async for part in client.iter_download(
                requests[0].location, size=len(payload), offset=50, length=20, request_size=4096
            )
        ]
        assert b"".join(result) == payload[50:70]
        assert [part async for part in client.iter_download_media(media_message, length=0)] == []


async def test_public_send_document_photo_forward_upload_controls():
    parts = []

    async def respond(request):
        assert isinstance(request, f.upload.SaveFilePartRequest)
        parts.append(request)
        return True

    client, backend = make(respond)
    peer = t.InputPeerUser(user_id=12, access_hash=1200)
    payload = b"x" * 2500
    async with client:
        handle = await client.upload_file(
            io.BytesIO(payload), name="sample.bin", part_size=1024, concurrency=2
        )
        assert handle.parts == 3
        assert [len(part.bytes) for part in parts] == [1024, 1024, 452]
        parts.clear()
        await client.send_document(
            peer, io.BytesIO(payload), name="document.bin", part_size=1024, concurrency=3
        )
        assert len(parts) == 3
        assert backend.media[-1][1].name == "document.bin"
        assert backend.media[-1][2]["force_document"] is True
        parts.clear()
        await client.send_photo(peer, io.BytesIO(payload), part_size=1024, concurrency=2)
        assert len(parts) == 3
        assert isinstance(backend.media[-1][1], t.InputMediaUploadedPhoto)
