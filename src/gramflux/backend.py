"""GramFlux's own MTProto runtime; no third-party Telegram client dependency."""

import asyncio
import base64
import copy
import json
import logging
import math
import mimetypes
import re
import secrets
from dataclasses import dataclass, field
from typing import Any

from .config import Config
from .errors import (
    AuthenticationError,
    FloodWait,
    GramFluxError,
    MigrationRequired,
    PasswordRequired,
    RPCError,
    SerializationError,
    SessionError,
    TransportError,
    UnsupportedFeature,
)
from .mtproto.auth_key import create_key
from .mtproto.connection import Connection
from .mtproto.crypto import TRUST
from .mtproto.sender import Sender
from .raw import LAYER, functions, types
from .storage import SessionData

DCS = {int(ident): host for ident, host in TRUST["production_dcs"].items()}
_INITIALIZATION_ERRORS = frozenset(
    {
        "API_ID_INVALID",
        "CONNECTION_API_ID_INVALID",
        "CONNECTION_LAYER_INVALID",
        "CONNECTION_NOT_INITED",
        "CONNECTION_LANG_PACK_INVALID",
    }
)


class RedactedLogger(logging.Logger):
    def getChild(self, suffix: str) -> "RedactedLogger":
        return self

    def handle(self, record: logging.LogRecord) -> None:
        safe = copy.copy(record)
        safe.msg = "MTProto diagnostic (payload and exception details suppressed)"
        safe.args = ()
        safe.exc_info = None
        safe.exc_text = None
        safe.stack_info = None
        super().handle(safe)


def backend_logger() -> logging.Logger:
    logger = RedactedLogger("gramflux.mtproto", logging.WARNING)
    logger.addHandler(logging.NullHandler())
    logger.parent = logging.getLogger("gramflux")
    return logger


def rpc_error(code: int, name: str) -> RPCError:
    name = RPCError(code, name).name
    if name == "SESSION_PASSWORD_NEEDED":
        return PasswordRequired(code, name)
    wait = re.fullmatch(r"(?:FLOOD_WAIT|FLOOD_PREMIUM_WAIT|SLOWMODE_WAIT)_(\d+)", name)
    if wait:
        return FloodWait(code, int(wait[1]), name=name)
    migrate = re.fullmatch(r"(?:PHONE|NETWORK|USER|FILE)_MIGRATE_(\d+)", name)
    if migrate:
        return MigrationRequired(code, int(migrate[1]), name=name)
    cls = (
        AuthenticationError
        if code == 401 or name.startswith(("PHONE_", "PASSWORD_", "SESSION_", "API_ID_", "AUTH_"))
        else RPCError
    )
    return cls(code, name)


def map_rpc(error: RPCError) -> RPCError:
    return error


@dataclass(slots=True)
class Key:
    key: bytes = field(repr=False)


@dataclass(slots=True)
class NativeSession:
    dc_id: int = 2
    server_address: str = DCS[2]
    port: int = 443
    auth_key: Key | None = field(default=None, repr=False)
    salt: int = 0
    time_offset: float = 0.0
    states: dict[int, Any] = field(default_factory=dict, repr=False)

    def set_dc(self, dc: int, server: str, port: int) -> None:
        self.dc_id, self.server_address, self.port = dc, server, port

    def get_update_states(self) -> Any:
        return self.states.items()

    def get_update_state(self, entity: int) -> Any:
        return self.states.get(entity)

    def set_update_state(self, entity: int, state: Any) -> None:
        self.states[entity] = state


