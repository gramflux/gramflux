"""RSA_PAD + validated DH authorization key creation, per Telegram's specification."""

import hmac
import math
import secrets
import struct
import time
from dataclasses import dataclass, field
from typing import Any

from gramflux.errors import SerializationError, TransportError
from gramflux.tl.codec import Reader

from . import crypto, protocol
from .connection import Connection
from .workers import compute


@dataclass(frozen=True, slots=True)
class AuthorizationKey:
    key: bytes = field(repr=False)
    salt: int
    time_offset: float


def factor(pq: int) -> tuple[int, int]:
    if not 15 <= pq < 2**64 or not pq % 2:
        raise SerializationError("invalid pq")
    for _ in range(16):
        x = y = secrets.randbelow(pq - 3) + 2
        c = secrets.randbelow(pq - 1) + 1
        for _ in range(200000):
            x = (x * x + c) % pq
            y = (y * y + c) % pq
            y = (y * y + c) % pq
            divisor = math.gcd(abs(x - y), pq)
            if divisor == pq:
                break
            if divisor > 1:
                p, q = sorted((divisor, pq // divisor))
                if p * q == pq and p != q and p.bit_length() <= 32 and q.bit_length() <= 32:
                    return p, q
                raise SerializationError("invalid pq factorization")
    raise SerializationError("pq factorization budget exhausted")


async def create_key(connection: Connection, dc_id: int, *, test: bool = False) -> AuthorizationKey:
    previous_id = 0

    async def exchange(name: str, **fields: Any) -> Any:
        nonlocal previous_id
        body = protocol.CODEC.encode(protocol.object(name, **fields))
        ident = max(previous_id + 4, (time.time_ns() * 2**32 // 10**9) & ~3)
        if ident & 0xFFFFFFFF == 0:
            ident += 4
        previous_id = ident
        await connection.send(struct.pack("<QQi", 0, ident, len(body)) + body)
        payload = await connection.receive()
        if len(payload) < 24 or payload[:8] != bytes(8):
            raise TransportError("invalid unencrypted handshake envelope")
        response_id, length = struct.unpack("<Qi", payload[8:20])
        if response_id % 4 != 1 or length != len(payload) - 20 or length < 4 or length % 4:
            raise SerializationError("invalid handshake response metadata")
        return protocol.CODEC.decode(payload[20:])

    nonce = secrets.token_bytes(16)
    response = await exchange("req_pq_multi", nonce=nonce)
    if (
        response.definition.name != "resPQ"
        or response.nonce != nonce
        or not 1 <= len(response.pq) <= 8
    ):
        raise SerializationError("invalid resPQ response")
    server_nonce = response.server_nonce
    key = crypto.trusted_rsa(test=test)
    fingerprint = crypto.rsa_fingerprint(key)
    if fingerprint not in response.server_public_key_fingerprints:
        raise SerializationError("Telegram RSA fingerprint is not pinned")
    p, q = await compute(factor, int.from_bytes(response.pq, "big"))
    p_bytes, q_bytes = (
        p.to_bytes((p.bit_length() + 7) // 8, "big"),
        q.to_bytes((q.bit_length() + 7) // 8, "big"),
    )
    new_nonce = secrets.token_bytes(32)
    inner = protocol.CODEC.encode(
        protocol.object(
            "p_q_inner_data_dc",
            pq=response.pq,
            p=p_bytes,
            q=q_bytes,
            nonce=nonce,
            server_nonce=server_nonce,
            new_nonce=new_nonce,
            dc=dc_id + (10000 if test else 0),
        )
    )
    encrypted = await compute(crypto.rsa_pad, inner, key)
    answer = await exchange(
        "req_DH_params",
        nonce=nonce,
        server_nonce=server_nonce,
        p=p_bytes,
        q=q_bytes,
        public_key_fingerprint=fingerprint,
        encrypted_data=encrypted,
    )
    if (
        answer.definition.name != "server_DH_params_ok"
        or answer.nonce != nonce
        or answer.server_nonce != server_nonce
    ):
        raise SerializationError("invalid server DH response")
    temporary_key, iv = crypto.temporary_aes(new_nonce, server_nonce)
    decrypted = await compute(crypto.ige, answer.encrypted_answer, temporary_key, iv, decrypt=True)
    reader = Reader(memoryview(decrypted[20:]))
    dh = protocol.CODEC._read(reader, "Object", 0)
    if not 0 <= len(decrypted) - 20 - reader.offset <= 15 or not hmac.compare_digest(
        decrypted[:20], crypto.sha1(decrypted[20 : 20 + reader.offset])
    ):
        raise SerializationError("invalid server DH answer hash")
    if (
        dh.definition.name != "server_DH_inner_data"
        or dh.nonce != nonce
        or dh.server_nonce != server_nonce
    ):
        raise SerializationError("invalid server DH inner nonces")
    offset = dh.server_time - time.time()
    public, auth = await compute(crypto.dh_exchange, dh.dh_prime, dh.g, dh.g_a)
    client = protocol.CODEC.encode(
        protocol.object(
            "client_DH_inner_data", nonce=nonce, server_nonce=server_nonce, retry_id=0, g_b=public
        )
    )
    padded = crypto.sha1(client) + client
    padded += secrets.token_bytes(-len(padded) % 16)
    encrypted = await compute(crypto.ige, padded, temporary_key, iv)
    result = await exchange(
        "set_client_DH_params", nonce=nonce, server_nonce=server_nonce, encrypted_data=encrypted
    )
    if result.nonce != nonce or result.server_nonce != server_nonce:
        raise SerializationError("invalid DH confirmation nonces")
    if result.definition.name != "dh_gen_ok":
        raise TransportError("DH key generation rejected; restart explicitly")
    expected = crypto.sha1(new_nonce + b"\x01" + crypto.sha1(auth)[:8])[-16:]
    if not hmac.compare_digest(result.new_nonce_hash1, expected):
        raise SerializationError("invalid authorization-key confirmation")
    salt = int.from_bytes(crypto.xor(new_nonce[:8], server_nonce[:8]), "little", signed=True)
    return AuthorizationKey(auth, salt, offset)
