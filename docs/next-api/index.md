---
title: Next-Generation API
description: Next-Generation API for the additive GramFlux Next-Generation API.
---

# Next-Generation API

:::info Development availability

This additive surface is available in the development checkout. Install this repository
with `python -m pip install -e .` to use it until a tagged distribution including these
features is published. An older PyPI artifact with the same documentation version
may not contain Router or the new views.

:::

For new projects, organize operations by domain and define subscriptions in standalone
Routers. The original Client methods remain supported with their existing signatures,
defaults, results and exceptions. You can adopt one view without migrating everything.

## What owns what?

| Object | Responsibility | Created locally? |
| --- | --- | --- |
| Client | Connection, configuration, local session and native MTProto execution | Construction does not connect |
| Router | Ordered event definitions independent of any client | Yes |
| CommandContext | Parsed command plus the original MessageEvent | Created only for a matching message |
| ChatResource | Peer-bound message, history, search and membership operations | Yes; peer is retained, not resolved |
| Domain view | Typed grouping of existing Client operations | Yes; cached on the Client |
| Subscription | Client-specific router mount and explicit removal | Registration only; no independent worker |

The call path is view → existing Client method → existing validation, peer resolution,
request admission and native runtime. Routers compile into existing subscriptions.
There is no additional connection, event loop, dispatcher, queue or write-retry layer.

## Start with one operation

### Legacy API — supported

```python
await client.send_message(peer, "Hello")
```

### Next-Generation API — recommended for new projects

```python
chat = client.chat(peer)
await chat.send("Hello")
```

Both snippets assume a connected authorized client and a real accessible peer. Creating
`chat` alone does not resolve the username, prove membership or open a connection.

## Read by task

1. [Authentication and lifecycle](authentication.md): preserve explicit connection and session intent.
2. [Routers and events](routing.md): independent definitions, nesting, ordering and removal.
3. [Commands](commands.md): exact parsing rules and CommandContext fields.
4. [Chat resources](chats.md): peer-bound messaging and mutations.
5. [Lists and streams](iterators.md): total limits, page sizes and lazy errors.
6. [File transfers](files.md): existing chunk, progress and ownership contracts.
7. [Other domains](domains.md): account, contacts, dialogs, bots, invites and membership.
8. [Raw API](raw.md): the original typed namespaces and invoke route.
9. [Migration](migration.md): adopt views gradually alongside existing handlers.
10. [Complete examples](examples.md): equivalent executable legacy and modular applications.
11. [Coverage and limits](compatibility.md): implemented surfaces and remaining runtime boundaries.
12. [Exact API reference](reference.md): every exposed view signature and parameter.
