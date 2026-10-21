"""Ordered, bounded dispatch with backpressure and explicit handler failures."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, TypeVar

from .errors import ConfigurationError, LifecycleError, StopPropagation
from .raw import types
from .tl.model import TLObject

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


@dataclass(frozen=True, slots=True)
class RawUpdateEvent:
    update: TLObject = field(repr=False)
    client: "Client | None" = field(default=None, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class DeletedMessagesEvent:
    message_ids: tuple[int, ...]
    chat_id: int | None = None
    client: "Client | None" = field(default=None, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ReadHistoryEvent:
    chat_id: int
    max_id: int
    outbox: bool
    client: "Client | None" = field(default=None, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class UserStatusEvent:
    sender_id: int
    status: types.TypeUserStatus = field(repr=False)
    client: "Client | None" = field(default=None, repr=False, compare=False)

    @property
    def online(self) -> bool:
        return isinstance(self.status, types.UserStatusOnline)


@dataclass(frozen=True, slots=True)
class ChatActionEvent:
    message: types.MessageService = field(repr=False)
    client: "Client | None" = field(default=None, repr=False, compare=False)

    @property
    def action(self) -> TLObject:
        return self.message.action

    @property
    def chat_id(self) -> int:
        from .peer_utils import get_peer_id

        return get_peer_id(self.message.peer_id)

    @property
    def sender_id(self) -> int | None:
        return self.message.sender_id  # type: ignore[no-any-return]

    @property
    def user_ids(self) -> tuple[int, ...]:
        action = self.action
        if isinstance(action, types.MessageActionChatAddUser):
            return tuple(action.users)
        if isinstance(action, types.MessageActionChatDeleteUser):
            return (action.user_id,)
        return ()


@dataclass(frozen=True, slots=True)
class CallbackQueryEvent:
    query_id: int
    sender_id: int
    data: bytes | None = field(default=None, repr=False)
    chat_id: int | None = None
    message_id: int | None = None
    inline_message_id: types.TypeInputBotInlineMessageID | None = field(default=None, repr=False)
    game_short_name: str | None = field(default=None, repr=False)
    client: "Client | None" = field(default=None, repr=False, compare=False)

    async def answer(self, text: str = "", *, alert: bool = False, cache_time: int = 0) -> bool:
        if self.client is None:
            raise LifecycleError("event has no client context")
        return await self.client.answer_callback_query(
            self.query_id, text=text, alert=alert, cache_time=cache_time
        )


@dataclass(frozen=True, slots=True)
class InlineQueryEvent:
    query_id: int
    sender_id: int
    query: str = field(repr=False)
    offset: str = field(repr=False)
    client: "Client | None" = field(default=None, repr=False, compare=False)

    async def answer(
        self,
        results: list[types.TypeInputBotInlineResult],
        *,
        cache_time: int = 300,
        next_offset: str = "",
        private: bool = False,
    ) -> bool:
        if self.client is None:
            raise LifecycleError("event has no client context")
        return await self.client.answer_inline_query(
            self.query_id, results, cache_time=cache_time, next_offset=next_offset, private=private
        )


Event: TypeAlias = (
    MessageEvent
    | RawUpdateEvent
    | DeletedMessagesEvent
    | ReadHistoryEvent
    | UserStatusEvent
    | ChatActionEvent
    | CallbackQueryEvent
    | InlineQueryEvent
)
E = TypeVar("E")


def from_update(update: TLObject, client: "Client") -> list[Event]:
    """Build events from an accepted native Update; never infer unknown chat IDs."""
    from .peer_utils import get_peer_id

    result: list[Event] = [RawUpdateEvent(update, client)]
    if isinstance(update, (types.UpdateDeleteMessages, types.UpdateDeleteChannelMessages)):
        channel = getattr(update, "channel_id", None)
        result.append(
            DeletedMessagesEvent(
                tuple(update.messages),
                -1000000000000 - channel if channel is not None else None,
                client,
            )
        )
    elif isinstance(
        update,
        (
            types.UpdateReadHistoryInbox,
            types.UpdateReadHistoryOutbox,
            types.UpdateReadChannelInbox,
            types.UpdateReadChannelOutbox,
        ),
    ):
        channel = getattr(update, "channel_id", None)
        peer = -1000000000000 - channel if channel is not None else get_peer_id(update.peer)
        outbox = isinstance(update, (types.UpdateReadHistoryOutbox, types.UpdateReadChannelOutbox))
        result.append(ReadHistoryEvent(peer, update.max_id, outbox, client))
    elif isinstance(update, types.UpdateUserStatus):
        result.append(UserStatusEvent(update.user_id, update.status, client))
    elif isinstance(update, (types.UpdateBotCallbackQuery, types.UpdateInlineBotCallbackQuery)):
        inline = isinstance(update, types.UpdateInlineBotCallbackQuery)
        result.append(
            CallbackQueryEvent(
                update.query_id,
                update.user_id,
                update.data,
                None if inline else get_peer_id(update.peer),
                update.msg_id if isinstance(update, types.UpdateBotCallbackQuery) else None,
                update.msg_id if inline else None,
                update.game_short_name,
                client,
            )
        )
    elif isinstance(update, types.UpdateBotInlineQuery):
        result.append(
            InlineQueryEvent(update.query_id, update.user_id, update.query, update.offset, client)
        )
    return result


Handler = Callable[[MessageEvent], Awaitable[None]]
ErrorHandler = Callable[[Event, Exception], Awaitable[None]]


class Dispatcher:
    """One worker; events arrive in order, handlers use stable priority order.

    Full queues block the producer. A cancelled or failing callback is reported
    and does not discard the event for subsequent handlers. Stop cancels the
    worker; pending events are not durably persisted by this dispatcher.
    """

    def __init__(self, size: int, on_error: ErrorHandler | None = None) -> None:
        self._queue: asyncio.Queue[Event] = asyncio.Queue(size)
        self._handlers: list[
            tuple[int, Callable[[Any], Awaitable[None]], Filter, type[Any], bool | None]
        ] = []
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
        self.add_event(callback, MessageEvent, predicate, edited=edited, priority=priority)

    def add_event(
        self,
        callback: Callable[[E], Awaitable[None]],
        event_type: type[E],
        predicate: Filter = all_messages,
        *,
        edited: bool | None = None,
        priority: int = 0,
    ) -> None:
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ConfigurationError("handler priority must be an integer")
        self._handlers.append((priority, callback, predicate, event_type, edited))
        self._handlers.sort(key=lambda item: item[0])

    def remove(self, callback: Callable[..., Awaitable[None]]) -> int:
        before = len(self._handlers)
        self._handlers[:] = [item for item in self._handlers if item[1] != callback]
        return before - len(self._handlers)

    def interested(self, event: Event) -> bool:
        """Check routing only; user predicates run once, inside dispatch."""
        return any(isinstance(event, item[3]) for item in self._handlers)

    def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("dispatcher already running")
        self._task = asyncio.create_task(self._run(), name="gramflux-dispatch")

    async def put(self, event: Event) -> None:
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

    async def _report(self, event: Event, exc: Exception) -> None:
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
                for _, callback, predicate, event_type, edited in tuple(self._handlers):
                    try:
                        if (
                            isinstance(event, event_type)
                            and (edited is None or getattr(event, "edited", False) == edited)
                            and predicate(event)
                        ):
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
