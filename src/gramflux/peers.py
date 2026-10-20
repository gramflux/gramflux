"""Bounded account-local peer cache and explicit access-hash resolution."""

import json
import re
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from . import peer_utils as utils
from .errors import ConfigurationError, PeerNotFound, SessionError
from .raw import functions, types
from .storage import SessionData

PeerLike: TypeAlias = (
    str | int | types.TypeInputPeer | types.TypePeer | types.TypeUser | types.TypeChat
)
Entity: TypeAlias = (
    types.User | types.Chat | types.Channel | types.ChatForbidden | types.ChannelForbidden
)
InputPeer: TypeAlias = types.TypeInputPeer
Kind: TypeAlias = Literal["user", "group", "channel"]
Invoke: TypeAlias = Callable[[Any], Awaitable[Any]]


def marked_id(peer: Any) -> int:
    return int(utils.get_peer_id(peer))


def as_channel(peer: InputPeer) -> types.TypeInputChannel:
    try:
        return utils.get_input_channel(peer)
    except TypeError:
        raise ConfigurationError("this operation requires a channel or supergroup") from None


def as_user(peer: InputPeer) -> types.TypeInputUser:
    try:
        return utils.get_input_user(peer)
    except TypeError:
        raise ConfigurationError("this operation requires a user") from None


@dataclass(frozen=True, slots=True)
class PeerRecord:
    id: int
    kind: Kind
    access_hash: int | None = field(default=None, repr=False)
    username: str | None = field(default=None, repr=False)
    is_self: bool = False

    def input_peer(self) -> InputPeer:
        if self.is_self:
            return types.InputPeerSelf()
        raw_id, _ = utils.resolve_id(self.id)
        if self.kind == "group":
            return types.InputPeerChat(chat_id=raw_id)
        if self.access_hash is None:
            raise PeerNotFound("peer access hash is unknown; resolve its username or load dialogs")
        if self.kind == "channel":
            return types.InputPeerChannel(channel_id=raw_id, access_hash=self.access_hash)
        return types.InputPeerUser(user_id=raw_id, access_hash=self.access_hash)


