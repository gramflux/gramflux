"""Independent update synchronization against controlled official TL responses."""

import asyncio

import pytest

from gramflux.backend import NativeSession
from gramflux.errors import TransportError, UnsupportedFeature
from gramflux.mtproto.updates import UpdateEngine
from gramflux.raw import functions, types


def state(pts=10, seq=1):
    return types.updates.State(pts=pts, qts=0, date=100, seq=seq, unread_count=0)


def message(ident=1, peer=None):
    return types.Message(
        id=ident, peer_id=peer or types.PeerUser(user_id=12), date=101, message="synthetic fixture"
    )


def update(pts=11, ident=1):
    return types.UpdateNewMessage(message=message(ident), pts=pts, pts_count=1)


def envelope(*updates, seq=2):
    return types.Updates(
        updates=list(updates), users=[types.User(id=12, access_hash=1)], chats=[], date=101, seq=seq
    )


class Backend:
    def __init__(self, respond=None):
        self.session = NativeSession()
        self.session.states[0] = state()
        self.events = []
        self._handlers = [self.receive]
        self._user = types.User(id=99)
        self.respond = respond
        self.requests = []

    async def receive(self, event):
        self.events.append(event)

    async def __call__(self, request):
        self.requests.append(request)
        assert self.respond is not None
        return await self.respond(request)


async def test_pts_seq_progress_and_duplicate_suppression():
    backend = Backend()
    engine = UpdateEngine(backend)
    await engine.process(envelope(update()))
    assert len(backend.events) == 1
    assert backend.session.states[0].pts == 11 and backend.session.states[0].seq == 2
    await engine.process(envelope(update()))
    await engine.process(envelope(update(), seq=0))
    assert len(backend.events) == 1
    assert backend.events[0].is_private and backend.events[0].message.id == 1
    assert list(backend.events[0]._entities) == [12]


async def test_pts_gap_fetches_difference_and_does_not_redeliver_recovered_update():
    async def respond(request):
        assert isinstance(request, functions.updates.GetDifferenceRequest)
        assert request.pts == 10
        return types.updates.Difference(
            new_messages=[message(1), message(2)],
            new_encrypted_messages=[],
            other_updates=[],
            chats=[],
            users=[types.User(id=12, access_hash=1)],
            state=state(12, 2),
        )

    backend = Backend(respond)
    engine = UpdateEngine(backend)
    await engine.process(envelope(update(pts=12, ident=2)))
    assert [event.message.id for event in backend.events] == [1, 2]
    assert len(backend.requests) == 1 and backend.session.states[0].pts == 12


async def test_seq_gap_fetches_difference_before_later_envelope():
    async def respond(request):
        return types.updates.DifferenceEmpty(date=102, seq=3)

    backend = Backend(respond)
    engine = UpdateEngine(backend)
    await engine.process(envelope(update(), seq=4))
    assert len(backend.requests) == 1
    assert backend.session.states[0].seq == 4
    assert len(backend.events) == 1


async def test_difference_slices_continue_and_bound_cursor_commit():
    replies = [
        types.updates.DifferenceSlice(
            new_messages=[message(1)],
            new_encrypted_messages=[],
            other_updates=[],
            chats=[],
            users=[],
            intermediate_state=state(11, 2),
        ),
        types.updates.Difference(
            new_messages=[message(2)],
            new_encrypted_messages=[],
            other_updates=[],
            chats=[],
            users=[],
            state=state(12, 3),
        ),
    ]

    async def respond(request):
        return replies.pop(0)

    backend = Backend(respond)
    engine = UpdateEngine(backend)
    await engine.recover()
    assert [request.pts for request in backend.requests] == [10, 11]
    assert [event.message.id for event in backend.events] == [1, 2]
    assert backend.session.states[0].pts == 12


async def test_callback_cancellation_does_not_advance_pts_or_seq():
    backend = Backend()
    engine = UpdateEngine(backend)
    entered = asyncio.Event()

    async def blocked(event):
        entered.set()
        await asyncio.Event().wait()

    backend._handlers = [blocked]
    task = asyncio.create_task(engine.process(envelope(update())))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert backend.session.states[0].pts == 10
    assert backend.session.states[0].seq == 1


