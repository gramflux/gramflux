---
title: Raw API access
description: Raw API access for the additive GramFlux Next-Generation API.
---

# Raw API access

The existing generated facade and explicit request route remain supported unchanged.
The optional raw view adds an invoke method alongside the same typed namespaces.

### Legacy API — supported

```python
from gramflux.raw import functions, types

users = await client.api.users.get_users(id=[types.InputUserSelf()])
users = await client.invoke(functions.users.GetUsersRequest(id=[types.InputUserSelf()]))
```

### Next-Generation API

```python
from gramflux.raw import functions, types

users = await client.raw.users.get_users(id=[types.InputUserSelf()])
users = await client.raw.invoke(functions.users.GetUsersRequest(id=[types.InputUserSelf()]))
```

Every route ultimately calls the original Client.invoke. Namespace method signatures,
request constructors, result types, TL names/IDs and the pinned layer are unchanged.
There is no separate transport, serialization path, auth key or connection pool.

## Native inputs stay explicit

raw.users.get_users accepts native InputUser variants, not a username or InputPeer.
Import data classes from gramflux.raw.types; client.raw is the invocation view, not
an additional constructor registry. Use client.peers.resolve for supported high-level
peer resolution where it fits the required raw input type.

Unknown keywords and invalid native fields still fail through the existing argument
and codec boundaries. Flag words declared as # are computed by the codec; ordinary
integer fields named flags retain their real required signatures.

## Coverage remains a separate claim

The layer-225 facade exposes 783 generated functions. Adding raw does not implement
all workflows those functions can participate in. Payments, calls, secret chats,
CDN downloads and cross-DC media may need unsupported runtime/application behavior.
No new live interoperability claim or automatic write replay follows from an alias.

Use the [existing raw reference](../reference/raw/index.md) for each method's complete
fields and native alternatives, and the [compatibility matrix](../design/compatibility.md)
for actual runtime boundaries.
