"""Actual native request encoding/result processing with controlled server fixtures."""

import io

import pytest

from gramflux import AdminPrivileges, AlbumItem, ChatPermissions
from gramflux.errors import ConfigurationError, FloodWait, SerializationError
from gramflux.raw import types as t
from gramflux.tl import Codec
from tests.integration.test_core_api import make, message, user
from tests.native_fixtures import fixture_field

USER = t.InputPeerUser(user_id=12, access_hash=1200)
CHANNEL = t.InputPeerChannel(channel_id=8, access_hash=800)
GROUP = t.InputPeerChat(chat_id=7)
FILE = t.InputFile(id=1, parts=1, name="media.bin", md5_checksum="")


def native(cls, **values):
    for p in cls.definition.params:
        if p.type != "#" and "?" not in p.type and p.name not in values:
            values[p.name] = fixture_field(p.type)
    return cls(**values)


def photo():
    return native(
        t.Photo,
        id=5,
        access_hash=50,
        file_reference=b"synthetic-reference",
        sizes=[t.PhotoSize(type="c", w=4, h=4, size=7)],
    )


def sent(request, ident=77):
    if request.definition.name == "messages.sendMultiMedia":
        updates = []
        for i, item in enumerate(request.multi_media):
            updates.extend(
                [
                    t.UpdateMessageID(id=ident + i, random_id=item.random_id),
                    t.UpdateNewMessage(
                        message=message(ident + i, text=item.message), pts=i + 1, pts_count=1
                    ),
                ]
            )
        return t.Updates(updates=updates, users=[], chats=[], date=0, seq=0)
    return t.UpdateShortSentMessage(id=ident, pts=1, pts_count=1, date=0, out=True)


MEDIA_CASES = [
    (
        "send_video",
        {"duration": 1.5, "width": 320, "height": 240, "supports_streaming": True},
        t.DocumentAttributeVideo,
        "video/mp4",
    ),
    ("send_video_note", {"duration": 1.5, "length": 240}, t.DocumentAttributeVideo, "video/mp4"),
    (
        "send_audio",
        {"duration": 5, "title": "Track", "performer": "Artist"},
        t.DocumentAttributeAudio,
        "audio/mpeg",
    ),
    ("send_voice", {"duration": 5, "waveform": b"\x01"}, t.DocumentAttributeAudio, "audio/ogg"),
    ("send_animation", {}, t.DocumentAttributeAnimated, "image/gif"),
    ("send_sticker", {"emoji": "x"}, t.DocumentAttributeSticker, "image/webp"),
]


@pytest.mark.parametrize("name,options,attribute,mime", MEDIA_CASES)
async def test_specialized_media_build_real_attributes_and_return_messages(
    name, options, attribute, mime
):
    requests = []
    markup = t.ReplyInlineMarkup(rows=[])
    entity = t.MessageEntityBold(offset=0, length=3)

    async def respond(request):
        Codec().encode(request)
        requests.append(request)
        assert request.definition.name == "messages.sendMedia"
        assert request.media.file is FILE
        assert request.media.mime_type == mime
        attr = next(a for a in request.media.attributes if isinstance(a, attribute))
        if name == "send_video_note":
            assert attr.round_message and attr.w == attr.h == 240
        if name == "send_voice":
            assert attr.voice and attr.waveform == b"\x01"
        if name == "send_video":
            assert attr.supports_streaming and attr.duration == 1.5
        assert request.peer is USER and request.silent
        assert request.reply_to.reply_to_msg_id == 9
        assert request.reply_markup is markup and request.entities == [entity]
        return sent(request)

    c, _ = make(respond)
    async with c:
        result = await getattr(c, name)(
            USER,
            FILE,
            caption="cap",
            reply_to=9,
            silent=True,
            entities=[entity],
            reply_markup=markup,
            **options,
        )
        assert isinstance(result, t.Message) and result.id == 77 and result.message == "cap"
    assert len(requests) == 1


