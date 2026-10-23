"""Routers compile to the existing ordered, bounded dispatcher, never a new one."""

import asyncio
from types import SimpleNamespace
from typing import get_args

import pytest

from gramflux import Client, filters
from gramflux.errors import ConfigurationError, LifecycleError, StopPropagation
from gramflux.events import Event, MessageEvent, RawUpdateEvent
from gramflux.raw import types
from gramflux.routing import Chat, Direction, Router


def client():
    return Client(api_id=1, api_hash="0" * 32)


def message(text="/hello", *, edited=False, out=False, owner=None, kind="private"):
    return MessageEvent(
        SimpleNamespace(message=text, out=out, chat_id=1, sender_id=2, id=3),
        edited=edited,
        client=owner,
        chat_type=kind,
    )


async def dispatch(c, *events):
    d = c._dispatcher
    d.start()
    try:
        for e in events:
            await d.put(e)
        await d.join()
    finally:
        await d.stop()


async def test_nested_router_preserves_priority_legacy_order_and_error_policy():
    c = client()
    root, child = Router("root"), Router("child")
    seen, errors = [], []

    async def record_error(event, error):
        errors.append((event, type(error)))

    c._dispatcher._on_error = record_error

    @c.on_message(priority=-1)
    async def legacy(e):
        seen.append("legacy")

    @root.message()
    async def first(e):
        seen.append("first")

    @child.message()
    async def bad(e):
        seen.append("bad")
        raise ValueError("private contents")

    root.include(child)

    @root.message()
    async def last(e):
        seen.append("last")

    original = c._dispatcher
    mount = c.events.include(root)
    assert c.events.include(root) is mount
    assert c._dispatcher is original
    e = message()
    await dispatch(c, e)
    assert seen == ["legacy", "first", "bad", "last"]
    assert errors == [(e, ValueError)]
    assert mount.close() == 3 and mount.close() == 0
    seen.clear()
    await dispatch(c, e)
    assert seen == ["legacy"]


async def test_stop_propagation_and_selective_removal_keep_native_semantics():
    c, r = client(), Router()
    seen = []

    @r.message(priority=-10)
    async def stop(e):
        seen.append("stop")
        raise StopPropagation

    @c.on_message()
    async def later(e):
        seen.append("later")

    c.events.include(r)
    await dispatch(c, message(), message())
    assert seen == ["stop", "stop"]
    assert c.events.remove(stop) == 1
    await dispatch(c, message())
    assert seen[-1] == "later"
    assert c.events.exclude(r) == 0


@pytest.mark.parametrize("event_type", get_args(Event))
async def test_router_preserves_each_original_event_type(event_type):
    c, r = client(), Router()
    seen = []

    @r.on(event_type)
    async def handler(e):
        seen.append(e)

    c.events.include(r)
    e = object.__new__(event_type)
    await dispatch(c, e)
    assert len(seen) == 1 and seen[0] is e


async def test_edited_message_and_raw_events_are_not_command_contexts():
    c, r = client(), Router()
    seen = []

    @r.edited_message(filters.text)
    async def edited(e):
        seen.append(e)

    @r.raw_update(filters.update_type(types.UpdateDeleteMessages))
    async def raw(e):
        seen.append(e)

    c.events.include(r)
    a = message(edited=True)
    b = RawUpdateEvent(types.UpdateDeleteMessages(messages=[1], pts=1, pts_count=1))
    await dispatch(c, message(), a, b)
    assert seen == [a, b]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("/HELLO a  b", ("hello", ("a", "b"), " a  b")),
        ('  /hello "two words" \\x', ("hello", ('"two', 'words"', "\\x"), ' "two words" \\x')),
        ("/hello@mybot\tfirst\nsecond  ", ("hello", ("first", "second"), "\tfirst\nsecond  ")),
        ("/hello", ("hello", (), "")),
    ],
)
async def test_command_context_whitespace_without_shell_interpretation(text, expected):
    c, r = client(), Router()
    seen = []

    @r.command("hello", chat=Chat.PRIVATE, username="MyBot")
    async def hello(ctx):
        assert ctx.event is e and ctx.message is e.message and ctx.client is c
        seen.append((ctx.command, ctx.args, ctx.raw_args))

    c.events.include(r)
    e = message(text, owner=c)
    await dispatch(c, e)
    assert seen == [expected]


