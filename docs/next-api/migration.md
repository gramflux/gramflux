---
title: Adopting the new API gradually
description: Adopting the new API gradually for the additive GramFlux Next-Generation API.
---

# Adopting the new API gradually

Migration is optional. Existing Client methods, decorators, filters, events, session
modes, raw calls and examples remain supported. No automatic deprecation warnings or
session conversion are introduced. Begin with one domain or one Router.

## Common equivalents

| Existing API | New API |
| --- | --- |
| client.login(...) | client.auth.login(...) |
| client.get_me() | client.account.me() |
| client.resolve_peer(peer, ...) | client.peers.resolve(peer, ...) |
| client.send_message(peer, text, ...) | client.chat(peer).send(text, ...) |
| client.get_history(peer, ...) | client.chat(peer).history.fetch(...) |
| client.iter_history(peer, ...) | client.chat(peer).history.iter(...) |
| client.get_messages(peer, ids) | client.chat(peer).history.get(ids) |
| client.search_messages(peer, query, ...) | client.chat(peer).search.fetch(query, ...) |
| client.upload_file(...) | client.files.upload(...) |
| client.download_file(...) | client.files.download(...) |
| client.get_contacts() | client.contacts.list() |
| client.get_dialogs(...) | client.dialogs.list(...) |
| client.join_chat(peer) | client.membership.join(peer) |
| client.check_invite(hash) | client.invites.check(hash) |
| client.invoke(request) | client.raw.invoke(request) |
| client.api.users.get_users(...) | client.raw.users.get_users(...) |

The full [reference](reference.md) covers all mappings, signatures and parameters.
Bound resource methods remove only the destination peer argument; all other supported
options and result/error behavior remain in the original implementation.

## Mix styles deliberately

```python
chat = client.chat(peer)
sent = await chat.send("Hello")
await client.edit_message(peer, sent.id, "Updated through the existing API")
```

Both calls share the same account, peer resolver and request engine. A resource is
not a frozen authorization or a persistent username-ownership binding.

## Move handlers without changing event semantics

### Legacy API

```python
@client.on_message(filters.incoming & filters.text, priority=-1)
async def receive(event):
    await event.reply("Received")
```

### Next-Generation API

```python
@router.message(filters.incoming & filters.text, priority=-1)
async def receive(event):
    await event.reply("Received")


client.events.include(router)
```

Register definitions before inclusion, then include before connecting. Shared priority
ordering includes legacy callbacks. When priorities tie, the inclusion point determines
where routed subscriptions enter registration order. Move registration order with care
if your application depends on StopPropagation or multiple callbacks touching state.

For commands, migrating to router.command changes the callback input to CommandContext;
use ctx.event for the original MessageEvent. Arbitrary router.message callbacks retain
the original event type. Existing filters.command remains a synchronous selector.

## Removal and reuse

Use Subscription.close or client.events.exclude for a whole mounted router and
client.events.remove(original_callback) for its definitions. Existing off_event and
off_message still remove directly registered legacy callbacks. Routed wrappers are
tracked by the new manager; they are not disguised as the original function object.

Definitions freeze at first inclusion, persist across disconnects and can be mounted
on different clients. Closing a mount removes registrations without logging out or
changing session storage. See [routing contracts](routing.md) before using plugins
that modify route definitions dynamically; post-mount mutation is intentionally rejected.

## What does not migrate

No new session format, cryptography, transport, update recovery algorithm, schema
regeneration, retry policy or flood-limit behavior is required for these views.
Existing programs can keep all their imports and calls. Cross-library session
conversion and unsupported Telegram workflows remain outside this change.
