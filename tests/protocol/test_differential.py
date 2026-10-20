"""Independent encoders compared on shared official constructor IDs."""

import pytest
from telethon.tl import types

from gramflux.tl import Codec
from gramflux.tl.generated import objects as o


@pytest.mark.parametrize(
    "independent,reference",
    [
        (o.InputPeerSelf(), types.InputPeerSelf()),
        (o.InputPeerUser(user_id=1234, access_hash=-2345), types.InputPeerUser(1234, -2345)),
        (
            o.InputFile(id=23, parts=4, name="emoji 🌟", md5_checksum="abc"),
            types.InputFile(23, 4, "emoji 🌟", "abc"),
        ),
        (
            o.InputMediaUploadedPhoto(
                file=o.InputFile(id=1, parts=2, name="x", md5_checksum="a"), spoiler=True
            ),
            types.InputMediaUploadedPhoto(types.InputFile(1, 2, "x", "a"), spoiler=True),
        ),
    ],
)
def test_serialize_against_backend(independent, reference):
    assert independent.definition.id == reference.CONSTRUCTOR_ID
    assert Codec().encode(independent) == bytes(reference)
    assert Codec().decode(bytes(reference)) == independent
