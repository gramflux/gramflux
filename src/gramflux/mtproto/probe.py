"""Credential-free native MTProto req_pq probe; NOT authorization-key creation."""

import asyncio
import secrets
import struct
import time
from dataclasses import dataclass
from typing import Literal

from gramflux.errors import TransportError
from gramflux.tl.codec import Reader
from gramflux.tl.parser import parse
from gramflux.tools.schema import DATA

from .framing import Framing


@dataclass(frozen=True, slots=True)
class ProbeResult:
    fingerprint_count: int
    pq_bits: int


async def probe_datacenter(
    host: str = "149.154.167.51",
    port: int = 443,
    *,
    mode: Literal["full", "intermediate", "abridged"] = "intermediate",
    deadline: float = 5.0,
) -> ProbeResult:
    """Perform one unencrypted req_pq_multi exchange without credentials.

    This proves framing and the initial handshake exchange only. Nonce agreement
    does not authenticate the server; RSA fingerprint validation and DH remain
    the live backend's responsibility. The connection always closes afterwards.
    """
    definitions = {d.name: d for d in parse((DATA / "mtproto.tl").read_text())}
    nonce = secrets.token_bytes(16)
    body = struct.pack("<I", definitions["req_pq_multi"].id) + nonce
    msg_id = int(time.time() * 2**32) & ~3
    envelope = struct.pack("<QQI", 0, msg_id, len(body)) + body
    framing = Framing(mode, limit=1024 * 1024)
    async with asyncio.timeout(deadline):
        reader, writer = await asyncio.open_connection(host, port)
        try:
            writer.write(framing.preamble + framing.encode(envelope))
            await writer.drain()
            payload = await framing.read(reader)
            incoming = Reader(memoryview(payload))
            if incoming.take(8) != bytes(8):
                raise TransportError("expected unencrypted handshake response")
            response_id = int.from_bytes(incoming.take(8), "little")
            length = incoming.uint()
            if response_id % 4 != 1 or length != len(payload) - 20:
                raise TransportError("invalid handshake envelope")
            if incoming.uint() != definitions["resPQ"].id or incoming.take(16) != nonce:
                raise TransportError("unexpected handshake response or nonce")
            incoming.take(16)  # server_nonce; no key negotiation in this probe
            n = incoming.take(1)[0]
            if n == 0 or n > 8:
                raise TransportError("invalid pq length")
            pq = int.from_bytes(incoming.take(n), "big")
            if any(incoming.take(-(n + 1) % 4)):
                raise TransportError("invalid pq padding")
            if incoming.uint() != 0x1CB5C415:
                raise TransportError("invalid fingerprint vector")
            count = incoming.uint()
            if not 1 <= count <= 64:
                raise TransportError("invalid fingerprint count")
            incoming.take(count * 8)
            if incoming.offset != len(payload):
                raise TransportError("trailing handshake data")
            return ProbeResult(count, pq.bit_length())
        finally:
            writer.close()
            await writer.wait_closed()
