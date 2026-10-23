---
title: Sending and managing messages
description: Send literal text, reply, format with entities, edit, forward and delete with explicit scope.
---

# Sending and managing messages

Examples on this page run inside a coroutine with a connected, authorized Client.
Use a conversation you control while learning. Telegram decides account eligibility,
permissions and rate limits; a high-level convenience does not bypass those rules.

## Send text and use the returned identity

```python
sent = await client.send_message("me", "A note for later", link_preview=False)
reply = await client.send_message("me", "Following up", reply_to=sent.id)
```

`peer` is the destination, `text` is literal content, and `reply_to` is a positive
ordinary message ID in that conversation. Store the destination alongside `sent.id`.
`silent=True` requests silent delivery; it does not hide the message or guarantee no
recipient UI changes. `link_preview=False` disables the requested web preview.

Read [send_message](../reference/client/send_message.md) for every parameter,
including keyboard markup and explicit native entities.

## Format explicitly

```python
from gramflux.raw import types

sent = await client.send_message(
    "me",
    "Important note",
    entities=[types.MessageEntityBold(offset=0, length=9)],
)
```

There is no implicit `parse_mode` option. Native entity offsets/lengths are UTF-16
units. Keyboard markup belongs to `reply_markup`, not the entities vector. Use
[buttons.inline](../reference/helpers/buttons-inline.md) to build supported keyboards.

## Edit a known message

```python
result = await client.edit_message("me", sent.id, "Revised note", link_preview=False)
```

The result is a native update result, not a guarantee of a returned Message.
Current `edit_message` does not expose entities or reply markup and sends an empty
entities vector. Use the documented raw method when you need additional supported
Telegram fields. Editing is subject to account permissions and Telegram's limits;
old content is not restored automatically if a later application step fails.

## Forward with an explicit source

```python
results = await client.forward_messages(
    "me",
    source_peer,
    [source_message_id],
    silent=True,
)
```

`source_peer` and `source_message_id` must come from an accessible real message.
The destination and source have different roles. The helper batches requests and
returns actual update results. A later batch failure does not roll back earlier
forwards, and an uncertain response must not trigger a blind resend.

## Delete with the intended visibility

```python
await client.delete_messages("me", [sent.id, reply.id], revoke=False)
```

For private/basic-group global message IDs, the helper preflights requested IDs
against the supplied conversation. Missing/other-chat IDs fail rather than being
assumed safe. In a channel/supergroup, deletion is peer-scoped, affects everyone and
requires explicit `revoke=True`; the default cannot silently become global deletion.

Check [delete_messages](../reference/client/delete_messages.md) before deleting.
Multi-batch deletion is not an atomic transaction, and permission errors are real
server rejections. Reconcile partial/uncertain outcomes rather than retrying all IDs.

## Pinning, reading and drafts are separate operations

Use [pin_message](../reference/client/pin_message.md) and
[unpin_message](../reference/client/unpin_message.md) for pins;
[read_history](../reference/client/read_history.md) for the endpoint's read cursor;
and [save_draft](../reference/client/save_draft.md) for drafts. A zero sentinel or
empty string does not have one universal meaning across these methods.

For retrieval, continue with [history and pagination](history.md). For incoming
messages, use [events and filters](events.md). For uncertain writes and server waits,
read [error handling](errors.md) before adding retry logic.
