"""Shared outgoing peer and response correlation, independent of the connection."""

from typing import Any, cast

from .errors import SerializationError, UnsupportedFeature
from .raw import types


def output_peer(peer: Any, self_id: int | None = None) -> Any:
    if isinstance(peer, types.InputPeerSelf):
        if self_id is None:
            raise SerializationError("self identity is required for sent-message normalization")
        return types.PeerUser(user_id=self_id)
    if isinstance(peer, (types.InputPeerUser, types.InputPeerUserFromMessage)):
        return types.PeerUser(user_id=peer.user_id)
    if isinstance(peer, types.InputPeerChat):
        return types.PeerChat(chat_id=peer.chat_id)
    if isinstance(peer, (types.InputPeerChannel, types.InputPeerChannelFromMessage)):
        return types.PeerChannel(channel_id=peer.channel_id)
    raise UnsupportedFeature("unsupported sent-message target")


def sent_message(result: Any, target: Any, text: str, random_id: int) -> types.Message:
    from .peer_utils import get_peer_id

    if isinstance(result, types.UpdateShortSentMessage):
        return types.Message(
            id=result.id,
            peer_id=target,
            date=result.date,
            message=text,
            out=bool(result.out),
            media=result.media,
            entities=result.entities,
            ttl_period=result.ttl_period,
        )
    updates = (
        [result.update] if isinstance(result, types.UpdateShort) else getattr(result, "updates", [])
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
        return cast(types.Message, matches[0])
    raise SerializationError(
        "send response cannot be correlated uniquely; remote write may have completed"
    )
