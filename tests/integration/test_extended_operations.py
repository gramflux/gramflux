"""Real method serialization and domain routing with synthetic server responses."""

import pytest

from gramflux import buttons
from gramflux.errors import ConfigurationError
from gramflux.raw import types as t
from gramflux.tl import Codec
from tests.integration.test_core_api import make
from tests.native_fixtures import fixture_field

USER = t.InputPeerUser(user_id=12, access_hash=1200)
GROUP = t.InputPeerChat(chat_id=7)
CHANNEL = t.InputPeerChannel(channel_id=8, access_hash=800)

CASES = [
    (
        "answer_callback_query",
        (99,),
        {"text": "ok", "alert": True},
        "messages.setBotCallbackAnswer",
        {"query_id": 99, "message": "ok", "alert": True},
    ),
    (
        "answer_inline_query",
        (99, [buttons.article("one", "Title", "body")]),
        {"private": True},
        "messages.setInlineBotResults",
        {"query_id": 99, "private": True},
    ),
    (
        "get_inline_results",
        (USER, "query"),
        {"peer": GROUP, "offset": "next"},
        "messages.getInlineBotResults",
        {"query": "query", "offset": "next"},
    ),
    (
        "get_callback_answer",
        (USER, 9),
        {"data": b"click"},
        "messages.getBotCallbackAnswer",
        {"msg_id": 9, "data": b"click"},
    ),
    (
        "set_bot_commands",
        ([t.BotCommand(command="help", description="Help")],),
        {},
        "bots.setBotCommands",
        {"lang_code": ""},
    ),
    ("get_bot_commands", (), {}, "bots.getBotCommands", {"lang_code": ""}),
    ("set_typing", (GROUP,), {}, "messages.setTyping", {}),
    ("send_reaction", (USER, 9, "👍"), {}, "messages.sendReaction", {"msg_id": 9}),
    ("send_reaction", (USER, 9, None), {}, "messages.sendReaction", {"reaction": []}),
    ("save_draft", (GROUP, "draft"), {"reply_to": 9}, "messages.saveDraft", {"message": "draft"}),
    (
        "export_invite_link",
        (CHANNEL,),
        {"title": "Test", "usage_limit": 3},
        "messages.exportChatInvite",
        {"usage_limit": 3, "title": "Test"},
    ),
    ("check_invite", ("valid_hash",), {}, "messages.checkChatInvite", {"hash": "valid_hash"}),
    (
        "set_chat_title",
        (GROUP, "Group"),
        {},
        "messages.editChatTitle",
        {"chat_id": 7, "title": "Group"},
    ),
    ("set_chat_title", (CHANNEL, "Channel"), {}, "channels.editTitle", {"title": "Channel"}),
    ("set_chat_description", (CHANNEL, "About"), {}, "messages.editChatAbout", {"about": "About"}),
    (
        "add_contact",
        (USER, "First"),
        {"share_phone": True},
        "contacts.addContact",
        {"first_name": "First", "add_phone_privacy_exception": True},
    ),
    ("delete_contacts", ([USER],), {}, "contacts.deleteContacts", {}),
    ("update_profile", (), {"about": "About"}, "account.updateProfile", {"about": "About"}),
    ("get_active_sessions", (), {}, "account.getAuthorizations", {}),
    ("terminate_session", (-123,), {}, "account.resetAuthorization", {"hash": -123}),
    (
        "start_bot",
        (USER,),
        {"peer": GROUP, "start_param": "start"},
        "messages.startBot",
        {"start_param": "start"},
    ),
    (
        "edit_inline_message",
        (t.InputBotInlineMessageID(dc_id=2, id=3, access_hash=4), "edited"),
        {},
        "messages.editInlineBotMessage",
        {"message": "edited"},
    ),
]


@pytest.mark.parametrize("name,args,kwargs,method,fields", CASES)
async def test_operations_serialize_correct_requests_and_route_peers(
    name, args, kwargs, method, fields
):
    codec = Codec()

    async def respond(request):
        assert request.definition.name == method
        codec.encode(request)
        for key, value in fields.items():
            assert getattr(request, key) == value
        if hasattr(request, "peer"):
            assert request.peer in (USER, GROUP, CHANNEL)
        if method == "contacts.deleteContacts":
            assert request.id[0].user_id == 12
        if method == "channels.editTitle":
            assert request.channel.channel_id == 8
        if method == "messages.startBot":
            assert 0 <= request.random_id < 2**63
        if request.definition.result == "User":
            return t.User(id=12)
        response = fixture_field(request.definition.result)
        return codec.decode(
            codec.encode(response, request.definition.result), request.definition.result
        )

    client, backend = make(respond)
    async with client:
        await getattr(client, name)(*args, **kwargs)
    assert len(backend.calls) == 1


@pytest.mark.parametrize(
    "name,args,kwargs",
    [
        ("answer_callback_query", (True,), {}),
        ("answer_callback_query", (1,), {"alert": 1}),
        ("answer_inline_query", (1, []), {"private": "false"}),
        ("add_contact", (USER, "First"), {"share_phone": "false"}),
        ("answer_callback_query", (1,), {"cache_time": -1}),
        ("answer_inline_query", (1, [buttons.article("same", "T", "x")] * 2), {}),
        ("update_profile", (), {}),
        ("set_chat_title", (GROUP, ""), {}),
        ("export_invite_link", (GROUP,), {"request_needed": True, "usage_limit": 2}),
        ("delete_contacts", ("username",), {}),
        ("send_location", (USER, 91, 0), {}),
        ("send_location", (USER, 0, float("nan")), {}),
        ("get_callback_answer", (USER, 0), {}),
        ("set_bot_commands", ([t.BotCommand(command="help", description="h")] * 2,), {}),
    ],
)
async def test_invalid_operations_never_issue_rpc(name, args, kwargs):
    async def respond(request):
        pytest.fail("invalid operation reached RPC")

    client, backend = make(respond)
    async with client:
        with pytest.raises(ConfigurationError):
            await getattr(client, name)(*args, **kwargs)
    assert not backend.calls and not backend.media


@pytest.mark.parametrize(
    "name,args,kind",
    [
        ("send_contact", (USER, "+100000", "First"), "inputMediaContact"),
        ("send_location", (USER, 12.5, -13.5), "inputMediaGeoPoint"),
        ("send_dice", (USER,), "inputMediaDice"),
    ],
)
async def test_media_helpers_use_existing_native_media_pipeline(name, args, kind):
    async def respond(request):
        pytest.fail("helper bypassed the media boundary")

    client, backend = make(respond)
    async with client:
        result = await getattr(client, name)(*args)
    assert result.id == 101
    media = backend.media[0][1]
    assert media.definition.name == kind
    Codec().encode(media)