class NativeBackend:
    def __init__(self, api_id: int, api_hash: str, config: Config) -> None:
        self.api_id, self.api_hash, self.config = api_id, api_hash, config
        self.session = NativeSession()
        self.sender: Sender | None = None
        self._initialized = False
        self._initialize_lock = asyncio.Lock()
        self._handlers: list[Any] = []
        self.update_task: asyncio.Task[None] | None = None
        self.heartbeat_task: asyncio.Task[None] | None = None
        self._user: Any = None
        self.connection_error: Exception | None = None
        self.entities: dict[int, Any] = {}
        self.peer_cache: Any = None
        self._ready = asyncio.Event()
        self._authorized = asyncio.Event()
        self._recover_on_ready = False

    @property
    def failure(self) -> Exception | None:
        return self.connection_error or (self.sender.error if self.sender else None)

    @property
    def disconnected(self) -> asyncio.Future[None]:
        if self.sender is None:
            raise TransportError("native runtime is not connected")
        return self.sender.disconnected

    def is_connected(self) -> bool:
        return self.sender is not None and not self.sender.disconnected.done()

    def add_event_handler(self, callback: Any, builder: Any = None) -> None:
        if callback not in self._handlers:
            self._handlers.append(callback)

    def ready(self) -> None:
        self._ready.set()

    async def connect(self) -> None:
        if self.is_connected():
            return
        self._ready.clear()
        self._authorized.clear()
        self.connection_error = None
        connection = Connection(
            self.session.server_address,
            self.session.port,
            self.config.transport,
            io_timeout=self.config.request_timeout,
        )
        try:
            for attempt in range(self.config.reconnect_attempts + 1):
                try:
                    await connection.connect()
                    break
                except OSError:
                    await connection.close()
                    if attempt == self.config.reconnect_attempts:
                        raise
                    await asyncio.sleep(min(attempt + 1, 3))
            if self.session.auth_key is None:
                key = await create_key(connection, self.session.dc_id)
                self.session.auth_key = Key(key.key)
                self.session.salt, self.session.time_offset = key.salt, key.time_offset
            self.sender = Sender(
                connection,
                self.session.auth_key.key,
                self.session.salt,
                time_offset=self.session.time_offset,
                queue_size=self.config.event_queue_size,
                max_pending=self.config.max_concurrent_requests,
            )
            self.sender.start()
            self._initialized = False
            try:
                current = await self(functions.updates.GetStateRequest())
            except AuthenticationError as error:
                if error.code != 401:
                    raise
            else:
                self._recover_on_ready = 0 in self.session.states
                if not self._recover_on_ready:
                    self.session.states[0] = current
                self._authorized.set()
            self.update_task = asyncio.create_task(self._updates(), name="gramflux-native-updates")
            self.heartbeat_task = asyncio.create_task(
                self._heartbeat(), name="gramflux-native-heartbeat"
            )
        except BaseException:
            # Once started, the sender owns a reader task and pending futures.
            # Closing its socket alone leaves those resources alive on setup
            # rejection (for example an invalid API ID).
            if self.sender is not None:
                await self.sender.close()
                self.sender = None
            await connection.close()
            raise

    async def stop_updates(self) -> None:
        if self.update_task:
            self.update_task.cancel()
            await asyncio.gather(self.update_task, return_exceptions=True)
            self.update_task = None

    async def disconnect(self) -> None:
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            await asyncio.gather(self.heartbeat_task, return_exceptions=True)
            self.heartbeat_task = None
        await self.stop_updates()
        if self.sender:
            await self.sender.close()
            self.session.salt, self.session.time_offset = self.sender.salt, self.sender.offset
            self.connection_error = self.connection_error or self.sender.error

    async def _invoke_initialized(self, request: Any) -> Any:
        if self.sender is None or not self.is_connected():
            raise TransportError("native connection is closed")
        if not self._initialized:
            async with self._initialize_lock:
                if not self._initialized:
                    wrapped = functions.InvokeWithLayerRequest(
                        layer=LAYER,
                        query=functions.InitConnectionRequest(
                            api_id=self.api_id,
                            device_model="GramFlux",
                            system_version="Python",
                            app_version="0.3.0a1",
                            system_lang_code="en",
                            lang_pack="",
                            lang_code="en",
                            query=request,
                        ),
                    )
                    try:
                        result = await self.sender.invoke(
                            wrapped, deadline_seconds=self.config.request_timeout
                        )
                    except RPCError as error:
                        self._initialized = (
                            error.code < 500 and error.name not in _INITIALIZATION_ERRORS
                        )
                        raise
                    self._initialized = True
                    return result
        try:
            return await self.sender.invoke(request, deadline_seconds=self.config.request_timeout)
        except RPCError as error:
            if error.name in _INITIALIZATION_ERRORS:
                self._initialized = False
            raise

    async def __call__(self, request: Any) -> Any:
        try:
            result = await self._invoke_initialized(request)
        except MigrationRequired as error:
            if (
                request.definition.name in {"auth.sendCode", "auth.importBotAuthorization"}
                and self._user is None
            ):
                if error.dc not in DCS:
                    raise UnsupportedFeature("unknown destination data center") from None
                was_ready = self._ready.is_set()
                await self.disconnect()
                self.session = NativeSession(dc_id=error.dc, server_address=DCS[error.dc])
                await self.connect()
                if was_ready:
                    self.ready()
                error.retry_ready = True
            raise
        from .peer_utils import ingest_entities

        ingest_entities(self.entities, result)
        if hasattr(result, "definition") and result.definition.result == "Updates":
            update = result
            if isinstance(result, types.UpdateShortSentMessage):
                if request.definition.name not in {"messages.sendMessage", "messages.sendMedia"}:
                    raise SerializationError("short sent-message result lacks request context")
                if isinstance(request.peer, types.InputPeerSelf) and self._user is None:
                    await self.get_me()
                message = self._sent_message(
                    result, request.peer, request.message, request.random_id
                )
                update = types.UpdateShort(
                    update=types.UpdateNewMessage(
                        message=message, pts=result.pts, pts_count=result.pts_count
                    ),
                    date=result.date,
                )
            assert self.sender is not None
            try:
                self.sender._offer(update)
            except TransportError as error:
                self.connection_error = error
                await self.sender.close()
                raise
        return result

    async def get_me(self) -> Any:
        try:
            result = await self(functions.users.GetUsersRequest(id=[types.InputUserSelf()]))
        except AuthenticationError as error:
            if error.code == 401:
                return None
            raise
        if not result or not isinstance(result[0], types.User):
            raise SerializationError("invalid self-user response")
        self._user = result[0]
        return self._user

    async def send_code_request(self, phone: str) -> Any:
        return await self(
            functions.auth.SendCodeRequest(
                phone_number=phone,
                api_id=self.api_id,
                api_hash=self.api_hash,
                settings=types.CodeSettings(),
            )
        )

    async def _on_login(self, user: Any) -> Any:
        if not isinstance(user, types.User):
            raise SerializationError("authorization did not include a full user")
        self._user = user
        self.session.states[0] = await self(functions.updates.GetStateRequest())
        self._authorized.set()
        return user

    async def sign_in(
        self,
        *,
        phone: str | None = None,
        code: str | None = None,
        phone_code_hash: str | None = None,
        bot_token: str | None = None,
    ) -> Any:
        if bot_token is not None:
            request: Any = functions.auth.ImportBotAuthorizationRequest(
                api_id=self.api_id, api_hash=self.api_hash, bot_auth_token=bot_token, flags=0
            )
        else:
            if phone is None or phone_code_hash is None:
                raise ValueError("phone and challenge are required")
            request = functions.auth.SignInRequest(
                phone_number=phone, phone_code_hash=phone_code_hash, phone_code=code
            )
        result = await self(request)
        if not isinstance(result, types.auth.Authorization):
            raise UnsupportedFeature("signup or alternative authorization is required")
        return await self._on_login(result.user)

    def _target_peer(self, peer: Any) -> Any:
        if isinstance(peer, types.InputPeerSelf):
            if self._user is None:
                raise SerializationError("self identity is required for sent-message normalization")
            return types.PeerUser(user_id=self._user.id)
        if isinstance(peer, (types.InputPeerUser, types.InputPeerUserFromMessage)):
            return types.PeerUser(user_id=peer.user_id)
        if isinstance(peer, types.InputPeerChat):
            return types.PeerChat(chat_id=peer.chat_id)
        if isinstance(peer, (types.InputPeerChannel, types.InputPeerChannelFromMessage)):
            return types.PeerChannel(channel_id=peer.channel_id)
        raise UnsupportedFeature("unsupported sent-message target")

    def _sent_message(self, result: Any, peer: Any, text: str, random_id: int) -> Any:
        from .peer_utils import get_peer_id

        target = self._target_peer(peer)
        if isinstance(result, types.UpdateShortSentMessage):
            return types.Message(
                id=result.id,
                peer_id=target,
                date=result.date,
                message=text,
                out=bool(result.out),
                media=result.media,
                entities=result.entities,
            )
        updates = (
            [result.update]
            if isinstance(result, types.UpdateShort)
            else getattr(result, "updates", [])
        )
        mapped = [
            update.id
            for update in updates
            if isinstance(update, types.UpdateMessageID) and update.random_id == random_id
        ]
        matches = [
            update.message
            for update in updates
            if isinstance(update, (types.UpdateNewMessage, types.UpdateNewChannelMessage))
            and get_peer_id(update.message.peer_id) == get_peer_id(target)
            and (not mapped or update.message.id == mapped[0])
        ]
        if len(matches) == 1:
            return matches[0]
        raise SerializationError(
            "send response cannot be correlated uniquely; remote write may have completed"
        )

    async def send_message(
        self,
        peer: Any,
        text: str,
        *,
        parse_mode: Any = None,
        reply_to: int | None = None,
        silent: bool = False,
        link_preview: bool = True,
    ) -> Any:
        if isinstance(peer, types.InputPeerSelf) and self._user is None:
            await self.get_me()
        random_id = secrets.randbits(63)
        result = await self(
            functions.messages.SendMessageRequest(
                peer=peer,
                message=text,
                random_id=random_id,
                silent=silent,
                no_webpage=not link_preview,
                reply_to=types.InputReplyToMessage(reply_to_msg_id=reply_to)
                if reply_to is not None
                else None,
            )
        )
        return self._sent_message(result, peer, text, random_id)

    async def send_file(
        self,
        peer: Any,
        file: Any,
        *,
        caption: str = "",
        parse_mode: Any = None,
        reply_to: int | None = None,
        force_document: bool = False,
        mime_type: str | None = None,
    ) -> Any:
        if isinstance(file, (types.InputFile, types.InputFileBig)):
            media = types.InputMediaUploadedDocument(
                file=file,
                mime_type=mime_type
                or mimetypes.guess_type(file.name)[0]
                or "application/octet-stream",
                attributes=[types.DocumentAttributeFilename(file_name=file.name)],
                force_file=force_document,
            )
        elif hasattr(file, "definition") and file.definition.result == "InputMedia":
            media = file
        else:
            raise TypeError("send_file requires an uploaded native file or native InputMedia")
        if isinstance(peer, types.InputPeerSelf) and self._user is None:
            await self.get_me()
        random_id = secrets.randbits(63)
        result = await self(
            functions.messages.SendMediaRequest(
                peer=peer,
                media=media,
                message=caption,
                random_id=random_id,
                reply_to=types.InputReplyToMessage(reply_to_msg_id=reply_to)
                if reply_to is not None
                else None,
            )
        )
        return self._sent_message(result, peer, caption, random_id)

    async def _heartbeat(self) -> None:
        from .mtproto import protocol

        try:
            while self.sender is not None:
                await asyncio.sleep(30)
                ping_id = secrets.randbits(63)
                result = await self.sender.invoke(
                    protocol.object("ping_delay_disconnect", ping_id=ping_id, disconnect_delay=60),
                    deadline_seconds=max(15, self.config.request_timeout),
                    _control=True,
                )
                if result.ping_id != ping_id:
                    raise SerializationError("heartbeat correlation mismatch")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.connection_error = TransportError(
                f"native heartbeat failed ({type(error).__name__})"
            )
            if self.sender:
                await self.sender.close()

    async def _updates(self) -> None:
        from .mtproto.updates import UpdateEngine

        engine = UpdateEngine(self)
        try:
            await self._ready.wait()
            await self._authorized.wait()
            if self._recover_on_ready:
                await engine.recover()
                self._recover_on_ready = False
            while self.sender is not None:
                value = await self.sender.updates.get()
                try:
                    if value.definition.name == "new_session_created":
                        await engine.recover()
                    else:
                        await engine.process(value)
                finally:
                    self.sender.updates.task_done()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Fail closed with a value-free error; state is not advanced past failed callbacks.
            self.connection_error = (
                error
                if isinstance(error, GramFluxError)
                else TransportError(
                    f"native update synchronization failed ({type(error).__name__})"
                )
            )
            if self.sender:
                await self.sender.close()


