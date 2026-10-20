"""Join pure codec/cryptographic work on cancellation before releasing admission."""

import asyncio
from collections.abc import Callable
from typing import Any


async def compute(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.wait({task})
            except asyncio.CancelledError:
                continue
        # Cancellation wins over a simultaneous worker error; retrieve it safely.
        if not task.cancelled():
            task.exception()
        raise
