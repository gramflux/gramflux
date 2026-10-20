"""Explicit Telethon adapter. No third-party protocol source is copied.

The backend owns DH/RSA/SRP, MTProto 2.0 AES-IGE, salts, correlation,
acknowledgments, service messages, migrations, reconnect and update gaps.
Its exact release is pinned; independent schema output is NOT its runtime schema.
"""

import base64
import copy
import json
import logging
from datetime import UTC, datetime
from typing import Any

from telethon import TelegramClient, errors, events
from telethon.crypto import AuthKey
from telethon.network.connection import (
    ConnectionTcpAbridged,
    ConnectionTcpFull,
    ConnectionTcpIntermediate,
)
from telethon.sessions import MemorySession
from telethon.tl.types import updates

from .config import Config
from .errors import (
    AuthenticationError,
    FloodWait,
    MigrationRequired,
    PasswordRequired,
    RPCError,
    SessionError,
)
from .storage import SessionData


class RedactedLogger(logging.Logger):
    """Defense against backend error paths that include request reprs."""

    def getChild(self, suffix: str) -> "RedactedLogger":
        return self

    def handle(self, record: logging.LogRecord) -> None:
        safe = copy.copy(record)
        safe.msg = "MTProto backend diagnostic (payload and exception details suppressed)"
        safe.args = ()
        safe.exc_info = None
        safe.exc_text = None
        safe.stack_info = None
        super().handle(safe)


def backend_logger() -> logging.Logger:
    logger = RedactedLogger("gramflux.backend", logging.WARNING)
    logger.parent = logging.getLogger("gramflux")
    return logger


RPC_NAMES = {cls: name for name, cls in errors.rpc_errors_dict.items()}


def map_rpc(exc: Any) -> RPCError:
    code = int(getattr(exc, "code", 400))
    if isinstance(exc, errors.SessionPasswordNeededError):
        return PasswordRequired(code, "SESSION_PASSWORD_NEEDED")
    if hasattr(exc, "seconds"):
        return FloodWait(code, int(exc.seconds))
    if hasattr(exc, "new_dc"):
        return MigrationRequired(code, int(exc.new_dc))
    name = RPC_NAMES.get(type(exc), str(getattr(exc, "message", "RPC_ERROR")))
    if code == 401 or name.startswith(("PHONE_", "PASSWORD_", "SESSION_", "API_ID_", "AUTH_")):
        return AuthenticationError(code, name)
    return RPCError(code, name)


def create_backend(api_id: int, api_hash: str, config: Config) -> Any:
    connections = {
        "full": ConnectionTcpFull,
        "intermediate": ConnectionTcpIntermediate,
        "abridged": ConnectionTcpAbridged,
    }
    return TelegramClient(
        MemorySession(),
        api_id,
        api_hash,
        connection=connections[config.transport],
        timeout=config.request_timeout,
        request_retries=0,
        connection_retries=config.reconnect_attempts,
        retry_delay=1,
        auto_reconnect=True,
        sequential_updates=True,
        flood_sleep_threshold=0,
        raise_last_call_error=True,
        base_logger=backend_logger(),
        catch_up=True,
    )


def bind_updates(backend: Any, callback: Any) -> None:
    backend.add_event_handler(callback, events.NewMessage())
    backend.add_event_handler(callback, events.MessageEdited())


def snapshot(session: Any) -> SessionData:
    key = session.auth_key.key if session.auth_key else None
    states = [
        {
            "id": entity,
            "pts": s.pts,
            "qts": s.qts,
            "seq": s.seq,
            "date": int(s.date.timestamp()),
            "unread_count": s.unread_count,
        }
        for entity, s in session.get_update_states()
    ]
    return SessionData(
        json.dumps(
            {
                "version": 1,
                "dc": session.dc_id,
                "server": session.server_address,
                "port": session.port,
                "key": base64.b64encode(key).decode() if key else None,
                "states": states,
            },
            separators=(",", ":"),
        ).encode()
    )


def restore(session: Any, data: SessionData) -> None:
    try:
        obj = json.loads(data.payload)
        if obj["version"] != 1:
            raise ValueError("version")
        key = base64.b64decode(obj["key"], validate=True) if obj["key"] else None
        if key is not None and len(key) != 256:
            raise ValueError("key length")
        dc, port, server = obj["dc"], obj["port"], obj["server"]
        if (
            not isinstance(dc, int)
            or not 1 <= dc <= 100
            or not isinstance(port, int)
            or not 1 <= port <= 65535
            or not isinstance(server, str)
            or len(server) > 255
        ):
            raise ValueError("data center")
        # Validate everything before mutating the session.
        states = [
            (
                s["id"],
                updates.State(
                    pts=s["pts"],
                    qts=s["qts"],
                    seq=s["seq"],
                    date=datetime.fromtimestamp(s["date"], UTC),
                    unread_count=s["unread_count"],
                ),
            )
            for s in obj["states"]
        ]
        session.set_dc(dc, server, port)
        if key is not None:
            session.auth_key = AuthKey(key)
        for entity, state in states:
            session.set_update_state(entity, state)
    except (ValueError, TypeError, KeyError, OverflowError, OSError) as exc:
        raise SessionError("invalid GramFlux session snapshot") from exc
