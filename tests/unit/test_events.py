import asyncio
from types import SimpleNamespace

from gramflux import filters
from gramflux.events import Dispatcher, MessageEvent


def event(text="hello", out=False, edited=False):
    return MessageEvent(SimpleNamespace(message=text, out=out, chat_id=1, sender_id=2), edited)


def test_filter_composition():
    predicate = (
        filters.text & filters.incoming & filters.chat(1) & filters.sender(2) & filters.regex("^he")
    )
    assert predicate(event())
    assert not predicate(event(out=True))
    assert (filters.outgoing | ~filters.text)(event(""))


async def test_order_error_and_handler_cancellation(caplog):
    seen, errors = [], []

    async def bad(e):
        raise ValueError("DO-NOT-LOG-MESSAGE")

    async def cancel(e):
        raise asyncio.CancelledError

    async def good(e):
        seen.append(e.text)

    async def report(e, exc):
        errors.append(type(exc).__name__)

    dispatcher = Dispatcher(2, report)
    for handler in [bad, cancel, good]:
        dispatcher.add(handler)
    dispatcher.start()
    await dispatcher.put(event("one"))
    await dispatcher.put(event("two"))
    await dispatcher.join()
    await dispatcher.stop()
    assert seen == ["one", "two"]
    assert errors == ["ValueError", "RuntimeError"] * 2
    assert "DO-NOT-LOG-MESSAGE" not in caplog.text


async def test_bounded_queue_applies_backpressure():
    dispatcher = Dispatcher(1)
    await dispatcher.put(event("one"))
    blocked = asyncio.create_task(dispatcher.put(event("two")))
    await asyncio.sleep(0)
    assert not blocked.done()
    dispatcher.start()
    await blocked
    await dispatcher.join()
    await dispatcher.stop()


async def test_edited_routing():
    seen = []

    async def handler(e):
        seen.append(e.edited)

    dispatcher = Dispatcher(2)
    dispatcher.add(handler, edited=True)
    dispatcher.start()
    await dispatcher.put(event())
    await dispatcher.put(event(edited=True))
    await dispatcher.join()
    await dispatcher.stop()
    assert seen == [True]
