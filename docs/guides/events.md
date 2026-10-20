# Events and filters

Register handlers before connecting. Returning from the context disconnects; use
`run_until_disconnected()` to receive indefinitely or await your application's own
shutdown event.

```python
@client.on_message(filters.incoming & filters.text & filters.regex(r"^hello"))
async def hello(event):
    print(event.chat_id)  # event.text contains private content; log deliberately


@client.on_message(filters.chat(-1001234567890), edited=True)
async def edited(event):
    print("An existing message changed")
```

`MessageEvent` exposes `message` (backend Message), `text`, `outgoing`, `chat_id`,
`sender_id`, `edited`. Marked chat IDs follow Telethon conventions: users positive,
groups negative, channels prefixed by -100. Raw access hashes are still required for
some operations; filters do not resolve peers.

Filters support `&`, `|`, `~`, with short-circuit evaluation: `text`, `incoming`,
`outgoing`, `all_messages`, `chat(*ids)`, `sender(*ids)`, `regex(pattern, flags=0)`.
Regex evaluation is synchronous; avoid pathological patterns on hostile input.

One worker awaits each callback sequentially, in registration order for each event.
Slow handlers delay subsequent events. The local queue is bounded and applies
backpressure; the backend has its own queue that is not yet bounded. Do not claim
unlimited-throughput handling or bounded total update memory.

Failures log only exception class, never contents/tracebacks. Optional async
`on_handler_error(event, exception)` can inspect failures; it is responsible for its
own safe logging. Other handlers still run. A callback raising CancelledError without
worker cancellation is reported like a handler failure; client shutdown cancels the
worker. Shutdown discards its pending in-memory queue, without exactly-once delivery.

Callbacks should signal the main task to disconnect, rather than await `disconnect()`
from inside the dispatcher. Use an asyncio.Event for graceful application shutdown.
Backend update counters, gaps, differences and duplicate handling are delegated to
Telethon; live recovery and crash-consistent callback delivery remain unverified.
