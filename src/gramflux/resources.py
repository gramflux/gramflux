"""Typed local resource views; execution is delegated to the original Client API.

This handwritten API layer neither opens connections nor caches resolved peers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Literal

from . import chats, dialogs, messages
from .auth import LoginPrompts
from .files import CHUNK, Progress
from .pagination import MessageIDs
from .peers import Entity, InputPeer, PeerLike
from .raw import types

if TYPE_CHECKING:
    from .client import Client, LoginChallenge


class Resource:
    """A local view of one Client, with no independent lifetime or transport."""

    def __init__(self, client: Client) -> None:
        self._client = client


class PeerResource(Resource):
    """Retain the supplied peer reference; resolution happens in delegated calls."""

    def __init__(self, client: Client, peer: PeerLike) -> None:
        super().__init__(client)
        self._peer = peer


class Auth(Resource):
    """Client-bound auth operations on the original execution path."""

    async def login(
        self,
        *,
        phone: str | None = None,
        bot_token: str | None = None,
        max_attempts: int = 3,
        prompts: LoginPrompts | None = None,
    ) -> types.User:
        """Delegate to Client.login; identical options, result and errors."""
        return await self._client.login(
            phone=phone, bot_token=bot_token, max_attempts=max_attempts, prompts=prompts
        )

    async def is_authorized(self) -> bool:
        """Delegate to Client.is_authorized; identical options, result and errors."""
        return await self._client.is_authorized()

    async def request_login_code(self, phone: str) -> LoginChallenge:
        """Delegate to Client.request_login_code; identical options, result and errors."""
        return await self._client.request_login_code(phone)

    async def sign_in(
        self, challenge: LoginChallenge | None = None, code: str | None = None
    ) -> types.User:
        """Delegate to Client.sign_in; identical options, result and errors."""
        return await self._client.sign_in(challenge, code)

    async def check_password(self, password: str) -> types.User:
        """Delegate to Client.check_password; identical options, result and errors."""
        return await self._client.check_password(password)

    async def sign_in_bot(self, token: str) -> types.User:
        """Delegate to Client.sign_in_bot; identical options, result and errors."""
        return await self._client.sign_in_bot(token)

    async def log_out(self) -> None:
        """Delegate to Client.log_out; identical options, result and errors."""
        return await self._client.log_out()

    @property
    def stage(self) -> Literal["code", "password"] | None:
        """Saved local login stage, as on Client.login_stage."""
        return self._client.login_stage

    @property
    def challenge(self) -> LoginChallenge | None:
        """Saved sensitive login checkpoint; no network request."""
        return self._client.login_challenge


class Account(Resource):
    """Client-bound account operations on the original execution path."""

    async def me(self) -> types.User:
        """Delegate to Client.get_me; identical options, result and errors."""
        return await self._client.get_me()

    async def update_profile(
        self,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        about: str | None = None,
    ) -> types.User:
        """Delegate to Client.update_profile; identical options, result and errors."""
        return await self._client.update_profile(
            first_name=first_name, last_name=last_name, about=about
        )

    async def sessions(self) -> list[types.Authorization]:
        """Delegate to Client.get_active_sessions; identical options, result and errors."""
        return await self._client.get_active_sessions()

    async def terminate_session(self, authorization_hash: int) -> bool:
        """Delegate to Client.terminate_session; identical options, result and errors."""
        return await self._client.terminate_session(authorization_hash)


class Peers(Resource):
    """Client-bound peers operations on the original execution path."""

    async def resolve(self, peer: PeerLike, *, refresh: bool = False) -> InputPeer:
        """Delegate to Client.resolve_peer; identical options, result and errors."""
        return await self._client.resolve_peer(peer, refresh=refresh)

    async def user(self, peer: PeerLike = "me") -> types.User:
        """Delegate to Client.get_user; identical options, result and errors."""
        return await self._client.get_user(peer)

    async def user_full(self, peer: PeerLike = "me") -> types.users.UserFull:
        """Delegate to Client.get_user_full; identical options, result and errors."""
        return await self._client.get_user_full(peer)

    async def chat(self, peer: PeerLike) -> Entity:
        """Delegate to Client.get_chat; identical options, result and errors."""
        return await self._client.get_chat(peer)

    async def chat_full(self, peer: PeerLike) -> types.messages.ChatFull:
        """Delegate to Client.get_chat_full; identical options, result and errors."""
        return await self._client.get_chat_full(peer)


class Files(Resource):
    """Client-bound files operations on the original execution path."""

    async def upload(
        self,
        source: str | Path | BinaryIO,
        *,
        name: str | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.InputFile | types.InputFileBig:
        """Delegate to Client.upload_file; identical options, result and errors."""
        return await self._client.upload_file(
            source, name=name, on_progress=on_progress, part_size=part_size, concurrency=concurrency
        )

    async def download(
        self,
        location: Any,
        destination: str | Path | BinaryIO,
        *,
        size: int,
        on_progress: Progress | None = None,
        offset: int = 0,
        length: int | None = None,
        request_size: int = CHUNK,
    ) -> Path | None:
        """Delegate to Client.download_file; identical options, result and errors."""
        return await self._client.download_file(
            location,
            destination,
            size=size,
            on_progress=on_progress,
            offset=offset,
            length=length,
            request_size=request_size,
        )

    async def download_media(
        self,
        message: types.Message,
        destination: str | Path | BinaryIO,
        *,
        on_progress: Progress | None = None,
        offset: int = 0,
        length: int | None = None,
        request_size: int = CHUNK,
    ) -> Path | None:
        """Delegate to Client.download_media; identical options, result and errors."""
        return await self._client.download_media(
            message,
            destination,
            on_progress=on_progress,
            offset=offset,
            length=length,
            request_size=request_size,
        )

    def iter_download(
        self,
        location: Any,
        *,
        size: int,
        offset: int = 0,
        length: int | None = None,
        request_size: int = CHUNK,
    ) -> AsyncIterator[bytes]:
        """Delegate to Client.iter_download; identical options, result and errors."""
        return self._client.iter_download(
            location, size=size, offset=offset, length=length, request_size=request_size
        )

    def iter_download_media(
        self,
        message: types.Message,
        *,
        offset: int = 0,
        length: int | None = None,
        request_size: int = CHUNK,
    ) -> AsyncIterator[bytes]:
        """Delegate to Client.iter_download_media; identical options, result and errors."""
        return self._client.iter_download_media(
            message, offset=offset, length=length, request_size=request_size
        )


class Contacts(Resource):
    """Client-bound contacts operations on the original execution path."""

    async def list(self) -> list[types.User]:
        """Delegate to Client.get_contacts; identical options, result and errors."""
        return await self._client.get_contacts()

    async def add(
        self,
        peer: PeerLike,
        first_name: str,
        *,
        last_name: str = "",
        phone: str = "",
        share_phone: bool = False,
    ) -> Any:
        """Delegate to Client.add_contact; identical options, result and errors."""
        return await self._client.add_contact(
            peer, first_name, last_name=last_name, phone=phone, share_phone=share_phone
        )

    async def delete(self, peers: Sequence[PeerLike]) -> Any:
        """Delegate to Client.delete_contacts; identical options, result and errors."""
        return await self._client.delete_contacts(peers)

    async def block(self, peer: PeerLike) -> bool:
        """Delegate to Client.block_user; identical options, result and errors."""
        return await self._client.block_user(peer)

    async def unblock(self, peer: PeerLike) -> bool:
        """Delegate to Client.unblock_user; identical options, result and errors."""
        return await self._client.unblock_user(peer)


class Dialogs(Resource):
    """Client-bound dialogs operations on the original execution path."""

    async def list(self, *, limit: int = 100, folder_id: int = 0) -> list[dialogs.Dialog]:
        """Delegate to Client.get_dialogs; identical options, result and errors."""
        return await self._client.get_dialogs(limit=limit, folder_id=folder_id)

    def iter(
        self, *, limit: int | None = None, folder_id: int = 0, page_size: int = 100
    ) -> AsyncIterator[dialogs.Dialog]:
        """Delegate to Client.iter_dialogs; identical options, result and errors."""
        return self._client.iter_dialogs(limit=limit, folder_id=folder_id, page_size=page_size)


class Bot(Resource):
    """Client-bound bot operations on the original execution path."""

    async def commands(
        self, *, lang_code: str = "", scope: types.TypeBotCommandScope | None = None
    ) -> list[types.BotCommand]:
        """Delegate to Client.get_bot_commands; identical options, result and errors."""
        return await self._client.get_bot_commands(lang_code=lang_code, scope=scope)

    async def set_commands(
        self,
        commands: Sequence[types.BotCommand],
        *,
        lang_code: str = "",
        scope: types.TypeBotCommandScope | None = None,
    ) -> bool:
        """Delegate to Client.set_bot_commands; identical options, result and errors."""
        return await self._client.set_bot_commands(commands, lang_code=lang_code, scope=scope)

    async def answer_callback(
        self,
        query_id: int,
        *,
        text: str = "",
        alert: bool = False,
        url: str | None = None,
        cache_time: int = 0,
    ) -> bool:
        """Delegate to Client.answer_callback_query; identical options, result and errors."""
        return await self._client.answer_callback_query(
            query_id, text=text, alert=alert, url=url, cache_time=cache_time
        )

    async def answer_inline(
        self,
        query_id: int,
        results: Sequence[types.TypeInputBotInlineResult],
        *,
        cache_time: int = 300,
        next_offset: str = "",
        private: bool = False,
        gallery: bool = False,
    ) -> bool:
        """Delegate to Client.answer_inline_query; identical options, result and errors."""
        return await self._client.answer_inline_query(
            query_id,
            results,
            cache_time=cache_time,
            next_offset=next_offset,
            private=private,
            gallery=gallery,
        )

    async def inline_results(
        self, bot: PeerLike, query: str, *, peer: PeerLike = "me", offset: str = ""
    ) -> types.messages.BotResults:
        """Delegate to Client.get_inline_results; identical options, result and errors."""
        return await self._client.get_inline_results(bot, query, peer=peer, offset=offset)

    async def callback_answer(
        self, peer: PeerLike, message_id: int, *, data: bytes | None = None, game: bool = False
    ) -> types.messages.BotCallbackAnswer:
        """Delegate to Client.get_callback_answer; identical options, result and errors."""
        return await self._client.get_callback_answer(peer, message_id, data=data, game=game)

    async def edit_inline(
        self,
        message_id: types.TypeInputBotInlineMessageID,
        text: str,
        *,
        reply_markup: types.TypeReplyMarkup | None = None,
        link_preview: bool = True,
    ) -> bool:
        """Delegate to Client.edit_inline_message; identical options, result and errors."""
        return await self._client.edit_inline_message(
            message_id, text, reply_markup=reply_markup, link_preview=link_preview
        )

    async def start(self, bot: PeerLike, *, peer: PeerLike = "me", start_param: str = "") -> Any:
        """Delegate to Client.start_bot; identical options, result and errors."""
        return await self._client.start_bot(bot, peer=peer, start_param=start_param)


class Invites(Resource):
    """Client-bound invites operations on the original execution path."""

    async def check(self, invite_hash: str) -> types.TypeChatInvite:
        """Delegate to Client.check_invite; identical options, result and errors."""
        return await self._client.check_invite(invite_hash)

    async def accept(self, invite_hash: str) -> Any:
        """Delegate to Client.import_invite; identical options, result and errors."""
        return await self._client.import_invite(invite_hash)

    async def export(
        self,
        peer: PeerLike,
        *,
        title: str | None = None,
        expire_date: int | None = None,
        usage_limit: int | None = None,
        request_needed: bool = False,
    ) -> types.TypeExportedChatInvite:
        """Delegate to Client.export_invite_link; identical options, result and errors."""
        return await self._client.export_invite_link(
            peer,
            title=title,
            expire_date=expire_date,
            usage_limit=usage_limit,
            request_needed=request_needed,
        )


class Membership(Resource):
    """Client-bound membership operations on the original execution path."""

    async def join(self, peer: PeerLike) -> Any:
        """Delegate to Client.join_chat; identical options, result and errors."""
        return await self._client.join_chat(peer)

    async def leave(self, peer: PeerLike) -> Any:
        """Delegate to Client.leave_chat; identical options, result and errors."""
        return await self._client.leave_chat(peer)

    async def members(
        self, peer: PeerLike, *, limit: int = 100, query: str = ""
    ) -> list[chats.ChatMember]:
        """Delegate to Client.get_members; identical options, result and errors."""
        return await self._client.get_members(peer, limit=limit, query=query)

    def iter_members(
        self, peer: PeerLike, *, limit: int | None = None, query: str = "", page_size: int = 100
    ) -> AsyncIterator[chats.ChatMember]:
        """Delegate to Client.iter_members; identical options, result and errors."""
        return self._client.iter_members(peer, limit=limit, query=query, page_size=page_size)


class History(PeerResource):
    """Peer-bound history operations on the original execution path."""

    async def fetch(self, *, limit: int = 100, offset_id: int = 0) -> list[messages.Message]:
        """Delegate to Client.get_history; identical options, result and errors."""
        return await self._client.get_history(self._peer, limit=limit, offset_id=offset_id)

    def iter(
        self, *, limit: int | None = None, offset_id: int = 0, page_size: int = 100
    ) -> AsyncIterator[messages.Message]:
        """Delegate to Client.iter_history; identical options, result and errors."""
        return self._client.iter_history(
            self._peer, limit=limit, offset_id=offset_id, page_size=page_size
        )

    async def get(self, ids: MessageIDs) -> list[messages.Message | None]:
        """Delegate to Client.get_messages; identical options, result and errors."""
        return await self._client.get_messages(self._peer, ids)


class Search(PeerResource):
    """Peer-bound search operations on the original execution path."""

    async def fetch(
        self, query: str, *, limit: int = 100, sender: PeerLike | None = None
    ) -> list[messages.Message]:
        """Delegate to Client.search_messages; identical options, result and errors."""
        return await self._client.search_messages(self._peer, query, limit=limit, sender=sender)

    def iter(
        self,
        query: str,
        *,
        limit: int | None = None,
        sender: PeerLike | None = None,
        page_size: int = 100,
    ) -> AsyncIterator[messages.Message]:
        """Delegate to Client.iter_search; identical options, result and errors."""
        return self._client.iter_search(
            self._peer, query, limit=limit, sender=sender, page_size=page_size
        )


class Members(PeerResource):
    """Peer-bound members operations on the original execution path."""

    async def fetch(self, *, limit: int = 100, query: str = "") -> list[chats.ChatMember]:
        """Delegate to Client.get_members; identical options, result and errors."""
        return await self._client.get_members(self._peer, limit=limit, query=query)

    def iter(
        self, *, limit: int | None = None, query: str = "", page_size: int = 100
    ) -> AsyncIterator[chats.ChatMember]:
        """Delegate to Client.iter_members; identical options, result and errors."""
        return self._client.iter_members(self._peer, limit=limit, query=query, page_size=page_size)


class ChatResource(PeerResource):
    """Peer-bound chatresource operations on the original execution path."""

    async def send(
        self,
        text: str,
        *,
        reply_to: int | None = None,
        silent: bool = False,
        link_preview: bool = True,
        reply_markup: types.TypeReplyMarkup | None = None,
        entities: list[types.TypeMessageEntity] | None = None,
    ) -> types.Message:
        """Delegate to Client.send_message; identical options, result and errors."""
        return await self._client.send_message(
            self._peer,
            text,
            reply_to=reply_to,
            silent=silent,
            link_preview=link_preview,
            reply_markup=reply_markup,
            entities=entities,
        )

    async def edit(self, message_id: int, text: str, *, link_preview: bool = True) -> Any:
        """Delegate to Client.edit_message; identical options, result and errors."""
        return await self._client.edit_message(
            self._peer, message_id, text, link_preview=link_preview
        )

    async def delete(
        self, ids: MessageIDs, *, revoke: bool = False
    ) -> list[types.messages.AffectedMessages]:
        """Delegate to Client.delete_messages; identical options, result and errors."""
        return await self._client.delete_messages(self._peer, ids, revoke=revoke)

    async def forward(
        self,
        from_peer: PeerLike,
        ids: MessageIDs,
        *,
        silent: bool = False,
        drop_author: bool = False,
    ) -> list[Any]:
        """Delegate to Client.forward_messages; identical options, result and errors."""
        return await self._client.forward_messages(
            self._peer, from_peer, ids, silent=silent, drop_author=drop_author
        )

    async def mark_read(self, *, max_id: int = 0) -> Any:
        """Delegate to Client.read_history; identical options, result and errors."""
        return await self._client.read_history(self._peer, max_id=max_id)

    async def pin(self, message_id: int, *, silent: bool = True) -> Any:
        """Delegate to Client.pin_message; identical options, result and errors."""
        return await self._client.pin_message(self._peer, message_id, silent=silent)

    async def unpin(self, message_id: int) -> Any:
        """Delegate to Client.unpin_message; identical options, result and errors."""
        return await self._client.unpin_message(self._peer, message_id)

    async def react(
        self,
        message_id: int,
        reactions: str | Sequence[types.TypeReaction] | None,
        *,
        big: bool = False,
        add_to_recent: bool = True,
    ) -> Any:
        """Delegate to Client.send_reaction; identical options, result and errors."""
        return await self._client.send_reaction(
            self._peer, message_id, reactions, big=big, add_to_recent=add_to_recent
        )

    async def draft(
        self, text: str, *, reply_to: int | None = None, link_preview: bool = True
    ) -> bool:
        """Delegate to Client.save_draft; identical options, result and errors."""
        return await self._client.save_draft(
            self._peer, text, reply_to=reply_to, link_preview=link_preview
        )

    async def typing(
        self,
        *,
        action: types.TypeSendMessageAction | None = None,
        top_message_id: int | None = None,
    ) -> bool:
        """Delegate to Client.set_typing; identical options, result and errors."""
        return await self._client.set_typing(
            self._peer, action=action, top_message_id=top_message_id
        )

    async def info(self) -> Entity:
        """Delegate to Client.get_chat; identical options, result and errors."""
        return await self._client.get_chat(self._peer)

    async def full_info(self) -> types.messages.ChatFull:
        """Delegate to Client.get_chat_full; identical options, result and errors."""
        return await self._client.get_chat_full(self._peer)

    async def set_title(self, title: str) -> Any:
        """Delegate to Client.set_chat_title; identical options, result and errors."""
        return await self._client.set_chat_title(self._peer, title)

    async def set_description(self, description: str) -> bool:
        """Delegate to Client.set_chat_description; identical options, result and errors."""
        return await self._client.set_chat_description(self._peer, description)

    async def send_file(
        self,
        file: types.InputFile | types.InputFileBig | types.TypeInputMedia,
        *,
        caption: str = "",
        reply_to: int | None = None,
        as_document: bool = False,
        mime_type: str | None = None,
    ) -> types.Message:
        """Delegate to Client.send_file; identical options, result and errors."""
        return await self._client.send_file(
            self._peer,
            file,
            caption=caption,
            reply_to=reply_to,
            as_document=as_document,
            mime_type=mime_type,
        )

    async def send_document(
        self,
        source: str | Path | BinaryIO,
        *,
        name: str | None = None,
        caption: str = "",
        mime_type: str | None = None,
        reply_to: int | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.Message:
        """Delegate to Client.send_document; identical options, result and errors."""
        return await self._client.send_document(
            self._peer,
            source,
            name=name,
            caption=caption,
            mime_type=mime_type,
            reply_to=reply_to,
            on_progress=on_progress,
            part_size=part_size,
            concurrency=concurrency,
        )

    async def send_photo(
        self,
        source: str | Path | BinaryIO,
        *,
        caption: str = "",
        reply_to: int | None = None,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.Message:
        """Delegate to Client.send_photo; identical options, result and errors."""
        return await self._client.send_photo(
            self._peer,
            source,
            caption=caption,
            reply_to=reply_to,
            on_progress=on_progress,
            part_size=part_size,
            concurrency=concurrency,
        )

    async def send_contact(
        self, phone: str, first_name: str, *, last_name: str = "", vcard: str = ""
    ) -> types.Message:
        """Delegate to Client.send_contact; identical options, result and errors."""
        return await self._client.send_contact(
            self._peer, phone, first_name, last_name=last_name, vcard=vcard
        )

    async def send_location(self, latitude: float, longitude: float) -> types.Message:
        """Delegate to Client.send_location; identical options, result and errors."""
        return await self._client.send_location(self._peer, latitude, longitude)

    async def send_dice(self, *, emoji: str = "🎲") -> types.Message:
        """Delegate to Client.send_dice; identical options, result and errors."""
        return await self._client.send_dice(self._peer, emoji=emoji)

    async def export_invite(
        self,
        *,
        title: str | None = None,
        expire_date: int | None = None,
        usage_limit: int | None = None,
        request_needed: bool = False,
    ) -> types.TypeExportedChatInvite:
        """Delegate to Client.export_invite_link; identical options, result and errors."""
        return await self._client.export_invite_link(
            self._peer,
            title=title,
            expire_date=expire_date,
            usage_limit=usage_limit,
            request_needed=request_needed,
        )

    async def join(self) -> Any:
        """Delegate to Client.join_chat; identical options, result and errors."""
        return await self._client.join_chat(self._peer)

    async def leave(self) -> Any:
        """Delegate to Client.leave_chat; identical options, result and errors."""
        return await self._client.leave_chat(self._peer)

    @property
    def history(self) -> History:
        """Local history view for this peer; no request is made."""
        return History(self._client, self._peer)

    @property
    def search(self) -> Search:
        """Local search view for this peer; no request is made."""
        return Search(self._client, self._peer)

    @property
    def members(self) -> Members:
        """Local members view for this peer; no request is made."""
        return Members(self._client, self._peer)


class ChatFactory(Resource):
    """Callable local factory exposed as client.chat(peer)."""

    def __call__(self, peer: PeerLike) -> ChatResource:
        """Construct a local peer view without resolving identity or doing I/O."""
        return ChatResource(self._client, peer)
