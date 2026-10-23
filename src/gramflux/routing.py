"""Declarative routing compiled into the Client's existing event subscriptions."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, TypeVar, cast, get_args

from . import filters
from .errors import ConfigurationError, LifecycleError
from .events import (
    CallbackQueryEvent,
    ChatActionEvent,
    DeletedMessagesEvent,
    Event,
    Handler,
    InlineQueryEvent,
    MessageEvent,
    RawUpdateEvent,
    ReadHistoryEvent,
    UserStatusEvent,
)
from .filters import Filter, all_messages
from .raw import types

if TYPE_CHECKING:
    from .client import Client

E = TypeVar("E", bound=Event)
Callback = Callable[..., Awaitable[None]]


class Chat(StrEnum):
    """Message conversation classification; no resolution or network access."""

    PRIVATE = "private"
    GROUP = "group"
    CHANNEL = "channel"


class Direction(StrEnum):
    """Select message direction, or leave it unrestricted."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    ANY = "any"


@dataclass(frozen=True, slots=True)
class CommandContext:
    """Message command context; raw_args preserves the original token suffix.

    args uses Unicode whitespace splitting, without shell quoting or escaping.
    With parse_args=False, args is None. The original event remains available.
    """

    event: MessageEvent = field(repr=False)
    command: str
    args: tuple[str, ...] | None = field(repr=False)
    raw_args: str = field(repr=False)

    @property
    def message(self) -> types.Message:
        return cast(types.Message, self.event.message)

    @property
    def client(self) -> Client:
        if self.event.client is None:
            raise LifecycleError("command event has no bound client")
        return self.event.client

    async def reply(self, text: str, *, silent: bool = False) -> types.Message:
        """Use the original event helper, preserving its reply/permission semantics."""
        return await self.event.reply(text, silent=silent)


@dataclass(frozen=True, slots=True)
class _Route:
    callback: Callable[[Event], Awaitable[None]]
    original: object
    event_type: type[Event]
    predicate: Filter
    priority: int
    edited: bool | None


