"""Count and decoded-wire byte budgets for waiting native update envelopes."""

import asyncio

from gramflux.tl.model import TLObject


class UpdateQueue:
    """Single-consumer queue; byte charges are released when an item is dequeued.

    Bytes describe the uncompressed TL body, not the Python object's heap size.
    The consumer can hold one additional envelope outside this waiting budget.
    """

    def __init__(self, maxsize: int, byte_limit: int) -> None:
        for value in (maxsize, byte_limit):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("update queue limits must be positive integers")
        self._queue: asyncio.Queue[tuple[TLObject, int]] = asyncio.Queue(maxsize)
        self.byte_limit = byte_limit
        self.queued_bytes = 0

    def put_nowait(self, value: TLObject, *, size: int) -> None:
        if isinstance(size, bool) or not isinstance(size, int) or size < 4:
            raise ValueError("update wire size must be an integer of at least four bytes")
        if size > self.byte_limit - self.queued_bytes:
            raise asyncio.QueueFull
        self._queue.put_nowait((value, size))
        self.queued_bytes += size

    def get_nowait(self) -> TLObject:
        value, size = self._queue.get_nowait()
        self.queued_bytes -= size
        return value

    async def get(self) -> TLObject:
        value, size = await self._queue.get()
        self.queued_bytes -= size
        return value

    def task_done(self) -> None:
        self._queue.task_done()

    async def join(self) -> None:
        await self._queue.join()

    def qsize(self) -> int:
        return self._queue.qsize()

    def empty(self) -> bool:
        return self._queue.empty()