async def test_command_selection_parse_opt_out_reply_and_legacy_filter_unchanged():
    from unittest.mock import AsyncMock

    c, r = client(), Router()
    c.send_message = AsyncMock(return_value=object())
    seen = []

    @r.command(
        "go",
        prefix="!",
        direction=Direction.ANY,
        parse_args=False,
        predicate=filters.sender(2),
        username="Mine",
    )
    async def go(ctx):
        seen.append(ctx.args)
        await ctx.reply("ok", silent=True)

    c.events.include(r)
    await dispatch(
        c,
        message("!go@Mine 'x y'", owner=c, out=True),
        message("!go@Other x", owner=c),
        message("!goMore", owner=c),
        message("!go", edited=True, owner=c),
    )
    assert seen == [None]
    c.send_message.assert_awaited_once_with(1, "ok", reply_to=3, silent=True)
    assert filters.command("go")(message("/go 'x y'"))
    assert not filters.command("go")(message("!go"))


def test_cycles_overlaps_duplicate_handlers_and_frozen_definitions_fail_atomically():
    a, b = Router("a"), Router("b")
    a.include(b)
    with pytest.raises(ConfigurationError):
        b.include(a)
    with pytest.raises(ConfigurationError):
        a.include(b)

    async def handler(e):
        return None

    a.message()(handler)
    with pytest.raises(ConfigurationError):
        a.message()(handler)
    c = client()
    mount = c.events.include(a)
    assert mount.active
    with pytest.raises(LifecycleError):
        b.message()(handler)
    with pytest.raises(ConfigurationError):
        c.events.include(b)
    mount.close()
    assert not mount.active
    c.events.include(a)  # Frozen definitions remain reusable after unmount.


def test_late_diamond_is_rejected_before_any_subscription():
    a, b, child, root = Router(), Router(), Router(), Router()
    a.include(child)
    root.include(a)
    root.include(b)
    b.include(child)
    c = client()
    with pytest.raises(ConfigurationError):
        c.events.include(root)
    assert c._dispatcher._handlers == []


async def test_same_router_can_mount_on_two_clients_with_independent_unsubscription():
    a, b, r = client(), client(), Router()
    seen = []

    @r.message()
    async def handler(e):
        seen.append(e.client)

    a.events.include(r)
    b.events.include(r)
    a.events.exclude(r)
    await dispatch(a, message(owner=a))
    await dispatch(b, message(owner=b))
    assert seen == [b]


async def test_shutdown_cancels_routed_handler_without_new_worker():
    c, r = client(), Router()
    entered, cancelled = asyncio.Event(), asyncio.Event()

    @r.message()
    async def wait(e):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    c.events.include(r)
    assert c._dispatcher._task is None
    c._dispatcher.start()
    await c._dispatcher.put(message())
    await entered.wait()
    await c._dispatcher.stop()
    assert cancelled.is_set()


def test_router_remove_before_mount_and_invalid_configuration():
    r = Router()

    async def handler(e):
        return None

    r.message()(handler)
    assert r.remove(handler) == 1 and r.remove(handler) == 0
    for make in [
        lambda: r.on(object),
        lambda: r.message(priority=True),
        lambda: r.command("/bad"),
        lambda: r.command("ok", chat="private"),
        lambda: r.command("ok", parse_args="yes"),
    ]:
        with pytest.raises(ConfigurationError):
            make()


async def test_command_context_repr_does_not_expose_arguments():
    c, r = client(), Router()
    seen = []

    @r.command("hello")
    async def hello(ctx):
        seen.append(repr(ctx))

    c.events.include(r)
    await dispatch(c, message("/hello PRIVATE-COMMAND-ARGUMENT", owner=c))
    assert len(seen) == 1 and "PRIVATE-COMMAND-ARGUMENT" not in seen[0]


def test_bound_method_duplicates_and_removal_use_existing_callback_equality():
    class Handlers:
        async def hello(self, event):
            return None

    owner, r, c = Handlers(), Router(), client()
    r.message()(owner.hello)
    with pytest.raises(ConfigurationError):
        r.message()(owner.hello)
    c.events.include(r)
    assert c.events.remove(owner.hello) == 1
    assert c._dispatcher._handlers == []
