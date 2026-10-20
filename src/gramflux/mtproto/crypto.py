"""MTProto 2.0 glue around OpenSSL-backed AES and DH; no alternative protocol."""

import hashlib
import hmac
import json
import secrets
import struct
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dh, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from gramflux.errors import SerializationError

TRUST = json.loads((Path(__file__).parents[1] / "tl/data/trust.json").read_text())
DH_PRIME = int(TRUST["dh_prime_hex"], 16)


def sha1(data: bytes) -> bytes:
    return hashlib.sha1(data, usedforsecurity=False).digest()


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def xor(left: bytes, right: bytes) -> bytes:
    if len(left) != len(right):
        raise ValueError("XOR operand lengths differ")
    return (int.from_bytes(left, "big") ^ int.from_bytes(right, "big")).to_bytes(len(left), "big")


def ige(data: bytes, key: bytes, iv: bytes, *, decrypt: bool = False) -> bytes:
    if len(key) not in (16, 32) or len(iv) != 32 or not data or len(data) % 16:
        raise SerializationError("invalid AES-IGE parameters")
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    context = cipher.decryptor() if decrypt else cipher.encryptor()
    previous_cipher, previous_plain = iv[:16], iv[16:]
    output = bytearray()
    for offset in range(0, len(data), 16):
        block = data[offset : offset + 16]
        if decrypt:
            plain = xor(context.update(xor(block, previous_plain)), previous_cipher)
            previous_cipher, previous_plain = block, plain
            output.extend(plain)
        else:
            encrypted = xor(context.update(xor(block, previous_cipher)), previous_plain)
            previous_cipher, previous_plain = encrypted, block
            output.extend(encrypted)
    context.finalize()
    return bytes(output)


def tl_bytes(data: bytes) -> bytes:
    prefix = bytes([len(data)]) if len(data) < 254 else b"\xfe" + len(data).to_bytes(3, "little")
    return prefix + data + bytes(-(len(prefix) + len(data)) % 4)


def rsa_fingerprint(key: rsa.RSAPublicKey) -> int:
    values = key.public_numbers()
    data = tl_bytes(values.n.to_bytes(256, "big")) + tl_bytes(
        values.e.to_bytes((values.e.bit_length() + 7) // 8, "big")
    )
    return int.from_bytes(sha1(data)[-8:], "little", signed=True)


def trusted_rsa(*, test: bool = False) -> rsa.RSAPublicKey:
    key = serialization.load_pem_public_key(
        TRUST["test_rsa_pem" if test else "production_rsa_pem"].encode()
    )
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size != 2048:
        raise SerializationError("invalid pinned Telegram public key")
    return key


def rsa_pad(data: bytes, key: rsa.RSAPublicKey) -> bytes:
    if len(data) > 144 or key.key_size != 2048:
        raise SerializationError("invalid RSA_PAD input")
    numbers = key.public_numbers()
    padded = data + secrets.token_bytes(192 - len(data))
    for _ in range(128):
        temporary = secrets.token_bytes(32)
        encrypted = ige(padded[::-1] + sha256(temporary + padded), temporary, bytes(32))
        value = int.from_bytes(xor(temporary, sha256(encrypted)) + encrypted, "big")
        if value < numbers.n:
            return pow(value, numbers.e, numbers.n).to_bytes(256, "big")
    raise SerializationError("RSA_PAD randomness rejection budget exhausted")


def validate_dh(prime: bytes, generator: int, public: bytes | None = None) -> int:
    p = int.from_bytes(prime, "big")
    # Strict official known-prime whitelist. Unknown primes fail closed, never guessed safe.
    conditions = {
        2: p % 8 == 7,
        3: p % 3 == 2,
        4: True,
        5: p % 5 in (1, 4),
        6: p % 24 in (19, 23),
        7: p % 7 in (3, 5, 6),
    }
    if len(prime) != 256 or p != DH_PRIME or not conditions.get(generator, False):
        raise SerializationError("untrusted DH parameters")
    if public is not None:
        value = int.from_bytes(public, "big")
        bound = 1 << (2048 - 64)
        if len(public) > 256 or not bound < value < p - bound:
            raise SerializationError("unsafe DH public value")
    return p


def dh_exchange(prime: bytes, generator: int, remote: bytes) -> tuple[bytes, bytes]:
    p = validate_dh(prime, generator, remote)
    parameters = dh.DHParameterNumbers(p, generator)
    private = parameters.parameters().generate_private_key()
    public = private.public_key().public_numbers().y.to_bytes(256, "big")
    validate_dh(prime, generator, public)
    peer = dh.DHPublicNumbers(int.from_bytes(remote, "big"), parameters).public_key()
    return public, private.exchange(peer).rjust(256, b"\0")


def temporary_aes(new_nonce: bytes, server_nonce: bytes) -> tuple[bytes, bytes]:
    if len(new_nonce) != 32 or len(server_nonce) != 16:
        raise SerializationError("invalid handshake nonce length")
    a, b = sha1(new_nonce + server_nonce), sha1(server_nonce + new_nonce)
    return a + b[:12], b[12:] + sha1(new_nonce + new_nonce) + new_nonce[:4]


def message_aes(auth: bytes, message_key: bytes, *, incoming: bool) -> tuple[bytes, bytes]:
    x = 8 if incoming else 0
    a = sha256(message_key + auth[x : x + 36])
    b = sha256(auth[40 + x : 76 + x] + message_key)
    return a[:8] + b[8:24] + a[24:], b[:8] + a[8:24] + b[24:]


@dataclass(frozen=True, slots=True)
class Envelope:
    salt: int
    session: int
    message_id: int
    sequence: int
    body: bytes = field(repr=False)


def encrypt(auth: bytes, envelope: Envelope, *, incoming: bool = False) -> bytes:
    if len(auth) != 256 or not envelope.body or len(envelope.body) % 4:
        raise SerializationError("invalid encrypted message input")
    plain = (
        struct.pack(
            "<qqQii",
            envelope.salt,
            envelope.session,
            envelope.message_id,
            envelope.sequence,
            len(envelope.body),
        )
        + envelope.body
    )
    padding = 12 + (-(len(plain) + 12) % 16)
    plain += secrets.token_bytes(padding)
    x = 8 if incoming else 0
    message_key = sha256(auth[88 + x : 120 + x] + plain)[8:24]
    key, iv = message_aes(auth, message_key, incoming=incoming)
    return sha1(auth)[-8:] + message_key + ige(plain, key, iv)


def decrypt(auth: bytes, data: bytes, session: int, *, incoming: bool = True) -> Envelope:
    if (
        len(auth) != 256
        or len(data) < 72
        or (len(data) - 24) % 16
        or not hmac.compare_digest(data[:8], sha1(auth)[-8:])
    ):
        raise SerializationError("invalid encrypted envelope")
    message_key = data[8:24]
    key, iv = message_aes(auth, message_key, incoming=incoming)
    plain = ige(data[24:], key, iv, decrypt=True)
    x = 8 if incoming else 0
    if not hmac.compare_digest(message_key, sha256(auth[88 + x : 120 + x] + plain)[8:24]):
        raise SerializationError("MTProto message key mismatch")
    salt, remote_session, ident, sequence, length = struct.unpack("<qqQii", plain[:32])
    if (
        remote_session != session
        or length < 4
        or length % 4
        or not 12 <= len(plain) - 32 - length <= 1024
        or sequence < 0
    ):
        raise SerializationError("invalid MTProto plaintext metadata")
    return Envelope(salt, remote_session, ident, sequence, plain[32 : 32 + length])
