"""Independent pts/seq gap detection and bounded difference recovery.

Callbacks feed the bounded dispatcher. Persistence is a clean-shutdown snapshot,
not a transactional event journal. Unknown channel gaps fail explicitly.
"""

from dataclasses import dataclass, field
from typing import Any

from gramflux.errors import SerializationError, TransportError, UnsupportedFeature
from gramflux.peer_utils import get_peer_id, ingest_entities
from gramflux.raw import functions, types


@dataclass(slots=True)
class NativeEvent:
    message: Any = field(repr=False)
    edited: bool = False
    _entities: dict[int, Any] = field(default_factory=dict, repr=False)
    is_private: bool = False
    is_group: bool = False
    is_channel: bool = False


class UpdateEngine:
    def __init__(self, backend: Any) -> None:
        self.backend = backend
        self.states = backend.session.states
        self.entities: dict[int, Any] = getattr(backend, "entities", {})
        self.recovering = False

    def ingest(self, value: Any) -> None:
        ingest_entities(self.entities, value)
        # Preserve every full entity from a batch once, rather than copying and
        # re-ingesting the entire native cache for each message in that batch.
        peer_cache = getattr(self.backend, "peer_cache", None)
        if peer_cache is not None:
            peer_cache.ingest(value)

    async def emit(self, message: Any, edited: bool = False) -> None:
        if isinstance(message, types.MessageEmpty):
            return
        peer = message.peer_id
        private = isinstance(peer, types.PeerUser)
        entity = self.entities.get(get_peer_id(peer))
        group = isinstance(peer, types.PeerChat) or bool(getattr(entity, "megagroup", False))
        relevant = {get_peer_id(peer)}
        sender = getattr(message, "from_id", None)
        if sender is not None:
            relevant.add(get_peer_id(sender))
        bot = getattr(message, "via_bot_id", None)
        if bot is not None:
            relevant.add(bot)
        forwarded = getattr(message, "fwd_from", None)
        if forwarded is not None:
            for field_name in ("from_id", "saved_from_peer", "saved_from_id"):
                origin = getattr(forwarded, field_name, None)
                if origin is not None:
                    relevant.add(get_peer_id(origin))
        event = NativeEvent(
            message,
            edited,
            {ident: self.entities[ident] for ident in relevant if ident in self.entities},
            private,
            group,
            isinstance(peer, types.PeerChannel),
        )
        for callback in self.backend._handlers:
            await callback(event)

    async def recover(self) -> None:
        if self.recovering:
            raise TransportError("recursive update difference gap")
        state = self.states.get(0)
        if state is None:
            raise TransportError("update state is missing; initialize authorized state first")
        self.recovering = True
        try:
            for _ in range(100):
                result = await self.backend(
                    functions.updates.GetDifferenceRequest(
                        pts=state.pts, date=state.date, qts=state.qts
                    )
                )
                self.ingest(result)
                if isinstance(result, types.updates.DifferenceTooLong):
                    raise UnsupportedFeature(
                        "difference too long requires explicit history resynchronization"
                    )
                if isinstance(result, types.updates.DifferenceEmpty):
                    state.date, state.seq = result.date, result.seq
                    return
                if not isinstance(
                    result, (types.updates.Difference, types.updates.DifferenceSlice)
                ):
                    raise SerializationError("unexpected updates.getDifference response")
                if result.new_encrypted_messages:
                    raise UnsupportedFeature("secret-chat updates are unsupported")
                for message in result.new_messages:
                    await self.emit(message)
                for update in result.other_updates:
                    await self.apply(update, authoritative=True)
                state = (
                    result.intermediate_state
                    if isinstance(result, types.updates.DifferenceSlice)
                    else result.state
                )
                self.states[0] = state
                if isinstance(result, types.updates.Difference):
                    return
            raise TransportError("difference recovery page budget exhausted")
        finally:
            self.recovering = False

    async def channel(self, ident: int) -> None:
        entity = self.entities.get(-1000000000000 - ident)
        if entity is None:
            peers = getattr(self.backend, "peer_cache", None)
            entity = peers.get(-1000000000000 - ident) if peers is not None else None
        if entity is None or getattr(entity, "access_hash", None) is None:
            raise TransportError("channel difference requires a known access hash")
        state = self.states.get(ident)
        pts = state.pts if state else 1
        for _ in range(100):
            result = await self.backend(
                functions.updates.GetChannelDifferenceRequest(
                    channel=types.InputChannel(channel_id=ident, access_hash=entity.access_hash),
                    filter=types.ChannelMessagesFilterEmpty(),
                    pts=pts,
                    limit=100,
                    force=True,
                )
            )
            self.ingest(result)
            if isinstance(result, types.updates.ChannelDifferenceTooLong):
                raise UnsupportedFeature(
                    "channel difference too long requires explicit history resynchronization"
                )
            if isinstance(result, types.updates.ChannelDifference):
                for message in result.new_messages:
                    await self.emit(message)
                for update in result.other_updates:
                    await self.apply(update, authoritative=True)
            elif not isinstance(result, types.updates.ChannelDifferenceEmpty):
                raise SerializationError("unexpected channel difference response")
            pts = result.pts
            self.states[ident] = types.updates.State(pts=pts, qts=0, date=0, seq=0, unread_count=0)
            if result.final:
                return
        raise TransportError("channel difference page budget exhausted")

    async def apply(self, update: Any, *, authoritative: bool = False) -> None:
        kind = update.definition.name
        if kind == "updateChannelTooLong":
            await self.channel(update.channel_id)
            return
        pts = getattr(update, "pts", None)
        count = getattr(update, "pts_count", 0)
        if pts is not None and (pts < 0 or count < 0 or count > pts):
            raise SerializationError("invalid update counter")
        message = getattr(update, "message", None)
        channel_id = getattr(update, "channel_id", None)
        if message is not None and isinstance(getattr(message, "peer_id", None), types.PeerChannel):
            channel_id = message.peer_id.channel_id
        state_id = channel_id or 0
        state = self.states.get(state_id)
        if pts is not None and not authoritative:
            if state is None:
                if channel_id:
                    await self.channel(channel_id)
                else:
                    raise TransportError("global update baseline is missing")
                state = self.states.get(state_id)
            if state is None:
                raise TransportError("update recovery did not establish a baseline")
            if pts < state.pts or count and pts == state.pts:
                return
            if state.pts + count < pts:
                if channel_id:
                    await self.channel(channel_id)
                else:
                    await self.recover()
                state = self.states[state_id]
                if pts <= state.pts:
                    return
                if state.pts + count != pts:
                    raise TransportError("update gap remains after difference")
        if kind in (
            "updateNewMessage",
            "updateNewChannelMessage",
            "updateEditMessage",
            "updateEditChannelMessage",
        ):
            await self.emit(update.message, kind.startswith("updateEdit"))
        if pts is not None and not authoritative and state is not None:
            state.pts = pts
        if getattr(update, "qts", None) is not None:
            raise UnsupportedFeature("encrypted update synchronization is unsupported")

    async def process(self, value: Any) -> None:
        self.ingest(value)
        kind = value.definition.name
        if kind == "updatesTooLong":
            await self.recover()
            return
        state = self.states.get(0)
        if state is None:
            raise TransportError("authorized update baseline has not been initialized")
        if kind in ("updates", "updatesCombined"):
            seq_start = getattr(value, "seq_start", value.seq)
            if value.seq and value.seq <= state.seq:
                return
            if seq_start > state.seq + 1:
                await self.recover()
                state = self.states[0]
                if value.seq <= state.seq:
                    return
                if seq_start > state.seq + 1:
                    raise TransportError("sequence gap remains after recovery")
            for update in value.updates:
                await self.apply(update)
            state = self.states[0]
            if value.seq:
                state.seq = max(state.seq, value.seq)
            state.date = max(state.date, value.date)
        elif kind == "updateShort":
            await self.apply(value.update)
            self.states[0].date = max(self.states[0].date, value.date)
        elif kind in ("updateShortMessage", "updateShortChatMessage"):
            private = kind == "updateShortMessage"
            peer = (
                types.PeerUser(user_id=value.user_id)
                if private
                else types.PeerChat(chat_id=value.chat_id)
            )
            sender = value.user_id if private and not value.out else getattr(value, "from_id", None)
            if sender is None and self.backend._user is not None:
                sender = self.backend._user.id
            message = types.Message(
                id=value.id,
                peer_id=peer,
                message=value.message,
                date=value.date,
                out=value.out,
                from_id=types.PeerUser(user_id=sender) if sender else None,
                entities=value.entities,
                reply_to=value.reply_to,
            )
            update = types.UpdateNewMessage(
                message=message, pts=value.pts, pts_count=value.pts_count
            )
            await self.apply(update)
            self.states[0].date = max(self.states[0].date, value.date)
        elif value.definition.result == "Update":
            await self.apply(value)
        else:
            raise UnsupportedFeature("unsupported native update envelope")
