import asyncio
import json
import struct
from pathlib import Path

import pytest

from gramflux.errors import TransportError
from gramflux.mtproto.framing import Framing


@pytest.mark.parametrize(
    "mode,reference",
    [
        ("full", "full"),
        ("intermediate", "intermediate"),
        ("abridged", "abridged"),
    ],
)
@pytest.mark.parametrize("length", [4, 504, 508, 512, 1024])
async def test_reference_and_fragmented_read(mode, reference, length):
    framing = Framing(mode)
    reader = asyncio.StreamReader()
    packet = framing.encode(b"x" * length)
    assert packet == bytes.fromhex(
        json.loads(Path(__file__).with_name("framing_vectors.json").read_text())["frames"][
            f"{reference}:{length}"
        ]
    )

    async def feed():
        for start in range(0, len(packet), 13):
            reader.feed_data(packet[start : start + 13])
            await asyncio.sleep(0)
        reader.feed_eof()

    task = asyncio.create_task(feed())
    assert await framing.read(reader) == b"x" * length
    await task


@pytest.mark.parametrize(
    "mode,raw",
    [
        ("full", struct.pack("<I", 0xFFFFFFFF)),
        ("intermediate", struct.pack("<I", 0xFFFFFFFF)),
        ("abridged", b"\x7f\xff\xff\xff"),
        ("abridged", b"\x80"),
    ],
)
async def test_length_rejected_before_payload(mode, raw):
    reader = asyncio.StreamReader()
    reader.feed_data(raw)
    with pytest.raises(TransportError):
        await Framing(mode).read(reader)


async def test_crc_sequence_truncation():
    valid = Framing("full").encode(b"abcd")
    for packet in [
        valid[:-1],
        valid[:-1] + bytes([valid[-1] ^ 1]),
        valid[:4] + b"\x02\0\0\0" + valid[8:],
    ]:
        reader = asyncio.StreamReader()
        reader.feed_data(packet)
        reader.feed_eof()
        with pytest.raises(TransportError):
            await Framing("full").read(reader)