def create_backend(api_id: int, api_hash: str, config: Config) -> NativeBackend:
    return NativeBackend(api_id, api_hash, config)


def bind_updates(backend: Any, callback: Any) -> None:
    backend.add_event_handler(callback, None)


async def is_authorized(backend: Any) -> bool:
    try:
        await backend(functions.updates.GetStateRequest())
    except AuthenticationError as error:
        if error.code == 401:
            return False
        raise
    return True


def snapshot(
    session: Any, *, peers: list[dict[str, object]] | None = None, clear_authorization: bool = False
) -> SessionData:
    key = session.auth_key.key if session.auth_key and not clear_authorization else None
    states = [
        {
            "id": ident,
            "pts": state.pts,
            "qts": state.qts,
            "seq": state.seq,
            "date": int(state.date.timestamp()) if hasattr(state.date, "timestamp") else state.date,
            "unread_count": state.unread_count,
        }
        for ident, state in session.get_update_states()
    ]
    return SessionData(
        json.dumps(
            {
                "version": 1,
                "dc": session.dc_id,
                "server": session.server_address,
                "port": session.port,
                "key": base64.b64encode(key).decode() if key else None,
                "states": [] if clear_authorization else states,
                "peers": [] if clear_authorization else peers or [],
                "native_salt": getattr(session, "salt", 0),
                "native_time_offset": float(getattr(session, "time_offset", 0)),
            },
            separators=(",", ":"),
        ).encode()
    )


