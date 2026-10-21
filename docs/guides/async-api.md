# Typed asynchronous API

`client.api` exposes **all 783 functions** in the pinned official layer 225 as
explicit asynchronous Python methods. These are generated definitions with typed
keyword arguments and native result types, not dynamic `__getattr__` proxies.
Your editor can discover methods, parameters and constructor result unions.

```python
from gramflux.raw import types

# Inside an already authorized Client context:
result = await client.api.messages.get_history(
    peer=types.InputPeerSelf(),
    offset_id=0,
    offset_date=0,
    add_offset=0,
    limit=10,
    max_id=0,
    min_id=0,
    hash=0,
)

sessions = await client.api.account.get_authorizations()
commands = await client.api.bots.get_bot_commands(
    scope=types.BotCommandScopeDefault(), lang_code=""
)
```

Official `messages.getHistory` becomes `client.api.messages.get_history`.
Root methods such as `invokeWithLayer` are available directly on `client.api`.
Python keywords receive a trailing underscore. Flags words are computed by the
codec; optional fields default to None and flag-only booleans default to False.
Required parameters remain required, including hashes and random IDs; the library
never invents safe retry semantics or API defaults for these raw functions.

This is a typed alternative to `client.invoke(functions.messages.GetHistoryRequest(...))`.
Every call uses the same independent native request engine, deadlines, bounded
admission, cancellation and errors as Client.invoke. It does not create another
connection. Results are native TL objects, lists or primitives. Peer parameters
require native InputPeer objects: use `await client.resolve_peer(...)` when needed.
Use high-level `client.get_history(...)` for peer resolution and simpler defaults.

Generated coverage is not a promise that every RPC works end to end. Telegram
requires appropriate account permissions, API initialization and method-specific
state. Payment, secret-chat, CDN and other unsupported workflows do not become
implemented just because their RPC entry points exist. Cross-DC migrations remain
explicit errors. Real-account interoperability has not been verified here.

## Select any native update type

```python
from gramflux import filters
from gramflux.raw import types


@client.on_raw_update(filters.update_type(types.UpdateUserTyping, types.UpdateChatUserTyping))
async def typing(event):
    update = event.update
    print(update.definition.name)
```

The selector accepts any of the **156 official Update constructor classes** in the
pinned schema. It validates classes against GramFlux's native registry and composes
with other filters. This is one raw event interface, not 156 invented event aliases.
Delivery follows update counter/gap acceptance; unsupported qts/secret-chat updates
still raise explicitly. Difference recovery may deliver Message objects directly,
so raw Update subscriptions are not a substitute for `on_message`. The eight
high-level event classes provide convenient fields for commonly used updates.

## Reproducibility and verification

```bash
python -m gramflux.tools.schema generate
python -m gramflux.tools.schema verify
python -m gramflux.tools.api_inventory --check
pytest tests/unit/test_async_api.py tests/integration/test_async_api.py
```

The inventory lists each of the 783 actual coroutine paths and every native Update
constructor separately from Client helpers. Exhaustive controlled tests construct
all requests, compare encoded bytes to direct native request construction, check
required/optional signatures, and test result forwarding. Additional Client-boundary
tests cover concurrent correlation, decoded results, flags, cancellation and closed
lifecycle errors. These tests use synthetic responses, not Telegram accounts.
