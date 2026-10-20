"""Small async-first public API with explicit authentication and shutdown."""

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, BinaryIO, TypeVar

from telethon import errors as backend_errors
from telethon import events as backend_events
from telethon.password import compute_check
from telethon.tl import functions, types
from telethon.tl.tlobject import TLRequest

from . import backend as adapter
from .config import Config
from .errors import ConfigurationError, LifecycleError, TransportError, UnsupportedFeature
from .events import Dispatcher, ErrorHandler, Handler, MessageEvent
from .files import Progress, disk, download, upload
from .filters import Filter, all_messages
from .storage import MemoryStorage, SQLiteStorage, Storage
from .tl.model import TLObject

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class LoginChallenge:
    phone: str = field(repr=False)
    code_hash: str = field(repr=False)


class Client:
    """Connect without prompting or implicitly logging in.

    ``session=None`` uses memory. A path creates a GramFlux-only SQLite database;
    custom asynchronous stores implement :class:`gramflux.storage.Storage`.
    Register handlers before connecting to avoid missing startup updates.
    All methods must run on the same asyncio loop.
    """

    def __init__(
        self,
        session: str | Path | Storage | None = None,
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
        if session is None:
            self._storage: Storage = MemoryStorage()
        elif isinstance(session, (str, Path)):
            path = Path(session)
            self._storage = SQLiteStorage(path if path.suffix else path.with_suffix(".session"))
        else:
            self._storage = session
        self._backend = (
            _backend
            if _backend is not None
            else adapter.create_backend(api_id, api_hash, self.config)
        )
        self._dispatcher = Dispatcher(self.config.event_queue_size, on_handler_error)
        self._slots = asyncio.Semaphore(self.config.max_concurrent_requests)
        self._lifecycle = asyncio.Lock()
        self._pending: set[asyncio.Task[Any]] = set()
        self._connected = False
        self._closing = False
        adapter.bind_updates(self._backend, self._receive)

    @property
    def connected(self) -> bool:
        return self._connected and not self._closing and bool(self._backend.is_connected())

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
            if self._connected:
                if self._backend.is_connected():
                    return
                raise LifecycleError("backend disconnected; call disconnect before reconnect")
            self._closing = False
            await self._storage.open()
            try:
                data = await self._storage.load()
                if data is not None:
                    adapter.restore(self._backend.session, data)
                self._dispatcher.start()
                async with asyncio.timeout(self.config.request_timeout):
                    await self._backend.connect()
                await self._save()
                self._connected = True
            except BaseException:
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
            try:
                await task
            finally:
                raise

    async def _disconnect(self) -> None:
        async with self._lifecycle:
            if not self._connected:
                return
            self._closing = True
            try:
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
        await self._storage.save(adapter.snapshot(self._backend.session))

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
                        except (
                            backend_errors.PhoneMigrateError,
                            backend_errors.NetworkMigrateError,
                            backend_errors.UserMigrateError,
                        ):
                            # Pinned backend has switched DC before re-raising. Only
                            # opt-in auth operations may repeat after this rejection.
                            if attempt == migration_retries:
                                raise
                    raise AssertionError("unreachable migration retry")

                task = asyncio.create_task(execute())
                self._pending.add(task)
                try:
                    return await task
                except backend_errors.RPCError as exc:
                    raise adapter.map_rpc(exc) from None
                except (ConnectionError, OSError) as exc:
                    raise TransportError(
                        "connection failed; request outcome may be unknown"
                    ) from exc
                finally:
                    self._pending.discard(task)

    async def is_authorized(self) -> bool:
        return bool(await self._run(self._backend.is_user_authorized))

    async def request_login_code(self, phone: str) -> LoginChallenge:
        """Send a code; use the returned challenge with sign_in. Never logs phone."""
        if await self.is_authorized():
            raise LifecycleError("session is already authorized")
        result = await self._run(
            lambda: self._backend.send_code_request(phone), migration_retries=2
        )
        if not hasattr(result, "phone_code_hash"):
            raise UnsupportedFeature("this account requires an alternative authorization flow")
        await self._save()
        return LoginChallenge(phone, result.phone_code_hash)

    async def sign_in(self, challenge: LoginChallenge, code: str) -> types.User:
        if not isinstance(code, str) or not code.strip():
            raise ConfigurationError("login code must not be empty")
        if await self.is_authorized():
            raise LifecycleError("session is already authorized")
        user: types.User = await self._run(
            lambda: self._backend.sign_in(
                phone=challenge.phone, code=code, phone_code_hash=challenge.code_hash
            )
        )
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
            authorization = await self._backend(functions.auth.CheckPasswordRequest(check))
            user: types.User = await self._backend._on_login(authorization.user)
            return user

        user = await self._run(verify, migration_retries=2)
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
        await self._save()
        return user

    async def get_me(self) -> types.User:
        user: types.User | None = await self._run(self._backend.get_me)
        if user is None:
            from .errors import AuthenticationError

            raise AuthenticationError(401, "AUTH_KEY_UNREGISTERED")
        return user

    async def send_message(self, peer: Any, text: str) -> types.Message:
        """Send literal text (no implicit Markdown parsing). No application retry."""
        message: types.Message = await self._run(
            lambda: self._backend.send_message(peer, text, parse_mode=None)
        )
        return message

    async def invoke(self, request: Any) -> Any:
        """Invoke a backend-generated raw request from ``gramflux.raw.functions``.

        Independent layer-225 objects are deliberately rejected: they have not
        been validated against the backend's negotiated layer and result reader.
        """
        if isinstance(request, TLObject):
            raise UnsupportedFeature(
                "independent schema objects are offline-only; use gramflux.raw.functions"
            )
        if not isinstance(request, TLRequest):
            raise TypeError("invoke requires a generated API request")
        return await self._run(lambda: self._backend(request))

    def on_message(
        self, predicate: Filter = all_messages, *, edited: bool = False
    ) -> Callable[[Handler], Handler]:
        def register(callback: Handler) -> Handler:
            self._dispatcher.add(callback, predicate, edited=edited)
            return callback

        return register

    async def _receive(self, event: Any) -> None:
        await self._dispatcher.put(
            MessageEvent(event.message, isinstance(event, backend_events.MessageEdited.Event))
        )

    async def run_until_disconnected(self) -> None:
        if not self.connected:
            raise LifecycleError("connect before waiting for updates")
        await asyncio.shield(self._backend.disconnected)

    async def upload_file(
        self,
        source: str | Path | BinaryIO,
        *,
        name: str | None = None,
        on_progress: Progress | None = None,
    ) -> types.InputFile | types.InputFileBig:
        result: types.InputFile | types.InputFileBig = await upload(
            self.invoke, source, name=name, on_progress=on_progress
        )
        return result

    async def send_file(
        self, peer: Any, file: types.InputFile | types.InputFileBig, *, caption: str = ""
    ) -> types.Message:
        message: types.Message = await self._run(
            lambda: self._backend.send_file(peer, file, caption=caption, parse_mode=None)
        )
        return message

    async def download_file(
        self,
        location: Any,
        destination: str | Path | BinaryIO,
        *,
        size: int,
        on_progress: Progress | None = None,
    ) -> Path | None:
        """Download an explicit raw InputFileLocation; destination paths never overwrite."""
        return await download(
            self.invoke, location, destination, size=size, on_progress=on_progress
        )

    async def download_media(
        self,
        message: types.Message,
        destination: str | Path,
        *,
        on_progress: Progress | None = None,
    ) -> Path:
        """Resolve a message's document/photo and use the bounded download pipeline."""
        document = getattr(message, "document", None)
        photo = getattr(message, "photo", None)
        if document is not None:
            location = types.InputDocumentFileLocation(
                document.id, document.access_hash, document.file_reference, ""
            )
            size = document.size
        elif photo is not None:
            candidates = [
                p
                for p in photo.sizes
                if isinstance(p, (types.PhotoSize, types.PhotoSizeProgressive))
            ]
            if not candidates:
                raise UnsupportedFeature("photo has no downloadable full-size thumbnail")
            selected = candidates[-1]
            location = types.InputPhotoFileLocation(
                photo.id, photo.access_hash, photo.file_reference, selected.type
            )
            size = selected.size if isinstance(selected, types.PhotoSize) else max(selected.sizes)
        else:
            raise UnsupportedFeature("message must contain a document or downloadable photo")
        result = await self.download_file(location, destination, size=size, on_progress=on_progress)
        assert result is not None
        return result