async def test_video_stream_uses_existing_upload_pipeline_and_caller_ownership():
    parts = []
    progress = []
    source = io.BytesIO(b"x" * 2500)

    async def respond(request):
        Codec().encode(request)
        if request.definition.name == "upload.saveFilePart":
            parts.append(request.bytes)
            return True
        return sent(request)

    c, _ = make(respond)
    async with c:
        await c.send_video(
            USER,
            source,
            duration=1,
            width=320,
            height=240,
            part_size=1024,
            concurrency=2,
            on_progress=lambda n, total: progress.append((n, total)),
        )
    assert b"".join(parts) == b"x" * 2500 and not source.closed
    assert progress[0] == (0, 2500) and progress[-1] == (2500, 2500)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.send_video(USER, FILE, duration=-1, width=320, height=240),
        lambda c: c.send_video(USER, FILE, duration=1, width=0, height=240),
        lambda c: c.send_video(USER, FILE, duration=float("nan"), width=320, height=240),
        lambda c: c.send_audio(USER, FILE, duration=True),
        lambda c: c.send_voice(USER, FILE, duration=1, waveform="bad"),
        lambda c: c.send_animation(USER, FILE, mime_type="text/plain"),
        lambda c: c.send_sticker(USER, FILE, mime_type="image/jpeg"),
        lambda c: c.send_video(USER, FILE, duration=1, width=1, height=1, reply_to=-1),
        lambda c: c.send_video(USER, FILE, duration=1, width=1, height=1, entities=["bad"]),
    ],
)
async def test_invalid_media_metadata_rejected_before_any_rpc(call):
    async def respond(request):
        pytest.fail("invalid media must not send a request")

    c, backend = make(respond)
    async with c:
        with pytest.raises(ConfigurationError):
            await call(c)
    assert backend.calls == []


async def test_album_uploads_resources_then_correlates_out_of_order_messages():
    stages = []

    async def respond(request):
        Codec().encode(request)
        stages.append(request.definition.name)
        if request.definition.name == "messages.uploadMedia":
            return t.MessageMediaPhoto(photo=photo())
        assert all(isinstance(i.media, t.InputMediaPhoto) for i in request.multi_media)
        result = sent(request)
        result.updates.reverse()
        return result

    c, _ = make(respond)
    async with c:
        result = await c.send_media_group(
            USER, [AlbumItem(FILE, "first"), AlbumItem(FILE, "second")], silent=True
        )
    assert [m.id for m in result] == [77, 78]
    assert [m.message for m in result] == ["first", "second"]
    assert stages == ["messages.uploadMedia", "messages.uploadMedia", "messages.sendMultiMedia"]


@pytest.mark.parametrize(
    "items", [[], [AlbumItem(FILE)], [AlbumItem(FILE), AlbumItem(FILE, as_document=True)]]
)
async def test_album_validation_happens_before_upload(items):
    async def respond(request):
        pytest.fail("no request expected")

    c, _ = make(respond)
    async with c:
        with pytest.raises(ConfigurationError):
            await c.send_media_group(USER, items)


async def test_album_ambiguous_result_is_not_retried_or_fabricated():
    count = 0

    async def respond(request):
        nonlocal count
        if request.definition.name == "messages.uploadMedia":
            return t.MessageMediaPhoto(photo=photo())
        count += 1
        return t.Updates(updates=[], users=[], chats=[], date=0, seq=0)

    c, _ = make(respond)
    async with c:
        with pytest.raises(SerializationError):
            await c.send_media_group(USER, [AlbumItem(FILE), AlbumItem(FILE)])
    assert count == 1


