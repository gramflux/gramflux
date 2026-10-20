"""Native marked IDs and conversion of official peer constructors."""

from typing import Any

from .raw import types


def resolve_id(value: int) -> tuple[int, Any]:
    if value >= 0:
        return value, types.PeerUser
    if value <= -1000000000000:
        return -value - 1000000000000, types.PeerChannel
    return -value, types.PeerChat


def get_peer_id(peer: Any) -> int:
    if isinstance(peer, int) and not isinstance(peer, bool):
        return peer
    kind = peer.definition.name if hasattr(peer, "definition") else ""
    if hasattr(peer, "definition") and "channel_id" in {p.name for p in peer.definition.params}:
        return int(-1000000000000 - peer.channel_id)
    if kind in ("channel", "channelForbidden"):
        return int(-1000000000000 - peer.id)
    if kind in ("chat", "chatForbidden", "chatEmpty"):
        return int(-peer.id)
    if hasattr(peer, "chat_id"):
        return int(-peer.chat_id)
    if hasattr(peer, "user_id"):
        return int(peer.user_id)
    if kind in ("user", "userEmpty"):
        return int(peer.id)
    raise TypeError("peer has no stable numeric identity")


def get_input_peer(peer: Any) -> Any:
    if not hasattr(peer, "definition"):
        raise TypeError("expected a native peer")
    if peer.definition.result == "InputPeer":
        return peer
    kind = peer.definition.name
    if kind == "inputUserSelf" or kind == "user" and peer.is_self:
        return types.InputPeerSelf()
    if kind in ("chat", "chatForbidden", "chatEmpty"):
        return types.InputPeerChat(chat_id=peer.id)
    if kind in ("peerChat",):
        return types.InputPeerChat(chat_id=peer.chat_id)
    if getattr(peer, "min", False):
        raise TypeError("minimal peers need contextual access hashes")
    if kind in ("user", "inputUser") and peer.access_hash is not None:
        return types.InputPeerUser(
            user_id=peer.id if kind == "user" else peer.user_id, access_hash=peer.access_hash
        )
    if kind in ("channel", "channelForbidden", "inputChannel") and peer.access_hash is not None:
        return types.InputPeerChannel(
            channel_id=peer.id if kind != "inputChannel" else peer.channel_id,
            access_hash=peer.access_hash,
        )
    raise TypeError("full peer/access hash is required")


def get_input_user(peer: Any) -> Any:
    if isinstance(peer, types.InputPeerSelf):
        return types.InputUserSelf()
    if isinstance(peer, types.InputPeerUser):
        return types.InputUser(user_id=peer.user_id, access_hash=peer.access_hash)
    if isinstance(peer, types.InputPeerUserFromMessage):
        return types.InputUserFromMessage(peer=peer.peer, msg_id=peer.msg_id, user_id=peer.user_id)
    raise TypeError("user peer required")


def get_input_channel(peer: Any) -> Any:
    if isinstance(peer, types.InputPeerChannel):
        return types.InputChannel(channel_id=peer.channel_id, access_hash=peer.access_hash)
    if isinstance(peer, types.InputPeerChannelFromMessage):
        return types.InputChannelFromMessage(
            peer=peer.peer, msg_id=peer.msg_id, channel_id=peer.channel_id
        )
    raise TypeError("channel peer required")


def ingest_entities(cache: dict[int, Any], value: Any) -> None:
    if isinstance(value, (list, tuple)):
        values = value
    else:
        values = [*getattr(value, "users", []), *getattr(value, "chats", [])]
        if isinstance(
            value,
            (types.User, types.Chat, types.Channel, types.ChatForbidden, types.ChannelForbidden),
        ):
            values.append(value)
    for entity in values:
        if not isinstance(
            entity,
            (types.User, types.Chat, types.Channel, types.ChatForbidden, types.ChannelForbidden),
        ) or getattr(entity, "min", False):
            continue
        cache[get_peer_id(entity)] = entity
        while len(cache) > 4096:
            cache.pop(next(iter(cache)))
