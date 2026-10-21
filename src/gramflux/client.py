"""Small async-first public API with explicit authentication and shutdown."""

import asyncio
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, BinaryIO, Literal, TypeVar

from . import backend as adapter
from . import chats, dialogs, messages
from .auth import LoginPrompts
from .config import Config
from .errors import (
    AuthenticationError,
    AuthenticationRequired,
    ConfigurationError,
    LifecycleError,
    MigrationRequired,
    PasswordRequired,
    SerializationError,
    TransportError,
    UnsupportedFeature,
)
from .events import (
    CallbackQueryEvent,
    ChatActionEvent,
    DeletedMessagesEvent,
    Dispatcher,
    ErrorHandler,
    Handler,
    InlineQueryEvent,
    MessageEvent,
    RawUpdateEvent,
    ReadHistoryEvent,
    UserStatusEvent,
    from_update,
)
from .files import CHUNK, Progress, disk, download, media_location, upload
from .files import iter_download as stream_download
from .filters import Filter, all_messages
from .login_state import PendingLogin
from .mtproto.srp import compute_check
from .operations import TelegramMethods
from .pagination import MessageIDs, count, message_ids
from .peers import Entity, InputPeer, PeerLike, PeerResolver, as_channel, as_user
from .raw import functions, types
from .sessions import Session, session_path
from .storage import MemoryStorage, SQLiteStorage, Storage
from .tl.model import TLObject

if TYPE_CHECKING:
    from .tl.generated.methods import API

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class LoginChallenge:
    phone: str = field(repr=False)
    code_hash: str = field(repr=False)