def restore(session: Any, data: SessionData) -> None:
    """Validate the entire snapshot before committing any runtime state."""
    try:
        obj = json.loads(data.payload)
        if isinstance(obj["version"], bool) or obj["version"] != 1:
            raise ValueError("version")
        key = base64.b64decode(obj["key"], validate=True) if obj["key"] else None
        if key is not None and len(key) != 256:
            raise ValueError("key length")
        dc, port, server = obj["dc"], obj["port"], obj["server"]
        if (
            isinstance(dc, bool)
            or not isinstance(dc, int)
            or not 1 <= dc <= 100
            or isinstance(port, bool)
            or not isinstance(port, int)
            or not 1 <= port <= 65535
            or not isinstance(server, str)
            or not server
            or len(server) > 255
        ):
            raise ValueError("data center")
        salt, offset = obj.get("native_salt", 0), obj.get("native_time_offset", 0)
        if (
            isinstance(salt, bool)
            or not isinstance(salt, int)
            or not -(2**63) <= salt < 2**63
            or isinstance(offset, bool)
            or not isinstance(offset, (int, float))
            or not math.isfinite(offset)
            or not -(2**40) <= offset <= 2**40
        ):
            raise ValueError("native metadata")
        if not isinstance(obj["states"], list) or len(obj["states"]) > 4096:
            raise ValueError("update-state count")
        states = []
        for row in obj["states"]:
            ident = row["id"]
            if isinstance(ident, bool) or not isinstance(ident, int) or not 0 <= ident < 2**63:
                raise ValueError("update-state identity")
            for name in ("pts", "qts", "seq", "date", "unread_count"):
                value = row[name]
                if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**31:
                    raise ValueError("update counter")
            states.append(
                (
                    ident,
                    types.updates.State(
                        pts=row["pts"],
                        qts=row["qts"],
                        seq=row["seq"],
                        date=row["date"],
                        unread_count=row["unread_count"],
                    ),
                )
            )
        if len({ident for ident, _ in states}) != len(states):
            raise ValueError("duplicate update-state identity")
        session.set_dc(dc, server, port)
        session.auth_key = Key(key) if key is not None else None
        session.states.clear()
        for ident, state in states:
            session.set_update_state(ident, state)
        if isinstance(session, NativeSession):
            session.salt, session.time_offset = salt, float(offset)
    except (ValueError, TypeError, KeyError, OverflowError, OSError, AttributeError) as error:
        raise SessionError("invalid GramFlux session snapshot") from error
