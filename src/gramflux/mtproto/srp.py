"""Telegram's published SRP password proof; PBKDF2/hashlib and validated DH prime."""

import hashlib
import secrets
from typing import Any

from gramflux.errors import SerializationError, UnsupportedFeature
from gramflux.raw import types

from .crypto import sha256, validate_dh, xor


def compute_check(parameters: Any, password: str) -> Any:
    algo = parameters.current_algo
    if algo.definition.name != "passwordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow":
        raise UnsupportedFeature("unsupported Telegram password KDF")
    p = validate_dh(algo.p, algo.g)
    if parameters.srp_B is None or parameters.srp_id is None:
        raise SerializationError("missing SRP challenge")
    remote = int.from_bytes(parameters.srp_B, "big")
    if not 0 < remote < p or len(parameters.srp_B) > 256:
        raise SerializationError("invalid SRP public challenge")

    def padded(value: int) -> bytes:
        return value.to_bytes(256, "big")

    password_hash = sha256(algo.salt1 + password.encode() + algo.salt1)
    password_hash = sha256(algo.salt2 + password_hash + algo.salt2)
    password_hash = hashlib.pbkdf2_hmac("sha512", password_hash, algo.salt1, 100000)
    x = int.from_bytes(sha256(algo.salt2 + password_hash + algo.salt2), "big")
    k = int.from_bytes(sha256(algo.p + padded(algo.g)), "big")
    a = int.from_bytes(secrets.token_bytes(256), "big")
    public = pow(algo.g, a, p)
    validate_dh(algo.p, algo.g, padded(public))
    u = int.from_bytes(sha256(padded(public) + padded(remote)), "big")
    base = (remote - k * pow(algo.g, x, p)) % p
    validate_dh(algo.p, algo.g, padded(base))
    if not u:
        raise SerializationError("invalid SRP scrambling parameter")
    secret = pow(base, a + u * x, p)
    key = sha256(padded(secret))
    proof = sha256(
        xor(sha256(algo.p), sha256(padded(algo.g)))
        + sha256(algo.salt1)
        + sha256(algo.salt2)
        + padded(public)
        + padded(remote)
        + key
    )
    return types.InputCheckPasswordSRP(srp_id=parameters.srp_id, A=padded(public), M1=proof)
