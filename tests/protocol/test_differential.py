"""Independent encoders compared on shared official constructor IDs."""

import json
from pathlib import Path

import pytest

from gramflux.tl import Codec
from gramflux.tl.generated import objects as o

VECTORS = json.loads((Path(__file__).with_name("tl_vectors.json")).read_text())["vectors"]


@pytest.mark.parametrize(
    "independent,reference",
    [
        (o.InputPeerSelf(), bytes.fromhex(VECTORS[0])),
        (o.InputPeerUser(user_id=1234, access_hash=-2345), bytes.fromhex(VECTORS[1])),
        (
            o.InputFile(id=23, parts=4, name="emoji 🌟", md5_checksum="abc"),
            bytes.fromhex(VECTORS[2]),
        ),
        (
            o.InputMediaUploadedPhoto(
                file=o.InputFile(id=1, parts=2, name="x", md5_checksum="a"), spoiler=True
            ),
            bytes.fromhex(VECTORS[3]),
        ),
    ],
)
def test_serialize_against_backend(independent, reference):
    assert independent.definition.id == int.from_bytes(reference[:4], "little")
    assert Codec().encode(independent) == bytes(reference)
    assert Codec().decode(bytes(reference)) == independent
