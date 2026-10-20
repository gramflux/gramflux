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
