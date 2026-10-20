"""Raw API message retrieval and mutations with explicit pagination and routing."""

import secrets
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Protocol, TypeAlias

from .errors import ConfigurationError, PaginationError, PeerNotFound
from .pagination import MessageIDs, RecentIDs, count, message_ids, page_size
from .peers import InputPeer, PeerLike, as_channel, marked_id
from .raw import functions, types
from .tl.model import TLObject

Message: TypeAlias = types.Message | types.MessageService


class API(Protocol):
    async def invoke(self, request: Any) -> Any: ...
    async def get_me(self) -> types.User: ...
    async def resolve_peer(self, peer: PeerLike, *, refresh: bool = False) -> InputPeer: ...


def is_channel(peer: InputPeer) -> bool:
    return isinstance(peer, (types.InputPeerChannel, types.InputPeerChannelFromMessage))


async def history(
    api: API,
    peer: PeerLike,
    *,
    limit: int | None,
    offset_id: int = 0,
    offset_date: datetime | None = None,
    batch_size: int = 100,
    query: str | None = None,
    sender: PeerLike | None = None,
) -> AsyncIterator[Message]:
    count(limit)
    count(offset_id, name="offset_id", allow_none=False)
    if offset_id >= 2**31:
        raise ConfigurationError("offset_id must fit a signed 32-bit integer")
    page_size(batch_size)
    if query is not None and not isinstance(query, str):
        raise ConfigurationError("query must be a string")
    if limit == 0:
        return
    target = await api.resolve_peer(peer)
    from_peer = await api.resolve_peer(sender) if sender is not None else None
    seen = RecentIDs(batch_size * 2)
    remaining = limit
    cursor = offset_id
    while remaining is None or remaining > 0:
        request_size = batch_size if remaining is None else min(batch_size, remaining)
        if query is None:
            request: Any = functions.messages.GetHistoryRequest(
                peer=target,
                offset_id=cursor,
                offset_date=int(offset_date.timestamp()) if offset_date is not None else 0,
                add_offset=0,
                limit=request_size,
                max_id=0,
                min_id=0,
                hash=0,
            )
        else:
            request = functions.messages.SearchRequest(
                peer=target,
                q=query,
                filter=types.InputMessagesFilterEmpty(),
                min_date=0,
                max_date=int(offset_date.timestamp()) if offset_date is not None else 0,
                offset_id=cursor,
                add_offset=0,
                limit=request_size,
                max_id=0,
                min_id=0,
                hash=0,
                from_id=from_peer,
            )
        response = await api.invoke(request)
        raw = getattr(response, "messages", None)
        if raw is None:
            raise PaginationError("history returned no message collection")
        if not raw:
            return
        ids = [m.id for m in raw if isinstance(getattr(m, "id", None), int) and m.id > 0]
        if not ids:
            raise PaginationError("history page has no valid cursor")
        next_cursor = min(ids)
        if cursor and next_cursor >= cursor:
            raise PaginationError("history cursor did not move backwards")
        for message in raw:
            if not isinstance(message, (types.Message, types.MessageService)):
                continue
            if cursor and message.id >= cursor:
                continue
            if not seen.add(message.id):
                continue
            yield message
            if remaining is not None:
                remaining -= 1
                if remaining == 0:
                    return
        cursor = next_cursor
        # Empty pages, not short pages, terminate sliced histories. A server can
        # return fewer results than requested while more history remains.
        if isinstance(response, types.messages.Messages):
            return


async def get_messages(api: API, peer: PeerLike, ids: MessageIDs) -> list[Message | None]:
    wanted = message_ids(ids)
    target = await api.resolve_peer(peer)
    expected = (
        (await api.get_me()).id if isinstance(target, types.InputPeerSelf) else marked_id(target)
    )
    found: dict[int, Message] = {}
    for start in range(0, len(wanted), 100):
        batch: list[TLObject] = [types.InputMessageID(id=i) for i in wanted[start : start + 100]]
        request = (
            functions.channels.GetMessagesRequest(channel=as_channel(target), id=batch)
            if is_channel(target)
            else functions.messages.GetMessagesRequest(id=batch)
        )
        response = await api.invoke(request)
        for message in response.messages:
            if (
                isinstance(message, (types.Message, types.MessageService))
                and marked_id(message.peer_id) == expected
            ):
                found[message.id] = message
    return [found.get(ident) for ident in wanted]


async def delete(
    api: API, peer: PeerLike, ids: MessageIDs, *, revoke: bool
) -> list[types.messages.AffectedMessages]:
    if not isinstance(revoke, bool):
        raise ConfigurationError("revoke must be bool")
    wanted = list(dict.fromkeys(message_ids(ids)))
    target = await api.resolve_peer(peer)
    if is_channel(target) and not revoke:
        raise ConfigurationError("channel deletion affects everyone; pass revoke=True explicitly")
    if not is_channel(target):
        verified = await get_messages(api, target, wanted)
        if any(message is None for message in verified):
            raise PeerNotFound(
                "cannot delete missing or other-chat message IDs; no deletion was sent"
            )
    results = []
    for start in range(0, len(wanted), 100):
        batch = wanted[start : start + 100]
        request = (
            functions.channels.DeleteMessagesRequest(channel=as_channel(target), id=batch)
            if is_channel(target)
            else functions.messages.DeleteMessagesRequest(id=batch, revoke=revoke)
        )
        results.append(await api.invoke(request))
    return results


async def forward(
    api: API,
    destination: PeerLike,
    source: PeerLike,
    ids: MessageIDs,
    *,
    silent: bool,
    drop_author: bool,
) -> list[Any]:
    wanted = message_ids(ids)
    target, origin = await api.resolve_peer(destination), await api.resolve_peer(source)
    updates = []
    for start in range(0, len(wanted), 100):
        batch = wanted[start : start + 100]
        random_ids = [secrets.randbits(63) for _ in batch]
        updates.append(
            await api.invoke(
                functions.messages.ForwardMessagesRequest(
                    from_peer=origin,
                    id=batch,
                    to_peer=target,
                    silent=silent,
                    drop_author=drop_author,
                    random_id=random_ids,
                )
            )
        )
    return updates


async def read(api: API, peer: PeerLike, *, max_id: int) -> Any:
    count(max_id, name="max_id", allow_none=False)
    if max_id >= 2**31:
        raise ConfigurationError("max_id must fit a signed 32-bit integer")
    target = await api.resolve_peer(peer)
    request = (
        functions.channels.ReadHistoryRequest(channel=as_channel(target), max_id=max_id)
        if is_channel(target)
        else functions.messages.ReadHistoryRequest(peer=target, max_id=max_id)
    )
    return await api.invoke(request)
