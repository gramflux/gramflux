"""Local upload pipeline benchmark with explicitly simulated RPC latency, no Telegram I/O."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import platform
import statistics
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

from gramflux.files import CHUNK, disk, upload
from gramflux.raw import types


async def measure(
    source: Path,
    *,
    part_size: int,
    concurrency: int,
    latency: float,
    rounds: int,
    checksum: str,
) -> dict[str, Any]:
    size = (await disk(source.stat)).st_size
    active = maximum = calls = accepted_bytes = 0

    async def invoke(request: Any) -> bool:
        nonlocal active, maximum, calls, accepted_bytes
        active += 1
        maximum = max(maximum, active)
        calls += 1
        try:
            await asyncio.sleep(latency)
            accepted_bytes += len(request.bytes)
            return True
        finally:
            active -= 1

    async def once() -> None:
        nonlocal calls, accepted_bytes
        calls = accepted_bytes = 0
        result = await upload(invoke, source, part_size=part_size, concurrency=concurrency)
        if active or accepted_bytes != size or calls != result.parts:
            raise RuntimeError("benchmark transfer accounting failed")
        if isinstance(result, types.InputFile) and result.md5_checksum != checksum:
            raise RuntimeError("benchmark upload checksum failed")

    await once()  # warm-up and accounting check, excluded from timing
    elapsed = []
    for _ in range(rounds):
        start = time.perf_counter()
        await once()
        elapsed.append(time.perf_counter() - start)
    tracemalloc.start()
    try:
        await once()  # separate instrumented sample, excluded from throughput timing
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    median = statistics.median(elapsed)
    return {
        "concurrency": concurrency,
        "part_size": part_size,
        "round_seconds": elapsed,
        "median_seconds": median,
        "median_mib_per_second": size / 1048576 / median,
        "observed_maximum_in_flight": maximum,
        "tracemalloc_peak_bytes": peak,
        "parts": calls,
    }


def prepare_input(source: Path, size_mib: int) -> str:
    block = bytes(range(256)) * 4096
    digest = hashlib.md5(usedforsecurity=False)
    with source.open("wb") as stream:
        for _ in range(size_mib):
            stream.write(block)
            digest.update(block)
    return digest.hexdigest()


async def run(args: argparse.Namespace) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="gramflux-local-benchmark-") as directory:
        source = Path(directory) / "input.bin"
        checksum = await disk(prepare_input, source, args.size_mib)
        results = []
        for concurrency in args.concurrency:
            results.append(
                await measure(
                    source,
                    part_size=args.part_size,
                    concurrency=concurrency,
                    latency=args.latency_ms / 1000,
                    rounds=args.rounds,
                    checksum=checksum,
                )
            )
    return {
        "kind": "controlled local upload pipeline; synthetic RPC latency; NOT Telegram throughput",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "versions": {
            name: importlib.metadata.version(name) for name in ("gramflux", "cryptography")
        },
        "size_bytes": args.size_mib * 1048576,
        "simulated_latency_ms_per_rpc": args.latency_ms,
        "rounds": args.rounds,
        "memory_method": "separate tracemalloc sample; not RSS, not backend/network buffering",
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size-mib", type=int, default=4)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 4])
    parser.add_argument("--part-size", type=int, default=CHUNK)
    parser.add_argument("--latency-ms", type=float, default=2)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.size_mib <= 128 or not 1 <= args.rounds <= 100:
        parser.error("size-mib must be 1..128 and rounds 1..100")
    if not 0 <= args.latency_ms <= 1000:
        parser.error("latency-ms must be finite and within 0..1000")
    if any(not 1 <= value <= 16 for value in args.concurrency):
        parser.error("each concurrency must be 1..16")
    if not 1024 <= args.part_size <= CHUNK or args.part_size & (args.part_size - 1):
        parser.error("part-size must be a power of two within 1024..524288")
    if (args.size_mib * 1048576 + args.part_size - 1) // args.part_size > 4000:
        parser.error("input exceeds the conservative 4000-part upload limit")
    print(json.dumps(asyncio.run(run(args)), indent=2))


if __name__ == "__main__":
    main()
