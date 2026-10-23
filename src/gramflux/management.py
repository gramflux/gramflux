"""Validated account/chat administration over the existing Client invoker."""

from __future__ import annotations

import re
import secrets
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, BinaryIO, cast

from .errors import ConfigurationError, SerializationError
from .files import CHUNK, Progress
from .highlevel import Draft, Source, UpdateResult, client, invoke_updates
from .operations import require_booleans, validate_text
from .pagination import count
from .peers import PeerLike, as_channel, as_user
from .raw import functions, types
from .tl.model import TLObject


@dataclass(frozen=True, slots=True)
class ChatPermissions:
    """Allowed member actions. False becomes a forbidden Telegram right."""

    send_messages: bool = True
    send_media: bool = True
    send_polls: bool = True
    embed_links: bool = True
    change_info: bool = False
    invite_users: bool = False
    pin_messages: bool = False
    manage_topics: bool = False

    def __post_init__(self) -> None:
        require_booleans(**{field.name: getattr(self, field.name) for field in fields(self)})

    def _banned(self, until_date: int = 0) -> types.ChatBannedRights:
        count(until_date, name="until_date", allow_none=False)
        if until_date >= 2**31:
            raise ConfigurationError("until_date must fit signed 32-bit Unix seconds")
        return types.ChatBannedRights(
            until_date=until_date,
            send_plain=not self.send_messages,
            send_media=not self.send_media,
            send_photos=not self.send_media,
            send_videos=not self.send_media,
            send_roundvideos=not self.send_media,
            send_audios=not self.send_media,
            send_voices=not self.send_media,
            send_docs=not self.send_media,
            send_stickers=not self.send_media,
            send_gifs=not self.send_media,
            send_games=not self.send_media,
            send_inline=not self.send_media,
            send_polls=not self.send_polls,
            embed_links=not self.embed_links,
            change_info=not self.change_info,
            invite_users=not self.invite_users,
            pin_messages=not self.pin_messages,
            manage_topics=not self.manage_topics,
        )


@dataclass(frozen=True, slots=True)
class AdminPrivileges:
    """Explicit admin grants; all False demotes rather than implying full access."""

    change_info: bool = False
    post_messages: bool = False
    edit_messages: bool = False
    delete_messages: bool = False
    ban_users: bool = False
    invite_users: bool = False
    pin_messages: bool = False
    add_admins: bool = False
    manage_call: bool = False
    manage_topics: bool = False
    anonymous: bool = False
    post_stories: bool = False
    edit_stories: bool = False
    delete_stories: bool = False

    def __post_init__(self) -> None:
        require_booleans(**{field.name: getattr(self, field.name) for field in fields(self)})

    def _native(self) -> types.ChatAdminRights:
        return types.ChatAdminRights(
            **{field.name: getattr(self, field.name) for field in fields(self)}
        )


