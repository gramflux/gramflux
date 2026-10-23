---
title: Updates and delivery guarantees
description: Follow a Telegram update from the socket through synchronization, filtering, callbacks and checkpointing.
---

# Updates and delivery guarantees

An update arriving on a socket is only the beginning of event processing. GramFlux
must validate it, reconcile Telegram's state counters, build the applicable event,
run subscriptions and preserve an appropriate checkpoint. These stages explain
both handler behavior and the limits of recovery.

## Follow the processing path

1. The native receiver decrypts and validates the incoming protocol message.
2. The update engine examines global/channel state, duplicates and applicable gaps.
3. Supported difference recovery reconciles missing server state.
4. Supported native updates become high-level events and/or raw update events.
5. The dispatcher evaluates subscription kind, filters, priority and registration order.
6. Eligible callbacks are awaited; update progress crosses the documented handler boundary.

Envelope deduplication and Telegram message-box counters are separate concerns.
Application callbacks should not implement their own pts arithmetic. See
[update-state internals](../design/update-state.md) for the exact implemented rules.

## Register first, connect second

```python
from gramflux import filters


@client.on_message(filters.incoming & filters.text)
async def receive(event):
    print(event.chat_id)


async with client:
    await client.run_until_disconnected()
```

This fragment assumes an authorized session and a constructed Client. Registering
after connecting can miss startup delivery. Returning from the context disconnects;
a handler registration does not keep the main task alive by itself.

## Ordering is explicit

One worker awaits handlers sequentially. Smaller `priority` values run first, and
registration order breaks ties. Registration changes affect subsequent dispatch
snapshots. `StopPropagation` stops remaining callbacks for the current event; it does
not stop the receiver or discard future events.

An exception in one callback is reported and does not prevent other eligible
callbacks from running. Configure `on_handler_error` for application reporting.
Default diagnostics omit private payloads and exception contents; your custom
reporter must also avoid leaking those values.

## Slow handlers create backpressure

A handler that awaits slow external work delays subsequent events. Queues have
count/byte bounds, not unlimited retention. Overflow fails explicitly rather than
silently treating lost updates as successful processing. Raising queue limits is
not a substitute for understanding an overloaded consumer.

An application may hand work to a bounded queue, but then the callback can finish
before that work completes. GramFlux cannot include your separate worker's outcome
in its handler boundary. Use application-owned durable jobs/idempotency if this
changes your reliability requirements; there is no built-in transactional outbox.

## Checkpointing is not exactly-once delivery

Shutdown cancellation does not commit an update merely because it was enqueued.
Clean snapshots support recovery, but partial difference processing and process
crashes can still produce replayed callbacks. There is no durable exactly-once
callback journal and no transaction coupling a callback's external side effect to
Telegram update state.

If duplicate processing is costly, design an application key appropriate to the
actual event. A bare message ID is insufficient across different conversations;
edits and callbacks also have different identities. Avoid claiming deduplication
for every event with a single universal key.

## Raw events preserve the same boundaries

`on_raw_update` exposes accepted native Update constructors; it is not a bypass
around synchronization or a promise of secret-chat/qts support. Some workflows,
too-long differences and missing channel access metadata fail explicitly. Consult
the [event quick reference](../quick-references/events.md) and
[compatibility matrix](../design/compatibility.md) before selecting an update family.

For shutdown, signal your main task and let it leave the Client context. Do not
await dispatcher shutdown from inside its own callback. See
[lifecycle and shutdown](../guides/lifecycle.md).