class PeerCache:
    """LRU of IDs/access hashes/primary usernames. Never store message contents.

    Min constructors never replace full access hashes. Username invalidation is
    reactive; use refresh=True to force resolving potentially reassigned names.
    """

    def __init__(
        self, capacity: int = 2048, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or not 1 <= capacity <= 4096:
            raise ConfigurationError("peer cache capacity must be between 1 and 4096")
        self._clock = clock
        self._name_times: dict[str, float] = {}
        self.capacity = capacity
        self._records: OrderedDict[int, PeerRecord] = OrderedDict()
        self._entities: dict[int, Entity] = {}
        self._names: dict[str, int] = {}

    def _put(self, record: PeerRecord, *, fresh: bool = True) -> None:
        old = self._records.pop(record.id, None)
        if old and old.username and self._names.get(old.username.casefold()) == record.id:
            self._names.pop(old.username.casefold(), None)
            self._name_times.pop(old.username.casefold(), None)
        self._records[record.id] = record
        if record.username and fresh:
            self._names[record.username.casefold()] = record.id
            self._name_times[record.username.casefold()] = self._clock()
        while len(self._records) > self.capacity:
            ident, dropped = self._records.popitem(last=False)
            self._entities.pop(ident, None)
            if dropped.username and self._names.get(dropped.username.casefold()) == ident:
                self._names.pop(dropped.username.casefold(), None)
                self._name_times.pop(dropped.username.casefold(), None)

    def get(self, ident: int) -> PeerRecord | None:
        record = self._records.get(ident)
        if record:
            self._records.move_to_end(ident)
        return record

    def by_name(self, name: str) -> PeerRecord | None:
        key = name.casefold()
        ident = self._names.get(key)
        received = self._name_times.get(key)
        if received is None or self._clock() - received >= 60:
            return None
        return self.get(ident) if ident is not None else None

    def invalidate_name(self, name: str) -> None:
        self._names.pop(name.casefold(), None)
        self._name_times.pop(name.casefold(), None)

    def entity(self, ident: int) -> Entity | None:
        return self._entities.get(ident)

    def ingest(self, value: Any) -> None:
        if isinstance(value, (list, tuple)):
            for entity in value:
                self.ingest(entity)
            return
        if isinstance(
            value,
            (types.User, types.Chat, types.ChatForbidden, types.Channel, types.ChannelForbidden),
        ):
            if getattr(value, "min", False):
                return
            ident = marked_id(value)
            kind: Kind = (
                "user"
                if isinstance(value, types.User)
                else (
                    "channel"
                    if isinstance(value, (types.Channel, types.ChannelForbidden))
                    else "group"
                )
            )
            previous = self._records.get(ident)
            access_hash = getattr(value, "access_hash", None)
            if access_hash is None and previous:
                access_hash = previous.access_hash
            username = getattr(value, "username", None)
            is_self = bool(getattr(value, "is_self", False)) or bool(previous and previous.is_self)
            self._put(PeerRecord(ident, kind, access_hash, username, is_self))
            self._entities[ident] = value
            return
        for key in ("users", "chats"):
            collection = getattr(value, key, None)
            if isinstance(collection, (list, tuple)):
                for entity in collection:
                    self.ingest(entity)
        user = getattr(value, "user", None)
        if isinstance(user, types.User):
            self.ingest(user)

    def clear(self) -> None:
        self._records.clear()
        self._entities.clear()
        self._names.clear()
        self._name_times.clear()

    def dump(self) -> list[dict[str, object]]:
        return [
            {
                "id": p.id,
                "kind": p.kind,
                "access_hash": p.access_hash,
                "username": p.username,
                "is_self": p.is_self,
            }
            for p in self._records.values()
        ]

    def restore(self, snapshot: SessionData) -> None:
        try:
            rows = json.loads(snapshot.payload).get("peers", [])
            if not isinstance(rows, list) or len(rows) > 4096:
                raise ValueError("peer cache size")
            validated = []
            for row in rows:
                ident, kind = row["id"], row["kind"]
                access_hash, username = row["access_hash"], row["username"]
                is_self = row.get("is_self", False)
                if not isinstance(is_self, bool) or is_self and kind != "user":
                    raise ValueError("self peer")
                if (
                    isinstance(ident, bool)
                    or not isinstance(ident, int)
                    or not -(2**63) < ident < 2**63
                    or ident == 0
                    or kind not in {"user", "group", "channel"}
                ):
                    raise ValueError("peer identity")
                _, peer_type = utils.resolve_id(ident)
                expected: dict[type[Any], str] = {
                    types.PeerUser: "user",
                    types.PeerChat: "group",
                    types.PeerChannel: "channel",
                }
                if expected.get(peer_type) != kind:
                    raise ValueError("peer kind mismatch")
                if access_hash is not None and (
                    isinstance(access_hash, bool)
                    or not isinstance(access_hash, int)
                    or not -(2**63) <= access_hash < 2**63
                ):
                    raise ValueError("peer hash")
                if username is not None and (
                    not isinstance(username, str)
                    or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", username)
                ):
                    raise ValueError("peer username")
                validated.append(PeerRecord(ident, kind, access_hash, username, is_self))
            if sum(p.is_self for p in validated) > 1:
                raise ValueError("multiple self peers")
            if len({p.id for p in validated}) != len(validated):
                raise ValueError("duplicate peers")
            self._records.clear()
            self._names.clear()
            self._entities.clear()
            self._name_times.clear()
            for record in validated:
                # Names can be reassigned while offline; only numeric IDs/hashes
                # are reused without a new username lookup after restart.
                self._put(record, fresh=False)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise SessionError("invalid saved peer cache") from exc


class PeerResolver:
    def __init__(self, invoke: Invoke, capacity: int = 2048) -> None:
        self.invoke = invoke
        self.cache = PeerCache(capacity)

    async def resolve(self, peer: PeerLike, *, refresh: bool = False) -> InputPeer:
        if isinstance(peer, bool):
            raise ConfigurationError("peer must not be bool")
        if isinstance(peer, str):
            name = peer.strip().removeprefix("@")
            if name.casefold() in {"me", "self"}:
                return types.InputPeerSelf()
            if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", name):
                raise ConfigurationError(
                    "use a username, a marked numeric ID, or an explicit input peer"
                )
            cached = self.cache.by_name(name)
            if (
                cached is not None
                and not refresh
                and (cached.is_self or cached.kind == "group" or cached.access_hash is not None)
            ):
                return cached.input_peer()
            self.cache.invalidate_name(name)
            result = await self.invoke(functions.contacts.ResolveUsernameRequest(username=name))
            self.cache.ingest(result)
            ident = marked_id(result.peer)
            resolved = self.cache.get(ident)
            if resolved is None:
                raise PeerNotFound("resolved peer has no usable full entity")
            return resolved.input_peer()
        if isinstance(peer, int):
            if peer == 0 or not -(2**63) < peer < 2**63:
                raise ConfigurationError("peer ID must be a nonzero signed 64-bit integer")
            cached = self.cache.get(peer)
            if cached is not None:
                return cached.input_peer()
            raw_id, peer_type = utils.resolve_id(peer)
            if peer_type is types.PeerChat:
                return types.InputPeerChat(chat_id=raw_id)
            raise PeerNotFound(
                "unknown peer ID; resolve a username, load dialogs, or supply an input peer"
            )
        try:
            result = utils.get_input_peer(peer)
            self.cache.ingest(peer)
            return result
        except (TypeError, ValueError):
            try:
                return await self.resolve(marked_id(peer))
            except (TypeError, ValueError):
                raise ConfigurationError("unsupported peer value") from None

    async def entity(self, peer: PeerLike) -> Entity:
        resolved = await self.resolve(peer)
        if isinstance(
            resolved, (types.InputPeerSelf, types.InputPeerUser, types.InputPeerUserFromMessage)
        ):
            result = await self.invoke(functions.users.GetUsersRequest(id=[as_user(resolved)]))
            if not result or not isinstance(result[0], types.User):
                raise PeerNotFound("user is unavailable")
            entity: Entity = result[0]
        elif isinstance(resolved, types.InputPeerChat):
            result = await self.invoke(functions.messages.GetChatsRequest(id=[resolved.chat_id]))
            if not result.chats:
                raise PeerNotFound("group is unavailable")
            entity = result.chats[0]
        else:
            result = await self.invoke(
                functions.channels.GetChannelsRequest(id=[as_channel(resolved)])
            )
            if not result.chats:
                raise PeerNotFound("channel is unavailable")
            entity = result.chats[0]
        self.cache.ingest(entity)
        return entity
