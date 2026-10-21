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

`MessageEvent` exposes `message` (native Message), `text`, `outgoing`, `chat_id`,
`sender_id`, `edited`, `chat_type`, `client`. Marked chat IDs use the documented numeric convention: users positive,
groups negative, channels prefixed by -100. Raw access hashes are still required for
some operations; filters do not resolve peers.

Filters support `&`, `|`, `~`, with short-circuit evaluation: `text`, `incoming`,
`outgoing`, `all_messages`, `chat(*ids)`, `sender(*ids)`, `regex(pattern, flags=0)`,
`private`, `group`, `channel`, `media`, `photo`, `document`, `video`, `audio`, `voice`,
`sticker`, `command(*names, prefix="/", username=None, case_sensitive=False)`.
`text` includes captions; media predicates inspect native media properties. Commands
match only the first token and do not parse arguments. Supply the bot username
without @ to reject commands addressed to another bot; without it any address matches.
Regex evaluation is synchronous; avoid pathological patterns on hostile input.

One worker awaits each callback sequentially. `priority` defaults to zero; lower
numbers run first, with registration order preserved for ties. Dispatch begins only
after connection, authorization checks and initial session saving have completed.
`client.off_message(callback)` removes matching registrations and returns their count;
registration changes affect the next event, not the current dispatch snapshot.
Raising `gramflux.errors.StopPropagation` stops other callbacks for the current event
without losing subsequent events.
Slow handlers delay later events. The native receive queue and dispatcher queue are
bounded. A full native receive queue disconnects with an explicit synchronization
failure instead of silently discarding updates or deadlocking a handler's RPC response.
This bounds queue counts, not total process RSS or arbitrary application retention.

Failures log only exception class, never contents/tracebacks. Optional async
`on_handler_error(event, exception)` can inspect failures; it is responsible for its
own safe logging. Other handlers still run. A callback raising CancelledError without
worker cancellation is reported like a handler failure; client shutdown cancels the
worker. Shutdown cancels the native producer before stopping handlers. Native pts/seq advances
after the handler boundary completes, so an interrupted update is not committed merely
because it was enqueued. Clean-shutdown snapshots permit replay after reconnect; partial
difference batches and process crashes can still duplicate callbacks. There is no
transactional event journal or exactly-once delivery guarantee.

Callbacks should signal the main task to disconnect, rather than await `disconnect()`
from inside the dispatcher. Use an asyncio.Event for graceful application shutdown.
The native UpdateEngine handles global pts/seq gaps, difference slices, channel
differences, duplicates, short-message normalization and server session-reset recovery.
Too-long differences, missing channel access hashes and secret-chat/qts work fail
explicitly. Account-level live recovery remains unverified.
Client-bound events offer `await event.reply("text")`, `await event.edit("text")`,
`await event.delete(revoke=True)` and `await event.download("explicit-path")`.
These call the GramFlux client, preserving its deadlines and scoped deletion checks.
A reply uses the original message ID; channel deletion always needs explicit
`revoke=True`. Telegram permissions still apply. Detached events raise LifecycleError
when asked to execute actions. Raw event.message is a native dataclass; actions belong to event helpers or Client.

Message-box counters are processed independently of envelope sequence deduplication. Combined envelopes use seq_start for ordered updates. Invalid/regressive difference state, non-progressing intermediate pages and recursive channel recovery fail explicitly. See [update ordering and recovery](../design/update-state.md) for counter rules and cancellation boundaries.

Typed non-message subscriptions and bot response helpers are covered in [bot operations and events](bots-and-events.md). Error callbacks now accept the Event union. Use message-specific attributes after narrowing event type.