async def test_cancelled_difference_does_not_commit_unfinished_slice():
    async def respond(request):
        return types.updates.Difference(
            new_messages=[message(1)],
            new_encrypted_messages=[],
            other_updates=[],
            chats=[],
            users=[],
            state=state(11, 2),
        )

    backend = Backend(respond)
    engine = UpdateEngine(backend)

    async def cancelled(event):
        raise asyncio.CancelledError

    backend._handlers = [cancelled]
    with pytest.raises(asyncio.CancelledError):
        await engine.recover()
    assert backend.session.states[0].pts == 10
    assert engine.recovering is False


async def test_short_private_and_basic_group_messages_are_normalized_from_real_fields():
    backend = Backend()
    engine = UpdateEngine(backend)
    short = types.UpdateShortMessage(
        id=4, user_id=12, message="test text", pts=11, pts_count=1, date=102
    )
    await engine.process(short)
    assert backend.events[0].message.chat_id == 12
    assert backend.events[0].message.sender_id == 12
    group = types.UpdateShortChatMessage(
        id=5, from_id=12, chat_id=7, message="group text", pts=12, pts_count=1, date=103
    )
    await engine.process(group)
    assert backend.events[1].is_group
    assert backend.events[1].message.chat_id == -7
    assert backend.session.states[0].pts == 12


async def test_first_channel_update_recovers_authoritatively_before_emitting():
    async def respond(request):
        assert isinstance(request, functions.updates.GetChannelDifferenceRequest)
        assert request.channel.channel_id == 7 and request.pts == 1
        return types.updates.ChannelDifference(
            pts=50,
            new_messages=[message(7, types.PeerChannel(channel_id=7))],
            other_updates=[],
            chats=[],
            users=[],
            final=True,
        )

    backend = Backend(respond)
    engine = UpdateEngine(backend)
    value = envelope(
        types.UpdateNewChannelMessage(
            message=message(7, types.PeerChannel(channel_id=7)), pts=50, pts_count=1
        )
    )
    value.chats = [
        types.Channel(
            id=7,
            title="synthetic",
            photo=types.ChatPhotoEmpty(),
            date=100,
            access_hash=42,
            megagroup=True,
        )
    ]
    await engine.process(value)
    assert backend.session.states[7].pts == 50
    assert len(backend.events) == 1 and backend.events[0].is_group
    assert backend.session.states[0].pts == 10


async def test_too_long_difference_is_explicit_and_preserves_old_counters():
    async def respond(request):
        return types.updates.DifferenceTooLong(pts=99)

    backend = Backend(respond)
    engine = UpdateEngine(backend)
    with pytest.raises(UnsupportedFeature):
        await engine.recover()
    assert backend.session.states[0].pts == 10


async def test_uninitialized_state_is_not_guessed_from_first_incoming_update():
    backend = Backend()
    backend.session.states.clear()
    with pytest.raises(TransportError):
        await UpdateEngine(backend).process(envelope(update()))
    assert not backend.events and not backend.session.states


async def test_difference_state_replacement_does_not_roll_back_newer_seq_or_date():
    async def respond(request):
        return types.updates.Difference(
            new_messages=[message(2)],
            new_encrypted_messages=[],
            other_updates=[],
            chats=[],
            users=[],
            state=types.updates.State(pts=12, qts=0, date=110, seq=10, unread_count=0),
        )

    backend = Backend(respond)
    engine = UpdateEngine(backend)
    await engine.process(envelope(update(pts=12, ident=2), seq=2))
    assert backend.session.states[0].seq == 10
    assert backend.session.states[0].date == 110
    assert len(backend.events) == 1


async def test_event_metadata_does_not_copy_unrelated_cached_entities():
    backend = Backend()
    backend.entities = {i: types.User(id=i, access_hash=i) for i in range(1, 4097)}
    engine = UpdateEngine(backend)
    value = types.Message(
        id=1,
        peer_id=types.PeerUser(user_id=12),
        from_id=types.PeerUser(user_id=13),
        via_bot_id=14,
        fwd_from=types.MessageFwdHeader(date=100, from_id=types.PeerUser(user_id=15)),
        date=101,
        message="synthetic fixture",
    )
    await engine.emit(value)
    event = backend.events[0]
    assert set(event._entities) == {12, 13, 14, 15}
    assert len(backend.entities) == 4096
    backend.entities.clear()
    assert set(event._entities) == {12, 13, 14, 15}


