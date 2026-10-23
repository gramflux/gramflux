---
title: Client lifecycle and shutdown
description: Own connection lifetime explicitly, separate authorization, stop handlers safely and handle disconnection.
---

# Client lifecycle and shutdown

Use one Client on one asyncio event loop. Construction stores configuration and
session intent; it does not connect or prompt. Connecting opens storage and the
native connection. Authorization is a separate account state.

## Choose the session before connecting

| Intent | Construct with | First action after connect |
| --- | --- | --- |
| Existing account | `Session.open("account")` | Perform authorized operations |
| New named login | `Session.create("account")` | Explicitly call `login()` |
| Incomplete named login | `Session.open("account", require_authorized=False)` | Resume `login()` or the saved low-level step |
| Process-local login | `Session.temporary()` | Explicitly authorize; no file is saved |

Opening a completed session never silently replaces it with a new login. A missing
file, an existing create target or incomplete authorization has a distinct failure.
See [sessions](sessions.md) and [authentication](authentication.md).

## Prefer an async context

```python
from gramflux import Client, Session

async with Client(Session.open("account"), api_id=api_id, api_hash=api_hash) as client:
    me = await client.get_me()
```

Supply your own credentials. The context awaits connection on entry and disconnect
on exit, including exceptional exit. A successfully opened socket does not itself
prove completed account authorization. `client.connected` and
`await client.is_authorized()` answer different questions.

For manual ownership, put disconnect in a finally block:

```python
await client.connect()
try:
    me = await client.get_me()
finally:
    await client.disconnect()
```

Do not rely on interpreter shutdown or a destructor to commit storage and join
background tasks. Abrupt process death can interrupt operations; login checkpoints
have their separately documented commit boundaries.

## Let the main task own shutdown

This complete application opens an existing bot session. Run the bot tutorial first
to create one. A command signals shutdown; it does not stop its own dispatcher:

```python
import asyncio
import os

from gramflux import Client, Session, filters


async def main():
    stop = asyncio.Event()
    operator_id = int(os.environ["GRAMFLUX_OPERATOR_ID"])
    client = Client(
        Session.open("bot"),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    )

    @client.on_message(
        filters.incoming & filters.private & filters.sender(operator_id) & filters.command("stop")
    )
    async def request_shutdown(event):
        stop.set()

    async with client:
        async with asyncio.TaskGroup() as group:
            wait_for_stop = group.create_task(stop.wait())
            wait_for_disconnect = group.create_task(client.run_until_disconnected())
            await asyncio.wait(
                {wait_for_stop, wait_for_disconnect},
                return_when=asyncio.FIRST_COMPLETED,
            )
            wait_for_stop.cancel()
            wait_for_disconnect.cancel()


if __name__ == "__main__":
    asyncio.run(main())
```

Set GRAMFLUX_OPERATOR_ID to the numeric account ID you authorize to stop the bot.
Alternatively replace the handler with your framework's shutdown signal. Pending
requests/tasks must have an owner; cancelling a wait does not undo a remote mutation.

## Disconnection is an application decision point

Initial connection retries are bounded by configuration. GramFlux does not promise
transparent replay of outstanding application RPCs or automatic recovery of every
account workflow. Inspect the failure and reconcile uncertain writes before creating
a replacement connection/request. A server migration response does not authorize
blindly reissuing an operation to any data center.

See [errors](errors.md), [asyncio](../concepts/asyncio.md) and
[operational notes](operations.md) before writing a long-running supervisor.