class Router:
    """Local ordered definitions, independent of any Client.

    Inclusion takes an immutable snapshot and freezes the whole included tree.
    Frozen definitions can be reused by multiple clients. Children are expanded
    at their inclusion position. No dispatcher, task or queue is created here.
    """

    def __init__(self, name: str = "default") -> None:
        if not isinstance(name, str) or not name:
            raise ConfigurationError("router name must be a nonempty string")
        self.name = name
        self._entries: list[_Route | Router] = []
        self._frozen = False

    def _mutable(self) -> None:
        if self._frozen:
            raise LifecycleError("router definitions are frozen after inclusion")

    def _tree(self) -> Iterator[Router]:
        yield self
        for entry in self._entries:
            if isinstance(entry, Router):
                yield from entry._tree()

    def _routes(self) -> Iterator[_Route]:
        for entry in self._entries:
            if isinstance(entry, Router):
                yield from entry._routes()
            else:
                yield entry

    def include(self, router: Router) -> Router:
        """Include a child at this position; reject cycles and overlapping trees."""
        self._mutable()
        if not isinstance(router, Router):
            raise ConfigurationError("include requires a Router")
        if set(self._tree()) & set(router._tree()):
            raise ConfigurationError("router inclusion would duplicate a tree or create a cycle")
        self._entries.append(router)
        return router

    def _register(
        self,
        event_type: type[E],
        predicate: Filter,
        priority: int,
        edited: bool | None,
    ) -> Callable[[Callable[[E], Awaitable[None]]], Callable[[E], Awaitable[None]]]:
        self._mutable()
        if event_type not in get_args(Event):
            raise ConfigurationError("provide a supported GramFlux event class")
        if edited is not None and not isinstance(edited, bool):
            raise ConfigurationError("edited must be a bool")
        if not isinstance(predicate, Filter):
            raise ConfigurationError("router predicates must be GramFlux Filters")
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ConfigurationError("handler priority must be an integer")

        def register(callback: Callable[[E], Awaitable[None]]) -> Callable[[E], Awaitable[None]]:
            self._mutable()
            if any(
                r.original == callback and r.event_type is event_type and r.edited == edited
                for r in self._routes()
            ):
                raise ConfigurationError("callback already registered for this router event kind")

            async def invoke(event: Event) -> None:
                await callback(cast(E, event))

            self._entries.append(
                _Route(invoke, callback, cast(type[Event], event_type), predicate, priority, edited)
            )
            return callback

        return register

    def on(
        self, event_type: type[E], predicate: Filter = all_messages, *, priority: int = 0
    ) -> Callable[[Callable[[E], Awaitable[None]]], Callable[[E], Awaitable[None]]]:
        """Define any currently supported typed event, retaining the original event."""
        return self._register(event_type, predicate, priority, None)

    def message(
        self, predicate: Filter = all_messages, *, edited: bool = False, priority: int = 0
    ) -> Callable[[Handler], Handler]:
        """Define a new-message handler, or an edited-message handler explicitly."""
        return self._register(MessageEvent, predicate, priority, edited)

    def edited_message(
        self, predicate: Filter = all_messages, *, priority: int = 0
    ) -> Callable[[Handler], Handler]:
        return self.message(predicate, edited=True, priority=priority)

    def remove(self, callback: Callback) -> int:
        """Remove this tree's definitions before it is frozen; count removed routes."""
        self._mutable()
        for router in self._tree():
            router._mutable()
        count = 0
        for router in self._tree():
            before = len(router._entries)
            router._entries[:] = [
                e for e in router._entries if isinstance(e, Router) or e.original != callback
            ]
            count += before - len(router._entries)
        return count

    def raw_update(
        self, predicate: Filter = all_messages, *, priority: int = 0
    ) -> Callable[
        [Callable[[RawUpdateEvent], Awaitable[None]]], Callable[[RawUpdateEvent], Awaitable[None]]
    ]:
        """Register the original RawUpdateEvent; the shared dispatcher retains delivery policy."""
        return self.on(RawUpdateEvent, predicate, priority=priority)

    def deleted_messages(
        self, predicate: Filter = all_messages, *, priority: int = 0
    ) -> Callable[
        [Callable[[DeletedMessagesEvent], Awaitable[None]]],
        Callable[[DeletedMessagesEvent], Awaitable[None]],
    ]:
        """Register DeletedMessagesEvent on the shared dispatcher."""
        return self.on(DeletedMessagesEvent, predicate, priority=priority)

    def read_history(
        self, predicate: Filter = all_messages, *, priority: int = 0
    ) -> Callable[
        [Callable[[ReadHistoryEvent], Awaitable[None]]],
        Callable[[ReadHistoryEvent], Awaitable[None]],
    ]:
        """Register the original ReadHistoryEvent; the shared dispatcher retains delivery policy."""
        return self.on(ReadHistoryEvent, predicate, priority=priority)

    def user_status(
        self, predicate: Filter = all_messages, *, priority: int = 0
    ) -> Callable[
        [Callable[[UserStatusEvent], Awaitable[None]]], Callable[[UserStatusEvent], Awaitable[None]]
    ]:
        """Register the original UserStatusEvent; the shared dispatcher retains delivery policy."""
        return self.on(UserStatusEvent, predicate, priority=priority)

    def chat_action(
        self, predicate: Filter = all_messages, *, priority: int = 0
    ) -> Callable[
        [Callable[[ChatActionEvent], Awaitable[None]]], Callable[[ChatActionEvent], Awaitable[None]]
    ]:
        """Register the original ChatActionEvent; the shared dispatcher retains delivery policy."""
        return self.on(ChatActionEvent, predicate, priority=priority)

    def callback_query(
        self, predicate: Filter = all_messages, *, priority: int = 0
    ) -> Callable[
        [Callable[[CallbackQueryEvent], Awaitable[None]]],
        Callable[[CallbackQueryEvent], Awaitable[None]],
    ]:
        """Register CallbackQueryEvent on the shared dispatcher."""
        return self.on(CallbackQueryEvent, predicate, priority=priority)

    def inline_query(
        self, predicate: Filter = all_messages, *, priority: int = 0
    ) -> Callable[
        [Callable[[InlineQueryEvent], Awaitable[None]]],
        Callable[[InlineQueryEvent], Awaitable[None]],
    ]:
        """Register the original InlineQueryEvent; the shared dispatcher retains delivery policy."""
        return self.on(InlineQueryEvent, predicate, priority=priority)

    def command(
        self,
        *names: str,
        chat: Chat | None = None,
        direction: Direction = Direction.INCOMING,
        username: str | None = None,
        prefix: str = "/",
        case_sensitive: bool = False,
        parse_args: bool = True,
        predicate: Filter = all_messages,
        priority: int = 0,
    ) -> Callable[
        [Callable[[CommandContext], Awaitable[None]]], Callable[[CommandContext], Awaitable[None]]
    ]:
        """Select commands with existing filters; optionally split arguments on whitespace."""
        if chat is not None and not isinstance(chat, Chat):
            raise ConfigurationError("chat must be a Chat value or None")
        if not isinstance(direction, Direction) or not isinstance(parse_args, bool):
            raise ConfigurationError("invalid command direction or parse_args")
        selected = predicate & filters.command(
            *names, prefix=prefix, username=username, case_sensitive=case_sensitive
        )
        if chat is not None:
            selected = selected & Filter(lambda e: getattr(e, "chat_type", None) == chat.value)
        if direction is Direction.INCOMING:
            selected = selected & filters.incoming
        elif direction is Direction.OUTGOING:
            selected = selected & filters.outgoing
        # Validate eagerly, so a bad priority cannot fail midway through client mounting.
        self._register(MessageEvent, selected, priority, False)

        def register(
            callback: Callable[[CommandContext], Awaitable[None]],
        ) -> Callable[[CommandContext], Awaitable[None]]:
            if any(route.original == callback for route in self._routes()):
                raise ConfigurationError("command callback already registered")

            async def invoke(event: MessageEvent) -> None:
                token = re.search(r"\S+", event.text)
                if token is None:
                    return
                command = token.group()[len(prefix) :].split("@", 1)[0]
                if not case_sensitive:
                    command = command.casefold()
                raw = event.text[token.end() :]
                await callback(
                    CommandContext(event, command, tuple(raw.split()) if parse_args else None, raw)
                )

            self.message(selected, priority=priority)(invoke)
            route = self._entries[-1]
            assert isinstance(route, _Route)
            self._entries[-1] = _Route(
                route.callback,
                callback,
                route.event_type,
                route.predicate,
                route.priority,
                route.edited,
            )
            return callback

        return register