SIMPLE_CASES = [
    ("set_username", ("valid_name",), {}, "account.updateUsername", {"username": "valid_name"}),
    ("delete_bot_commands", (), {}, "bots.resetBotCommands", {"lang_code": ""}),
    (
        "set_chat_menu_button",
        (),
        {"text": "Open", "url": "https://example.com"},
        "bots.setBotMenuButton",
        {},
    ),
    ("set_chat_menu_button", (), {"commands": True}, "bots.setBotMenuButton", {}),
    ("get_chat_menu_button", (), {}, "bots.getBotMenuButton", {}),
    ("ban_chat_member", (CHANNEL, USER), {}, "channels.editBanned", {}),
    ("unban_chat_member", (CHANNEL, USER), {}, "channels.editBanned", {}),
    (
        "restrict_chat_member",
        (CHANNEL, USER, ChatPermissions(send_messages=False)),
        {},
        "channels.editBanned",
        {},
    ),
    (
        "promote_chat_member",
        (CHANNEL, USER, AdminPrivileges(delete_messages=True)),
        {"rank": "Moderator"},
        "channels.editAdmin",
        {},
    ),
    (
        "set_chat_permissions",
        (GROUP, ChatPermissions(send_media=False)),
        {},
        "messages.editChatDefaultBannedRights",
        {},
    ),
    ("set_chat_photo", (GROUP, FILE), {}, "messages.editChatPhoto", {}),
    ("set_chat_photo", (CHANNEL, FILE), {}, "channels.editPhoto", {}),
    ("delete_chat_photo", (GROUP,), {}, "messages.editChatPhoto", {}),
    ("delete_chat_photo", (CHANNEL,), {}, "channels.editPhoto", {}),
    ("set_profile_photo", (FILE,), {}, "photos.uploadProfilePhoto", {}),
    ("delete_profile_photos", ([photo()],), {}, "photos.deletePhotos", {}),
    (
        "create_chat_invite_link",
        (CHANNEL,),
        {"title": "Invite"},
        "messages.exportChatInvite",
        {"title": "Invite"},
    ),
    (
        "revoke_chat_invite_link",
        (CHANNEL, "https://t.me/+synthetic"),
        {},
        "messages.editExportedChatInvite",
        {"revoked": True},
    ),
    ("edit_folder", ([USER, GROUP], 1), {}, "folders.editPeerFolders", {}),
    (
        "approve_chat_join_request",
        (GROUP, USER),
        {},
        "messages.hideChatJoinRequest",
        {"approved": True},
    ),
    (
        "edit_message_caption",
        (USER, 9, "new caption"),
        {},
        "messages.editMessage",
        {"message": "new caption", "entities": []},
    ),
    (
        "edit_message_reply_markup",
        (USER, 9, t.ReplyInlineMarkup(rows=[])),
        {},
        "messages.editMessage",
        {},
    ),
    ("edit_message_media", (USER, 9, FILE), {}, "messages.editMessage", {}),
    ("send_inline_bot_result", (USER, 123, "result"), {}, "messages.sendInlineBotResult", {}),
    ("send_venue", (USER, 10.0, 20.0, "Venue", "Address"), {}, "messages.sendMedia", {}),
    ("send_game", (USER, USER, "game_name"), {}, "messages.sendMedia", {}),
    ("send_poll", (USER, "Question", ["Yes", "No"]), {}, "messages.sendMedia", {}),
    (
        "send_poll",
        (USER, "Question", ["Yes", "No"]),
        {"correct_option": 1, "solution": "Explanation"},
        "messages.sendMedia",
        {},
    ),
    ("send_cached_media", (USER, photo()), {}, "messages.sendMedia", {}),
]


@pytest.mark.parametrize("name,args,kwargs,method,expected", SIMPLE_CASES)
async def test_management_and_message_operations_build_correct_native_requests(
    name, args, kwargs, method, expected
):
    requests = []

    async def respond(request):
        Codec().encode(request)
        requests.append(request)
        assert request.definition.name == method
        for key, value in expected.items():
            assert getattr(request, key) == value
        if method in {"messages.sendMedia", "messages.sendInlineBotResult"}:
            if name == "send_poll":
                assert isinstance(request.media.poll.question, t.TextWithEntities)
                assert [a.text.text for a in request.media.poll.answers] == ["Yes", "No"]
                assert request.media.correct_answers == ([1] if kwargs else None)
                assert request.media.solution_entities == ([] if kwargs else None)
            return sent(request)
        if method == "channels.editBanned":
            if name == "ban_chat_member":
                assert request.banned_rights.view_messages
            elif name == "unban_chat_member":
                assert not request.banned_rights.view_messages
            else:
                assert request.banned_rights.send_plain and not request.banned_rights.view_messages
        if method == "channels.editAdmin":
            assert request.admin_rights.delete_messages
        if method == "messages.editChatDefaultBannedRights":
            assert request.banned_rights.send_media
        if method == "folders.editPeerFolders":
            assert all(p.folder_id == 1 for p in request.folder_peers)
        return fixture_field(request.definition.result)

    c, _ = make(respond)
    async with c:
        result = await getattr(c, name)(*args, **kwargs)
        if method.startswith("messages.send"):
            assert isinstance(result, t.Message)
    assert len(requests) == 1


