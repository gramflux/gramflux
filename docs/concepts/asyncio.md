---
title: Asyncio and concurrency
description: Coroutines, async iterators, event loops, background work, timeouts and cancellation in GramFlux.
---

# Asyncio and concurrency

GramFlux uses Python's asyncio directly. An asynchronous operation yields control
while waiting for I/O, allowing other tasks on the same event loop to run. It does
not create a thread per request and does not offer a synchronous compatibility shim.

## Calling a coroutine

Calling an `async def` function creates a coroutine. `await` executes it and obtains
its result. Access attributes on the result, not on the unawaited coroutine:

```python
me = await client.get_me()
print(me.id)
```

In a script, create one event loop at the application boundary:

```python
import asyncio


async def main():
    await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
```

A notebook or async web framework may already run a loop. In its async entry point,
use `await` directly. Calling `asyncio.run()` inside a running loop raises an error;
creating a second loop does not make a connected Client transferable between loops.

## Iterators are a different API shape

An async iterator produces items over time. Factories such as `iter_history` are
used directly in `async for`; do not await the iterator itself:

```python
async for message in client.iter_history("me", limit=25, page_size=10):
    print(message.id)
```

By comparison, `await client.get_history("me", limit=25)` collects a finite list.
The iterator fetches pages on demand. Validation and network errors can arise during
iteration, and a later page is not guaranteed by the success of an earlier one.

## Run independent work together

Structured concurrency makes task lifetime explicit:

```python
import asyncio

async with asyncio.TaskGroup() as group:
    me_task = group.create_task(client.get_me())
    contacts_task = group.create_task(client.get_contacts())

me = me_task.result()
contacts = contacts_task.result()
```

Both calls must run on the Client's own loop and require authorization. A TaskGroup
failure cancels its sibling tasks; that is the application's chosen task-group
policy. It is separate from GramFlux's request correlation: cancelling a standalone
request does not implicitly cancel unrelated callers sharing the connection.

Limit application concurrency instead of creating one task for every item in a
large dataset. `Config.max_concurrent_requests` bounds RPC admission; it does not
bound the number of tasks or objects your application allocates before admission.

## Keep blocking work off the loop

Do not call `time.sleep()` in a handler. Use `await asyncio.sleep()`. For a blocking
application function, use `await asyncio.to_thread(function, argument)` where thread
execution is appropriate. Do not move a connected Client into that worker thread.
Pure Python CPU-heavy work can still contend for the interpreter; choose a process
boundary when that is the actual bottleneck.

Default terminal login reads use worker threads. Cancelling the awaiting coroutine
cannot interrupt an OS terminal read already executing in that thread. Supply
cancellation-aware `LoginPrompts` callbacks for an application UI.

## Wait without freezing other tasks

`await client.run_until_disconnected()` suspends its caller until disconnection.
Other scheduled tasks continue. It does not automatically supervise unrelated tasks
or make their exceptions visible to your main task. Use a TaskGroup or an explicit
application supervisor when you need that behavior.

See the [lifecycle guide](../guides/lifecycle.md) for shutdown ownership and why a
handler should signal the main task rather than disconnect its own dispatcher.

## Cancellation is not a rollback

An application timeout may surround a read:

```python
import asyncio

try:
    async with asyncio.timeout(10):
        me = await client.get_me()
except TimeoutError:
    print("The identity lookup did not complete before the deadline")
```

The outer deadline is separate from the configured per-request deadline. Neither
can retract a mutation Telegram already accepted. Preserve cancellation, clean up
owned resources with context managers/finally blocks, and reconcile uncertain writes
before deciding whether to retry. Read [error handling](../guides/errors.md).