async def test_update_batch_preserves_unrelated_full_entities_in_public_peer_cache():
    from gramflux.peers import PeerCache

    backend = Backend()
    backend.peer_cache = PeerCache()
    engine = UpdateEngine(backend)
    value = envelope(update())
    value.users.append(types.User(id=77, access_hash=99))
    await engine.process(value)
    assert backend.peer_cache.get(77).access_hash == 99
    assert set(backend.events[0]._entities) == {12}


async def test_duplicate_envelope_sequence_does_not_drop_fresh_message_counter():
    backend = Backend()
    engine = UpdateEngine(backend)
    await engine.process(envelope(update(), seq=1))
    assert [event.message.id for event in backend.events] == [1]
    assert backend.session.states[0].pts == 11
    assert backend.session.states[0].seq == 1
    await engine.process(envelope(update(), seq=1))
    assert len(backend.events) == 1


async def test_overlapping_pts_range_is_ignored_without_advancing_state():
    backend = Backend()
    value = update(pts=11)
    value.pts_count = 2  # local 10 + count 2 > remote 11: already applied
    await UpdateEngine(backend).process(envelope(value))
    assert not backend.events and not backend.requests
    assert backend.session.states[0].pts == 10


@pytest.mark.parametrize("private", [True, False])
async def test_short_message_preserves_forwarding_flags_and_lifetime(private):
    backend = Backend()
    shared = {
        "id": 1,
        "message": "fixture",
        "pts": 11,
        "pts_count": 1,
        "date": 101,
        "out": True,
        "mentioned": True,
        "media_unread": True,
        "silent": True,
        "via_bot_id": 5,
        "ttl_period": 60,
        "fwd_from": types.MessageFwdHeader(date=99, from_id=types.PeerUser(user_id=4)),
        "entities": [types.MessageEntityBold(offset=0, length=3)],
        "reply_to": types.MessageReplyHeader(reply_to_msg_id=10),
    }
    value = (
        types.UpdateShortMessage(user_id=12, **shared)
        if private
        else types.UpdateShortChatMessage(from_id=99, chat_id=7, **shared)
    )
    await UpdateEngine(backend).process(value)
    result = backend.events[0].message
    for key in (
        "out",
        "mentioned",
        "media_unread",
        "silent",
        "via_bot_id",
        "ttl_period",
        "fwd_from",
        "entities",
        "reply_to",
    ):
        assert getattr(result, key) == shared[key]
    assert result.sender_id == 99


@pytest.mark.parametrize("field", ["pts", "qts", "seq", "date"])
async def test_invalid_difference_state_is_rejected_before_delivering_messages(field):
    from gramflux.errors import SerializationError

    next_state = state(11, 2)
    setattr(next_state, field, -1)

    async def respond(request):
        return types.updates.Difference(
            new_messages=[message()],
            new_encrypted_messages=[],
            other_updates=[],
            chats=[],
            users=[],
            state=next_state,
        )

    backend = Backend(respond)
    with pytest.raises(SerializationError):
        await UpdateEngine(backend).recover()
    assert not backend.events
    assert backend.session.states[0].pts == 10


@pytest.mark.parametrize("field", ["pts", "qts", "seq"])
async def test_regressive_difference_state_is_rejected_before_delivery(field):
    from gramflux.errors import SerializationError

    previous = state()
    previous.qts = 5
    next_state = state(11, 2)
    next_state.qts = 5
    setattr(next_state, field, getattr(previous, field) - 1)

    async def respond(request):
        return types.updates.Difference(
            new_messages=[message()],
            new_encrypted_messages=[],
            other_updates=[],
            chats=[],
            users=[],
            state=next_state,
        )

    backend = Backend(respond)
    backend.session.states[0] = previous
    with pytest.raises(SerializationError, match="regressed"):
        await UpdateEngine(backend).recover()
    assert not backend.events and backend.session.states[0] is previous


async def test_nonprogressing_difference_slice_fails_before_repeat_delivery():
    async def respond(request):
        return types.updates.DifferenceSlice(
            new_messages=[message()],
            new_encrypted_messages=[],
            other_updates=[],
            chats=[],
            users=[],
            intermediate_state=state(),
        )

    backend = Backend(respond)
    with pytest.raises(TransportError, match="no progress"):
        await UpdateEngine(backend).recover()
    assert len(backend.requests) == 1 and not backend.events


