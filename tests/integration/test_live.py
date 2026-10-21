"""Read-only account test, disabled unless the tester explicitly opts in."""

import asyncio
import os

import pytest

from gramflux import Client, Session


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("GRAMFLUX_LIVE") != "1",
    reason="requires explicit live opt-in and authorized GramFlux session",
)
async def test_live_identity():
    previous_id = None
    for _ in range(2):
        async with Client(
            Session.open(os.environ["GRAMFLUX_SESSION"]),
            api_id=int(os.environ["GRAMFLUX_API_ID"]),
            api_hash=os.environ["GRAMFLUX_API_HASH"],
        ) as client:
            assert await client.is_authorized()
            identity = (await client.get_me()).id
            if identity <= 0 or previous_id is not None and identity != previous_id:
                pytest.fail("Saved session identity was invalid or changed on reuse")
            previous_id = identity


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("GRAMFLUX_LIVE_BOT") != "1", reason="requires dedicated test bot opt-in"
)
async def test_live_bot_authorization_in_temporary_session():
    async with Client(
        Session.temporary(),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    ) as client:
        me = await client.sign_in_bot(os.environ["GRAMFLUX_BOT_TOKEN"])
        try:
            assert bool(me.bot)
            assert await client.is_authorized()
            assert (await client.get_me()).id == me.id
        finally:
            await client.log_out()


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("GRAMFLUX_LIVE_WRITE") != "1",
    reason="requires explicit writes to a dedicated test user's Saved Messages",
)
async def test_live_saved_message_and_document_roundtrip(tmp_path):
    import hashlib

    payload = os.urandom(16 * 1024 + 7)
    source, destination = tmp_path / "fixture.bin", tmp_path / "download.bin"
    source.write_bytes(payload)
    async with Client(
        Session.open(os.environ["GRAMFLUX_SESSION"]),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    ) as client:
        if (await client.get_me()).bot:
            pytest.fail("Saved Messages roundtrip requires a dedicated user account")
        received = asyncio.Event()
        observed = set()

        @client.on_message()
        async def on_message(event):
            if event.text == "GramFlux explicit integration test":
                observed.add(event.message.id)
                received.set()

        created = []
        try:
            text = await client.send_message("me", "GramFlux explicit integration test")
            created.append(text.id)
            async with asyncio.timeout(20):
                await received.wait()
            if text.id not in observed:
                pytest.fail("Expected test message was not dispatched")
            uploaded = await client.upload_file(source)
            media = await client.send_file("me", uploaded, caption="GramFlux integration fixture")
            created.append(media.id)
            await client.download_media(media, destination)
            if (
                hashlib.sha256(destination.read_bytes()).digest()
                != hashlib.sha256(payload).digest()
            ):
                pytest.fail("Telegram document roundtrip checksum differs")
        finally:
            if created:
                # Scope cleanup to IDs returned by this test; never delete unknown outcomes.
                await client.delete_messages("me", created, revoke=True)
