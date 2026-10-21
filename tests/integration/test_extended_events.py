"""Native update ordering -> typed Client events -> async handlers; no real account."""

import asyncio

import pytest

from gramflux import Client, Config, buttons, events, filters
from gramflux.backend import NativeBackend
from gramflux.errors import LifecycleError, StopPropagation
from gramflux.mtproto.updates import UpdateEngine
from gramflux.raw import types as t
from gramflux.tl import Codec


def state():
    return t.updates.State(pts=10, qts=0, date=100, seq=0, unread_count=0)


def make():
    backend = NativeBackend(1234, "a" * 32, Config())
    backend.session.states = {0: state(), 7: state()}
    backend.connect = lambda: asyncio.sleep(0)
    backend.is_connected = lambda: True
    client = Client(api_id=1234, api_hash="a" * 32, _backend=backend)
    return client, backend, UpdateEngine(backend)


CASES = [
    (t.UpdateDeleteMessages(messages=[1, 2], pts=11, pts_count=1), events.DeletedMessagesEvent),
    (
        t.UpdateDeleteChannelMessages(channel_id=7, messages=[1], pts=11, pts_count=1),
        events.DeletedMessagesEvent,
    ),
    (
        t.UpdateReadHistoryInbox(
            peer=t.PeerUser(user_id=12), max_id=3, still_unread_count=0, pts=11, pts_count=1
        ),
        events.ReadHistoryEvent,
    ),
    (
        t.UpdateReadHistoryOutbox(peer=t.PeerChat(chat_id=7), max_id=3, pts=11, pts_count=1),
        events.ReadHistoryEvent,
    ),
    (
        t.UpdateReadChannelInbox(channel_id=7, max_id=3, still_unread_count=0, pts=10),
        events.ReadHistoryEvent,
    ),
    (t.UpdateReadChannelOutbox(channel_id=7, max_id=3), events.ReadHistoryEvent),
    (
        t.UpdateUserStatus(user_id=12, status=t.UserStatusOnline(expires=200)),
        events.UserStatusEvent,
    ),
    (
        t.UpdateBotCallbackQuery(
            query_id=3,
            user_id=12,
            peer=t.PeerUser(user_id=12),
            msg_id=5,
            chat_instance=9,
            data=b"secret-click",
        ),
        events.CallbackQueryEvent,
    ),
    (
        t.UpdateInlineBotCallbackQuery(
            query_id=3,
            user_id=12,
            msg_id=t.InputBotInlineMessageID(dc_id=2, id=5, access_hash=9),
            chat_instance=9,
            data=b"secret-click",
        ),
        events.CallbackQueryEvent,
    ),
    (
        t.UpdateBotInlineQuery(query_id=3, user_id=12, query="secret-query", offset="next"),
        events.InlineQueryEvent,
    ),
]


@pytest.mark.parametrize("update,kind", CASES)
async def test_accepted_native_updates_reach_correct_event_without_message_leakage(update, kind):
    client, backend, engine = make()
    received = []
    raw = []

    @client.on(kind)
    async def handler(event):
        assert event.client is client
        received.append(event)

    @client.on_raw_update()
    async def raw_handler(event):
        raw.append(event.update)

    @client.on_message()
    async def message_handler(event):
        pytest.fail("non-message update leaked into on_message")

    async with client:
        await engine.process(t.Updates(updates=[update], users=[], chats=[], date=101, seq=1))
        await engine.process(t.Updates(updates=[update], users=[], chats=[], date=101, seq=1))
    # pts_count=0 describes a read-state snapshot, not a uniquely counted event.
    expected = 2 if isinstance(update, t.UpdateReadChannelInbox) else 1
    assert len(received) == expected and raw == [update] * expected
    assert "secret" not in repr(received[0])
    event = received[0]
    if isinstance(event, events.DeletedMessagesEvent):
        assert event.chat_id == (-1000000000007 if hasattr(update, "channel_id") else None)
        assert event.message_ids == tuple(update.messages)
    if isinstance(event, events.UserStatusEvent):
        assert event.online and event.sender_id == 12
    if isinstance(event, events.CallbackQueryEvent):
        assert event.data == b"secret-click" and event.sender_id == 12
        assert filters.data("secret-click")(event)
        assert not filters.media(event) and not filters.incoming(event)


