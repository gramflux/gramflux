"""Encrypted native RPC bursts and abrupt failure over actual loopback TCP.

The controlled peer shares protocol primitives with the client. This tests load,
framing and cleanup, not independently verified Telegram interoperability.
"""

import asyncio
import struct
import time

import pytest

from gramflux.errors import TransportError
from gramflux.mtproto import crypto
from gramflux.mtproto.connection import Connection
from gramflux.mtproto.framing import Framing
from gramflux.mtproto.sender import Sender
from gramflux.raw import functions, types
from gramflux.tl import Codec

AUTH = bytes(range(256))
SALT = 12345
SESSION = 67890


@pytest.mark.parametrize("mode", ["full", "intermediate", "abridged"])
@pytest.mark.parametrize("disconnect", [False, True])
async def test_bounded_encrypted_rpc_burst_and_cleanup(mode, disconnect):
    codec = Codec()
    completed = asyncio.Event()
    server_errors = []
    request_ids = []
    total, window = 1000, 5

    async def peer(reader, writer):
        try:
            framing = Framing(mode)
            if framing.preamble:
                assert await reader.readexactly(len(framing.preamble)) == framing.preamble
            batch = []
            last_id = 0
            count = 0
            while True:
                packet = await framing.read(reader)
                envelope = crypto.decrypt(AUTH, packet, SESSION, incoming=False)
                if envelope.body[:4] == struct.pack("<I", 0x62D6B459):
                    continue
                assert envelope.body == codec.encode(functions.help.GetNearestDcRequest())
                assert len(request_ids) == 0 or envelope.message_id > request_ids[-1]
                request_ids.append(envelope.message_id)
                count += 1
                if disconnect and count == 11:
                    return
                batch.append(envelope)
                if len(batch) < window:
                    continue
                for item in reversed(batch):
                    last_id = max((time.time_ns() * 2**32 // 10**9 & ~3) | 1, last_id + 4)
                    body = struct.pack("<Iq", 0xF35C6D01, item.message_id) + codec.encode(
                        types.NearestDc(country="fixture", this_dc=2, nearest_dc=2)
                    )
                    writer.write(
                        framing.encode(
                            crypto.encrypt(
                                AUTH,
                                crypto.Envelope(SALT, SESSION, last_id, 1, body),
                                incoming=True,
                            )
                        )
                    )
                await writer.drain()
                batch.clear()
                if count == total:
                    # Keep the peer alive until client cleanup, so successful RPCs
                    # cannot race an artificial server EOF.
                    while await reader.read(4096):
                        continue
                    return
        except (ConnectionError, asyncio.IncompleteReadError):
            if not disconnect:
                server_errors.append("unexpected connection loss")
        except Exception as error:
            server_errors.append(type(error).__name__)
        finally:
            writer.close()
            await writer.wait_closed()
            completed.set()

    server = await asyncio.start_server(peer, "127.0.0.1", 0)
    connection = Connection("127.0.0.1", server.sockets[0].getsockname()[1], mode)
    sender = Sender(connection, AUTH, SALT, max_pending=window)
    sender.session = SESSION
    tasks = []
    try:
        async with asyncio.timeout(60):
            await connection.connect()
            sender.start()
            tasks = [
                asyncio.create_task(
                    sender.invoke(
                        functions.help.GetNearestDcRequest(),
                        deadline_seconds=45,
                    )
                )
                for _ in range(total)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            assert not server_errors
            if disconnect:
                # Closing can race decoding of the second reply batch. Those
                # outstanding outcomes must fail explicitly, never be fabricated.
                assert 5 <= sum(isinstance(item, types.NearestDc) for item in results) <= 10
                assert len(request_ids) == 11
                assert all(isinstance(item, (types.NearestDc, TransportError)) for item in results)
                assert sender.disconnected.done()
            else:
                assert all(isinstance(item, types.NearestDc) for item in results)
                assert len(request_ids) == total
            assert not sender.pending
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await sender.close()
        await asyncio.wait_for(completed.wait(), 5)
        server.close()
        await server.wait_closed()
    assert not server_errors
    assert sender.reader_task.done()
    assert sender.updates.queued_bytes == 0
