"""Reproduce the native AES-IGE XOR optimization locally; no network comparison."""

import argparse
import importlib.metadata
import json
import platform
import statistics
import time
from collections.abc import Callable
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from gramflux.mtproto.crypto import ige


def bytewise_ige(data: bytes, key: bytes, iv: bytes) -> bytes:
    """GramFlux's pre-optimization implementation, retained only as a local baseline."""
    context = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    previous_cipher, previous_plain = iv[:16], iv[16:]
    output = bytearray()

    def xor(left: bytes, right: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(left, right, strict=True))

    for offset in range(0, len(data), 16):
        block = data[offset : offset + 16]
        encrypted = xor(context.update(xor(block, previous_cipher)), previous_plain)
        output.extend(encrypted)
        previous_cipher, previous_plain = encrypted, block
    context.finalize()
    return bytes(output)


def measure(operation: Callable[[], bytes], rounds: int) -> dict[str, Any]:
    samples = []
    for _ in range(rounds):
        start = time.perf_counter()
        operation()
        samples.append(time.perf_counter() - start)
    return {"seconds": samples, "median_seconds": statistics.median(samples)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=512 * 1024)
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    if not 16 <= args.size <= 16 * 1024 * 1024 or args.size % 16 or not 1 <= args.rounds <= 100:
        parser.error("size must be 16-byte aligned, 16..16777216; rounds must be 1..100")
    data, key, iv = bytes(args.size), bytes(range(32)), bytes(range(32))
    original = bytewise_ige(data, key, iv)
    optimized = ige(data, key, iv)
    if original != optimized or ige(optimized, key, iv, decrypt=True) != data:
        raise RuntimeError("native benchmark correctness check failed")
    result = {
        "kind": "local AES-IGE: bytewise vs integer XOR; synthetic input, NOT Telegram throughput",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "versions": {
            name: importlib.metadata.version(name) for name in ("gramflux", "cryptography")
        },
        "openssl": default_backend().openssl_version_text(),
        "bytes": args.size,
        "rounds": args.rounds,
        "original": measure(lambda: bytewise_ige(data, key, iv), args.rounds),
        "optimized": measure(lambda: ige(data, key, iv), args.rounds),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
