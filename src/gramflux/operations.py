"""Developer-facing Telegram operations, separate from transport and native sender."""

import math
import secrets
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from .errors import ConfigurationError
from .pagination import message_ids
from .peers import InputPeer, PeerLike, as_channel, as_user
from .raw import functions, types


def integer(value: int, name: str, *, signed: bool = False) -> int:
    lower = -(2**63) if signed else 0
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value < 2**63:
        raise ConfigurationError(f"{name} must be a valid integer")
    return value


def validate_text(value: str, name: str, *, empty: bool = True) -> str:
    if not isinstance(value, str) or not empty and not value.strip():
        raise ConfigurationError(f"invalid {name}")
    return value


def cache_seconds(value: int) -> int:
    integer(value, "cache_time")
    if value >= 2**31:
        raise ConfigurationError("cache_time must fit a signed 32-bit integer")
    return value


def require_booleans(**values: bool) -> None:
    if any(not isinstance(value, bool) for value in values.values()):
        raise ConfigurationError("operation flags must be bool values")


class TelegramMethods(ABC):
    """Operation implementations; Client supplies request execution and peer resolution."""

    @abstractmethod
    async def invoke(self, request: Any) -> Any:
        """Execute a generated native method."""

    @abstractmethod
    async def resolve_peer(self, peer: PeerLike, *, refresh: bool = False) -> InputPeer:
        """Resolve an accessible peer without guessing access hashes."""

    @abstractmethod
    async def send_file(self, peer: PeerLike, file: Any, *, caption: str = "") -> Any:
        """Send uploaded media using the client's result correlation."""

    async def answer_callback_query(
        self,
        query_id: int,
        *,
        text: str = "",
        alert: bool = False,
        url: str | None = None,
        cache_time: int = 0,
    ) -> bool:
        require_booleans(alert=alert)
        integer(query_id, "query_id", signed=True)
        return bool(
            await self.invoke(
                functions.messages.SetBotCallbackAnswerRequest(
                    query_id=query_id,
                    message=validate_text(text, "text") or None,
                    alert=alert,
                    url=validate_text(url, "url") if url is not None else None,
                    cache_time=cache_seconds(cache_time),
                )
            )
        )

    async def answer_inline_query(
        self,
        query_id: int,
        results: Sequence[types.TypeInputBotInlineResult],
        *,
        cache_time: int = 300,
        next_offset: str = "",
        private: bool = False,
        gallery: bool = False,
    ) -> bool:
        require_booleans(private=private, gallery=gallery)
        integer(query_id, "query_id", signed=True)
        if isinstance(results, (str, bytes)) or len(results) > 50:
            raise ConfigurationError("provide at most 50 native inline results")
        ids = []
        for result in results:
            if (
                getattr(getattr(result, "definition", None), "result", None)
                != "InputBotInlineResult"
            ):
                raise ConfigurationError("expected native inline results")
            ident = result.id
            if not isinstance(ident, str) or not 1 <= len(ident.encode("utf-8")) <= 64:
                raise ConfigurationError("inline result IDs require 1..64 UTF-8 bytes")
            ids.append(ident)
        if len(set(ids)) != len(ids):
            raise ConfigurationError("inline result IDs must be unique")
        return bool(
            await self.invoke(
                functions.messages.SetInlineBotResultsRequest(
                    query_id=query_id,
                    results=list(results),
                    cache_time=cache_seconds(cache_time),
                    next_offset=validate_text(next_offset, "next_offset") or None,
                    private=private,
                    gallery=gallery,
                )
            )
        )

    async def edit_inline_message(
        self,
        message_id: types.TypeInputBotInlineMessageID,
        text: str,
        *,
        reply_markup: types.TypeReplyMarkup | None = None,
        link_preview: bool = True,
    ) -> bool:
        require_booleans(link_preview=link_preview)
        return bool(
            await self.invoke(
                functions.messages.EditInlineBotMessageRequest(
                    id=message_id,
                    message=validate_text(text, "text"),
                    reply_markup=reply_markup,
                    no_webpage=not link_preview,
                )
            )
        )

    async def get_inline_results(
        self,
        bot: PeerLike,
        query: str,
        *,
        peer: PeerLike = "me",
        offset: str = "",
    ) -> types.messages.BotResults:
        result: types.messages.BotResults = await self.invoke(
            functions.messages.GetInlineBotResultsRequest(
                bot=as_user(await self.resolve_peer(bot)),
                peer=await self.resolve_peer(peer),
                query=validate_text(query, "query"),
                offset=validate_text(offset, "offset"),
            )
        )
        return result

    async def get_callback_answer(
        self,
        peer: PeerLike,
        message_id: int,
        *,
        data: bytes | None = None,
        game: bool = False,
    ) -> types.messages.BotCallbackAnswer:
        require_booleans(game=game)
        message_ids(message_id)
        if data is not None and not isinstance(data, bytes):
            raise ConfigurationError("callback data must be bytes")
        result: types.messages.BotCallbackAnswer = await self.invoke(
            functions.messages.GetBotCallbackAnswerRequest(
                peer=await self.resolve_peer(peer),
                msg_id=message_id,
                data=data,
                game=game,
            )
        )
        return result

    async def set_bot_commands(
        self,
        commands: Sequence[types.BotCommand],
        *,
        lang_code: str = "",
        scope: types.TypeBotCommandScope | None = None,
    ) -> bool:
        if len(commands) > 100 or any(not isinstance(item, types.BotCommand) for item in commands):
            raise ConfigurationError("provide at most 100 native BotCommand objects")
        names = [item.command for item in commands]
        if len(set(names)) != len(names):
            raise ConfigurationError("bot commands must be unique")
        return bool(
            await self.invoke(
                functions.bots.SetBotCommandsRequest(
                    scope=scope if scope is not None else types.BotCommandScopeDefault(),
                    lang_code=validate_text(lang_code, "lang_code"),
                    commands=list(commands),
                )
            )
        )

    async def get_bot_commands(
        self,
        *,
        lang_code: str = "",
        scope: types.TypeBotCommandScope | None = None,
    ) -> list[types.BotCommand]:
        result: list[types.BotCommand] = await self.invoke(
            functions.bots.GetBotCommandsRequest(
                scope=scope if scope is not None else types.BotCommandScopeDefault(),
                lang_code=validate_text(lang_code, "lang_code"),
            )
        )
        return result

    async def set_typing(
        self,
        peer: PeerLike,
        *,
        action: types.TypeSendMessageAction | None = None,
        top_message_id: int | None = None,
    ) -> bool:
        if top_message_id is not None:
            message_ids(top_message_id)
        return bool(
            await self.invoke(
                functions.messages.SetTypingRequest(
                    peer=await self.resolve_peer(peer),
                    action=action if action is not None else types.SendMessageTypingAction(),
                    top_msg_id=top_message_id,
                )
            )
        )

    async def send_reaction(
        self,
        peer: PeerLike,
        message_id: int,
        reactions: str | Sequence[types.TypeReaction] | None,
        *,
        big: bool = False,
        add_to_recent: bool = True,
    ) -> Any:
        require_booleans(big=big, add_to_recent=add_to_recent)
        message_ids(message_id)
        values = (
            [types.ReactionEmoji(emoticon=validate_text(reactions, "reaction", empty=False))]
            if isinstance(reactions, str)
            else list(reactions or [])
        )
        if any(
            getattr(getattr(value, "definition", None), "result", None) != "Reaction"
            for value in values
        ):
            raise ConfigurationError("provide an emoji or native Reaction objects")
        return await self.invoke(
            functions.messages.SendReactionRequest(
                peer=await self.resolve_peer(peer),
                msg_id=message_id,
                reaction=values,
                big=big,
                add_to_recent=add_to_recent,
            )
        )

    async def save_draft(
        self,
        peer: PeerLike,
        text: str,
        *,
        reply_to: int | None = None,
        link_preview: bool = True,
    ) -> bool:
        require_booleans(link_preview=link_preview)
        if reply_to is not None:
            message_ids(reply_to)
        return bool(
            await self.invoke(
                functions.messages.SaveDraftRequest(
                    peer=await self.resolve_peer(peer),
                    message=validate_text(text, "text"),
                    reply_to=types.InputReplyToMessage(reply_to_msg_id=reply_to)
                    if reply_to is not None
                    else None,
                    no_webpage=not link_preview,
                )
            )
        )

    async def export_invite_link(
        self,
        peer: PeerLike,
        *,
        title: str | None = None,
        expire_date: int | None = None,
        usage_limit: int | None = None,
        request_needed: bool = False,
    ) -> types.TypeExportedChatInvite:
        require_booleans(request_needed=request_needed)
        for name, value in (("expire_date", expire_date), ("usage_limit", usage_limit)):
            if value is not None and (integer(value, name) == 0 or value >= 2**31):
                raise ConfigurationError(f"{name} must be a positive signed 32-bit integer")
        if request_needed and usage_limit is not None:
            raise ConfigurationError("join requests cannot have a usage limit")
        result: types.TypeExportedChatInvite = await self.invoke(
            functions.messages.ExportChatInviteRequest(
                peer=await self.resolve_peer(peer),
                title=validate_text(title, "title") if title is not None else None,
                expire_date=expire_date,
                usage_limit=usage_limit,
                request_needed=request_needed,
            )
        )
        return result

    async def check_invite(self, invite_hash: str) -> types.TypeChatInvite:
        import re

        if not isinstance(invite_hash, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,256}", invite_hash
        ):
            raise ConfigurationError("provide an invite hash, not a URL")
        result: types.TypeChatInvite = await self.invoke(
            functions.messages.CheckChatInviteRequest(hash=invite_hash)
        )
        return result

    async def set_chat_title(self, peer: PeerLike, title: str) -> Any:
        target = await self.resolve_peer(peer)
        title = validate_text(title, "title", empty=False)
        if isinstance(target, types.InputPeerChat):
            return await self.invoke(
                functions.messages.EditChatTitleRequest(chat_id=target.chat_id, title=title)
            )
        return await self.invoke(
            functions.channels.EditTitleRequest(channel=as_channel(target), title=title)
        )

    async def set_chat_description(self, peer: PeerLike, description: str) -> bool:
        return bool(
            await self.invoke(
                functions.messages.EditChatAboutRequest(
                    peer=await self.resolve_peer(peer),
                    about=validate_text(description, "description"),
                )
            )
        )

    async def add_contact(
        self,
        peer: PeerLike,
        first_name: str,
        *,
        last_name: str = "",
        phone: str = "",
        share_phone: bool = False,
    ) -> Any:
        require_booleans(share_phone=share_phone)
        return await self.invoke(
            functions.contacts.AddContactRequest(
                id=as_user(await self.resolve_peer(peer)),
                first_name=validate_text(first_name, "first_name", empty=False),
                last_name=validate_text(last_name, "last_name"),
                phone=validate_text(phone, "phone"),
                add_phone_privacy_exception=share_phone,
            )
        )

    async def delete_contacts(self, peers: Sequence[PeerLike]) -> Any:
        if isinstance(peers, (str, bytes)) or not peers:
            raise ConfigurationError("provide a nonempty sequence of user peers")
        users = [as_user(await self.resolve_peer(peer)) for peer in peers]
        return await self.invoke(functions.contacts.DeleteContactsRequest(id=users))

    async def update_profile(
        self,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        about: str | None = None,
    ) -> types.User:
        if first_name is last_name is about is None:
            raise ConfigurationError("provide at least one profile field")
        for name, value in (("first_name", first_name), ("last_name", last_name), ("about", about)):
            if value is not None:
                validate_text(value, name, empty=name != "first_name")
        result: types.User = await self.invoke(
            functions.account.UpdateProfileRequest(
                first_name=first_name,
                last_name=last_name,
                about=about,
            )
        )
        return result

    async def get_active_sessions(self) -> list[types.Authorization]:
        result = await self.invoke(functions.account.GetAuthorizationsRequest())
        return list(result.authorizations)

    async def terminate_session(self, authorization_hash: int) -> bool:
        integer(authorization_hash, "authorization_hash", signed=True)
        return bool(
            await self.invoke(functions.account.ResetAuthorizationRequest(hash=authorization_hash))
        )

    async def start_bot(
        self, bot: PeerLike, *, peer: PeerLike = "me", start_param: str = ""
    ) -> Any:
        return await self.invoke(
            functions.messages.StartBotRequest(
                bot=as_user(await self.resolve_peer(bot)),
                peer=await self.resolve_peer(peer),
                start_param=validate_text(start_param, "start_param"),
                random_id=secrets.randbits(63),
            )
        )

    async def send_contact(
        self,
        peer: PeerLike,
        phone: str,
        first_name: str,
        *,
        last_name: str = "",
        vcard: str = "",
    ) -> types.Message:
        result: types.Message = await self.send_file(
            peer,
            types.InputMediaContact(
                phone_number=validate_text(phone, "phone", empty=False),
                first_name=validate_text(first_name, "first_name", empty=False),
                last_name=validate_text(last_name, "last_name"),
                vcard=validate_text(vcard, "vcard"),
            ),
        )
        return result

    async def send_location(
        self, peer: PeerLike, latitude: float, longitude: float
    ) -> types.Message:
        if (
            any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in (latitude, longitude)
            )
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise ConfigurationError("latitude/longitude must be finite valid coordinates")
        result: types.Message = await self.send_file(
            peer,
            types.InputMediaGeoPoint(
                geo_point=types.InputGeoPoint(lat=latitude, long=longitude),
            ),
        )
        return result

    async def send_dice(self, peer: PeerLike, *, emoji: str = "🎲") -> types.Message:
        result: types.Message = await self.send_file(
            peer, types.InputMediaDice(emoticon=validate_text(emoji, "emoji", empty=False))
        )
        return result
