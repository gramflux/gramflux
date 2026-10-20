"""Native cryptography boundaries and independent OpenSSL/standard-algebra evidence."""

import hashlib
import hmac
import json
import secrets
import struct
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import dh, rsa
from hypothesis import given
from hypothesis import strategies as st

from gramflux.errors import SerializationError
from gramflux.mtproto import crypto
from gramflux.mtproto.auth_key import factor
from gramflux.mtproto.srp import compute_check
from gramflux.raw import types

VECTOR = json.loads(Path(__file__).with_name("ige_vector.json").read_text())


def test_aes256_ige_matches_independent_openssl_known_answer():
    key, iv, plain, encrypted = (
        bytes.fromhex(VECTOR[name]) for name in ("key", "iv", "plaintext", "ciphertext")
    )
    assert crypto.ige(plain, key, iv) == encrypted
    assert crypto.ige(encrypted, key, iv, decrypt=True) == plain


@given(st.binary(max_size=256), st.binary(max_size=256))
def test_xor_exact_bytes_or_length_error(left, right):
    if len(left) != len(right):
        with pytest.raises(ValueError):
            crypto.xor(left, right)
    else:
        assert crypto.xor(left, right) == bytes(a ^ b for a, b in zip(left, right, strict=True))


@pytest.mark.parametrize("length", [0, 1, 15, 17, 31])
def test_ige_rejects_invalid_lengths(length):
    with pytest.raises(SerializationError):
        crypto.ige(bytes(length), bytes(32), bytes(32))


@pytest.mark.parametrize("key_len,iv_len", [(0, 32), (31, 32), (32, 16), (32, 33)])
def test_ige_rejects_bad_key_iv(key_len, iv_len):
    with pytest.raises(SerializationError):
        crypto.ige(bytes(16), bytes(key_len), bytes(iv_len))


def test_rsa_pad_independent_private_recovery_and_hash():
    private = rsa.generate_private_key(65537, 2048)
    data = b"official protocol fixture" * 4
    encrypted = crypto.rsa_pad(data, private.public_key())
    numbers = private.private_numbers()
    decoded = pow(int.from_bytes(encrypted, "big"), numbers.d, numbers.public_numbers.n).to_bytes(
        256, "big"
    )
    key = crypto.xor(decoded[:32], hashlib.sha256(decoded[32:]).digest())
    padded = crypto.ige(decoded[32:], key, bytes(32), decrypt=True)
    recovered = padded[:192][::-1]
    assert recovered.startswith(data)
    assert hmac.compare_digest(padded[192:], hashlib.sha256(key + recovered).digest())
    with pytest.raises(SerializationError):
        crypto.rsa_pad(bytes(145), private.public_key())


def test_pinned_rsa_fingerprint_is_stable_and_protocol_key_is_public_only():
    key = crypto.trusted_rsa()
    assert key.key_size == 2048
    assert crypto.rsa_fingerprint(key) == int.from_bytes(
        hashlib.sha1(
            crypto.tl_bytes(key.public_numbers().n.to_bytes(256, "big"))
            + crypto.tl_bytes(b"\x01\x00\x01"),
            usedforsecurity=False,
        ).digest()[-8:],
        "little",
        signed=True,
    )
    assert "PRIVATE KEY" not in json.dumps(crypto.TRUST)


@pytest.mark.parametrize("pq", [15, 17 * 19, 1000003 * 1000033])
def test_bounded_pq_factorization(pq):
    p, q = factor(pq)
    assert p < q and p * q == pq


@pytest.mark.parametrize("pq", [0, 1, 14, 2**64])
def test_pq_rejects_invalid_values(pq):
    with pytest.raises(SerializationError):
        factor(pq)


def test_dh_exchange_matches_independent_openssl_peer():
    p = crypto.DH_PRIME
    parameters = dh.DHParameterNumbers(p, 3)
    remote = parameters.parameters().generate_private_key()
    remote_public = remote.public_key().public_numbers().y.to_bytes(256, "big")
    public, secret = crypto.dh_exchange(p.to_bytes(256, "big"), 3, remote_public)
    independent = remote.exchange(
        dh.DHPublicNumbers(int.from_bytes(public, "big"), parameters).public_key()
    )
    assert secret == independent.rjust(256, b"\0")
    assert len(secret) == 256


