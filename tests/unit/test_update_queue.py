"""Resource admission invariants, including rejected enqueue and cancelled waits."""

import asyncio

import pytest

from gramflux import Config
from gramflux.errors import ConfigurationError
from gramflux.mtproto.queue import UpdateQueue
from gramflux.raw import types


def value():
    return types.UpdatesTooLong()


@pytest.mark.parametrize("budget", [0, -1, True, 1.5])
def test_invalid_queue_byte_configuration(budget):
    with pytest.raises(ConfigurationError):
        Config(update_queue_bytes=budget)


async def test_count_and_byte_limits_are_transactional_and_reusable():
    queue = UpdateQueue(2, 16)
    first, second = value(), value()
    queue.put_nowait(first, size=12)
    with pytest.raises(asyncio.QueueFull):
        queue.put_nowait(second, size=8)
    assert queue.qsize() == 1 and queue.queued_bytes == 12
    queue.put_nowait(second, size=4)
    with pytest.raises(asyncio.QueueFull):
        queue.put_nowait(value(), size=4)
    assert queue.qsize() == 2 and queue.queued_bytes == 16
    assert await queue.get() is first
    assert queue.queued_bytes == 4
    queue.task_done()
    queue.put_nowait(first, size=12)
    assert queue.get_nowait() is second
    queue.task_done()
    assert queue.get_nowait() is first
    queue.task_done()
    await queue.join()
    assert queue.empty() and queue.queued_bytes == 0


async def test_cancelled_wait_does_not_corrupt_accounting():
    queue = UpdateQueue(1, 4)
    waiter = asyncio.create_task(queue.get())
    await asyncio.sleep(0)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    queue.put_nowait(value(), size=4)
    assert queue.queued_bytes == 4
    queue.get_nowait()
    queue.task_done()
    await queue.join()
    assert queue.queued_bytes == 0
