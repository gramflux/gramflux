"""Native TCP framing used by the live connection and protocol tests.

Length bounds are checked before reading payload bytes. State belongs to one
connection. The full-transport checksum covers length, sequence and payload.
"""

import asyncio
import struct
import zlib
from typing import Literal

from gramflux.errors import TransportError


class Framing:
    def __init__(
        self, mode: Literal["full", "intermediate", "abridged"], *, limit: int = 16 * 1024 * 1024
    ) -> None:
        if mode not in {"full", "intermediate", "abridged"} or limit < 4:
            raise ValueError("invalid transport mode or size limit")
        self.mode = mode
        self.limit = limit
        self.sent = 0
        self.received = 0

    @property
    def preamble(self) -> bytes:
        return {"full": b"", "intermediate": b"\xee" * 4, "abridged": b"\xef"}[self.mode]

    def encode(self, payload: bytes) -> bytes:
        if not payload or len(payload) % 4 or len(payload) > self.limit:
            raise TransportError("invalid transport payload size")
        if self.mode == "full":
            frame = struct.pack("<II", len(payload) + 12, self.sent) + payload
            self.sent = (self.sent + 1) & 0xFFFFFFFF
            return frame + struct.pack("<I", zlib.crc32(frame))
        if self.mode == "intermediate":
            return struct.pack("<I", len(payload)) + payload
        words = len(payload) // 4
        if words >= 1 << 24:
            raise TransportError("abridged frame exceeds length field")
        return (bytes([words]) if words < 127 else b"\x7f" + words.to_bytes(3, "little")) + payload

    async def read(self, reader: asyncio.StreamReader) -> bytes:
        try:
            if self.mode == "abridged":
                length = (await reader.readexactly(1))[0]
                if length == 127:
                    length = int.from_bytes(await reader.readexactly(3), "little")
                    if length < 127:
                        raise TransportError("noncanonical abridged length")
                elif length > 127:
                    raise TransportError("invalid abridged length")
                length *= 4
                header = b""
            else:
                header = await reader.readexactly(4)
                length = int.from_bytes(header, "little") - (12 if self.mode == "full" else 0)
            if not 0 < length <= self.limit or length % 4:
                raise TransportError("invalid transport frame length")
            if self.mode == "full":
                seq_bytes = await reader.readexactly(4)
                sequence = int.from_bytes(seq_bytes, "little")
                if sequence != self.received:
                    raise TransportError("invalid transport sequence")
                payload = await reader.readexactly(length)
                crc = int.from_bytes(await reader.readexactly(4), "little")
                if zlib.crc32(header + seq_bytes + payload) != crc:
                    raise TransportError("invalid transport checksum")
                self.received = (self.received + 1) & 0xFFFFFFFF
                return payload
            return await reader.readexactly(length)
        except asyncio.IncompleteReadError as exc:
            raise TransportError("connection closed during transport frame") from exc