@pytest.mark.parametrize("name,args,kwargs,method,expected", SIMPLE_CASES)
async def test_rpc_failures_are_preserved_without_automatic_retry(
    name, args, kwargs, method, expected
):
    error = FloodWait(420, 3)
    calls = []

    async def respond(request):
        calls.append(request)
        raise error

    c, _ = make(respond)
    async with c:
        with pytest.raises(FloodWait) as actual:
            await getattr(c, name)(*args, **kwargs)
    assert actual.value is error and len(calls) == 1


async def test_creation_returns_server_entities_not_synthetic_success():
    async def respond(request):
        Codec().encode(request)
        if request.definition.name == "messages.createChat":
            entity = native(t.Chat, id=7, title=request.title)
            return t.messages.InvitedUsers(
                updates=t.Updates(updates=[], users=[], chats=[entity], date=0, seq=0),
                missing_invitees=[],
            )
        entity = native(
            t.Channel,
            id=8,
            title=request.title,
            megagroup=request.megagroup,
            broadcast=request.broadcast,
        )
        return t.Updates(updates=[], users=[], chats=[entity], date=0, seq=0)

    c, _ = make(respond)
    async with c:
        assert (await c.create_group("Group", [USER])).id == 7
        assert (await c.create_supergroup("Super", forum=True)).megagroup
        assert (await c.create_channel("Channel")).broadcast


async def test_counts_users_members_and_single_message_results():
    async def respond(request):
        Codec().encode(request)
        name = request.definition.name
        if name == "users.getUsers":
            return [user()]
        if name == "messages.getMessages":
            return t.messages.Messages(messages=[message(9)], chats=[], users=[], topics=[])
        if name == "channels.getParticipant":
            return t.channels.ChannelParticipant(
                participant=t.ChannelParticipant(user_id=12, date=0), users=[user()], chats=[]
            )
        if name in {"messages.getHistory", "messages.search"}:
            return t.messages.MessagesSlice(
                count=45, messages=[message(9)], chats=[], users=[], topics=[]
            )
        if name == "channels.getFullChannel":
            return t.messages.ChatFull(
                full_chat=native(t.ChannelFull, id=8, participants_count=23), chats=[], users=[]
            )
        pytest.fail(name)

    c, _ = make(respond)
    async with c:
        assert (await c.get_message(USER, 9)).id == 9
        assert len(await c.get_users([USER])) == 1
        assert (await c.get_chat_member(CHANNEL, USER)).id == 12
        assert await c.get_chat_members_count(CHANNEL) == 23
        assert await c.get_chat_history_count(USER) == 45
        assert await c.search_messages_count(USER, "query", sender=USER) == 45


async def test_copy_text_uses_existing_send_and_rejects_protected_source():
    protected = False

    async def respond(request):
        source = message(9, text="copied")
        source.noforwards = protected
        return t.messages.Messages(messages=[source], chats=[], users=[], topics=[])

    c, backend = make(respond)
    async with c:
        await c.copy_message(USER, USER, 9, silent=True)
        assert backend.sent[0][1] == "copied"
        protected = True
        with pytest.raises(ConfigurationError):
            await c.copy_message(USER, USER, 9)
        assert len(backend.sent) == 1


