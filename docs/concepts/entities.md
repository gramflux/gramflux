---
title: Entities, peers and identifiers
description: Distinguish full entities, input peers, marked IDs, access hashes, cached usernames and event identities.
---

# Entities, peers and identifiers

A Telegram account, conversation and message are different identities. The Python
representations also differ: a full entity describes something, while an input
peer supplies the identity and access information needed to address a request.
Confusing these forms is a common source of apparently valid but rejected calls.

## Choose the right representation

| Representation | Purpose | Example |
| --- | --- | --- |
| Full user/chat/channel entity | Display metadata and inspect its native fields | Result of `get_user` or `get_chat` |
| `InputPeer` | Address a conversation in a generic peer-taking raw method | `types.InputPeerSelf()` |
| `InputUser` | Supply a user to a user-specific raw method | `types.InputUserSelf()` |
| `InputChannel` | Supply a channel to a channel-specific raw method | Native ID plus its server-provided access hash |
| Marked integer ID | Distinguish user/group/channel identities locally | The `event.chat_id` convention |
| Username | Resolve a currently assigned public name | `"public_username"` |

An `InputPeerSelf` does not substitute for `InputUserSelf`. Native TL result types
are checked by serialization. The raw method page lists compatible constructors,
but a type-compatible constructor can still be invalid for a particular endpoint.

## High-level methods resolve supported inputs

```python
peer = await client.resolve_peer("public_username", refresh=True)
profile = await client.get_user(peer)
await client.send_message(peer, "Hello")
```

Resolve only accounts/conversations you are allowed to access. Resolution is not a
way to join a private group, obtain arbitrary access hashes or bypass permissions.
Invites are handled by explicit membership operations.

`"me"` and `"self"` represent your own account in supported high-level peer arguments.
The raw facade does not convert those strings automatically:

```python
from gramflux.raw import types

users = await client.api.users.get_users(id=[types.InputUserSelf()])
```

## Marked IDs versus wire IDs

| Conversation kind | Local marked form |
| --- | --- |
| User | Positive user ID |
| Basic group | Negative chat ID |
| Channel or supergroup with native ID N | `-(1000000000000 + N)` |

This convention disambiguates identities in filters and caches. It is not the
integer encoding inside every raw constructor. Do not paste a marked channel ID
into a native `channel_id` field that expects the unmarked Telegram ID.

A message ID is scoped by the operation and conversation. An MTProto envelope
message ID, a callback `query_id` and an ordinary chat message ID are unrelated
identifiers. Preserve the peer alongside message IDs in application records.

## Access hashes are obtained, not computed

User/channel requests often need an access hash from server-visible metadata. A
numeric ID alone does not supply it. Resolve a username, load accessible dialogs or
use a suitable full/native input entity. Unknown metadata raises `PeerNotFound`
rather than being replaced with an invented zero hash. Basic group peers and self
peers have different requirements.

Access metadata is account-specific context. A session's peer cache is not a
portable directory for another account, and an access hash does not grant more
permissions than Telegram gives that account.

## Understand the cache boundary

The account-local peer LRU defaults to 2048 records and is bounded by
`Config.peer_cache_size`. It retains the identity/access metadata described in the
[core operations guide](../guides/core-operations.md), not a complete downloaded
profile database. Clean shutdown can persist that metadata in the session.

Primary username lookups have a 60-second monotonic lifetime. Persisted username
bindings are not trusted after restart. A username can change owners, so use
`resolve_peer(name, refresh=True)` for identity-sensitive actions and then pass the
returned input peer. A failed refresh invalidates the old binding.

## Missing event identities are meaningful

Some deletion events cannot identify their conversation. Inline callbacks can
have an inline message identifier without an ordinary chat ID. A missing identity
is represented by None; do not guess it from a global message ID or assume every
event has the same fields. Narrow to the actual [event class](../reference/events.md).

See [resolve_peer](../reference/client/resolve_peer.md),
[peer parameters](../guides/parameters.md#high-level-peers-versus-native-input-peers)
and [migration](../guides/migration.md) for practical boundaries.