async def test_service_actions_route_once_and_are_available_during_difference_message_emission():
    client, backend, engine = make()
    action = t.MessageService(
        id=1,
        peer_id=t.PeerChat(chat_id=7),
        from_id=t.PeerUser(user_id=12),
        date=100,
        action=t.MessageActionChatAddUser(users=[12, 13]),
    )
    got = []

    @client.on_chat_action(filters.chat(-7))
    async def joined(event):
        got.append((event.chat_id, event.user_ids))

    async with client:
        # Difference pages carry Message objects, not fabricated Update wrappers.
        await engine.emit(action)
    assert got == [(-7, (12, 13))]


async def test_raw_handler_shutdown_cancellation_does_not_commit_message_counter():
    client, backend, engine = make()
    entered = asyncio.Event()

    @client.on_raw_update()
    async def raw(event):
        entered.set()
        await asyncio.Event().wait()

    async with client:
        backend.update_task = asyncio.create_task(
            engine.process(
                t.UpdateShort(
                    update=t.UpdateDeleteMessages(messages=[1], pts=11, pts_count=1),
                    date=101,
                )
            )
        )
        await entered.wait()
    assert backend.session.states[0].pts == 10


async def test_typed_handler_error_and_stop_propagation_preserve_other_event_types(caplog):
    client, backend, engine = make()
    seen = []

    @client.on_callback_query(priority=-1)
    async def bad(event):
        raise ValueError("SECRET-payload")

    @client.on_callback_query()
    async def first(event):
        seen.append(1)
        raise StopPropagation

    @client.on_callback_query()
    async def second(event):
        seen.append(2)

    async with client:
        await engine.process(t.UpdateShort(update=CASES[7][0], date=100))
    assert seen == [1] and "SECRET-payload" not in caplog.text
    assert client.off_event(first) == 1


async def test_detached_bot_events_fail_explicitly():
    callback = events.CallbackQueryEvent(1, 2, data=b"x")
    inline = events.InlineQueryEvent(1, 2, "query", "")
    with pytest.raises(LifecycleError):
        await callback.answer()
    with pytest.raises(LifecycleError):
        await inline.answer([])


def test_native_buttons_and_inline_results_serialize_and_validate_utf8_boundaries():
    markup = buttons.inline(
        [[buttons.callback("Click", "é" * 32), buttons.url("Site", "https://example.org")]]
    )
    Codec().encode(markup)
    Codec().encode(buttons.article("id", "Title", "message", reply_markup=markup))
    with pytest.raises(ValueError):
        buttons.callback("Click", "é" * 33)
    with pytest.raises(ValueError):
        buttons.inline([[t.KeyboardButton(text="reply only")]])


@pytest.mark.parametrize("kind", ["callback", "inline"])
async def test_event_answer_helpers_execute_real_native_answer_requests(kind):
    from tests.integration.test_core_api import make

    async def respond(request):
        expected = (
            "messages.setBotCallbackAnswer"
            if kind == "callback"
            else "messages.setInlineBotResults"
        )
        assert request.definition.name == expected and request.query_id == 77
        Codec().encode(request)
        return True

    client, backend = make(respond)
    async with client:
        if kind == "callback":
            event = events.CallbackQueryEvent(77, 12, client=client)
            assert await event.answer("answer", alert=True)
        else:
            event = events.InlineQueryEvent(77, 12, "query", "", client)
            assert await event.answer([buttons.article("one", "Title", "text")])
    assert len(backend.calls) == 1