class ManagementMethods:
    """Daily management operations; server authorization errors always propagate."""

    async def set_username(self, username: str) -> types.User:
        """Set/clear an ordinary account username; availability is determined by Telegram."""
        validate_text(username, "username")
        if username and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", username):
            raise ConfigurationError(
                "ordinary usernames require 5–32 ASCII letters/digits/underscores, "
                "starting with a letter"
            )
        return cast(
            types.User,
            await client(self).invoke(functions.account.UpdateUsernameRequest(username=username)),
        )

    async def delete_bot_commands(
        self, *, lang_code: str = "", scope: TLObject | None = None
    ) -> bool:
        """Reset commands in the explicit bot scope/language; does not modify other scopes."""
        validate_text(lang_code, "lang_code")
        if scope is not None and scope.definition.result != "BotCommandScope":
            raise ConfigurationError("scope must produce BotCommandScope")
        return bool(
            await client(self).invoke(
                functions.bots.ResetBotCommandsRequest(
                    scope=scope if scope is not None else types.BotCommandScopeDefault(),
                    lang_code=lang_code,
                )
            )
        )

    async def set_chat_menu_button(
        self,
        user: PeerLike | None = None,
        *,
        text: str | None = None,
        url: str | None = None,
        commands: bool = False,
    ) -> bool:
        """Set a bot's per-user/default Web App menu, commands menu or default menu."""
        require_booleans(commands=commands)
        if commands and (text is not None or url is not None):
            raise ConfigurationError("commands cannot be combined with Web App text/url")
        if (text is None) != (url is None):
            raise ConfigurationError("provide both text and url")
        if text is not None:
            validate_text(text, "text", empty=False)
            if not isinstance(url, str) or not url.startswith("https://"):
                raise ConfigurationError("menu Web App URL must use https")
            button: TLObject = types.BotMenuButton(text=text, url=url)
        else:
            button = types.BotMenuButtonCommands() if commands else types.BotMenuButtonDefault()
        target = (
            types.InputUserEmpty()
            if user is None
            else as_user(await client(self).get_input_entity(user))
        )
        return bool(
            await client(self).invoke(
                functions.bots.SetBotMenuButtonRequest(user_id=target, button=button)
            )
        )

    async def get_chat_menu_button(self, user: PeerLike | None = None) -> TLObject:
        """Fetch the bot menu for a user; None selects Telegram's default user scope."""
        target = (
            types.InputUserEmpty()
            if user is None
            else as_user(await client(self).get_input_entity(user))
        )
        return cast(
            TLObject,
            await client(self).invoke(functions.bots.GetBotMenuButtonRequest(user_id=target)),
        )

    async def get_inline_bot_results(
        self, bot: PeerLike, query: str, *, peer: PeerLike = "me", offset: str = ""
    ) -> types.messages.BotResults:
        """Familiar direct entry point for the existing get_inline_results implementation."""
        return await client(self).get_inline_results(bot, query, peer=peer, offset=offset)

    async def send_inline_bot_result(
        self,
        peer: PeerLike,
        query_id: int,
        result_id: str,
        *,
        reply_to: int | None = None,
        silent: bool = False,
    ) -> types.Message:
        """Send one actual inline result using its query ID and opaque result ID."""
        from .operations import integer
        from .sending import output_peer, sent_message

        client(self)._send_options("", reply_to, silent, None, None)
        integer(query_id, "query_id", signed=True)
        validate_text(result_id, "result_id", empty=False)
        if len(result_id.encode("utf-8")) > 64:
            raise ConfigurationError("result_id exceeds 64 UTF-8 bytes")
        target = await client(self).get_input_entity(peer)
        own_id = (
            (await client(self).get_me()).id if isinstance(target, types.InputPeerSelf) else None
        )
        ident = secrets.randbits(63)
        result = await client(self).invoke(
            functions.messages.SendInlineBotResultRequest(
                peer=target,
                query_id=query_id,
                id=result_id,
                random_id=ident,
                silent=silent,
                reply_to=types.InputReplyToMessage(reply_to_msg_id=reply_to)
                if reply_to is not None
                else None,
            )
        )
        return sent_message(result, output_peer(target, own_id), "", ident)

    async def ban_chat_member(
        self, peer: PeerLike, user: PeerLike, *, until_date: int = 0
    ) -> UpdateResult:
        """Ban viewing in a supergroup/channel; rights/ownership remain server enforced."""
        count(until_date, name="until_date", allow_none=False)
        if until_date >= 2**31:
            raise ConfigurationError("until_date must fit signed 32-bit Unix seconds")
        return await invoke_updates(
            self,
            functions.channels.EditBannedRequest(
                channel=as_channel(await client(self).get_input_entity(peer)),
                participant=await client(self).get_input_entity(user),
                banned_rights=types.ChatBannedRights(until_date=until_date, view_messages=True),
            ),
        )

    async def unban_chat_member(self, peer: PeerLike, user: PeerLike) -> UpdateResult:
        """Clear ban/restriction flags; this does not add the user back to the chat."""
        return await invoke_updates(
            self,
            functions.channels.EditBannedRequest(
                channel=as_channel(await client(self).get_input_entity(peer)),
                participant=await client(self).get_input_entity(user),
                banned_rights=types.ChatBannedRights(until_date=0),
            ),
        )

    async def restrict_chat_member(
        self, peer: PeerLike, user: PeerLike, permissions: ChatPermissions, *, until_date: int = 0
    ) -> UpdateResult:
        """Translate allowed actions into banned rights for a supergroup/channel member."""
        if not isinstance(permissions, ChatPermissions):
            raise ConfigurationError("provide ChatPermissions")
        rights = permissions._banned(until_date)
        return await invoke_updates(
            self,
            functions.channels.EditBannedRequest(
                channel=as_channel(await client(self).get_input_entity(peer)),
                participant=await client(self).get_input_entity(user),
                banned_rights=rights,
            ),
        )

    async def promote_chat_member(
        self, peer: PeerLike, user: PeerLike, privileges: AdminPrivileges, *, rank: str = ""
    ) -> UpdateResult:
        """Set explicit admin grants; all-false privileges remove admin rights."""
        if not isinstance(privileges, AdminPrivileges):
            raise ConfigurationError("provide AdminPrivileges")
        validate_text(rank, "rank")
        return await invoke_updates(
            self,
            functions.channels.EditAdminRequest(
                channel=as_channel(await client(self).get_input_entity(peer)),
                user_id=as_user(await client(self).get_input_entity(user)),
                admin_rights=privileges._native(),
                rank=rank or None,
            ),
        )

    async def set_chat_permissions(
        self, peer: PeerLike, permissions: ChatPermissions
    ) -> UpdateResult:
        """Set default group member rights; does not grant admin powers."""
        if not isinstance(permissions, ChatPermissions):
            raise ConfigurationError("provide ChatPermissions")
        return await invoke_updates(
            self,
            functions.messages.EditChatDefaultBannedRightsRequest(
                peer=await client(self).get_input_entity(peer), banned_rights=permissions._banned()
            ),
        )

    async def set_chat_photo(
        self,
        peer: PeerLike,
        source: Source,
        *,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> UpdateResult:
        """Upload and set a basic-group/channel photo through its proper endpoint."""
        target = await client(self).get_input_entity(peer)
        if not isinstance(
            target, (types.InputPeerChat, types.InputPeerChannel, types.InputPeerChannelFromMessage)
        ):
            raise ConfigurationError("chat photo requires a group or channel")
        file = (
            source
            if isinstance(source, (types.InputFile, types.InputFileBig))
            else await client(self).upload_file(
                source, on_progress=on_progress, part_size=part_size, concurrency=concurrency
            )
        )
        return await self._chat_photo(target, types.InputChatUploadedPhoto(file=file))

    async def delete_chat_photo(self, peer: PeerLike) -> UpdateResult:
        """Remove the group/channel photo without inventing an empty uploaded file."""
        return await self._chat_photo(
            await client(self).get_input_entity(peer), types.InputChatPhotoEmpty()
        )

    async def _chat_photo(self, target: Any, photo: TLObject) -> UpdateResult:
        if isinstance(target, types.InputPeerChat):
            return await invoke_updates(
                self, functions.messages.EditChatPhotoRequest(chat_id=target.chat_id, photo=photo)
            )
        return await invoke_updates(
            self, functions.channels.EditPhotoRequest(channel=as_channel(target), photo=photo)
        )

    async def create_group(self, title: str, users: Sequence[PeerLike]) -> types.Chat:
        """Create a basic group; returned entity does not imply every invitee was admitted."""
        validate_text(title, "title", empty=False)
        if (
            isinstance(users, (str, bytes))
            or not isinstance(users, Sequence)
            or not 1 <= len(users) <= 200
        ):
            raise ConfigurationError("provide 1–200 user references for a basic group")
        inputs = [as_user(await client(self).get_input_entity(user)) for user in users]
        result = await client(self).invoke(
            functions.messages.CreateChatRequest(users=inputs, title=title)
        )
        chats = [c for c in getattr(result.updates, "chats", []) if isinstance(c, types.Chat)]
        if len(chats) != 1:
            raise SerializationError(
                "created group cannot be identified uniquely; remote creation may have succeeded"
            )
        return chats[0]

    async def create_supergroup(
        self, title: str, *, about: str = "", forum: bool = False
    ) -> types.Channel:
        """Create a megagroup, optionally a forum, with explicit title/description."""
        return await self._create_channel(title, about, megagroup=True, forum=forum)

    async def create_channel(self, title: str, *, about: str = "") -> types.Channel:
        """Create a broadcast channel; creation is not retried after ambiguous failure."""
        return await self._create_channel(title, about, megagroup=False, forum=False)

    async def _create_channel(
        self, title: str, about: str, *, megagroup: bool, forum: bool
    ) -> types.Channel:
        validate_text(title, "title", empty=False)
        validate_text(about, "about")
        require_booleans(forum=forum)
        result = await client(self).invoke(
            functions.channels.CreateChannelRequest(
                title=title, about=about, megagroup=megagroup, broadcast=not megagroup, forum=forum
            )
        )
        chats = [c for c in getattr(result, "chats", []) if isinstance(c, types.Channel)]
        if len(chats) != 1:
            raise SerializationError(
                "created channel cannot be identified uniquely; remote creation may have succeeded"
            )
        return chats[0]

    async def create_chat_invite_link(
        self,
        peer: PeerLike,
        *,
        title: str | None = None,
        expire_date: int | None = None,
        usage_limit: int | None = None,
        request_needed: bool = False,
    ) -> types.ChatInviteExported | types.ChatInvitePublicJoinRequests:
        """Create an invite using the supported existing export_invite_link operation."""
        return cast(
            types.ChatInviteExported | types.ChatInvitePublicJoinRequests,
            await client(self).export_invite_link(
                peer,
                title=title,
                expire_date=expire_date,
                usage_limit=usage_limit,
                request_needed=request_needed,
            ),
        )

    async def revoke_chat_invite_link(
        self, peer: PeerLike, link: str
    ) -> types.messages.ExportedChatInvite | types.messages.ExportedChatInviteReplaced:
        """Revoke the supplied real invite link; does not remove existing participants."""
        validate_text(link, "link", empty=False)
        if not link.startswith("https://t.me/"):
            raise ConfigurationError("provide a Telegram invite URL")
        return cast(
            types.messages.ExportedChatInvite | types.messages.ExportedChatInviteReplaced,
            await client(self).invoke(
                functions.messages.EditExportedChatInviteRequest(
                    peer=await client(self).get_input_entity(peer), link=link, revoked=True
                )
            ),
        )

    async def get_chat_invite_link(self, peer: PeerLike) -> str | None:
        """Read the exported link exposed by full-chat metadata; never creates one implicitly."""
        full = await client(self).get_chat_full(peer)
        invite = getattr(full.full_chat, "exported_invite", None)
        return invite.link if isinstance(invite, types.ChatInviteExported) else None

    async def edit_folder(self, peers: Sequence[PeerLike], folder_id: int) -> UpdateResult:
        """Move explicit peers to main (0) or archive (1); custom dialog filters are distinct."""
        if isinstance(folder_id, bool) or not isinstance(folder_id, int) or folder_id not in (0, 1):
            raise ConfigurationError("folder_id must be 0 or 1")
        if (
            isinstance(peers, (str, bytes))
            or not isinstance(peers, Sequence)
            or not 1 <= len(peers) <= 100
        ):
            raise ConfigurationError("provide 1–100 peer references")
        values = [
            types.InputFolderPeer(
                peer=await client(self).get_input_entity(peer), folder_id=folder_id
            )
            for peer in peers
        ]
        return await invoke_updates(
            self,
            functions.folders.EditPeerFoldersRequest(folder_peers=cast("list[TLObject]", values)),
        )

    async def get_drafts(self) -> list[Draft]:
        """Fetch the account's nonempty cloud drafts in one server snapshot."""
        result = await client(self).invoke(functions.messages.GetAllDraftsRequest())
        if isinstance(result, types.UpdateShort):
            updates = [result.update]
        elif isinstance(result, (types.Updates, types.UpdatesCombined)):
            updates = result.updates
        else:
            raise SerializationError("draft response did not contain updates")
        return [
            Draft(update.peer, update.draft)
            for update in updates
            if isinstance(update, types.UpdateDraftMessage)
            and isinstance(update.draft, types.DraftMessage)
        ]

    async def iter_drafts(self) -> AsyncIterator[Draft]:
        """Lazy initial request, then iterate one complete server snapshot (not paginated)."""
        for draft in await self.get_drafts():
            yield draft

    async def get_profile_photos(
        self, peer: PeerLike = "me", *, limit: int = 100
    ) -> list[types.Photo]:
        """Fetch visible user profile photos in bounded 100-photo pages."""
        count(limit, allow_none=False)
        if limit > 10000:
            raise ConfigurationError("photo limit must not exceed 10000")
        if not limit:
            return []
        target = as_user(await client(self).get_input_entity(peer))
        photos: list[types.Photo] = []
        offset = 0
        while len(photos) < limit:
            result = await client(self).invoke(
                functions.photos.GetUserPhotosRequest(
                    user_id=target, offset=offset, max_id=0, limit=min(100, limit - len(photos))
                )
            )
            rows = [photo for photo in result.photos if isinstance(photo, types.Photo)]
            if not rows:
                break
            photos.extend(rows[: limit - len(photos)])
            offset += len(result.photos)
            if (
                not result.photos
                or not isinstance(result, types.photos.PhotosSlice)
                or offset >= result.count
            ):
                break
        return photos

    async def set_profile_photo(
        self,
        source: Source,
        *,
        on_progress: Progress | None = None,
        part_size: int = CHUNK,
        concurrency: int = 1,
    ) -> types.photos.Photo:
        """Upload and set a still profile photo, returning actual photo/user metadata."""
        file = (
            source
            if isinstance(source, (types.InputFile, types.InputFileBig))
            else await client(self).upload_file(
                source, on_progress=on_progress, part_size=part_size, concurrency=concurrency
            )
        )
        return cast(
            types.photos.Photo,
            await client(self).invoke(functions.photos.UploadProfilePhotoRequest(file=file)),
        )

    async def delete_profile_photos(
        self, photos: Sequence[types.Photo | types.InputPhoto]
    ) -> list[int]:
        """Delete explicit server photo references, preserving access hashes and file references."""
        if (
            isinstance(photos, (str, bytes))
            or not isinstance(photos, Sequence)
            or not 1 <= len(photos) <= 100
        ):
            raise ConfigurationError("provide 1–100 native photo references")
        refs = []
        for photo in photos:
            if isinstance(photo, types.Photo):
                refs.append(
                    types.InputPhoto(
                        id=photo.id,
                        access_hash=photo.access_hash,
                        file_reference=photo.file_reference,
                    )
                )
            elif isinstance(photo, types.InputPhoto):
                refs.append(photo)
            else:
                raise ConfigurationError("photos require native Photo/InputPhoto metadata")
        return cast(
            list[int],
            await client(self).invoke(
                functions.photos.DeletePhotosRequest(id=cast("list[TLObject]", refs))
            ),
        )

    async def download_profile_photo(
        self,
        peer: PeerLike,
        destination: str | Path | BinaryIO,
        *,
        on_progress: Progress | None = None,
    ) -> Path | None:
        """Download a visible profile photo through the existing ranged file pipeline."""
        target = await client(self).get_input_entity(peer)
        if isinstance(
            target, (types.InputPeerUser, types.InputPeerUserFromMessage, types.InputPeerSelf)
        ):
            photos = await self.get_profile_photos(target, limit=1)
            photo = photos[0] if photos else None
        else:
            result = await client(self).get_chat_full(target)
            photo = getattr(result.full_chat, "chat_photo", None)
        if not isinstance(photo, types.Photo):
            return None
        from .files import photo_location

        location, size = photo_location(photo)
        return await client(self).download_file(
            location, destination, size=size, on_progress=on_progress
        )

    async def get_admin_log(
        self, peer: PeerLike, *, query: str = "", limit: int = 100
    ) -> list[types.ChannelAdminLogEvent]:
        """Collect a finite channel/supergroup admin log; server admin eligibility still applies."""
        count(limit, allow_none=False)
        return [event async for event in self.iter_admin_log(peer, query=query, limit=limit)]

    async def iter_admin_log(
        self,
        peer: PeerLike,
        *,
        query: str = "",
        limit: int | None = None,
        max_id: int = 0,
        page_size: int = 100,
    ) -> AsyncIterator[types.ChannelAdminLogEvent]:
        """Traverse admin-log IDs backwards lazily with bounded overlap detection."""
        from .errors import PaginationError
        from .operations import integer
        from .pagination import RecentIDs
        from .pagination import page_size as validate_page_size

        count(limit)
        integer(max_id, "max_id")
        validate_page_size(page_size)
        validate_text(query, "query")
        if limit == 0:
            return
        target = as_channel(await client(self).get_input_entity(peer))
        seen = RecentIDs(page_size * 2)
        remaining = limit
        cursor = max_id
        while remaining is None or remaining > 0:
            result = await client(self).invoke(
                functions.channels.GetAdminLogRequest(
                    channel=target,
                    q=query,
                    max_id=cursor,
                    min_id=0,
                    limit=page_size if remaining is None else min(page_size, remaining),
                )
            )
            if not result.events:
                return
            ids = [event.id for event in result.events]
            if any(
                isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in ids
            ):
                raise PaginationError("admin log returned invalid IDs")
            next_id = min(ids)
            if cursor and next_id >= cursor:
                raise PaginationError("admin log cursor did not advance")
            for event in result.events:
                if cursor and event.id >= cursor:
                    continue
                if not seen.add(event.id):
                    continue
                yield event
                if remaining is not None:
                    remaining -= 1
                    if remaining == 0:
                        return
            cursor = next_id

    async def approve_chat_join_request(
        self, peer: PeerLike, user: PeerLike, *, approve: bool = True
    ) -> UpdateResult:
        """Approve or dismiss one server join request; no bulk or implicit approval."""
        require_booleans(approve=approve)
        return await invoke_updates(
            self,
            functions.messages.HideChatJoinRequestRequest(
                peer=await client(self).get_input_entity(peer),
                user_id=as_user(await client(self).get_input_entity(user)),
                approved=approve,
            ),
        )
