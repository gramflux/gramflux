"""Actual loopback TCP framing and bounded stalled-write behavior."""

import asyncio
from types import SimpleNamespace

import pytest

from gramflux.errors import TransportError
from gramflux.mtproto.connection import Connection
from gramflux.mtproto.framing import Framing


@pytest.mark.parametrize("mode", ["full", "intermediate", "abridged"])
async def test_own_connection_over_real_loopback_socket(mode):
    finished = asyncio.Event()
    received = []

    async def server_peer(reader, writer):
        try:
            framing = Framing(mode)
            if framing.preamble:
                assert await reader.readexactly(len(framing.preamble)) == framing.preamble
            data = await framing.read(reader)
            received.append(data)
            writer.write(framing.encode(data))
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            finished.set()

    server = await asyncio.start_server(server_peer, "127.0.0.1", 0)
    connection = Connection("127.0.0.1", server.sockets[0].getsockname()[1], mode)
    try:
        async with asyncio.timeout(3):
            await connection.connect()
            await connection.send(b"abcd" * 128)
            assert await connection.receive() == b"abcd" * 128
            await finished.wait()
        assert received == [b"abcd" * 128]
    finally:
        await connection.close()
        server.close()
        await server.wait_closed()


async def test_stalled_drain_has_bounded_deadline_and_aborts_socket():
    aborted = []

    async def drain():
        await asyncio.Event().wait()

    async def closed():
        return None

    writer = SimpleNamespace(
        write=lambda data: None,
        drain=drain,
        close=lambda: None,
        wait_closed=closed,
        transport=SimpleNamespace(abort=lambda: aborted.append(True)),
    )
    connection = Connection("127.0.0.1", 1, io_timeout=0.01)
    connection.writer = writer
    with pytest.raises(TransportError, match="write deadline"):
        await connection.send(b"abcd")
    assert aborted == [True] and connection.writer is None


@pytest.mark.parametrize("cancel", [False, True])
async def test_preamble_stall_closes_socket_on_deadline_or_cancellation(monkeypatch, cancel):
    entered = asyncio.Event()
    aborted = []

    async def drain():
        entered.set()
        await asyncio.Event().wait()

    async def closed():
        return None

    writer = SimpleNamespace(
        write=lambda data: None,
        drain=drain,
        close=lambda: None,
        wait_closed=closed,
        transport=SimpleNamespace(abort=lambda: aborted.append(True)),
    )

    async def open_connection(*args, **kwargs):
        return asyncio.StreamReader(), writer

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    connection = Connection("127.0.0.1", 1, io_timeout=0.05 if not cancel else 10)
    task = asyncio.create_task(connection.connect())
    await entered.wait()
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else TransportError):
        await task
    assert aborted == [True]
    assert connection.writer is connection.reader is None


async def test_reopened_full_transport_restarts_sequence_numbers():
    finished = asyncio.Queue()

    async def peer(reader, writer):
        try:
            framing = Framing("full")
            data = await framing.read(reader)
            writer.write(framing.encode(data))
            await writer.drain()
            finished.put_nowait(None)
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(peer, "127.0.0.1", 0)
    connection = Connection("127.0.0.1", server.sockets[0].getsockname()[1], "full")
    try:
        async with asyncio.timeout(3):
            for _ in range(2):
                await connection.connect()
                with pytest.raises(TransportError, match="already open"):
                    await connection.connect()
                await connection.send(b"abcd")
                assert await connection.receive() == b"abcd"
                await finished.get()
                await connection.close()
    finally:
        await connection.close()
        server.close()
        await server.wait_closed()


async def test_client_handshake_deadline_closes_real_socket_and_allows_retry():
    from gramflux import Client, Config
    from gramflux.backend import NativeBackend

    started = asyncio.Event()
    finished = asyncio.Queue()

    async def silent_peer(reader, writer):
        try:
            assert await reader.readexactly(4) == b"\xee" * 4
            framing = Framing("intermediate")
            assert await framing.read(reader)  # actual unencrypted req_pq_multi
            started.set()
            assert await reader.read() == b""
            finished.put_nowait(None)
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(silent_peer, "127.0.0.1", 0)
    backend = NativeBackend(1234, "a" * 32, Config(request_timeout=0.5))
    backend.session.set_dc(2, "127.0.0.1", server.sockets[0].getsockname()[1])
    client = Client(api_id=1234, api_hash="a" * 32, config=backend.config, _backend=backend)
    try:
        async with asyncio.timeout(5):
            for _ in range(2):
                started.clear()
                task = asyncio.create_task(client.connect())
                await started.wait()
                with pytest.raises(TimeoutError):
                    await task
                await finished.get()
                assert not client.connected and not backend.is_connected()
                assert backend.sender is None
                assert backend.update_task is backend.heartbeat_task is None
    finally:
        await client.disconnect()
        server.close()
        await server.wait_closed()
