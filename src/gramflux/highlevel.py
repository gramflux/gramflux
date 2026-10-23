"""Daily Client operations using existing peer, transfer and native invocation paths."""

from __future__ import annotations

import math
import re
import secrets
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, TypeAlias, cast
from urllib.parse import urlsplit

from .chats import ChatMember
from .errors import ConfigurationError, PeerNotFound, SerializationError, UnsupportedFeature
from .files import CHUNK, Progress
from .messages import Message
from .operations import require_booleans, validate_text
from .pagination import message_ids
from .peer_utils import get_peer_id as marked_peer_id
from .peers import Entity, InputPeer, PeerLike, as_channel, as_user
from .raw import functions, types
from .sending import output_peer, sent_message
from .tl.model import TLObject

if TYPE_CHECKING:
    from .client import Client

Source: TypeAlias = str | Path | BinaryIO | types.InputFile | types.InputFileBig


UpdateResult: TypeAlias = (
    types.Updates
    | types.UpdatesCombined
    | types.UpdateShort
    | types.UpdateShortMessage
    | types.UpdateShortChatMessage
    | types.UpdateShortSentMessage
    | types.UpdatesTooLong
)


async def invoke_updates(owner: object, request: TLObject) -> UpdateResult:
    """Return a validated native update result, preserving server failures and identity."""
    result = await client(owner).invoke(request)
    if not isinstance(
        result,
        (
            types.Updates,
            types.UpdatesCombined,
            types.UpdateShort,
            types.UpdateShortMessage,
            types.UpdateShortChatMessage,
            types.UpdateShortSentMessage,
            types.UpdatesTooLong,
        ),
    ):
        raise SerializationError("operation returned a non-update result")
    return result


def client(value: object) -> Client:
    """Internal mixin contract: Client supplies the documented public operations."""
    return cast("Client", value)


def reference(peer: PeerLike) -> PeerLike:
    if isinstance(peer, str) and peer.startswith(("https://", "http://")):
        url = urlsplit(peer)
        name = url.path.strip("/")
        if (
            url.hostname not in {"t.me", "telegram.me"}
            or url.query
            or url.fragment
            or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", name)
        ):
            raise ConfigurationError("only public Telegram username links are supported")
        return name
    return peer


def cached_media(media: TLObject | None) -> TLObject:
    if isinstance(media, types.Message):
        if media.noforwards:
            raise ConfigurationError("protected content cannot be copied or cached by this helper")
        media = media.photo or media.document
    if isinstance(media, types.Photo):
        return types.InputMediaPhoto(
            id=types.InputPhoto(
                id=media.id, access_hash=media.access_hash, file_reference=media.file_reference
            )
        )
    if isinstance(media, types.Document):
        return types.InputMediaDocument(
            id=types.InputDocument(
                id=media.id, access_hash=media.access_hash, file_reference=media.file_reference
            )
        )
    raise UnsupportedFeature("cached media requires a native photo/document with server metadata")


@dataclass(frozen=True, slots=True)
class AlbumItem:
    """One photo/document album item; captions and entities belong to each item."""

    source: Source
    caption: str = field(default="", repr=False)
    as_document: bool = False
    entities: Sequence[TLObject] | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class Draft:
    """A native draft and its conversation; not a fake Message object."""

    peer: TLObject
    draft: types.DraftMessage = field(repr=False)


