"""New views against existing request encoding, storage and file pipelines.

Responses are controlled test fixtures, not live Telegram verification.
"""

import io
import json
from pathlib import Path

import pytest

from gramflux import resources
from gramflux.raw import types
from gramflux.tl import Codec
from tests.integration.test_core_api import make
from tests.integration.test_extended_operations import CASES
from tests.integration.test_login_resume import crash_after_checkpoint, reopen
from tests.native_fixtures import fixture_field

MAPPING = json.loads(
    (Path(__file__).resolve().parents[2] / "research/next-api-mapping.json").read_text()
)


@pytest.mark.parametrize("name,args,kwargs,method,fields", CASES)
async def test_domains_execute_same_encoded_requests_as_legacy_operations(
    name, args, kwargs, method, fields
):
    codec, requests = Codec(), []

    async def respond(request):
        requests.append(request)
        assert request.definition.name == method
        codec.encode(request)
        for key, value in fields.items():
            assert getattr(request, key) == value
        if request.definition.result == "User":
            return types.User(id=12)
        response = fixture_field(request.definition.result)
        return codec.decode(
            codec.encode(response, request.definition.result), request.definition.result
        )

    c, _ = make(respond)
    cls, new = next(
        (cls, new) for cls, rows in MAPPING.items() for new, old in rows.items() if old == name
    )
    bound = cls in {"History", "Search", "Members", "ChatResource"}
    view = getattr(resources, cls)(c, args[0]) if bound else getattr(resources, cls)(c)
    async with c:
        legacy = await getattr(c, name)(*args, **kwargs)
        result = await getattr(view, new)(*(args[1:] if bound else args), **kwargs)
        assert type(result) is type(legacy)
    assert len(requests) == 2


async def test_auth_view_resumes_sqlite_checkpoint_created_by_legacy_process(tmp_path):
    path = tmp_path / "cross-api.session"
    await crash_after_checkpoint(path, "code")
    c, backend = reopen(path)
    async with c:
        assert c.auth.stage == c.login_stage == "code"
        assert c.auth.challenge == c.login_challenge
        assert (await c.auth.sign_in(code="12345")).id == 42
        assert c.auth.stage is None
        assert (await c.account.me()).id == 42
        assert await c.auth.is_authorized()
        assert backend.codes == []


async def test_file_view_keeps_stream_ownership_progress_and_no_overwrite(tmp_path):
    payload = b"x" * 2500
    parts, progress = {}, []

    async def respond(request):
        if request.definition.name == "upload.saveFilePart":
            parts[request.file_part] = request.bytes
            return True
        assert request.definition.name == "upload.getFile"
        return types.upload.File(
            type=types.storage.FileUnknown(),
            mtime=0,
            bytes=payload[request.offset : request.offset + request.limit],
        )

    c, _ = make(respond)
    source = io.BytesIO(payload)
    location = types.InputDocumentFileLocation(
        id=1, access_hash=2, file_reference=b"", thumb_size=""
    )
    destination = tmp_path / "output.bin"
    async with c:
        result = await c.files.upload(
            source,
            name="sample.bin",
            part_size=1024,
            concurrency=2,
            on_progress=lambda done, total: progress.append((done, total)),
        )
        assert result.parts == 3
        assert b"".join(parts[i] for i in sorted(parts)) == payload
        assert not source.closed
        assert progress[0] == (0, len(payload)) and progress[-1] == (len(payload), len(payload))
        assert (
            await c.files.download(location, destination, size=len(payload), request_size=4096)
            == destination
        )
        assert destination.read_bytes() == payload
        with pytest.raises(FileExistsError):
            await c.files.download(location, destination, size=len(payload), request_size=4096)
        assert destination.read_bytes() == payload


@pytest.mark.parametrize("module", ["examples.legacy_equivalent", "examples.next_app.__main__"])
async def test_complete_legacy_and_modular_examples_have_the_same_effect(module):
    import importlib
    from unittest.mock import AsyncMock

    from gramflux.events import MessageEvent
    from tests.integration.test_core_api import message, state

    async def respond(request):
        if request.definition.name == "updates.getState":
            return state()
        pytest.fail("example should not issue an unexpected raw RPC")

    c, backend = make(respond)
    backend.is_user_authorized = AsyncMock(return_value=True)

    async def receive_one():
        await c._dispatcher.put(
            MessageEvent(message(5, peer=1, text="/hello@MyBot"), client=c, chat_type="private")
        )
        await c._dispatcher.join()

    c.run_until_disconnected = receive_one
    await importlib.import_module(module).serve(
        c, bot_token="controlled-test-token", username="MyBot"
    )
    assert len(backend.sent) == 1
    assert backend.sent[0][1] == "Hello from GramFlux"
    assert backend.sent[0][2]["reply_to"] == 5
    assert not c.connected


async def test_chat_resource_preserves_channel_delete_scope_and_edit_request():
    from gramflux.errors import ConfigurationError

    channel = types.InputPeerChannel(channel_id=8, access_hash=800)
    requests = []

    async def respond(request):
        Codec().encode(request)
        requests.append(request)
        if request.definition.name == "channels.deleteMessages":
            assert request.channel.channel_id == 8 and request.id == [9]
            return types.messages.AffectedMessages(pts=1, pts_count=1)
        assert request.definition.name == "messages.editMessage"
        assert request.peer is channel and request.id == 9 and request.message == "updated"
        return types.Updates(updates=[], users=[], chats=[], date=0, seq=0)

    c, backend = make(respond)
    chat = c.chat(channel)
    assert not backend.calls
    async with c:
        with pytest.raises(ConfigurationError):
            await chat.delete(9)
        assert requests == []
        await chat.delete(9, revoke=True)
        await chat.edit(9, "updated", link_preview=False)
        await chat.send("hello", reply_to=9, silent=True)
    assert backend.sent[0][0] is channel
    assert backend.sent[0][2]["reply_to"] == 9
