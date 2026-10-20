"""Pinned-first lazy dialogs, with a complete date/ID/peer pagination cursor."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from .errors import ConfigurationError, PaginationError, PeerNotFound
from .messages import API, Message
from .pagination import RecentIDs, count, page_size
from .peers import Entity, marked_id
from .raw import functions, types


@dataclass(frozen=True, slots=True)
class Dialog:
    id: int
    name: str = field(repr=False)
    entity: Entity = field(repr=False)
    message: Message | None = field(repr=False)
    unread_count: int
    pinned: bool
    folder_id: int | None
    raw: types.Dialog = field(repr=False)


def unpack(result: Any) -> tuple[dict[int, Entity], dict[tuple[int, int], Message]]:
    entities = {marked_id(e): e for e in [*result.users, *result.chats]}
    messages = {
        (marked_id(m.peer_id), m.id): m
        for m in result.messages
        if isinstance(m, (types.Message, types.MessageService))
    }
    return entities, messages


def dialog(
    raw: types.Dialog, entities: dict[int, Entity], messages: dict[tuple[int, int], Message]
) -> Dialog:
    ident = marked_id(raw.peer)
    entity = entities.get(ident)
    if entity is None:
        raise PeerNotFound("dialog response omitted its peer entity")
    name = getattr(entity, "title", None) or " ".join(
        filter(None, (getattr(entity, "first_name", None), getattr(entity, "last_name", None)))
    )
    return Dialog(
        ident,
        name,
        entity,
        messages.get((ident, raw.top_message)),
        raw.unread_count,
        bool(raw.pinned),
        raw.folder_id,
        raw,
    )


async def dialogs(
    api: API,
    *,
    limit: int | None,
    folder_id: int,
    batch_size: int,
) -> AsyncIterator[Dialog]:
    count(limit)
    count(folder_id, name="folder_id", allow_none=False)
    if folder_id >= 2**31:
        raise ConfigurationError("folder_id must fit a signed 32-bit integer")
    page_size(batch_size)
    if limit == 0:
        return
    # Fetch all pinned dialogs explicitly. Mixing pinned rows into the first
    # ordinary page loses pins when page_size is smaller than the pinned count.
    pinned = await api.invoke(functions.messages.GetPinnedDialogsRequest(folder_id=folder_id))
    entities, message_map = unpack(pinned)
    pinned_ids: set[int] = set()
    remaining = limit
    for raw in pinned.dialogs:
        if not isinstance(raw, types.Dialog):
            continue
        ident = marked_id(raw.peer)
        if ident in pinned_ids:
            continue
        pinned_ids.add(ident)
        yield dialog(raw, entities, message_map)
        if remaining is not None:
            remaining -= 1
            if remaining == 0:
                return
    offset_date = 0
    offset_id = 0
    offset_peer: Any = types.InputPeerEmpty()
    previous_cursor: tuple[int, int, int] | None = None
    seen = RecentIDs(batch_size * 2)
    while remaining is None or remaining > 0:
        size = batch_size if remaining is None else min(batch_size, remaining)
        result = await api.invoke(
            functions.messages.GetDialogsRequest(
                offset_date=offset_date,
                offset_id=offset_id,
                offset_peer=offset_peer,
                limit=size,
                hash=0,
                exclude_pinned=True,
                folder_id=folder_id,
            )
        )
        if isinstance(result, types.messages.DialogsNotModified):
            raise PaginationError("unexpected not-modified dialog response to hash=0")
        if not result.dialogs:
            return
        entities, message_map = unpack(result)
        last: types.Dialog | None = None
        new_rows = 0
        for raw in result.dialogs:
            if not isinstance(raw, types.Dialog):
                continue  # DialogFolder is a summary, not a peer dialog.
            ident = marked_id(raw.peer)
            last = raw
            if ident in pinned_ids or not seen.add(ident):
                continue
            new_rows += 1
            yield dialog(raw, entities, message_map)
            if remaining is not None:
                remaining -= 1
                if remaining == 0:
                    return
        if isinstance(result, types.messages.Dialogs):
            return
        if last is None or new_rows == 0:
            raise PaginationError("dialog page made no progress")
        ident = marked_id(last.peer)
        top = message_map.get((ident, last.top_message))
        if top is None or top.date is None:
            raise PaginationError("dialog cursor top message/date is missing")
        offset_date, offset_id = top.date, last.top_message
        offset_peer = await api.resolve_peer(last.peer)
        cursor = (
            ident,
            offset_id,
            int(offset_date.timestamp()) if hasattr(offset_date, "timestamp") else int(offset_date),
        )
        if cursor == previous_cursor:
            raise PaginationError("dialog cursor did not advance")
        previous_cursor = cursor
