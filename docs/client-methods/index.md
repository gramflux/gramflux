---
title: Client Methods — High-Level API
---

# Client Methods — High-Level API

Use direct `Client` methods for everyday Telegram operations. They share the existing
peer resolver, upload pipeline and native MTProto request engine. No competing client
is used. Routers organize handlers; chat resources and domain views are optional.
All existing Client signatures, defaults and Raw API routes remain supported.

:::info Development checkout
These additions are unreleased. Install this checkout with `python -m pip install -e .`.
An older PyPI distribution may not contain them. Account-level live verification is
still outstanding; deterministic request encoding and result tests are separate evidence.
:::

## Start with direct methods

```python
sent = await client.send_message("me", "Hello")
await client.edit_message("me", sent.id, "Updated")
selected = await client.get_messages("me", [sent.id])
recent = await client.get_history("me", limit=100)
async for message in client.iter_messages("me", limit=100):
    print(message.id)
await client.send_file("me", "photo.jpg", caption="Photo")
```

These snippets require a connected, authorized client. Use your own accessible peers
and files. `get_messages` keeps its list result, including missing slots; `get_message`
is the optional single-ID convenience. Iterators make no request until advanced.

## Choose a guide

- [Messages, entities and iteration](messages.md)
- [Media, albums and file transfers](media.md)
- [Accounts, administration and bots](administration.md)
- [Coverage, compatibility and deferred work](coverage.md)
- [Exact signatures and every parameter](../reference/client.md)
- [Runnable application](https://github.com/gramflux/gramflux/blob/v0.x-dev/examples/high_level.py)

## Three layers

1. High-level Client methods validate inputs, resolve accessible peers and build requests.
2. The existing runtime owns connection, authorization, admission, cancellation and updates.
3. Generated Raw requests remain available through `client.api` and `client.invoke()`.

Names do not imply identical signatures to Telethon or Hydrogram. Native results are
retained where documented; not every mutation returns a Message. Telegram enforces
bot/account eligibility, membership and administrator permissions. RPC errors propagate.
Cancellation does not prove that a submitted write did not complete. Ambiguous writes
are never automatically retried by these helpers.
