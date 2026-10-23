---
title: Quick start
description: Authorize a named session, send a message, and receive updates with GramFlux.
---

# Your first client

This walkthrough creates a named session, sends a message to Saved Messages and
receives incoming text. Account operations require valid credentials and Telegram
permissions. The examples match the implemented API; live account behavior remains
unverified in the project's current validation environment.

## 1. Configure your credentials

Get your application's credentials from
[Telegram's developer portal](https://core.telegram.org/api/obtaining_api_id).
Follow the [API terms](https://core.telegram.org/api/terms).

The examples use environment variables for convenience. GramFlux accepts credentials
as arguments and does not require these particular variable names.

```bash
export GRAMFLUX_API_ID='YOUR_NUMERIC_API_ID'
export GRAMFLUX_API_HASH='YOUR_API_HASH'
```

Supply values through your application or secret manager. Do not commit them to Git.

## 2. Authorize once

Save this as `authorize.py` and run it:

```python
import asyncio
import os

from gramflux import Client, Session


async def main() -> None:
    async with Client(
        Session.create("account"),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    ) as client:
        user = await client.login()
        print(f"Authorized user ID: {user.id}")


if __name__ == "__main__":
    asyncio.run(main())
```

`Session.create` exclusively creates `account.session`. It refuses to overwrite an
existing file. `client.login()` explicitly prompts for the phone, code and two-step
password when needed, with a bounded input retry budget.

If you stop before finishing, reopen with
`Session.open("account", require_authorized=False)` and call `login()` again.
The saved login stage is resumed without sending another code. Read
[resumable login](../guides/authentication.md#resume-login-after-stopping-the-process).

## 3a. Recommended organization for new projects

The [Next-Generation API](../next-api/index.md) is available in the development checkout.
After the authorization step above, save this as `modular_client.py`. Handler definitions
remain independent of the client, and domain/resource calls use the same native engine:

```python
import asyncio
import os

from gramflux import Client, Session, filters
from gramflux.routing import Router


async def main() -> None:
    router = Router("incoming")

    @router.message(filters.incoming & filters.text)
    async def receive(event):
        print(f"Incoming text in chat {event.chat_id}")

    client = Client(
        Session.open("account"),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    )
    client.events.include(router)
    async with client:
        me = await client.account.me()
        print(f"Connected as user ID: {me.id}")
        await client.chat("me").send("Hello from GramFlux")
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
```

See [the complete modular bot example](../next-api/examples.md) for handlers in a
separate module and [migration](../next-api/migration.md) for gradual adoption.

## 3b. Existing Client style — still supported

Save this as `client.py`, then run it with the same credentials:

```python
import asyncio
import os

from gramflux import Client, Session, filters


async def main() -> None:
    client = Client(
        Session.open("account"),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    )

    @client.on_message(filters.incoming & filters.text)
    async def on_message(event):
        print(f"Incoming text in chat {event.chat_id}")

    async with client:
        me = await client.get_me()
        print(f"Connected as user ID: {me.id}")
        await client.send_message("me", "Hello from GramFlux")
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
```

Register handlers **before** connecting. `run_until_disconnected()` keeps this task
alive while other asyncio work continues. Exiting the context disconnects and joins
cleanup. Use Ctrl+C to stop the script.

The incoming filter excludes your own outgoing message. To receive both directions,
use `filters.text`. Message text is literal: Markdown parsing is not implicit.

## Next steps

Continue with [Where to go next](next-steps.md) for the recommended learning paths.

- [Core concepts](concepts.md): connection, authorization, native objects and peers.
- [Bot workflows](../guides/bots-and-events.md): tokens, buttons and callbacks.
- [Sessions](../guides/sessions.md): saved, new and temporary lifetimes.
- [Client reference](../reference/client.md): every public signature.