class HighLevelMethods:
    """Additive methods; existing Client implementations remain the primary API."""

    @property
    def is_connected(self) -> bool:
        """Same local connection indicator as connected; not authorization."""
        return client(self).connected

    async def is_bot(self) -> bool:
        """Fetch the authorized identity and inspect its server-provided bot flag."""
        return bool((await client(self).get_me()).bot)

    async def get_entity(self, peer: PeerLike) -> Entity:
        """Fetch an accessible full entity; public username links are accepted."""
        return await client(self).get_chat(reference(peer))

    async def get_input_entity(self, peer: PeerLike, *, refresh: bool = False) -> InputPeer:
        """Resolve an input peer without guessing access hashes or joining invites."""
        return await client(self).resolve_peer(reference(peer), refresh=refresh)

    async def get_peer_id(self, peer: PeerLike) -> int:
        """Return a marked identity; knowing an ID does not manufacture access rights."""
        if isinstance(peer, int) and not isinstance(peer, bool):
            if not peer or not -(2**63) < peer < 2**63:
                raise ConfigurationError("peer ID must be nonzero and fit signed 64 bits")
            return peer
        if isinstance(peer, (types.PeerUser, types.PeerChat, types.PeerChannel)):
            return marked_peer_id(peer)
        target = await self.get_input_entity(peer)
        if isinstance(target, types.InputPeerSelf):
            return (await client(self).get_me()).id
        return marked_peer_id(target)

    def iter_messages(
        self, peer: PeerLike, *, limit: int | None = None, offset_id: int = 0, page_size: int = 100
    ) -> AsyncIterator[Message]:
        """Lazy history convenience; explicit searching remains iter_search."""
        return client(self).iter_history(
            peer, limit=limit, offset_id=offset_id, page_size=page_size
        )

    async def get_participants(
        self, peer: PeerLike, *, limit: int = 100, query: str = ""
    ) -> list[ChatMember]:
        """Collect visible members through the existing group/channel service."""
        return await client(self).get_members(peer, limit=limit, query=query)

    async def get_users(self, peers: Sequence[PeerLike]) -> list[types.User | types.UserEmpty]:
        """Resolve users and fetch batches of at most 100; retain native empty-user results."""
        if isinstance(peers, (str, bytes)) or not isinstance(peers, Sequence) or len(peers) > 10000:
            raise ConfigurationError("provide a sequence of at most 10000 user references")
        inputs = [as_user(await self.get_input_entity(peer)) for peer in peers]
        result: list[types.User | types.UserEmpty] = []
        for start in range(0, len(inputs), 100):
            rows = await client(self).invoke(
                functions.users.GetUsersRequest(id=inputs[start : start + 100])
            )
            if not isinstance(rows, list) or any(
                not isinstance(u, (types.User, types.UserEmpty)) for u in rows
            ):
                raise SerializationError("get_users returned an invalid user collection")
            result.extend(rows)
        return result

    async def get_chat_member(self, peer: PeerLike, user: PeerLike) -> ChatMember:
        """Fetch one channel participant or inspect exposed basic-group participants."""
        target = await self.get_input_entity(peer)
        participant = await self.get_input_entity(user)
        user_id = (
            (await client(self).get_me()).id
            if isinstance(participant, types.InputPeerSelf)
            else marked_peer_id(participant)
        )
        if user_id <= 0:
            raise ConfigurationError("member must identify a user")
        if isinstance(target, types.InputPeerChat):
            async for member in client(self).iter_members(target):
                if member.id == user_id:
                    return member
            raise PeerNotFound("user is not in the exposed participant list")
        result = await client(self).invoke(
            functions.channels.GetParticipantRequest(
                channel=as_channel(target), participant=participant
            )
        )
        from .chats import member as build_member

        return build_member(
            result.participant, {u.id: u for u in result.users if isinstance(u, types.User)}
        )

    async def get_chat_members_count(self, peer: PeerLike) -> int:
        """Read server member counts; never infer hidden counts from a truncated list."""
        result = await client(self).get_chat_full(peer)
        full = result.full_chat
        value = getattr(full, "participants_count", None)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        participants = getattr(full, "participants", None)
        if isinstance(participants, types.ChatParticipants):
            return len(participants.participants)
        raise UnsupportedFeature("Telegram did not expose a participant count")

    async def get_chat_history_count(self, peer: PeerLike) -> int:
        """Ask for a single history page and use its actual server count."""
        result = await client(self).invoke(
            functions.messages.GetHistoryRequest(
                peer=await self.get_input_entity(peer),
                offset_id=0,
                offset_date=0,
                add_offset=0,
                limit=1,
                max_id=0,
                min_id=0,
                hash=0,
            )
        )
        return self._message_count(result)

    async def search_messages_count(
        self, peer: PeerLike, query: str, *, sender: PeerLike | None = None
    ) -> int:
        """Count a server-side conversation search, optionally restricted to a sender."""
        text = validate_text(query, "query")
        target = await self.get_input_entity(peer)
        from_peer = await self.get_input_entity(sender) if sender is not None else None
        result = await client(self).invoke(
            functions.messages.SearchRequest(
                peer=target,
                q=text,
                from_id=from_peer,
                filter=types.InputMessagesFilterEmpty(),
                min_date=0,
                max_date=0,
                offset_id=0,
                add_offset=0,
                limit=1,
                max_id=0,
                min_id=0,
                hash=0,
            )
        )
        return self._message_count(result)

    def _message_count(self, result: Any) -> int:
        value = getattr(result, "count", None)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        if isinstance(result, types.messages.Messages):
            return len(result.messages)
        raise SerializationError("response did not provide a valid message count")

    async def _send_media(
        self,
        peer: PeerLike,
        media: TLObject,
        *,
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
        entities: Sequence[TLObject] | None = None,
        reply_markup: TLObject | None = None,
    ) -> types.Message:
        self._send_options(caption, reply_to, silent, entities, reply_markup)
        if media.definition.result != "InputMedia":
            raise ConfigurationError("media must produce InputMedia")
        target = await self.get_input_entity(peer)
        own_id = (
            (await client(self).get_me()).id if isinstance(target, types.InputPeerSelf) else None
        )
        ident = secrets.randbits(63)
        request = functions.messages.SendMediaRequest(
            peer=target,
            media=media,
            message=caption,
            random_id=ident,
            silent=silent,
            entities=list(entities) if entities is not None else None,
            reply_markup=reply_markup,
            reply_to=types.InputReplyToMessage(reply_to_msg_id=reply_to)
            if reply_to is not None
            else None,
        )
        # Validate the complete request before a network write.
        from .tl import Codec

        Codec().encode(request)
        result = await client(self).invoke(request)
        return sent_message(result, output_peer(target, own_id), caption, ident)

    async def _document_media(
        self,
        source: Source,
        attributes: Sequence[TLObject],
        *,
        mime_type: str,
        on_progress: Progress | None,
        part_size: int,
        concurrency: int,
    ) -> TLObject:
        if isinstance(source, (types.InputFile, types.InputFileBig)):
            uploaded = source
        else:
            uploaded = await client(self).upload_file(
                source, on_progress=on_progress, part_size=part_size, concurrency=concurrency
            )
        return types.InputMediaUploadedDocument(
            file=uploaded,
            mime_type=mime_type,
            attributes=[types.DocumentAttributeFilename(file_name=uploaded.name), *attributes],
        )

    async def send_video(
        self,
        peer: PeerLike,
        source: Source,
        *,
        duration: float,
        width: int,
        height: int,
        supports_streaming: bool = False,
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
        entities: Sequence[TLObject] | None = None,
        reply_markup: TLObject | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.Message:
        """Upload/send video with explicit server metadata and literal caption."""
        self._video_metadata(duration, width, height)
        require_booleans(supports_streaming=supports_streaming)
        attributes = [
            types.DocumentAttributeVideo(
                duration=duration, w=width, h=height, supports_streaming=supports_streaming
            )
        ]
        self._send_options(caption, reply_to, silent, entities, reply_markup)
        target = await self.get_input_entity(peer)
        media = await self._document_media(
            source,
            attributes,
            mime_type="video/mp4",
            on_progress=on_progress,
            part_size=part_size,
            concurrency=concurrency,
        )
        return await self._send_media(
            target,
            media,
            caption=caption,
            reply_to=reply_to,
            silent=silent,
            entities=entities,
            reply_markup=reply_markup,
        )

    async def send_video_note(
        self,
        peer: PeerLike,
        source: Source,
        *,
        duration: float,
        length: int,
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
        entities: Sequence[TLObject] | None = None,
        reply_markup: TLObject | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.Message:
        """Upload/send video note with explicit server metadata and literal caption."""
        self._video_metadata(duration, length, length)
        attributes = [
            types.DocumentAttributeVideo(duration=duration, w=length, h=length, round_message=True)
        ]
        self._send_options(caption, reply_to, silent, entities, reply_markup)
        target = await self.get_input_entity(peer)
        media = await self._document_media(
            source,
            attributes,
            mime_type="video/mp4",
            on_progress=on_progress,
            part_size=part_size,
            concurrency=concurrency,
        )
        return await self._send_media(
            target,
            media,
            caption=caption,
            reply_to=reply_to,
            silent=silent,
            entities=entities,
            reply_markup=reply_markup,
        )

    async def send_audio(
        self,
        peer: PeerLike,
        source: Source,
        *,
        duration: int,
        title: str | None = None,
        performer: str | None = None,
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
        entities: Sequence[TLObject] | None = None,
        reply_markup: TLObject | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.Message:
        """Upload/send audio with explicit server metadata and literal caption."""
        self._duration(duration)
        if title is not None:
            validate_text(title, "title")
        if performer is not None:
            validate_text(performer, "performer")
        attributes = [
            types.DocumentAttributeAudio(duration=duration, title=title, performer=performer)
        ]
        self._send_options(caption, reply_to, silent, entities, reply_markup)
        target = await self.get_input_entity(peer)
        media = await self._document_media(
            source,
            attributes,
            mime_type="audio/mpeg",
            on_progress=on_progress,
            part_size=part_size,
            concurrency=concurrency,
        )
        return await self._send_media(
            target,
            media,
            caption=caption,
            reply_to=reply_to,
            silent=silent,
            entities=entities,
            reply_markup=reply_markup,
        )

    async def send_voice(
        self,
        peer: PeerLike,
        source: Source,
        *,
        duration: int,
        waveform: bytes | None = None,
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
        entities: Sequence[TLObject] | None = None,
        reply_markup: TLObject | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.Message:
        """Upload/send voice with explicit server metadata and literal caption."""
        self._duration(duration)
        if waveform is not None and not isinstance(waveform, bytes):
            raise ConfigurationError("waveform must be bytes")
        attributes = [
            types.DocumentAttributeAudio(duration=duration, voice=True, waveform=waveform)
        ]
        self._send_options(caption, reply_to, silent, entities, reply_markup)
        target = await self.get_input_entity(peer)
        media = await self._document_media(
            source,
            attributes,
            mime_type="audio/ogg",
            on_progress=on_progress,
            part_size=part_size,
            concurrency=concurrency,
        )
        return await self._send_media(
            target,
            media,
            caption=caption,
            reply_to=reply_to,
            silent=silent,
            entities=entities,
            reply_markup=reply_markup,
        )

    async def send_animation(
        self,
        peer: PeerLike,
        source: Source,
        *,
        mime_type: str = "image/gif",
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
        entities: Sequence[TLObject] | None = None,
        reply_markup: TLObject | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.Message:
        """Upload/send animation with explicit server metadata and literal caption."""
        if mime_type not in {"image/gif", "video/mp4"}:
            raise ConfigurationError("animation MIME must be image/gif or video/mp4")
        attributes = [types.DocumentAttributeAnimated()]
        self._send_options(caption, reply_to, silent, entities, reply_markup)
        target = await self.get_input_entity(peer)
        media = await self._document_media(
            source,
            attributes,
            mime_type=mime_type,
            on_progress=on_progress,
            part_size=part_size,
            concurrency=concurrency,
        )
        return await self._send_media(
            target,
            media,
            caption=caption,
            reply_to=reply_to,
            silent=silent,
            entities=entities,
            reply_markup=reply_markup,
        )

    async def send_sticker(
        self,
        peer: PeerLike,
        source: Source,
        *,
        emoji: str = "",
        mime_type: str = "image/webp",
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
        entities: Sequence[TLObject] | None = None,
        reply_markup: TLObject | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.Message:
        """Upload/send sticker with explicit server metadata and literal caption."""
        validate_text(emoji, "emoji")
        if mime_type not in {"image/webp", "application/x-tgsticker", "video/webm"}:
            raise ConfigurationError("unsupported sticker MIME")
        attributes = [
            types.DocumentAttributeSticker(alt=emoji, stickerset=types.InputStickerSetEmpty())
        ]
        self._send_options(caption, reply_to, silent, entities, reply_markup)
        target = await self.get_input_entity(peer)
        media = await self._document_media(
            source,
            attributes,
            mime_type=mime_type,
            on_progress=on_progress,
            part_size=part_size,
            concurrency=concurrency,
        )
        return await self._send_media(
            target,
            media,
            caption=caption,
            reply_to=reply_to,
            silent=silent,
            entities=entities,
            reply_markup=reply_markup,
        )

    def _duration(self, value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**31:
            raise ConfigurationError("duration must be nonnegative signed-32-bit seconds")

    def _video_metadata(self, duration: float, width: int, height: int) -> None:
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(duration)
            or duration < 0
        ):
            raise ConfigurationError("video duration must be finite nonnegative seconds")
        for value in (width, height):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < 2**31:
                raise ConfigurationError("video dimensions must be positive signed-32-bit pixels")

    def _send_options(
        self,
        caption: str,
        reply_to: int | None,
        silent: bool,
        entities: Sequence[TLObject] | None,
        reply_markup: TLObject | None,
    ) -> None:
        validate_text(caption, "caption")
        require_booleans(silent=silent)
        if reply_to is not None:
            message_ids(reply_to)
        if entities is not None:
            if isinstance(entities, (str, bytes)) or not isinstance(entities, Sequence):
                raise ConfigurationError(
                    "entities must be a sequence of native MessageEntity objects"
                )
            from .tl import Codec

            codec = Codec()
            for entity in entities:
                if not isinstance(entity, TLObject) or entity.definition.result != "MessageEntity":
                    raise ConfigurationError("entities must contain native MessageEntity objects")
                codec.encode(entity)
                offset, length = getattr(entity, "offset", None), getattr(entity, "length", None)
                units = len(caption.encode("utf-16-le")) // 2
                if (
                    not isinstance(offset, int)
                    or not isinstance(length, int)
                    or offset < 0
                    or length <= 0
                    or offset + length > units
                ):
                    raise ConfigurationError("entities must fit the caption's UTF-16 code units")
        if reply_markup is not None and (
            not isinstance(reply_markup, TLObject)
            or reply_markup.definition.result != "ReplyMarkup"
        ):
            raise ConfigurationError("reply_markup must produce ReplyMarkup")

    async def send_cached_media(
        self,
        peer: PeerLike,
        media: types.Message | types.Photo | types.Document,
        *,
        caption: str = "",
        reply_to: int | None = None,
        silent: bool = False,
        entities: Sequence[TLObject] | None = None,
        reply_markup: TLObject | None = None,
    ) -> types.Message:
        """Reuse native photo/document metadata; opaque file-ID strings are unsupported."""
        return await self._send_media(
            peer,
            cached_media(media),
            caption=caption,
            reply_to=reply_to,
            silent=silent,
            entities=entities,
            reply_markup=reply_markup,
        )

    async def copy_message(
        self,
        peer: PeerLike,
        from_peer: PeerLike,
        message_id: int,
        *,
        reply_to: int | None = None,
        silent: bool = False,
    ) -> types.Message:
        """Copy accessible ordinary text/photo/document content, rejecting protected messages."""
        self._send_options("", reply_to, silent, None, None)
        rows = await client(self).get_messages(from_peer, message_ids(message_id))
        original = rows[0] if rows else None
        if not isinstance(original, types.Message):
            raise PeerNotFound("source is missing or not an ordinary message")
        if original.noforwards:
            raise ConfigurationError("protected content cannot be copied")
        if original.media is None or isinstance(
            original.media, (types.MessageMediaEmpty, types.MessageMediaWebPage)
        ):
            return await client(self).send_message(
                peer, original.message, reply_to=reply_to, silent=silent, entities=original.entities
            )
        return await self.send_cached_media(
            peer,
            original,
            caption=original.message,
            reply_to=reply_to,
            silent=silent,
            entities=original.entities,
        )

    async def send_venue(
        self,
        peer: PeerLike,
        latitude: float,
        longitude: float,
        title: str,
        address: str,
        *,
        provider: str = "",
        venue_id: str = "",
        venue_type: str = "",
        reply_to: int | None = None,
        silent: bool = False,
    ) -> types.Message:
        """Send a geographic venue with explicit provider metadata, not plain text."""
        for coordinate, bound in ((latitude, 90), (longitude, 180)):
            if (
                isinstance(coordinate, bool)
                or not isinstance(coordinate, (int, float))
                or not math.isfinite(coordinate)
                or abs(coordinate) > bound
            ):
                raise ConfigurationError("coordinates must be finite degrees in range")
        for name, value in (
            ("title", title),
            ("address", address),
            ("provider", provider),
            ("venue_id", venue_id),
            ("venue_type", venue_type),
        ):
            validate_text(value, name, empty=name not in {"title", "address"})
        media = types.InputMediaVenue(
            geo_point=types.InputGeoPoint(lat=latitude, long=longitude),
            title=title,
            address=address,
            provider=provider,
            venue_id=venue_id,
            venue_type=venue_type,
        )
        return await self._send_media(peer, media, reply_to=reply_to, silent=silent)

    async def send_game(
        self,
        peer: PeerLike,
        bot: PeerLike,
        short_name: str,
        *,
        reply_to: int | None = None,
        silent: bool = False,
    ) -> types.Message:
        """Send a registered bot game; eligibility and game permissions are server enforced."""
        validate_text(short_name, "short_name", empty=False)
        game = types.InputGameShortName(
            bot_id=as_user(await self.get_input_entity(bot)), short_name=short_name
        )
        return await self._send_media(
            peer, types.InputMediaGame(id=game), reply_to=reply_to, silent=silent
        )

    async def edit_message_caption(
        self,
        peer: PeerLike,
        message_id: int,
        caption: str,
        *,
        entities: Sequence[TLObject] | None = None,
        reply_markup: TLObject | None = None,
    ) -> UpdateResult:
        """Edit literal message/caption text with explicit entities and optional native keyboard."""
        self._send_options(caption, message_id, False, entities, reply_markup)
        return await invoke_updates(
            self,
            functions.messages.EditMessageRequest(
                peer=await self.get_input_entity(peer),
                id=message_id,
                message=caption,
                entities=list(entities) if entities is not None else [],
                reply_markup=reply_markup,
            ),
        )

    async def edit_message_reply_markup(
        self, peer: PeerLike, message_id: int, reply_markup: TLObject
    ) -> UpdateResult:
        """Replace markup only; use ReplyInlineMarkup(rows=[]) for explicit empty markup."""
        self._send_options("", message_id, False, None, reply_markup)
        if reply_markup is None:
            raise ConfigurationError(
                "provide explicit markup, including an empty inline keyboard to clear"
            )
        return await invoke_updates(
            self,
            functions.messages.EditMessageRequest(
                peer=await self.get_input_entity(peer), id=message_id, reply_markup=reply_markup
            ),
        )

    async def edit_message_media(
        self,
        peer: PeerLike,
        message_id: int,
        source: Source,
        *,
        as_document: bool = False,
        caption: str | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> UpdateResult:
        """Upload replacement photo/document media; None caption omits the text edit."""
        require_booleans(as_document=as_document)
        message_ids(message_id)
        if caption is not None:
            validate_text(caption, "caption")
        target = await self.get_input_entity(peer)
        uploaded = (
            source
            if isinstance(source, (types.InputFile, types.InputFileBig))
            else await client(self).upload_file(
                source, on_progress=on_progress, part_size=part_size, concurrency=concurrency
            )
        )
        media = (
            types.InputMediaUploadedDocument(
                file=uploaded,
                mime_type="application/octet-stream",
                attributes=[types.DocumentAttributeFilename(file_name=uploaded.name)],
            )
            if as_document
            else types.InputMediaUploadedPhoto(file=uploaded)
        )
        return await invoke_updates(
            self,
            functions.messages.EditMessageRequest(
                peer=target,
                id=message_id,
                media=media,
                message=caption,
                entities=[] if caption is not None else None,
            ),
        )

    async def send_media_group(
        self,
        peer: PeerLike,
        items: Sequence[AlbumItem],
        *,
        reply_to: int | None = None,
        silent: bool = False,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> list[types.Message]:
        """Send 2–10 photos or 2–10 documents as an album, with explicit per-item captions."""
        if (
            isinstance(items, (str, bytes))
            or not isinstance(items, Sequence)
            or not 2 <= len(items) <= 10
        ):
            raise ConfigurationError("an album requires 2 through 10 AlbumItem values")
        for item in items:
            if not isinstance(item, AlbumItem):
                raise ConfigurationError("items must be AlbumItem values")
            require_booleans(as_document=item.as_document)
            self._send_options(item.caption, reply_to, silent, item.entities, None)
        if len({item.as_document for item in items}) != 1:
            raise ConfigurationError("do not mix generic documents with photo album items")
        target = await self.get_input_entity(peer)
        own_id = (
            (await client(self).get_me()).id if isinstance(target, types.InputPeerSelf) else None
        )
        prepared = []
        for item in items:
            handle = (
                item.source
                if isinstance(item.source, (types.InputFile, types.InputFileBig))
                else await client(self).upload_file(
                    item.source,
                    on_progress=on_progress,
                    part_size=part_size,
                    concurrency=concurrency,
                )
            )
            uploaded = (
                types.InputMediaUploadedDocument(
                    file=handle,
                    mime_type="application/octet-stream",
                    attributes=[types.DocumentAttributeFilename(file_name=handle.name)],
                )
                if item.as_document
                else types.InputMediaUploadedPhoto(file=handle)
            )
            result = await client(self).invoke(
                functions.messages.UploadMediaRequest(peer=target, media=uploaded)
            )
            resource = (
                result.photo
                if isinstance(result, types.MessageMediaPhoto)
                else result.document
                if isinstance(result, types.MessageMediaDocument)
                else None
            )
            media = cached_media(resource)
            prepared.append(
                types.InputSingleMedia(
                    media=media,
                    random_id=secrets.randbits(63),
                    message=item.caption,
                    entities=list(item.entities) if item.entities is not None else None,
                )
            )
        result = await client(self).invoke(
            functions.messages.SendMultiMediaRequest(
                peer=target,
                multi_media=cast("list[TLObject]", prepared),
                silent=silent,
                reply_to=types.InputReplyToMessage(reply_to_msg_id=reply_to)
                if reply_to is not None
                else None,
            )
        )
        return [
            sent_message(result, output_peer(target, own_id), item.message, item.random_id)
            for item in prepared
        ]

    async def get_message(self, peer: PeerLike, message_id: int) -> Message | None:
        """Get one scoped message without changing the legacy get_messages list contract."""
        rows = await client(self).get_messages(peer, message_ids(message_id))
        return rows[0] if rows else None

    async def send_poll(
        self,
        peer: PeerLike,
        question: str,
        options: Sequence[str],
        *,
        anonymous: bool = True,
        multiple_choice: bool = False,
        correct_option: int | None = None,
        solution: str | None = None,
        reply_to: int | None = None,
        silent: bool = False,
    ) -> types.Message:
        """Create a 2–10-option text poll or single-answer quiz using layer-225 field types."""
        validate_text(question, "question", empty=False)
        require_booleans(anonymous=anonymous, multiple_choice=multiple_choice)
        if (
            isinstance(options, (str, bytes))
            or not isinstance(options, Sequence)
            or not 2 <= len(options) <= 10
        ):
            raise ConfigurationError("provide 2–10 option strings")
        for option in options:
            validate_text(option, "option", empty=False)
        if len(set(options)) != len(options):
            raise ConfigurationError("poll option text must be distinct")
        if correct_option is not None:
            if (
                isinstance(correct_option, bool)
                or not isinstance(correct_option, int)
                or not 0 <= correct_option < len(options)
            ):
                raise ConfigurationError("correct_option must be a zero-based option index")
            if multiple_choice:
                raise ConfigurationError("this helper supports only single-answer quizzes")
        if solution is not None:
            if correct_option is None:
                raise ConfigurationError("solution requires a quiz")
            validate_text(solution, "solution")
            if len(solution) > 200 or solution.count("\n") > 2:
                raise ConfigurationError("solution exceeds quiz limits")
        answers = [
            types.PollAnswer(
                text=types.TextWithEntities(text=value, entities=[]),
                option=index.to_bytes(1, "little"),
            )
            for index, value in enumerate(options)
        ]
        poll = types.Poll(
            id=0,
            hash=0,
            question=types.TextWithEntities(text=question, entities=[]),
            answers=cast("list[TLObject]", answers),
            public_voters=not anonymous,
            multiple_choice=multiple_choice,
            quiz=correct_option is not None,
        )
        media = types.InputMediaPoll(
            poll=poll,
            correct_answers=[correct_option] if correct_option is not None else None,
            solution=solution,
            solution_entities=[] if solution is not None else None,
        )
        return await self._send_media(peer, media, reply_to=reply_to, silent=silent)

    async def send_media(
        self,
        peer: PeerLike,
        source: Source,
        *,
        as_document: bool = False,
        caption: str = "",
        mime_type: str | None = None,
        reply_to: int | None = None,
        silent: bool = False,
        entities: Sequence[TLObject] | None = None,
        reply_markup: TLObject | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.Message:
        """Send photo/document media with formatting, progress and delivery options."""
        require_booleans(as_document=as_document)
        self._send_options(caption, reply_to, silent, entities, reply_markup)
        if mime_type is not None:
            validate_text(mime_type, "mime_type", empty=False)
        if not as_document and mime_type is not None:
            raise ConfigurationError("mime_type applies only to document media")
        target = await self.get_input_entity(peer)
        handle = (
            source
            if isinstance(source, (types.InputFile, types.InputFileBig))
            else await client(self).upload_file(
                source, on_progress=on_progress, part_size=part_size, concurrency=concurrency
            )
        )
        if as_document:
            import mimetypes

            media: TLObject = types.InputMediaUploadedDocument(
                file=handle,
                mime_type=mime_type
                or mimetypes.guess_type(handle.name)[0]
                or "application/octet-stream",
                attributes=[types.DocumentAttributeFilename(file_name=handle.name)],
                force_file=True,
            )
        else:
            media = types.InputMediaUploadedPhoto(file=handle)
        return await self._send_media(
            target,
            media,
            caption=caption,
            reply_to=reply_to,
            silent=silent,
            entities=entities,
            reply_markup=reply_markup,
        )
