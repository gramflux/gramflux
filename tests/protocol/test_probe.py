import asyncio
import struct
import time

import pytest

from gramflux.errors import TransportError
from gramflux.mtproto.framing import Framing
from gramflux.mtproto.probe import probe_datacenter


@pytest.mark.parametrize("bad_nonce", [False, True])
async def test_native_req_pq_server(bad_nonce):
    closed = asyncio.Event()

    async def handle(reader, writer):
        framing = Framing("intermediate")
        try:
            assert await reader.readexactly(4) == b"\xee" * 4
            request = await framing.read(reader)
            assert request[:8] == bytes(8)
            assert int.from_bytes(request[16:20], "little") == 20
            assert request[20:24].hex() == "f18e7ebe"
            nonce = bytes(16) if bad_nonce else request[24:40]
            body = bytes.fromhex("63241605") + nonce + bytes(16)
            body += b"\x08" + b"\x01" * 8 + bytes(3)
            body += struct.pack("<IIq", 0x1CB5C415, 1, 1234)
            msg_id = (int(time.time() * 2**32) & ~3) | 1
            response = struct.pack("<QQI", 0, msg_id, len(body)) + body
            writer.write(framing.encode(response))
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            closed.set()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    async with server:
        port = server.sockets[0].getsockname()[1]
        if bad_nonce:
            with pytest.raises(TransportError):
                await probe_datacenter("127.0.0.1", port)
        else:
            assert (await probe_datacenter("127.0.0.1", port)).fingerprint_count == 1
        await closed.wait()