async def test_drafts_admin_log_and_photos_keep_lazy_contracts(tmp_path):
    calls = []

    async def respond(request):
        Codec().encode(request)
        calls.append(request)
        if request.definition.name == "messages.getAllDrafts":
            update = t.UpdateDraftMessage(
                peer=t.PeerUser(user_id=12), draft=t.DraftMessage(message="private draft", date=0)
            )
            return t.Updates(updates=[update], users=[], chats=[], date=0, seq=0)
        if request.definition.name == "channels.getAdminLog":
            return t.channels.AdminLogResults(
                events=[
                    t.ChannelAdminLogEvent(
                        id=9,
                        date=0,
                        user_id=12,
                        action=t.ChannelAdminLogEventActionChangeTitle(
                            prev_value="a", new_value="b"
                        ),
                    )
                ],
                users=[],
                chats=[],
            )
        if request.definition.name == "photos.getUserPhotos":
            return t.photos.Photos(photos=[photo()], users=[])
        assert request.definition.name == "upload.getFile"
        return t.upload.File(type=t.storage.FileJpeg(), mtime=0, bytes=b"1234567")

    c, _ = make(respond)
    async with c:
        drafts = c.iter_drafts()
        assert not calls
        assert (await anext(drafts)).draft.message == "private draft"
        stream = c.iter_admin_log(CHANNEL, limit=1)
        before = len(calls)
        assert (await anext(stream)).id == 9 and len(calls) == before + 1
        assert (await c.get_admin_log(CHANNEL, limit=1))[0].id == 9
        assert len(await c.get_profile_photos(USER, limit=1)) == 1
        path = tmp_path / "photo.jpg"
        assert await c.download_profile_photo(USER, path) == path
        assert path.read_bytes() == b"1234567"


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.set_username("bad name"),
        lambda c: c.set_chat_menu_button(text="only"),
        lambda c: c.set_chat_menu_button(text="a", url="http://example.com"),
        lambda c: c.set_chat_menu_button(text="a", url="https://example.com", commands=True),
        lambda c: c.ban_chat_member(CHANNEL, USER, until_date=-1),
        lambda c: c.promote_chat_member(CHANNEL, USER, "bad"),
        lambda c: c.set_chat_permissions(GROUP, "bad"),
        lambda c: c.create_group("", [USER]),
        lambda c: c.create_group("Group", []),
        lambda c: c.edit_folder([USER], True),
        lambda c: c.edit_folder("username", 1),
        lambda c: c.delete_profile_photos([]),
        lambda c: c.send_poll(USER, "Q", ["one"]),
        lambda c: c.send_poll(USER, "Q", ["one", "two"], correct_option=3),
        lambda c: c.send_poll(USER, "Q", ["one", "two"], correct_option=0, multiple_choice=True),
        lambda c: c.send_poll(USER, "Q", ["one", "two"], solution="bad"),
    ],
)
async def test_invalid_management_inputs_fail_without_rpc(call):
    async def respond(request):
        pytest.fail("invalid input must not call the server")

    c, _ = make(respond)
    async with c:
        with pytest.raises(ConfigurationError):
            await call(c)


@pytest.mark.parametrize("document", [False, True])
async def test_generic_media_builds_rich_actual_request(document):
    async def respond(request):
        assert request.definition.name == "messages.sendMedia"
        assert isinstance(
            request.media, t.InputMediaUploadedDocument if document else t.InputMediaUploadedPhoto
        )
        if document:
            assert request.media.mime_type == "application/test"
        assert request.message == "caption"
        assert request.silent is True
        assert request.reply_to.reply_to_msg_id == 6
        assert request.entities[0].length == 7
        return sent(request)

    c, _ = make(respond)
    async with c:
        result = await c.send_media(
            USER,
            FILE,
            as_document=document,
            mime_type="application/test" if document else None,
            caption="caption",
            silent=True,
            reply_to=6,
            entities=[t.MessageEntityBold(offset=0, length=7)],
        )
        assert result.id == 77


async def test_generic_media_rejects_mime_before_upload():
    async def respond(request):
        pytest.fail("invalid MIME must not upload or send")

    c, _ = make(respond)
    async with c:
        with pytest.raises(ConfigurationError):
            await c.send_media(USER, io.BytesIO(b"payload"), mime_type="image/jpeg")


