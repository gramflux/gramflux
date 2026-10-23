---
title: Events and subscriptions
description: Map each supported subscription to its delivered event, meaningful identities, helpers and filters.
---

# Events and subscriptions

Register callbacks before connecting. All rows use the same sequential dispatcher,
priority ordering and failure policy; a different event class does not create a
separate worker. Follow [event delivery](../concepts/updates.md) before relying on
ordering or recovery.

| Subscription | Delivered class | What to inspect |
| --- | --- | --- |
| [on_message](../reference/client/on_message.md) | [MessageEvent](../reference/events/MessageEvent.md) | message, text, chat_id, sender_id, outgoing |
| [on_edited_message](../reference/client/on_edited_message.md) | [MessageEvent](../reference/events/MessageEvent.md) | edited state and updated message content |
| [on_deleted_messages](../reference/client/on_deleted_messages.md) | [DeletedMessagesEvent](../reference/events/DeletedMessagesEvent.md) | message_ids; chat_id may be unknown |
| [on_read_history](../reference/client/on_read_history.md) | [ReadHistoryEvent](../reference/events/ReadHistoryEvent.md) | max_id, chat_id, outbox |
| [on_user_status](../reference/client/on_user_status.md) | [UserStatusEvent](../reference/events/UserStatusEvent.md) | sender_id and native status constructor |
| [on_chat_action](../reference/client/on_chat_action.md) | [ChatActionEvent](../reference/events/ChatActionEvent.md) | service message and action-specific native fields |
| [on_callback_query](../reference/client/on_callback_query.md) | [CallbackQueryEvent](../reference/events/CallbackQueryEvent.md) | query_id, data, chat/inline identity and answer helper |
| [on_inline_query](../reference/client/on_inline_query.md) | [InlineQueryEvent](../reference/events/InlineQueryEvent.md) | query text, offset, sender and answer helper |
| [on_raw_update](../reference/client/on_raw_update.md) | [RawUpdateEvent](../reference/events/RawUpdateEvent.md) | native update constructor; narrow before field access |

## Select by content, direction and identity

```python
from gramflux import filters

selector = filters.incoming & filters.private & filters.command("hello")


@client.on_message(selector)
async def hello(event):
    await event.reply("Hello")
```

`chat` and `sender` compare existing marked IDs without resolving peers.
`regex` uses synchronous Python pattern matching. `command` matches the first token,
not a parsed argument list. `data` selects exact callback payloads. Read each
[filter's parameter reference](../reference/filters.md) before composing it.

## Execute only supported helpers

MessageEvent provides contextual reply/edit/delete/download helpers. Callback and
inline query events provide their respective answer helpers. A deleted-message or
status event is not a MessageEvent and does not acquire `.text` or `.reply` simply
because it passed through the same dispatcher.

Use [off_event](../reference/client/off_event.md) or
[off_message](../reference/client/off_message.md) to remove callbacks, and
[StopPropagation](../guides/events.md) to stop remaining callbacks for one event.
For native constructors use [filters.update_type](../reference/helpers/filters-update_type.md);
raw selection does not enable unsupported secret-chat/qts synchronization.
