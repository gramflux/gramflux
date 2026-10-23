---
title: API overview
description: Navigate GramFlux's generated Client, event, filter, configuration and raw Telegram references.
---

# API overview

GramFlux exposes a high-level client, native TL data and a typed asynchronous raw
facade. Every operation goes through the same native execution policy.

Find an operation by task in the [Client quick reference](quick-references/client.md),
or choose a delivery shape in [Events and subscriptions](quick-references/events.md).
For the underlying model, read [Messages and results](concepts/messages.md) and
[Entities and identifiers](concepts/entities.md).

## Public imports

Every Client method and every raw function has its own detailed reference page.
Start with the [parameter guide](guides/parameters.md) for omission rules, native
input variants, pagination and transfer settings.

```python
from gramflux import Client, Config, LoginPrompts, Session, buttons, events, filters
from gramflux.raw import functions, types
```

Use `gramflux.errors` for exceptions and `gramflux.storage` for custom session stores.
The distribution includes `py.typed` for static analysis and editor completion.

## Generated reference

Reference pages are generated from actual signatures and the pinned official schema:

| Reference | Covers |
| --- | --- |
| [Client](reference/client.md) | All public methods, signatures and lifecycle properties |
| [Sessions and configuration](reference/configuration.md) | Factory signatures and Config field types/defaults |
| [Events](reference/events.md) | Eight event classes, fields, properties and bound helpers |
| [Filters](reference/filters.md) | Composable message, callback and native-update selectors |
| [Buttons](reference/buttons.md) | Inline keyboard builders and article results |
| [Errors](reference/errors.md) | Exception inheritance and class contracts |
| [Raw API](reference/raw/index.md) | All 783 pinned functions, parameter types, IDs and results |

The [machine-readable surface inventory](api-surface.json) lists public Client
methods and raw function paths separately. Lifecycle methods, subscription methods,
stream factories, raw functions, data constructors and event classes are distinct
categories, not interchangeable feature counts.

## High-level operations

```python
me = await client.get_me()
message = await client.send_message("me", "Hello")
history = await client.get_history("me", limit=10)
```

High-level helpers resolve supported peers and validate operation-specific inputs.
Results remain native Telegram objects or documented library records. See
[core operations](guides/core-operations.md) and [bot workflows](guides/bots-and-events.md).

## Typed raw methods

```python
result = await client.api.users.get_users(id=[types.InputUserSelf()])
```

The facade provides explicit coroutine signatures and native input/result unions.
It does not resolve peer names, invent random IDs, retry ambiguous writes or
implement every workflow needed by the schema's methods.

The equivalent explicit request route is:

```python
result = await client.invoke(functions.users.GetUsersRequest(id=[types.InputUserSelf()]))
```

Use GramFlux-generated request classes; foreign client objects are rejected. Native
constructor fields still use broad TLObject annotations in some places. Concrete
raw facade signatures provide narrower constructor unions, but schema declarations
alone are not proof of end-to-end feature coverage. Read
[compatibility](design/compatibility.md) and [raw usage](guides/async-api.md).

## Lifetimes and failures

Use one Client on one asyncio event loop. Register handlers before connecting.
Connecting, authenticating, waiting for updates and logging out are explicit actions.
Timeouts and cancellation do not revoke actions already accepted by the server.

See [core concepts](getting-started/concepts.md), [authentication](guides/authentication.md),
[events](guides/events.md) and [errors](guides/errors.md) for behavioral guarantees
that a signature cannot express by itself.
