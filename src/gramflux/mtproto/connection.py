"""One asyncio stream and framing state per connection; serialized writes."""

import asyncio
from typing import Literal

from gramflux.errors import TransportError

from .framing import Framing


class Connection:
    def __init__(
        self,
        host: str,
        port: int,
        mode: Literal["full", "intermediate", "abridged"] = "intermediate",
        *,
        limit: int = 16 * 1024 * 1024,
        io_timeout: float = 30,
    ) -> None:
        self.host, self.port, self.mode, self.limit = host, port, mode, limit
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.framing = Framing(mode, limit=limit)
        self.io_timeout = io_timeout
        self.lock = asyncio.Lock()

    async def connect(self) -> None:
        if self.writer is not None:
            raise TransportError("connection is already open")
        try:
            async with asyncio.timeout(self.io_timeout):
                self.reader, self.writer = await asyncio.open_connection(
                    self.host, self.port, limit=self.limit + 64
                )
                # Full-transport sequence numbers belong to this socket, not the
                # reusable Connection instance.
                self.framing = Framing(self.mode, limit=self.limit)
                self.writer.write(self.framing.preamble)
                await self.writer.drain()
        except TimeoutError:
            await self.close()
            raise TransportError("native transport connection deadline exceeded") from None
        except BaseException:
            await self.close()
            raise

    async def send(self, data: bytes) -> None:
        try:
            async with asyncio.timeout(self.io_timeout):
                async with self.lock:
                    if self.writer is None:
                        raise TransportError("connection is closed")
                    self.writer.write(self.framing.encode(data))
                    await self.writer.drain()
        except TimeoutError:
            await self.close()
            raise TransportError("native transport write deadline exceeded") from None

    async def receive(self) -> bytes:
        if self.reader is None:
            raise TransportError("connection is closed")
        return await self.framing.read(self.reader)

    async def close(self) -> None:
        writer, self.writer = self.writer, None
        self.reader = None
        if writer is not None:
            writer.close()
            # Terminal close must not wait indefinitely for a peer to drain buffered bytes.
            writer.transport.abort()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                # A broken socket is already closed; no request is retried here.
                return
