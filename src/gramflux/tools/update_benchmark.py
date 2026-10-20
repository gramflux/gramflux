"""Local event metadata cost; compares our previous full snapshot with native emit."""

import argparse
import asyncio
import gc
import json
import platform
import statistics
import time
import tracemalloc
from collections.abc import Awaitable, Callable
from typing import Any

from gramflux.backend import NativeBackend
from gramflux.config import Config
from gramflux.mtproto.updates import NativeEvent, UpdateEngine
from gramflux.peer_utils import get_peer_id
from gramflux.raw import types


async def measure(operation: Callable[[], Awaitable[None]], count: int) -> dict[str, Any]:
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        for _ in range(count):
            await operation()
        samples.append(time.perf_counter() - start)
    gc.collect()
    tracemalloc.start()
    try:
        for _ in range(100):
            await operation()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {"seconds": samples, "median_seconds": statistics.median(samples), "peak_bytes": peak}


async def benchmark_size(size: int, count: int) -> dict[str, Any]:
    backend = NativeBackend(1234, "a" * 32, Config())
    backend.entities = {i: types.User(id=i, access_hash=i) for i in range(1, size + 1)}
    last: NativeEvent | None = None

    async def receive(event: NativeEvent) -> None:
        nonlocal last
        last = event

    backend.add_event_handler(receive)
    engine = UpdateEngine(backend)
    message = types.Message(
        id=1,
        peer_id=types.PeerUser(user_id=12),
        from_id=types.PeerUser(user_id=13),
        message="synthetic benchmark",
        date=100,
    )

    async def old_snapshot() -> None:
        # GramFlux's previous emit path, retained only as a local baseline.
        peer = message.peer_id
        private = isinstance(peer, types.PeerUser)
        entity = engine.entities.get(get_peer_id(peer))
        group = isinstance(peer, types.PeerChat) or bool(getattr(entity, "megagroup", False))
        event = NativeEvent(
            message,
            False,
            dict(engine.entities),
            private,
            group,
            isinstance(peer, types.PeerChannel),
        )
        for callback in backend._handlers:
            await callback(event)

    async def native_emit() -> None:
        await engine.emit(message)

    await old_snapshot()
    assert last is not None and len(last._entities) == size
    await native_emit()
    assert last is not None and set(last._entities) == {12, 13}
    return {
        "cached_entities": size,
        "previous_full_snapshot": await measure(old_snapshot, count),
        "native_relevant_snapshot": await measure(native_emit, count),
    }


async def benchmark(count: int) -> dict[str, Any]:
    return {
        "kind": "local event emission; no network or competitor comparison",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "events_per_round": count,
        "rounds": 5,
        "results": [await benchmark_size(size, count) for size in (64, 1024, 4096)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=10000)
    args = parser.parse_args()
    if not 1 <= args.events <= 100000:
        parser.error("events must be 1..100000")
    print(json.dumps(asyncio.run(benchmark(args.events)), indent=2))


if __name__ == "__main__":
    main()
