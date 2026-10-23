"""Direct P0 operations use the existing upload, resolver and message services."""

import io

import pytest

from gramflux.raw import types
from tests.integration.test_core_api import history_slice, make, message, user


@pytest.mark.parametrize(
    "name,force,photo",
    [
        ("image.jpg", False, True),
        ("image.png", False, True),
        ("image.jpg", True, False),
        ("data.bin", False, False),
    ],
)
async def test_send_file_accepts_paths_preserves_uploaded_handle_behavior(
    tmp_path, name, force, photo
):
    payload = b"public synthetic test bytes"
    source = tmp_path / name
    source.write_bytes(payload)
    parts = []

    async def respond(request):
        assert request.definition.name == "upload.saveFilePart"
        parts.append(request.bytes)
        return True

    c, backend = make(respond)
    async with c:
        sent = await c.send_file(
            types.InputPeerChat(chat_id=7), source, caption="caption", as_document=force
        )
        assert sent.id == 101
        assert isinstance(backend.media[0][1], types.InputMediaUploadedPhoto) is photo
        handle = types.InputFile(id=1, parts=1, name="photo.jpg", md5_checksum="")
        await c.send_file(types.InputPeerChat(chat_id=7), handle)
        assert backend.media[-1][1] is handle
    assert b"".join(parts) == payload


async def test_send_file_stream_remains_owned_by_caller():
    async def respond(request):
        return True

    c, _ = make(respond)
    source = io.BytesIO(b"bytes")
    async with c:
        await c.send_file(types.InputPeerChat(chat_id=7), source, as_document=True)
    assert not source.closed


async def test_iter_messages_is_lazy_and_entity_links_resolve_through_native_methods():
    peer = types.InputPeerUser(user_id=12, access_hash=1200)

    async def respond(request):
        if request.definition.name == "contacts.resolveUsername":
            assert request.username == "user_12"
            return types.contacts.ResolvedPeer(
                peer=types.PeerUser(user_id=12), users=[user()], chats=[]
            )
        if request.definition.name == "users.getUsers":
            return [user()]
        assert request.definition.name == "messages.getHistory"
        return history_slice(message(9))

    c, backend = make(respond)
    async with c:
        stream = c.iter_messages(peer, limit=1)
        assert not backend.calls
        assert (await anext(stream)).id == 9
        entity = await c.get_entity("https://t.me/user_12")
        assert entity.id == 12
        assert (await c.get_input_entity("@user_12")).access_hash == 1200
        assert await c.get_peer_id(types.PeerChannel(channel_id=8)) == -1000000000008
