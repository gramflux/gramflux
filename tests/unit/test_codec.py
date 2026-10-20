import struct

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gramflux.errors import SerializationError
from gramflux.tl import Codec
from gramflux.tl.generated import objects as o


@given(st.integers(min_value=-(2**31), max_value=2**31 - 1))
def test_int_roundtrip(value):
    codec = Codec()
    assert codec.decode(codec.encode(value, "int"), "int") == value


@given(st.binary(max_size=1000))
def test_bytes_roundtrip(value):
    codec = Codec()
    assert codec.decode(codec.encode(value, "bytes"), "bytes") == value


@given(st.text(max_size=200).filter(lambda s: not any(0xD800 <= ord(c) <= 0xDFFF for c in s)))
def test_utf8(value):
    codec = Codec()
    assert codec.decode(codec.encode(value, "string"), "string") == value


@pytest.mark.parametrize("size", [0, 1, 253, 254, 255, 256, 1024])
def test_string_boundaries(size):
    codec = Codec()
    raw = b"x" * size
    encoded = codec.encode(raw, "bytes")
    assert len(encoded) % 4 == 0
    assert encoded[0] == (size if size < 254 else 254)
    assert codec.decode(encoded, "bytes") == raw


def test_known_wire_examples_and_type_check():
    codec = Codec()
    value = o.InputPeerSelf()
    assert codec.encode(value).hex() == "c97ea07d"
    assert codec.encode("abc", "string") == b"\x03abc"
    assert codec.encode(True, "Bool") == bytes.fromhex("b5757299")
    assert codec.decode(codec.encode(value)) == value
    with pytest.raises(SerializationError):
        codec.encode(value, "User")


def test_flags_and_vectors():
    codec = Codec()
    value = o.InputMediaUploadedPhoto(
        file=o.InputFile(id=7, parts=1, name="x", md5_checksum=""), spoiler=True
    )
    assert codec.decode(codec.encode(value)) == value
    assert codec.decode(codec.encode([1, -2, 3], "Vector<int>"), "Vector<int>") == [1, -2, 3]


def test_shared_flag_requires_all_fields():
    codec = Codec()
    value = o.InputMediaUploadedPhoto(
        file=o.InputFile(id=7, parts=1, name="x", md5_checksum=""), live_photo=True
    )
    with pytest.raises(SerializationError, match="sharing a flag"):
        codec.encode(value)


@pytest.mark.parametrize(
    "raw,t",
    [
        (b"\xff", "bytes"),
        (b"\xfe\x01\0\0x\0\0\0", "bytes"),
        (b"\x01x\0\x01", "bytes"),
        (b"\x04abc", "bytes"),
        (b"\0\0\0\0", "Object"),
        (b"\0\0\0\0", "Bool"),
        (struct.pack("<Ii", 0x1CB5C415, -1), "Vector<int>"),
        (b"\0\0\0\0x", "int"),
    ],
)
def test_malformed(raw, t):
    with pytest.raises(SerializationError):
        Codec().decode(raw, t)


def test_bounds_and_unknown_flags():
    codec = Codec(max_vector=2, max_bytes=100, max_depth=3)
    for value, t in [([1, 2, 3], "Vector<int>"), (b"x" * 101, "bytes"), (2**31, "int")]:
        with pytest.raises(SerializationError):
            codec.encode(value, t)
    with pytest.raises(SerializationError, match="unknown flags"):
        Codec().decode(struct.pack("<II", o.InputMediaUploadedPhoto.definition.id, 1 << 31))


def test_repr_does_not_include_secrets():
    value = o.InputFile(id=1234, parts=1, name="PRIVATE", md5_checksum="secret")
    assert repr(value) == "<inputFile>"


def test_optional_true_requires_bool():
    value = o.InputMediaUploadedPhoto(
        file=o.InputFile(id=7, parts=1, name="x", md5_checksum=""), spoiler=1
    )
    with pytest.raises(SerializationError, match="must be bool"):
        Codec().encode(value)


def test_nested_object_depth_limit_on_encode_and_decode():
    value = o.JsonNull()
    for _ in range(10):
        value = o.JsonArray(value=[value])
    encoded = Codec().encode(value)
    with pytest.raises(SerializationError, match="resource limit"):
        Codec(max_depth=3).encode(value)
    with pytest.raises(SerializationError, match="resource limit"):
        Codec(max_depth=3).decode(encoded)
