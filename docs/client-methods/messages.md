---
title: Messages, entities and iteration
---

# Messages, entities and iteration

## Resolve references without inventing access data

`get_entity` fetches a full basic User/Chat/Channel entity. `get_input_entity` returns
an input peer through the same resolver as `resolve_peer`; it is not a profile fetch.
Known native entities and session-cached hashes are reused. A numeric user/channel ID
without access metadata is not sufficient. `get_peer_id` can extract a known identity
locally; resolving a username or self identity can require RPC.

`get_entity`/`get_input_entity` also accept a public `https://t.me/username` or
`https://telegram.me/username` reference. Invite/post/query links are rejected rather
than guessed. Existing `resolve_peer` retains its original input contract.

## Send, edit and find

```python
peer = await client.get_entity("@example")
sent = await client.send_message(peer, "Hello", silent=True)
await client.edit_message(peer, sent.id, "Updated")
message = await client.get_message(peer, sent.id)
results = await client.search_messages(peer, "Updated", limit=10)
await client.read_history(peer, max_id=sent.id)
```

Text stays literal. There is no implicit parse_mode/Markdown/HTML parser. Supply native
entities through methods that expose `entities`; offsets use UTF-16 code units.
`edit_message_caption` also supports entities and markup. `edit_message_reply_markup`
replaces only the keyboard; pass an explicit empty ReplyInlineMarkup to remove it.
`edit_message_media` replaces a photo/document; caption=None leaves text untouched.

`copy_message` supports accessible ordinary text and cached photo/document content,
rejecting protected/service/unsupported media shapes. `forward_messages` retains its
existing explicit source-peer argument. Copying is not a bypass of content protection.

## Lists and lazy traversal

```python
messages = await client.get_history("me", limit=100)
async for message in client.iter_history("me", limit=None, page_size=50):
    print(message.id)
async for message in client.iter_search("me", "invoice", limit=100):
    print(message.id)
```

`iter_messages` delegates to `iter_history` with the same newest-first order, exclusive
offset and bounded overlap tracking. It does not silently switch to search. Finite
getters materialize lists; unlimited history must be consumed as an iterator. Network,
permission and pagination errors occur when advanced. Cancelling stops local iteration.

`get_chat_history_count` and `search_messages_count` read the actual server count from
a minimal page. They do not count a client-side scan or promise a stable snapshot.
`get_users` batches at most 100 inputs per request and retains native UserEmpty results.
`get_participants` reuses `get_members`; visible member listings need not be complete.

## Optional contextual syntax

```python
# Direct Client API — primary
await client.send_message(peer, "Hello")
# Optional Chat Resource — same implementation
await client.chat(peer).send("Hello")
```

No existing function is deprecated by these additions. See the [complete method
reference](../reference/client.md) for exact return shapes, argument names and errors.