async def test_public_additions_have_explicit_signatures_and_all_old_contracts_remain():
    import inspect
    import json
    from pathlib import Path

    from gramflux import Client

    inventory = json.loads(
        (Path(__file__).parents[2] / "research/high-level-inventory.json").read_text()
    )
    assert len(inventory["existing_methods"]) == 82
    assert len(inventory["added_methods"]) == 57
    for name in inventory["existing_methods"] + list(inventory["added_methods"]):
        fn = getattr(Client, name)
        sig = inspect.signature(fn)
        assert all(p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD) for p in sig.parameters.values())
        assert sig.return_annotation is not inspect.Signature.empty
    assert isinstance(Client.is_connected, property)


async def test_aliases_delegate_preserving_defaults_and_return_identity():
    from unittest.mock import AsyncMock

    async def respond(request):
        pytest.fail("delegating wrappers should not create additional requests")

    c, _ = make(respond)
    members = [object()]
    c.get_members = AsyncMock(return_value=members)
    c.resolve_peer = AsyncMock(return_value=USER)
    assert await c.get_participants(USER) is members
    c.get_members.assert_awaited_once_with(USER, limit=100, query="")
    assert await c.get_input_entity(USER, refresh=True) is USER
    c.resolve_peer.assert_awaited_once_with(USER, refresh=True)


async def test_identity_and_absent_metadata_never_invent_results(tmp_path):
    async def respond(request):
        Codec().encode(request)
        if request.definition.name == "photos.getUserPhotos":
            return t.photos.Photos(photos=[], users=[])
        if request.definition.name == "channels.getFullChannel":
            return t.messages.ChatFull(full_chat=native(t.ChannelFull, id=8), chats=[], users=[])
        pytest.fail(request.definition.name)

    c, _ = make(respond)
    async with c:
        assert c.is_connected
        assert await c.is_bot() is False
        assert await c.get_chat_invite_link(CHANNEL) is None
        destination = tmp_path / "absent.jpg"
        assert await c.download_profile_photo(USER, destination) is None
        assert not destination.exists()
        assert await c.get_users([]) == []
    assert not c.is_connected


async def test_admin_log_nonadvancing_cursor_is_an_error():
    from gramflux.errors import PaginationError

    calls = []

    async def respond(request):
        calls.append(request)
        return t.channels.AdminLogResults(
            events=[
                t.ChannelAdminLogEvent(
                    id=9,
                    date=0,
                    user_id=12,
                    action=t.ChannelAdminLogEventActionChangeTitle(prev_value="a", new_value="b"),
                )
            ],
            chats=[],
            users=[],
        )

    c, _ = make(respond)
    async with c:
        stream = c.iter_admin_log(CHANNEL)
        assert not calls
        assert (await anext(stream)).id == 9
        with pytest.raises(PaginationError):
            await anext(stream)
        assert [request.max_id for request in calls] == [0, 9]


@pytest.mark.parametrize("script", ["high_level", "high_level_legacy"])
async def test_complete_example_runs_with_controlled_native_boundaries(
    script, tmp_path, monkeypatch
):
    import importlib.util
    from pathlib import Path

    from tests.integration.test_core_api import history_slice

    async def respond(request):
        Codec().encode(request)
        if request.definition.name == "upload.saveFilePart":
            return True
        if request.definition.name == "messages.getMessages":
            return t.messages.Messages(
                messages=[message(100, peer=1)], chats=[], users=[], topics=[]
            )
        if request.definition.name == "messages.getHistory":
            return history_slice()
        if request.definition.name == "messages.editMessage":
            return t.Updates(updates=[], chats=[], users=[], date=0, seq=0)
        pytest.fail(request.definition.name)

    path = Path(__file__).parents[2] / "examples" / (script + ".py")
    spec = importlib.util.spec_from_file_location(script, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    c, backend = make(respond)
    monkeypatch.setattr(module, "Client", lambda *args, **kwargs: c)
    monkeypatch.setenv("GRAMFLUX_API_ID", "1234")
    monkeypatch.setenv("GRAMFLUX_API_HASH", "a" * 32)
    source = tmp_path / "file.pdf"
    source.write_bytes(b"synthetic example document")
    await module.main("example", source)
    assert backend.sent[0][1] == "Hello from GramFlux"
    assert backend.media[0][2]["force_document"] is True
    assert not c.connected
