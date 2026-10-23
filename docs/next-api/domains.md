---
title: Account, contacts, bots and membership
description: Account, contacts, bots and membership for the additive GramFlux Next-Generation API.
---

# Account, contacts, bots and membership

These are cached local views of one Client, not independent clients or connections.
Operations retain the legacy parameters, return shapes, server eligibility and errors.
The [reference](reference.md) documents every exposed method individually.

## Account data and remote authorizations

### Legacy API — supported

```python
me = await client.get_me()
await client.update_profile(about="Updated biography")
authorizations = await client.get_active_sessions()
```

### Next-Generation API

```python
me = await client.account.me()
await client.account.update_profile(about="Updated biography")
authorizations = await client.account.sessions()
```

account.terminate_session(authorization_hash) uses Telegram's remote authorization
hash. It does not accept a local session path. Local storage remains Session and the
existing storage interface. None profile fields are omitted, empty supported fields
can clear values, and an all-None update remains invalid.

## Contacts and blocking

```python
# Legacy API
contacts = await client.get_contacts()
await client.block_user(user_peer)

# Next-Generation API
contacts = await client.contacts.list()
await client.contacts.block(user_peer)
```

contacts.add, delete and unblock retain their corresponding existing behavior. In
particular, add(..., share_phone=True) requests the existing phone privacy exception;
it is not just display metadata. Resolve accessible identities rather than guessing
access hashes or treating arbitrary IDs as known contacts.

## Peers and dialogs

```python
# Legacy API
peer = await client.resolve_peer(username, refresh=True)
dialogs = await client.get_dialogs(limit=20)

# Next-Generation API
peer = await client.peers.resolve(username, refresh=True)
dialogs = await client.dialogs.list(limit=20)
```

peers.user/user_full/chat/chat_full delegate to entity lookup helpers. dialogs.iter
keeps lazy pagination. No background peer refresh or new identity cache is created.

## Bots and interactions

```python
# Legacy API
commands = await client.get_bot_commands()
await client.answer_callback_query(query_id, text="Done")

# Next-Generation API
commands = await client.bot.commands()
await client.bot.answer_callback(query_id, text="Done")
```

The bot view also groups set_commands, answer_inline, inline_results, callback_answer,
edit_inline and start. These methods do not grant bot accounts user-only permissions.
A query ID, ordinary message ID and inline message identifier remain distinct native
identities. Keep using event.answer when the event already supplies that context.

## Invites and membership are separate

```python
# Legacy API
invite = await client.check_invite(invite_hash)
await client.import_invite(invite_hash)
await client.join_chat(public_channel_peer)

# Next-Generation API
invite = await client.invites.check(invite_hash)
await client.invites.accept(invite_hash)
await client.membership.join(public_channel_peer)
```

invites.export(peer, ...) creates a supported invite link. membership.leave,
members and iter_members use the original group/channel handling and privacy limits.
Accepting an invite hash is not the same request as joining a resolved public channel.
Resolution alone never silently joins a conversation. Chat-bound export_invite,
join/leave and members views are conveniences for an already chosen peer.