@pytest.mark.parametrize("public", [0, 1, 2, 2**1984, crypto.DH_PRIME - 2, crypto.DH_PRIME])
def test_dh_rejects_boundary_public_values(public):
    with pytest.raises(SerializationError):
        crypto.validate_dh(crypto.DH_PRIME.to_bytes(256, "big"), 3, public.to_bytes(256, "big"))


def test_dh_rejects_unknown_prime_and_bad_generator():
    with pytest.raises(SerializationError):
        crypto.validate_dh((crypto.DH_PRIME - 2).to_bytes(256, "big"), 3)
    with pytest.raises(SerializationError):
        crypto.validate_dh(crypto.DH_PRIME.to_bytes(256, "big"), 1)


@pytest.mark.parametrize("incoming", [False, True])
@pytest.mark.parametrize("length", [4, 16, 64, 4096])
def test_envelope_roundtrip_and_tamper_rejection(incoming, length):
    auth = bytes(range(256))
    envelope = crypto.Envelope(-123, -456, 987654321, 7, bytes(length))
    data = crypto.encrypt(auth, envelope, incoming=incoming)
    assert crypto.decrypt(auth, data, -456, incoming=incoming) == envelope
    assert repr(envelope).find("body=") == -1
    for index in [0, 8, 24, len(data) - 1]:
        bad = bytearray(data)
        bad[index] ^= 1
        with pytest.raises(SerializationError):
            crypto.decrypt(auth, bytes(bad), -456, incoming=incoming)
    with pytest.raises(SerializationError):
        crypto.decrypt(auth, data, 123, incoming=incoming)
    with pytest.raises(SerializationError):
        crypto.decrypt(auth, data, -456, incoming=not incoming)


@pytest.mark.parametrize("length,padding", [(0, 16), (3, 13), (16, 0), (4, 1028), (4096, 12)])
def test_authenticated_malformed_metadata_is_rejected(length, padding):
    auth = bytes(range(256))
    # Authenticated fixture with explicitly invalid length/padding, independent framing.
    plain = struct.pack("<qqQii", 1, 2, 3, 1, length) + bytes(4) + bytes(padding)
    plain += bytes(-len(plain) % 16)
    message_key = hashlib.sha256(auth[96:128] + plain).digest()[8:24]
    key, iv = crypto.message_aes(auth, message_key, incoming=True)
    packet = crypto.sha1(auth)[-8:] + message_key + crypto.ige(plain, key, iv)
    with pytest.raises(SerializationError):
        crypto.decrypt(auth, packet, 2)


def test_srp_password_proof_matches_independent_server_algebra():
    p = crypto.DH_PRIME
    g = 3
    salt1, salt2 = b"first-salt", b"second-salt"
    password = "test-only password, never a real account"

    def H(value):
        return hashlib.sha256(value).digest()

    def pad(value):
        return value.to_bytes(256, "big")

    ph1 = H(salt2 + H(salt1 + password.encode() + salt1) + salt2)
    x = int.from_bytes(H(salt2 + hashlib.pbkdf2_hmac("sha512", ph1, salt1, 100000) + salt2), "big")
    verifier = pow(g, x, p)
    k = int.from_bytes(H(pad(p) + pad(g)), "big")
    b = int.from_bytes(secrets.token_bytes(256), "big")
    B = (k * verifier + pow(g, b, p)) % p
    algorithm = types.PasswordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow(
        salt1=salt1, salt2=salt2, g=g, p=pad(p)
    )
    parameters = types.account.Password(
        new_algo=types.PasswordKdfAlgoUnknown(),
        new_secure_algo=types.SecurePasswordKdfAlgoUnknown(),
        secure_random=b"",
        current_algo=algorithm,
        srp_B=pad(B),
        srp_id=42,
    )
    proof = compute_check(parameters, password)
    A = int.from_bytes(proof.A, "big")
    u = int.from_bytes(H(proof.A + pad(B)), "big")
    shared = pow((A * pow(verifier, u, p)) % p, b, p)
    expected = H(
        crypto.xor(H(pad(p)), H(pad(g))) + H(salt1) + H(salt2) + proof.A + pad(B) + H(pad(shared))
    )
    assert proof.srp_id == 42 and hmac.compare_digest(proof.M1, expected)
    parameters.srp_B = bytes(256)
    with pytest.raises(SerializationError):
        compute_check(parameters, password)
