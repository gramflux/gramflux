---
title: Core concepts
description: Understand connection state, authorization, peers, raw types and failure semantics.
---

# Core concepts

## Connection is not authorization

`async with Client(...)` manages a connection and storage lifetime. It does not
request a login code or prompt unexpectedly. Call `login`, `sign_in` or
`sign_in_bot` explicitly when creating an authorization.

`client.connected` reports connection state. `await client.is_authorized()` asks
Telegram whether the account is authorized. An MTProto authorization key alone
does not prove that a user or bot has completed account login.

## A session is a credential

| Factory | Intent |
| --- | --- |
| `Session.create(name)` | Exclusively create a new persistent file |
| `Session.open(name)` | Reuse an existing completed authorization |
| `Session.open(name, require_authorized=False)` | Resume an unfinished login |
| `Session.temporary()` | Keep authorization in memory for this process |

Do not copy a competitor's session file into a GramFlux session. No cross-library
session conversion is supported. A temporary session disappearing locally does
not revoke the server authorization; logout is an explicit remote operation.

## Peers carry identity and access information

High-level methods accept supported usernames, marked numeric IDs or native peer
objects. A user/channel numeric ID often requires a known access hash. Resolve a
username or accessible dialog first; GramFlux never invents an access hash.

```python
peer = await client.resolve_peer("public_username", refresh=True)
await client.send_message(peer, "Hello")
```

A username can change ownership. Refresh before identity-sensitive actions, then
use the returned input peer. See [peer resolution](../guides/core-operations.md).

## Choose the right API level

| Level | Example | Responsibility |
| --- | --- | --- |
| High-level | `await client.get_history("me", limit=10)` | Peer resolution and coherent defaults |
| Typed raw facade | `await client.api.messages.get_history(...)` | All schema parameters, native peers and IDs |
| Native request | `await client.invoke(functions.messages.GetHistoryRequest(...))` | Explicit request object |

All three share GramFlux's native request engine. Raw constructors expose protocol
data; they do not automatically resolve entities or execute methods on themselves.
Dates in native TL objects are Unix seconds. Generated declarations are keyword-only.

## Cancellation does not undo a server action

A deadline bounds admission and request execution. Cancelling one request does not
cancel unrelated correlations. However, a sent mutation may complete remotely even
if its caller times out or disconnects. Treat uncertain outcomes explicitly and
avoid blind retries of sends, forwards, deletions or other writes.

Read [error handling](../guides/errors.md) and [update delivery](../guides/events.md)
before building recovery behavior. There is no durable exactly-once callback journal.
