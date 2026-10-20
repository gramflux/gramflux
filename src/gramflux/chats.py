"""Channel/basic-group membership with explicit pagination and permission failures."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from .errors import ConfigurationError, PaginationError, UnsupportedFeature
from .messages import API, is_channel
from .pagination import RecentIDs, count, page_size
from .peers import PeerLike, as_channel, marked_id
from .raw import functions, types


@dataclass(frozen=True, slots=True)
class ChatMember:
    id: int
    user: types.User | None = field(repr=False)
    role: str
    raw: Any = field(repr=False)


def member(participant: Any, users: dict[int, types.User]) -> ChatMember:
    ident = participant.user_id if hasattr(participant, "user_id") else marked_id(participant.peer)
    name = type(participant).__name__
    role = (
        "owner"
        if name.endswith("Creator")
        else "administrator"
        if name.endswith("Admin")
        else ("banned" if name.endswith("Banned") else "member")
    )
    return ChatMember(ident, users.get(ident), role, participant)


async def members(
    api: API,
    peer: PeerLike,
    *,
    limit: int | None,
    query: str,
    batch_size: int,
) -> AsyncIterator[ChatMember]:
    count(limit)
    page_size(batch_size, 200)
    if not isinstance(query, str):
        raise ConfigurationError("member query must be a string")
    if limit == 0:
        return
    target = await api.resolve_peer(peer)
    if isinstance(target, types.InputPeerChat):
        result = await api.invoke(functions.messages.GetFullChatRequest(chat_id=target.chat_id))
        participants = result.full_chat.participants
        if not isinstance(participants, types.ChatParticipants):
            raise UnsupportedFeature("Telegram did not expose this basic group member list")
        users = {user.id: user for user in result.users if isinstance(user, types.User)}
        emitted = 0
        for row in participants.participants:
            value = member(row, users)
            if query:
                user = value.user
                name = " ".join(
                    filter(
                        None,
                        (
                            getattr(user, "first_name", None),
                            getattr(user, "last_name", None),
                            getattr(user, "username", None),
                        ),
                    )
                )
                if query.casefold() not in name.casefold():
                    continue
            yield value
            emitted += 1
            if limit is not None and emitted >= limit:
                return
        return
    if not is_channel(target):
        raise ConfigurationError("members require a group, supergroup or channel")
    offset = 0
    remaining = limit
    recent = RecentIDs(batch_size * 2)
    while remaining is None or remaining > 0:
        size = batch_size if remaining is None else min(batch_size, remaining)
        participant_filter = (
            types.ChannelParticipantsSearch(q=query) if query else types.ChannelParticipantsRecent()
        )
        result = await api.invoke(
            functions.channels.GetParticipantsRequest(
                channel=as_channel(target),
                filter=participant_filter,
                offset=offset,
                limit=size,
                hash=0,
            )
        )
        if isinstance(result, types.channels.ChannelParticipantsNotModified):
            raise PaginationError("unexpected not-modified members response to hash=0")
        if not result.participants:
            return
        users = {user.id: user for user in result.users if isinstance(user, types.User)}
        for row in result.participants:
            value = member(row, users)
            if not recent.add(value.id):
                continue
            yield value
            if remaining is not None:
                remaining -= 1
                if remaining == 0:
                    return
        offset += len(result.participants)
        if offset >= result.count:
            return


async def join(api: API, peer: PeerLike) -> Any:
    return await api.invoke(
        functions.channels.JoinChannelRequest(channel=as_channel(await api.resolve_peer(peer)))
    )


async def leave(api: API, peer: PeerLike) -> Any:
    target = await api.resolve_peer(peer)
    if is_channel(target):
        return await api.invoke(functions.channels.LeaveChannelRequest(channel=as_channel(target)))
    if isinstance(target, types.InputPeerChat):
        return await api.invoke(
            functions.messages.DeleteChatUserRequest(
                chat_id=target.chat_id, user_id=types.InputUserSelf()
            )
        )
    raise ConfigurationError("leave_chat requires a group or channel")