class Client(TelegramMethods):
    """Connect without prompting or implicitly logging in.

    Prefer ``Session.open(name)``, ``Session.create(name)`` or ``Session.temporary()``.
    ``session=None`` uses memory; a bare path means open an existing authorized
    GramFlux session. Custom async stores implement :class:`gramflux.storage.Storage`.
    Register handlers before connecting to avoid missing startup updates.
    All methods must run on the same asyncio loop.
    """

    def __init__(
        self,
        session: Session | str | Path | Storage | None = None,
        *,
        api_id: int,
        api_hash: str,
        config: Config | None = None,
        on_handler_error: ErrorHandler | None = None,
        _backend: Any = None,
    ) -> None:
        if isinstance(api_id, bool) or not isinstance(api_id, int) or not 0 < api_id < 2**31:
            raise ConfigurationError("api_id must be a positive signed 32-bit integer")
        if not isinstance(api_hash, str) or not re.fullmatch(r"[a-fA-F0-9]{32}", api_hash):
            raise ConfigurationError("api_hash must contain 32 hexadecimal characters")
        self.config = config or Config()
        self._require_authorized = isinstance(session, Session) and session.require_authorized
        if isinstance(session, Session):
            self._storage: Storage = session._storage()
        elif session is None:
            self._storage = MemoryStorage()
        elif isinstance(session, (str, Path)):
            self._storage = SQLiteStorage(session_path(session), mode="open")
            self._require_authorized = True
        else:
            self._storage = session
        self._backend = (
            _backend
            if _backend is not None
            else adapter.create_backend(api_id, api_hash, self.config)
        )
        self._peers = PeerResolver(self.invoke, self.config.peer_cache_size)
        if isinstance(self._backend, adapter.NativeBackend):
            self._backend.peer_cache = self._peers.cache
        self._dispatcher = Dispatcher(self.config.event_queue_size, on_handler_error)
        self._slots = asyncio.Semaphore(self.config.max_concurrent_requests)
        self._lifecycle = asyncio.Lock()
        self._auth_lock = asyncio.Lock()
        self._pending: set[asyncio.Task[Any]] = set()
        self._connected = False
        self._closing = False
        self._logged_out = False
        self._pending_login: PendingLogin | None = None
        adapter.bind_updates(self._backend, self._receive)
        bind_raw = getattr(self._backend, "add_raw_handler", None)
        if bind_raw is not None:
            bind_raw(self._receive_raw)

    @property
    def connected(self) -> bool:
        return (
            self._connected
            and not self._closing
            and not self._logged_out
            and bool(self._backend.is_connected())
        )

    async def __aenter__(self) -> "Client":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        async with self._lifecycle:
            if self._logged_out:
                raise LifecycleError("create a new Client after logging out")
            if self._connected:
                if self._backend.is_connected():
                    return
                raise LifecycleError("backend disconnected; call disconnect before reconnect")
            self._closing = False
            await self._storage.open()
            try:
                data = await self._storage.load()
                if data is not None:
                    self._pending_login = adapter.restore(self._backend.session, data)
                    self._peers.cache.restore(data)
                if self._require_authorized and (
                    data is None or self._backend.session.auth_key is None
                ):
                    raise AuthenticationRequired()
                async with asyncio.timeout(self.config.request_timeout):
                    await self._backend.connect()
                    if self._require_authorized and not await adapter.is_authorized(self._backend):
                        raise AuthenticationRequired()
                await self._save()
                self._connected = True
                self._dispatcher.start()
                ready = getattr(self._backend, "ready", None)
                if ready is not None:
                    ready()
            except BaseException:
                self._connected = False
                stop_updates = getattr(self._backend, "stop_updates", None)
                if stop_updates is not None:
                    await stop_updates()
                await self._dispatcher.stop()
                try:
                    await self._backend.disconnect()
                finally:
                    await self._storage.close()
                raise

    async def disconnect(self) -> None:
        """Cancel outstanding operations, disconnect, atomically save, release storage.

        Use from the application's main task. A callback should signal that task
        to shut down, rather than await disconnect from inside the dispatcher.
        """
        if asyncio.current_task() is self._dispatcher._task:
            raise LifecycleError("signal the main task to disconnect outside the event handler")
        # Cleanup survives caller cancellation and is joined before returning.
        task = asyncio.create_task(self._disconnect())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.wait({task})
                except asyncio.CancelledError:
                    continue
            # Cancellation wins, but retrieve a simultaneous cleanup exception.
            if not task.cancelled():
                task.exception()
            raise

    async def _disconnect(self) -> None:
        async with self._lifecycle:
            if not self._connected:
                return
            self._closing = True
            try:
                stop_updates = getattr(self._backend, "stop_updates", None)
                if stop_updates is not None:
                    await stop_updates()
                pending = tuple(self._pending)
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                await self._dispatcher.stop()
                try:
                    await self._backend.disconnect()
                finally:
                    await self._save()
            finally:
                self._connected = False
                await self._storage.close()

    async def _save(self) -> None:
        await self._storage.save(
            adapter.snapshot(
                self._backend.session,
                peers=self._peers.cache.dump(),
                clear_authorization=self._logged_out,
                pending_login=self._pending_login,
            )
        )

    async def _run(self, operation: Callable[[], Awaitable[T]], *, migration_retries: int = 0) -> T:
        if not self.connected:
            raise LifecycleError("connect before making requests")
        # Includes admission time; queued callers cannot wait indefinitely.
        async with asyncio.timeout(self.config.request_timeout):
            async with self._slots:
                if not self.connected:
                    raise LifecycleError("client is disconnecting")

                async def execute() -> T:
                    for attempt in range(migration_retries + 1):
                        try:
                            return await operation()
                        except MigrationRequired as error:
                            # Native runtime switches DC before re-raising. Only
                            # opt-in auth operations may repeat after this rejection.
                            if not error.retry_ready or attempt == migration_retries:
                                raise
                    raise AssertionError("unreachable migration retry")

                task = asyncio.create_task(execute())
                self._pending.add(task)
                try:
                    result = await task
                    self._peers.cache.ingest(result)
                    return result
                except (ConnectionError, OSError) as exc:
                    raise TransportError(
                        "connection failed; request outcome may be unknown"
                    ) from exc
                finally:
                    self._pending.discard(task)

    async def is_authorized(self) -> bool:
        authorized = await self._run(lambda: adapter.is_authorized(self._backend))
        if authorized and self._pending_login is not None:
            self._pending_login = None
            await self._save()
        return authorized

    async def login(
        self,
        *,
        phone: str | None = None,
        bot_token: str | None = None,
        max_attempts: int = 3,
        prompts: "LoginPrompts | None" = None,
    ) -> types.User:
        """Explicit interactive login; re-prompt invalid input within a local budget.

        Already authorized sessions return their current user. Flood waits,
        network errors, cancellation and unsupported flows propagate immediately.
        Context entry only connects; it never calls this method implicitly.
        """
        from .auth import login

        async with self._auth_lock:
            return await login(
                self, phone=phone, bot_token=bot_token, max_attempts=max_attempts, prompts=prompts
            )

    async def request_login_code(self, phone: str) -> LoginChallenge:
        """Send a code and commit its challenge for sign_in across process restarts."""
        if not isinstance(phone, str) or not phone.strip():
            raise ConfigurationError("phone number must not be empty")
        if await self.is_authorized():
            raise LifecycleError("session is already authorized")
        if len(phone) > 128:
            raise ConfigurationError("phone number is too long")
        try:
            result = await self._run(
                lambda: self._backend.send_code_request(phone), migration_retries=2
            )
        except PasswordRequired:
            self._pending_login = PendingLogin("password")
            await self._save()
            raise
        if not hasattr(result, "phone_code_hash"):
            raise UnsupportedFeature("this account requires an alternative authorization flow")
        self._pending_login = PendingLogin.load(
            {
                "stage": "code",
                "phone": phone,
                "code_hash": result.phone_code_hash,
            }
        )
        await self._save()
        return LoginChallenge(phone, result.phone_code_hash)

    @property
    def login_stage(self) -> Literal["code", "password"] | None:
        """Saved login step, available after connect; None means no pending flow."""
        return self._pending_login.stage if self._pending_login else None

    @property
    def login_challenge(self) -> LoginChallenge | None:
        """Restore the pending code challenge without requesting another code."""
        pending = self._pending_login
        if pending is None or pending.stage != "code":
            return None
        assert pending.phone is not None and pending.code_hash is not None
        return LoginChallenge(pending.phone, pending.code_hash)

    async def sign_in(
        self,
        challenge: LoginChallenge | None = None,
        code: str | None = None,
    ) -> types.User:
        """Submit a code using an explicit challenge or the saved pending challenge."""
        if not isinstance(code, str) or not code.strip():
            raise ConfigurationError("login code must not be empty")
        if await self.is_authorized():
            raise LifecycleError("session is already authorized")
        challenge = challenge if challenge is not None else self.login_challenge
        if not isinstance(challenge, LoginChallenge):
            raise LifecycleError("no pending code challenge; request a login code first")
        try:
            user: types.User = await self._run(
                lambda: self._backend.sign_in(
                    phone=challenge.phone, code=code, phone_code_hash=challenge.code_hash
                )
            )
        except PasswordRequired:
            self._pending_login = PendingLogin("password")
            await self._save()
            raise
        except AuthenticationError as error:
            if error.name in {
                "PHONE_CODE_EXPIRED",
                "PHONE_CODE_HASH_EMPTY",
                "PHONE_CODE_HASH_INVALID",
            }:
                self._pending_login = None
                await self._save()
            raise
        self._pending_login = None
        await self._save()
        return user

    async def check_password(self, password: str) -> types.User:
        if not isinstance(password, str) or not password:
            raise ConfigurationError("password must not be empty")
        if await self.is_authorized():
            raise LifecycleError("session is already authorized")

        async def verify() -> types.User:
            # SRP performs PBKDF2 and modular exponentiation. Keep it off the loop.
            parameters = await self._backend(functions.account.GetPasswordRequest())
            check = await disk(compute_check, parameters, password)
            authorization = await self._backend(functions.auth.CheckPasswordRequest(password=check))
            user: types.User = await self._backend._on_login(authorization.user)
            return user

        user = await self._run(verify, migration_retries=2)
        self._pending_login = None
        await self._save()
        return user

    async def sign_in_bot(self, token: str) -> types.User:
        if not isinstance(token, str) or not token:
            raise ConfigurationError("bot token must not be empty")
        if await self.is_authorized():
            raise LifecycleError(
                "session is already authorized; use a separate session for another account"
            )
        user: types.User = await self._run(
            lambda: self._backend.sign_in(bot_token=token), migration_retries=2
        )
        self._pending_login = None
        await self._save()
        return user

    async def log_out(self) -> None:
        """Revoke this authorization remotely, clear the saved key and disconnect.

        Not an implicit temporary-session action. A timeout has an ambiguous
        remote outcome; it is not automatically retried. Use from the main task.
        """
        if asyncio.current_task() is self._dispatcher._task:
            raise LifecycleError("signal the main task to log out outside the event handler")
        result = await self.invoke(functions.auth.LogOutRequest())
        if not isinstance(result, types.auth.LoggedOut):
            raise SerializationError("unexpected logout response; local authorization retained")
        self._logged_out = True
        self._pending_login = None
        self._peers.cache.clear()
        await self.disconnect()
        self._backend.session.auth_key = None

    async def get_me(self) -> types.User:
        user: types.User | None = await self._run(self._backend.get_me)
        if user is None:
            raise AuthenticationRequired()
        return user

    async def resolve_peer(self, peer: PeerLike, *, refresh: bool = False) -> InputPeer:
        """Resolve usernames/marked IDs without inventing access hashes."""
        if not self.connected:
            raise LifecycleError("connect before resolving peers")
        return await self._peers.resolve(peer, refresh=refresh)

    async def get_chat(self, peer: PeerLike) -> Entity:
        """Fetch the current basic entity, refreshing the peer cache."""
        return await self._peers.entity(peer)

    async def get_user(self, peer: PeerLike = "me") -> types.User:
        entity = await self.get_chat(peer)
        if not isinstance(entity, types.User):
            raise ConfigurationError("get_user requires a user peer")
        return entity

    async def get_user_full(self, peer: PeerLike = "me") -> types.users.UserFull:
        result: types.users.UserFull = await self.invoke(
            functions.users.GetFullUserRequest(id=as_user(await self.resolve_peer(peer)))
        )
        return result

    async def get_chat_full(self, peer: PeerLike) -> types.messages.ChatFull:
        target = await self.resolve_peer(peer)
        if isinstance(target, types.InputPeerChat):
            request: Any = functions.messages.GetFullChatRequest(chat_id=target.chat_id)
        else:
            request = functions.channels.GetFullChannelRequest(channel=as_channel(target))
        result: types.messages.ChatFull = await self.invoke(request)
        return result

    async def get_contacts(self) -> list[types.User]:
        result = await self.invoke(functions.contacts.GetContactsRequest(hash=0))
        if isinstance(result, types.contacts.ContactsNotModified):
            from .errors import PaginationError

            raise PaginationError("unexpected not-modified contacts response to hash=0")
        return [user for user in result.users if isinstance(user, types.User)]

    async def block_user(self, peer: PeerLike) -> bool:
        target = await self.resolve_peer(peer)
        as_user(target)
        return bool(await self.invoke(functions.contacts.BlockRequest(id=target)))

    async def unblock_user(self, peer: PeerLike) -> bool:
        target = await self.resolve_peer(peer)
        as_user(target)
        return bool(await self.invoke(functions.contacts.UnblockRequest(id=target)))

    async def send_message(
        self,
        peer: PeerLike,
        text: str,
        *,
        reply_to: int | None = None,
        silent: bool = False,
        link_preview: bool = True,
        reply_markup: types.TypeReplyMarkup | None = None,
        entities: list[types.TypeMessageEntity] | None = None,
    ) -> types.Message:
        """Send literal text; no new request is created to retry ambiguous failures."""
        if not isinstance(text, str) or not text:
            raise ConfigurationError("message text must not be empty")
        if reply_to is not None:
            message_ids(reply_to)
        extra: dict[str, Any] = {}
        if reply_markup is not None:
            extra["reply_markup"] = reply_markup
        if entities is not None:
            extra["entities"] = entities
        target = await self.resolve_peer(peer)
        message: types.Message = await self._run(
            lambda: self._backend.send_message(
                target,
                text,
                parse_mode=None,
                reply_to=reply_to,
                silent=silent,
                link_preview=link_preview,
                **extra,
            )
        )
        return message

    def iter_dialogs(
        self,
        *,
        limit: int | None = None,
        folder_id: int = 0,
        page_size: int = 100,
    ) -> AsyncIterator[dialogs.Dialog]:
        """Yield pinned then regular dialogs lazily; folder 0 is the main folder."""
        return dialogs.dialogs(self, limit=limit, folder_id=folder_id, batch_size=page_size)

    async def get_dialogs(self, *, limit: int = 100, folder_id: int = 0) -> list[dialogs.Dialog]:
        count(limit, allow_none=False)
        return [dialog async for dialog in self.iter_dialogs(limit=limit, folder_id=folder_id)]

    def iter_history(
        self,
        peer: PeerLike,
        *,
        limit: int | None = None,
        offset_id: int = 0,
        page_size: int = 100,
    ) -> AsyncIterator[messages.Message]:
        """Newest first; each network page is fetched only when needed."""
        return messages.history(self, peer, limit=limit, offset_id=offset_id, batch_size=page_size)

    async def get_history(
        self, peer: PeerLike, *, limit: int = 100, offset_id: int = 0
    ) -> list[messages.Message]:
        count(limit, allow_none=False)
        return [
            message async for message in self.iter_history(peer, limit=limit, offset_id=offset_id)
        ]

    def iter_search(
        self,
        peer: PeerLike,
        query: str,
        *,
        limit: int | None = None,
        sender: PeerLike | None = None,
        page_size: int = 100,
    ) -> AsyncIterator[messages.Message]:
        return messages.history(
            self, peer, limit=limit, query=query, sender=sender, batch_size=page_size
        )

    async def search_messages(
        self,
        peer: PeerLike,
        query: str,
        *,
        limit: int = 100,
        sender: PeerLike | None = None,
    ) -> list[messages.Message]:
        count(limit, allow_none=False)
        return [
            message async for message in self.iter_search(peer, query, limit=limit, sender=sender)
        ]

    async def get_messages(self, peer: PeerLike, ids: MessageIDs) -> list[messages.Message | None]:
        """Preserve ID order/duplicates; unavailable or other-chat messages are None."""
        return await messages.get_messages(self, peer, ids)

    async def edit_message(
        self,
        peer: PeerLike,
        message_id: int,
        text: str,
        *,
        link_preview: bool = True,
    ) -> Any:
        message_ids(message_id)
        if not isinstance(text, str) or not text:
            raise ConfigurationError("edited text must not be empty")
        return await self.invoke(
            functions.messages.EditMessageRequest(
                peer=await self.resolve_peer(peer),
                id=message_id,
                message=text,
                no_webpage=not link_preview,
                entities=[],
            )
        )

    async def delete_messages(
        self, peer: PeerLike, ids: MessageIDs, *, revoke: bool = False
    ) -> list[types.messages.AffectedMessages]:
        return await messages.delete(self, peer, ids, revoke=revoke)

    async def forward_messages(
        self,
        peer: PeerLike,
        from_peer: PeerLike,
        ids: MessageIDs,
        *,
        silent: bool = False,
        drop_author: bool = False,
    ) -> list[Any]:
        """Return Telegram Updates per batch; partial success is possible across batches."""
        return await messages.forward(
            self, peer, from_peer, ids, silent=silent, drop_author=drop_author
        )

    async def read_history(self, peer: PeerLike, *, max_id: int = 0) -> Any:
        return await messages.read(self, peer, max_id=max_id)

    async def pin_message(self, peer: PeerLike, message_id: int, *, silent: bool = True) -> Any:
        message_ids(message_id)
        return await self.invoke(
            functions.messages.UpdatePinnedMessageRequest(
                peer=await self.resolve_peer(peer), id=message_id, silent=silent
            )
        )

    async def unpin_message(self, peer: PeerLike, message_id: int) -> Any:
        message_ids(message_id)
        return await self.invoke(
            functions.messages.UpdatePinnedMessageRequest(
                peer=await self.resolve_peer(peer), id=message_id, unpin=True
            )
        )

    def iter_members(
        self,
        peer: PeerLike,
        *,
        limit: int | None = None,
        query: str = "",
        page_size: int = 100,
    ) -> AsyncIterator[chats.ChatMember]:
        return chats.members(self, peer, limit=limit, query=query, batch_size=page_size)

    async def get_members(
        self, peer: PeerLike, *, limit: int = 100, query: str = ""
    ) -> list[chats.ChatMember]:
        count(limit, allow_none=False)
        return [member async for member in self.iter_members(peer, limit=limit, query=query)]

    async def join_chat(self, peer: PeerLike) -> Any:
        return await chats.join(self, peer)

    async def leave_chat(self, peer: PeerLike) -> Any:
        return await chats.leave(self, peer)

    async def import_invite(self, invite_hash: str) -> Any:
        if not isinstance(invite_hash, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,256}", invite_hash
        ):
            raise ConfigurationError("provide the invite hash, not a URL")
        return await self.invoke(functions.messages.ImportChatInviteRequest(hash=invite_hash))

    @cached_property
    def api(self) -> "API":
        """Typed asynchronous access to every pinned official Telegram function.

        Arguments use native TL objects; this interface performs no peer resolution
        or automatic retry. It shares this client's lifecycle and request engine.
        """
        from .tl.generated.methods import API

        return API(self)

    async def invoke(self, request: Any) -> Any:
        """Invoke an independently generated official API method on the native runtime."""
        if not isinstance(request, TLObject) or not request.definition.method:
            raise TypeError("invoke requires a native generated API request")
        return await self._run(lambda: self._backend(request))

    def on_message(
        self, predicate: Filter = all_messages, *, edited: bool = False, priority: int = 0
    ) -> Callable[[Handler], Handler]:
        def register(callback: Handler) -> Handler:
            self._dispatcher.add(callback, predicate, edited=edited, priority=priority)
            return callback

        return register

    def off_message(self, callback: Handler) -> int:
        """Remove registrations for this callback; affects subsequent events."""
        return self._dispatcher.remove(callback)

    def on(
        self,
        event_type: type[T],
        predicate: Filter = all_messages,
        *,
        priority: int = 0,
    ) -> Callable[[Callable[[T], Awaitable[None]]], Callable[[T], Awaitable[None]]]:
        """Subscribe to a typed event with bounded, ordered callback execution."""
        allowed = (
            MessageEvent,
            RawUpdateEvent,
            DeletedMessagesEvent,
            ReadHistoryEvent,
            UserStatusEvent,
            ChatActionEvent,
            CallbackQueryEvent,
            InlineQueryEvent,
        )
        if event_type not in allowed:
            raise ConfigurationError("provide a supported GramFlux event class")

        def register(callback: Callable[[T], Awaitable[None]]) -> Callable[[T], Awaitable[None]]:
            self._dispatcher.add_event(callback, event_type, predicate, priority=priority)
            return callback

        return register

    def on_edited_message(
        self,
        predicate: Filter = all_messages,
        *,
        priority: int = 0,
    ) -> Callable[[Handler], Handler]:
        return self.on_message(predicate, edited=True, priority=priority)

    def on_raw_update(
        self,
        predicate: Filter = all_messages,
        *,
        priority: int = 0,
    ) -> Callable[
        [Callable[[RawUpdateEvent], Awaitable[None]]], Callable[[RawUpdateEvent], Awaitable[None]]
    ]:
        return self.on(RawUpdateEvent, predicate, priority=priority)

    def on_deleted_messages(
        self,
        predicate: Filter = all_messages,
        *,
        priority: int = 0,
    ) -> Callable[
        [Callable[[DeletedMessagesEvent], Awaitable[None]]],
        Callable[[DeletedMessagesEvent], Awaitable[None]],
    ]:
        return self.on(DeletedMessagesEvent, predicate, priority=priority)

    def on_read_history(
        self,
        predicate: Filter = all_messages,
        *,
        priority: int = 0,
    ) -> Callable[
        [Callable[[ReadHistoryEvent], Awaitable[None]]],
        Callable[[ReadHistoryEvent], Awaitable[None]],
    ]:
        return self.on(ReadHistoryEvent, predicate, priority=priority)

    def on_user_status(
        self,
        predicate: Filter = all_messages,
        *,
        priority: int = 0,
    ) -> Callable[
        [Callable[[UserStatusEvent], Awaitable[None]]], Callable[[UserStatusEvent], Awaitable[None]]
    ]:
        return self.on(UserStatusEvent, predicate, priority=priority)

    def on_chat_action(
        self,
        predicate: Filter = all_messages,
        *,
        priority: int = 0,
    ) -> Callable[
        [Callable[[ChatActionEvent], Awaitable[None]]], Callable[[ChatActionEvent], Awaitable[None]]
    ]:
        return self.on(ChatActionEvent, predicate, priority=priority)

    def on_callback_query(
        self,
        predicate: Filter = all_messages,
        *,
        priority: int = 0,
    ) -> Callable[
        [Callable[[CallbackQueryEvent], Awaitable[None]]],
        Callable[[CallbackQueryEvent], Awaitable[None]],
    ]:
        return self.on(CallbackQueryEvent, predicate, priority=priority)

    def on_inline_query(
        self,
        predicate: Filter = all_messages,
        *,
        priority: int = 0,
    ) -> Callable[
        [Callable[[InlineQueryEvent], Awaitable[None]]],
        Callable[[InlineQueryEvent], Awaitable[None]],
    ]:
        return self.on(InlineQueryEvent, predicate, priority=priority)

    def off_event(self, callback: Callable[..., Awaitable[None]]) -> int:
        return self._dispatcher.remove(callback)

    async def _receive_raw(self, update: TLObject) -> None:
        offered = False
        for event in from_update(update, self):
            if self._dispatcher.interested(event):
                await self._dispatcher.put(event)
                offered = True
        if offered and self._connected:
            await self._dispatcher.join()

    async def _receive(self, event: Any) -> None:
        entities = getattr(event, "_entities", {})
        if isinstance(entities, dict):
            self._peers.cache.ingest(list(entities.values()))
        chat_type: Literal["private", "group", "channel"] | None = (
            "private"
            if getattr(event, "is_private", False)
            else "group"
            if getattr(event, "is_group", False)
            else "channel"
            if getattr(event, "is_channel", False)
            else None
        )
        if isinstance(event.message, types.MessageService):
            await self._dispatcher.put(ChatActionEvent(event.message, self))
        await self._dispatcher.put(
            MessageEvent(
                event.message,
                bool(getattr(event, "edited", False)),
                self,
                chat_type,
            )
        )
        if self._connected:
            # Do not advance native pts/seq past handlers cancelled by shutdown.
            await self._dispatcher.join()

    async def run_until_disconnected(self) -> None:
        if not self.connected:
            raise LifecycleError("connect before waiting for updates")
        await asyncio.shield(self._backend.disconnected)
        failure = getattr(self._backend, "failure", None)
        if failure is not None:
            raise failure

    async def upload_file(
        self,
        source: str | Path | BinaryIO,
        *,
        name: str | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.InputFile | types.InputFileBig:
        """Stream ordered reads into at most concurrency outstanding part RPCs."""
        return await upload(
            self.invoke,
            source,
            name=name,
            on_progress=on_progress,
            part_size=part_size,
            concurrency=concurrency,
        )

    async def send_file(
        self,
        peer: PeerLike,
        file: types.InputFile | types.InputFileBig | types.TypeInputMedia,
        *,
        caption: str = "",
        reply_to: int | None = None,
        as_document: bool = False,
        mime_type: str | None = None,
    ) -> types.Message:
        if reply_to is not None:
            message_ids(reply_to)
        target = await self.resolve_peer(peer)
        message: types.Message = await self._run(
            lambda: self._backend.send_file(
                target,
                file,
                caption=caption,
                parse_mode=None,
                reply_to=reply_to,
                force_document=as_document,
                mime_type=mime_type,
            )
        )
        return message

    async def send_document(
        self,
        peer: PeerLike,
        source: str | Path | BinaryIO,
        *,
        name: str | None = None,
        caption: str = "",
        mime_type: str | None = None,
        reply_to: int | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.Message:
        target = await self.resolve_peer(peer)
        if reply_to is not None:
            message_ids(reply_to)
        file = await self.upload_file(
            source, name=name, on_progress=on_progress, part_size=part_size, concurrency=concurrency
        )
        return await self.send_file(
            target, file, caption=caption, reply_to=reply_to, as_document=True, mime_type=mime_type
        )

    async def send_photo(
        self,
        peer: PeerLike,
        source: str | Path | BinaryIO,
        *,
        caption: str = "",
        reply_to: int | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.Message:
        target = await self.resolve_peer(peer)
        if reply_to is not None:
            message_ids(reply_to)
        file = await self.upload_file(
            source, on_progress=on_progress, part_size=part_size, concurrency=concurrency
        )
        media = types.InputMediaUploadedPhoto(file=file)
        return await self.send_file(target, media, caption=caption, reply_to=reply_to)

    def iter_download(
        self,
        location: Any,
        *,
        size: int,
        offset: int = 0,
        length: int | None = None,
        request_size: int = CHUNK,
    ) -> AsyncIterator[bytes]:
        """Read an exact byte range lazily; no prefetch, implicit retry or resume."""
        return stream_download(
            self.invoke,
            location,
            size=size,
            offset=offset,
            length=length,
            request_size=request_size,
        )

    async def iter_download_media(
        self,
        message: types.Message,
        *,
        offset: int = 0,
        length: int | None = None,
        request_size: int = CHUNK,
    ) -> AsyncIterator[bytes]:
        """Yield document/photo bytes on demand, including arbitrary range edges."""
        location, size = media_location(message)
        async for block in self.iter_download(
            location, size=size, offset=offset, length=length, request_size=request_size
        ):
            yield block

    async def download_file(
        self,
        location: Any,
        destination: str | Path | BinaryIO,
        *,
        size: int,
        on_progress: Progress | None = None,
        offset: int = 0,
        length: int | None = None,
        request_size: int = CHUNK,
    ) -> Path | None:
        """Write an exact range; path targets never overwrite existing files."""
        return await download(
            self.invoke,
            location,
            destination,
            size=size,
            on_progress=on_progress,
            offset=offset,
            length=length,
            request_size=request_size,
        )

    async def download_media(
        self,
        message: types.Message,
        destination: str | Path | BinaryIO,
        *,
        on_progress: Progress | None = None,
        offset: int = 0,
        length: int | None = None,
        request_size: int = CHUNK,
    ) -> Path | None:
        """Resolve document/photo metadata and stream an exact range to the destination."""
        location, size = media_location(message)
        return await self.download_file(
            location,
            destination,
            size=size,
            on_progress=on_progress,
            offset=offset,
            length=length,
            request_size=request_size,
        )