@pytest.mark.parametrize("pts", [9, 10])
async def test_channel_difference_rejects_regression_or_nonprogress(pts):
    async def respond(request):
        return types.updates.ChannelDifference(
            pts=pts,
            new_messages=[message()],
            other_updates=[],
            chats=[],
            users=[],
            final=False,
        )

    backend = Backend(respond)
    backend.session.states[7] = state()
    backend.entities = {
        -1000000000007: types.ChannelForbidden(id=7, access_hash=42, title="fixture")
    }
    with pytest.raises((TransportError, ValueError)):
        await UpdateEngine(backend).channel(7)
    assert len(backend.requests) == 1 and not backend.events
    assert backend.session.states[7].pts == 10


async def test_message_box_applies_before_envelope_sequence_gap_recovery():
    async def respond(request):
        assert request.pts == 11
        assert len(backend.events) == 1
        return types.updates.DifferenceEmpty(date=102, seq=3)

    backend = Backend(respond)
    await UpdateEngine(backend).process(envelope(update(), seq=4))
    assert len(backend.requests) == 1 and len(backend.events) == 1
    assert backend.session.states[0].seq == 4


@pytest.mark.parametrize("seq_start,seq,applied", [(1, 4, False), (0, 0, True), (2, 4, True)])
async def test_combined_sequence_uses_start_for_non_message_updates(seq_start, seq, applied):
    backend = Backend()
    engine = UpdateEngine(backend)
    seen = []
    original = engine.apply

    async def apply(value, **kwargs):
        seen.append(value.definition.name)
        await original(value, **kwargs)

    engine.apply = apply
    value = types.UpdatesCombined(
        updates=[
            types.UpdateUserStatus(user_id=12, status=types.UserStatusOffline(was_online=100))
        ],
        users=[],
        chats=[],
        seq_start=seq_start,
        seq=seq,
        date=101,
    )
    await engine.process(value)
    assert bool(seen) is applied
    assert backend.session.states[0].seq == (seq if applied and seq else 1)


@pytest.mark.parametrize("seq_start,seq", [(-1, 2), (2, -1), (3, 2)])
async def test_malformed_sequence_range_does_not_deliver_message_box(seq_start, seq):
    from gramflux.errors import SerializationError

    backend = Backend()
    value = types.UpdatesCombined(
        updates=[update()],
        users=[],
        chats=[],
        seq_start=seq_start,
        seq=seq,
        date=101,
    )
    with pytest.raises(SerializationError):
        await UpdateEngine(backend).process(value)
    assert not backend.events and backend.session.states[0].pts == 10


async def test_recursive_channel_difference_fails_and_releases_recovery_guard():
    nested = True

    async def respond(request):
        return types.updates.ChannelDifference(
            pts=11,
            new_messages=[],
            other_updates=[types.UpdateChannelTooLong(channel_id=7)] if nested else [],
            chats=[],
            users=[],
            final=True,
        )

    backend = Backend(respond)
    backend.session.states[7] = state()
    backend.entities = {
        -1000000000007: types.ChannelForbidden(id=7, access_hash=42, title="fixture")
    }
    engine = UpdateEngine(backend)
    with pytest.raises(TransportError, match="nested channel"):
        await engine.channel(7)
    assert not engine.recovering_channels and len(backend.requests) == 1
    assert backend.session.states[7].pts == 10
    nested = False
    await engine.channel(7)
    assert not engine.recovering_channels and backend.session.states[7].pts == 11


async def test_cancelled_channel_page_keeps_only_completed_page_and_clears_guard():
    replies = [
        types.updates.ChannelDifference(
            pts=11,
            new_messages=[message(1)],
            other_updates=[],
            chats=[],
            users=[],
            final=False,
        ),
        types.updates.ChannelDifference(
            pts=12,
            new_messages=[message(2)],
            other_updates=[],
            chats=[],
            users=[],
            final=True,
        ),
    ]

    async def respond(request):
        return replies.pop(0)

    backend = Backend(respond)
    backend.session.states[7] = state()
    backend.entities = {
        -1000000000007: types.ChannelForbidden(id=7, access_hash=42, title="fixture")
    }

    async def receive(event):
        if event.message.id == 2:
            raise asyncio.CancelledError
        await backend.receive(event)

    backend._handlers = [receive]
    engine = UpdateEngine(backend)
    with pytest.raises(asyncio.CancelledError):
        await engine.channel(7)
    assert [request.pts for request in backend.requests] == [10, 11]
    assert [event.message.id for event in backend.events] == [1]
    assert backend.session.states[7].pts == 11
    assert not engine.recovering_channels