class Subscription:
    """Client-owned router mount; close removes only this mount's registrations."""

    def __init__(self, owner: EventManager, router: Router) -> None:
        self._owner = owner
        self.router = router
        self._handlers: list[tuple[object, Callback]] = []
        self._active = True

    @property
    def active(self) -> bool:
        """Whether this mount is still owned by the client event manager."""
        return self._active

    def close(self) -> int:
        """Idempotent synchronous unsubscription; current dispatch snapshots finish."""
        if not self.active:
            return 0
        removed = sum(self._owner._client.off_event(fn) for _, fn in self._handlers)
        self._handlers.clear()
        self._active = False
        self._owner._mounts.pop(self.router, None)
        return removed


class EventManager:
    """Compile routers through public Client subscriptions, sharing its dispatcher."""

    def __init__(self, client: Client) -> None:
        self._client = client
        self._mounts: dict[Router, Subscription] = {}

    def include(self, router: Router) -> Subscription:
        """Mount a router once per client; repeated inclusion returns its active mount."""
        if not isinstance(router, Router):
            raise ConfigurationError("include requires a Router")
        if router in self._mounts:
            return self._mounts[router]
        nodes = list(router._tree())
        tree = set(nodes)
        if len(nodes) != len(tree):
            raise ConfigurationError("router tree contains overlapping children")
        if any(tree & set(root._tree()) for root in self._mounts):
            raise ConfigurationError("a child router is already mounted on this client")
        mount = Subscription(self, router)
        try:
            for route in router._routes():

                async def handler(event: Event, route: _Route = route) -> None:
                    await route.callback(event)

                if route.event_type is MessageEvent and route.edited is not None:
                    self._client.on_message(
                        route.predicate, edited=route.edited, priority=route.priority
                    )(handler)
                else:
                    self._client.on(route.event_type, route.predicate, priority=route.priority)(
                        handler
                    )
                mount._handlers.append((route.original, handler))
        except BaseException:
            mount.close()
            raise
        for item in tree:
            item._frozen = True
        self._mounts[router] = mount
        return mount

    def exclude(self, router: Router) -> int:
        """Remove an included root; children are removed with it."""
        mount = self._mounts.get(router)
        return mount.close() if mount is not None else 0

    def remove(self, callback: Callback) -> int:
        """Remove matching routed and legacy registrations on this client only."""
        count = self._client.off_event(callback)
        for mount in self._mounts.values():
            for original, handler in tuple(mount._handlers):
                if original == callback:
                    count += self._client.off_event(handler)
                    mount._handlers.remove((original, handler))
        return count

    def on(
        self, event_type: type[E], predicate: Filter = all_messages, *, priority: int = 0
    ) -> Callable[[Callable[[E], Awaitable[None]]], Callable[[E], Awaitable[None]]]:
        return self._client.on(event_type, predicate, priority=priority)

    def message(
        self, predicate: Filter = all_messages, *, edited: bool = False, priority: int = 0
    ) -> Callable[[Handler], Handler]:
        return self._client.on_message(predicate, edited=edited, priority=priority)
