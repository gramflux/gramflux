---
title: Chat resources and messages
description: Chat resources and messages for the additive GramFlux Next-Generation API.
---

# Chat resources and messages

`client.chat(peer)` returns a local view retaining your supplied peer. Each operation
passes that peer into the existing Client method. No access hash is invented and no
membership, permission or username ownership is established by construction.

### Legacy API — supported

```python
sent = await client.send_message(peer, "Hello", silent=True, link_preview=False)
await client.edit_message(peer, sent.id, "Updated")
await client.pin_message(peer, sent.id)
```

### Next-Generation API

```python
chat = client.chat(peer)
sent = await chat.send("Hello", silent=True, link_preview=False)
await chat.edit(sent.id, "Updated")
await chat.pin(sent.id)
```

Use these snippets inside an authorized Client context. The original send options
remain available: reply_to, silent, link_preview, reply_markup and entities. Text is
literal and entity offsets remain UTF-16 units. Editing retains its existing smaller
signature and does not silently gain formatting or markup options.

## Match the operation to its context

| Resource operation | Existing implementation |
| --- | --- |
| send / edit / delete | send_message / edit_message / delete_messages with this peer |
| forward(from_peer, ids, ...) | forward_messages with this peer as destination |
| pin / unpin | Existing peer-scoped pin methods |
| react(message_id, reactions, ...) | send_reaction, preserving None/empty semantics |
| mark_read(max_id=0) | read_history with the exact original cursor default |
| draft / typing | save_draft / set_typing |
| info / full_info | get_chat / get_chat_full |
| set_title / set_description | Existing chat management operations |
| send_file / send_document / send_photo | Existing uploaded-handle or local-source pipelines |
| send_contact / send_location / send_dice | Existing media helpers |
| export_invite / join / leave | Existing explicit invite/membership operations |

The [reference](reference.md) lists every parameter and return type. Not all mutations
return Message: edit/pin/reaction results keep their existing native shapes.

## Deletion remains explicit

### Legacy API

```python
await client.delete_messages(peer, message_id, revoke=False)
```

### Next-Generation API

```python
await client.chat(peer).delete(message_id, revoke=False)
```

Private/basic-group ID preflight remains in the original helper. Channel/supergroup
deletion still requires explicit revoke=True and affects everyone. The resource does
not guess that an arbitrary ID belongs to its peer or bypass Telegram permissions.
Multi-batch mutations are not transactions, and uncertain writes are not replayed.

## Keep source and destination distinct

```python
await client.chat(destination_peer).forward(source_peer, [source_message_id], drop_author=False)
```

Provide real accessible identities. Creating two resources from the same username
does not permanently bind its ownership. For identity-sensitive operations, resolve
freshly using client.peers.resolve(..., refresh=True) and bind the returned input peer.

History, search and members are separate views with explicit fetch and iter methods.
Continue with [lists and streams](iterators.md). Contextual event.reply/edit/delete
helpers remain supported; extracting IDs manually is not required when you already
have a suitable bound event.
