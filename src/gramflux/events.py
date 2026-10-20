"""Ordered, bounded dispatch with backpressure and explicit handler failures."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from .errors import ConfigurationError, LifecycleError, StopPropagation
from .raw import types

if TYPE_CHECKING:
    from .client import Client

from .filters import Filter, all_messages

logger = logging.getLogger("gramflux.events")


@dataclass(frozen=True, slots=True)
class MessageEvent:
    message: Any = field(repr=False)
    edited: bool = False
    client: "Client | None" = field(default=None, repr=False, compare=False)
    chat_type: Literal["private", "group", "channel"] | None = None

    async def reply(self, text: str, *, silent: bool = False) -> types.Message:
        if self.client is None or self.chat_id is None:
            raise LifecycleError("event has no client/chat context")
        return await self.client.send_message(
            self.chat_id, text, reply_to=self.message.id, silent=silent
        )

    async def edit(self, text: str) -> Any:
        if self.client is None or self.chat_id is None:
            raise LifecycleError("event has no client/chat context")
        return await self.client.edit_message(self.chat_id, self.message.id, text)

    async def delete(self, *, revoke: bool = False) -> Any:
        if self.client is None or self.chat_id is None:
            raise LifecycleError("event has no client/chat context")
        return await self.client.delete_messages(self.chat_id, self.message.id, revoke=revoke)

    async def download(self, destination: str) -> Any:
        if self.client is None:
            raise LifecycleError("event has no client context")
        return await self.client.download_media(self.message, destination)

    @property
    def text(self) -> str:
        return str(self.message.message or "")

    @property
    def outgoing(self) -> bool:
        return bool(self.message.out)

    @property
    def chat_id(self) -> int | None:
        return self.message.chat_id  # type: ignore[no-any-return]

    @property
    def sender_id(self) -> int | None:
        return self.message.sender_id  # type: ignore[no-any-return]


Handler = Callable[[MessageEvent], Awaitable[None]]
ErrorHandler = Callable[[MessageEvent, Exception], Awaitable[None]]


class Dispatcher:
    """One worker; events arrive in order, handlers use stable priority order.

    Full queues block the producer. A cancelled or failing callback is reported
    and does not discard the event for subsequent handlers. Stop cancels the
    worker; pending events are not durably persisted by this dispatcher.
    """

    def __init__(self, size: int, on_error: ErrorHandler | None = None) -> None:
        self._queue: asyncio.Queue[MessageEvent] = asyncio.Queue(size)
        self._handlers: list[tuple[int, Handler, Filter, bool]] = []
        self._task: asyncio.Task[None] | None = None
        self._on_error = on_error

    def add(
        self,
        callback: Handler,
        predicate: Filter = all_messages,
        *,
        edited: bool = False,
        priority: int = 0,
    ) -> None:
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ConfigurationError("handler priority must be an integer")
        self._handlers.append((priority, callback, predicate, edited))
        self._handlers.sort(key=lambda item: item[0])

    def remove(self, callback: Handler) -> int:
        before = len(self._handlers)
        self._handlers[:] = [item for item in self._handlers if item[1] != callback]
        return before - len(self._handlers)

    def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("dispatcher already running")
        self._task = asyncio.create_task(self._run(), name="gramflux-dispatch")

    async def put(self, event: MessageEvent) -> None:
        await self._queue.put(event)

    async def join(self) -> None:
        await self._queue.join()

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                if not self._task.cancelled():
                    raise
            self._task = None
        while not self._queue.empty():
            self._queue.get_nowait()
            self._queue.task_done()

    async def _report(self, event: MessageEvent, exc: Exception) -> None:
        # No traceback or exception text: a user exception can contain secrets.
        logger.error("event handler failed (%s)", type(exc).__name__)
        if self._on_error is not None:
            try:
                await self._on_error(event, exc)
            except Exception:
                logger.error("event error callback failed")

    async def _run(self) -> None:
        while True:
            event = await self._queue.get()
            try:
                for _, callback, predicate, edited in tuple(self._handlers):
                    try:
                        if event.edited == edited and predicate(event):
                            await callback(event)
                    except StopPropagation:
                        break
                    except asyncio.CancelledError:
                        task = asyncio.current_task()
                        if task is not None and task.cancelling():
                            raise
                        await self._report(event, RuntimeError("handler cancelled itself"))
                    except Exception as exc:
                        await self._report(event, exc)
            finally:
                self._queue.task_done()
