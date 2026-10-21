"""Async facade through Client lifecycle, request policy and native wire codec."""

import asyncio

import pytest

from gramflux.errors import LifecycleError
from gramflux.raw import types
from gramflux.tl import Codec
from tests.integration.test_core_api import make


async def test_concurrent_calls_preserve_arguments_and_decoded_results():
    codec = Codec()
    requests = []

    async def respond(request):
        requests.append(request)
        codec.encode(request)
        await asyncio.sleep((10 - request.hash) / 1000)
        return codec.decode(codec.encode(types.messages.MessagesNotModified(count=request.hash)))

    client, backend = make(respond)
    async with client:
        results = await asyncio.gather(
            *[
                client.api.messages.get_history(
                    peer=types.InputPeerSelf(),
                    offset_id=0,
                    offset_date=0,
                    add_offset=0,
                    limit=1,
                    max_id=0,
                    min_id=0,
                    hash=i,
                )
                for i in range(10)
            ]
        )
        assert [result.count for result in results] == list(range(10))
        assert len(requests) == 10
        assert all(request.definition.name == "messages.getHistory" for request in requests)
    assert not backend.is_connected()
    with pytest.raises(LifecycleError):
        await client.api.help.get_nearest_dc()


async def test_optional_groups_and_cancellation_use_client_policy():
    entered = asyncio.Event()
    seen = []

    async def respond(request):
        seen.append(request)
        wire = Codec().encode(request)
        # saveDraft flags bit 1 is no_webpage, bit 6 is invert_media.
        flags = int.from_bytes(wire[4:8], "little")
        assert flags & 2 and flags & 64
        entered.set()
        await asyncio.Event().wait()

    client, _ = make(respond)
    async with client:
        task = asyncio.create_task(
            client.api.messages.save_draft(
                peer=types.InputPeerSelf(),
                message="draft",
                no_webpage=True,
                invert_media=True,
            )
        )
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(seen) == 1
