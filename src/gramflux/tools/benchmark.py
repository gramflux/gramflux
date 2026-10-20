"""Reproducible local codec benchmark. No network or comparative marketing claims."""

import argparse
import gc
import importlib.metadata
import json
import platform
import statistics
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

from gramflux.tl import Codec
from gramflux.tl.generated.objects import InputFile as GeneratedInputFile


def measure(operation: Callable[[], Any], iterations: int, rounds: int) -> dict[str, Any]:
    for _ in range(100):
        operation()
    samples = []
    for _ in range(rounds):
        gc.collect()
        start = time.perf_counter_ns()
        for _ in range(iterations):
            operation()
        samples.append((time.perf_counter_ns() - start) / iterations)
    tracemalloc.start()
    for _ in range(min(iterations, 1000)):
        operation()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "median_ns_per_operation": statistics.median(samples),
        "round_ns_per_operation": samples,
        "tracemalloc_peak_bytes": peak,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=10000)
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    if args.iterations < 1 or args.rounds < 1:
        parser.error("iterations and rounds must be positive")
    codec = Codec()
    own = GeneratedInputFile(id=123456, parts=10, name="example.bin", md5_checksum="0" * 32)
    data = codec.encode(own)
    if codec.decode(data) != own:
        raise RuntimeError("benchmark input failed round-trip check")

    operations = {
        "gramflux_encode": lambda: codec.encode(own),
        "gramflux_decode": lambda: codec.decode(data),
    }
    print(
        json.dumps(
            {
                "kind": "local microbenchmark; no network or file transfer measured",
                "python": platform.python_version(),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "versions": {
                    name: importlib.metadata.version(name) for name in ["gramflux", "cryptography"]
                },
                "input": {
                    "type": "inputFile",
                    "serialized_bytes": len(data),
                    "fields": "fixed synthetic values",
                },
                "iterations": args.iterations,
                "rounds": args.rounds,
                "results": {
                    name: measure(fn, args.iterations, args.rounds)
                    for name, fn in operations.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
