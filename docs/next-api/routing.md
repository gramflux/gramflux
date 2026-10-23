---
title: Routers and event subscriptions
description: Routers and event subscriptions for the additive GramFlux Next-Generation API.
---

# Routers and event subscriptions

Define a Router without constructing a Client. Import it from your application's
handler module, then include it before connecting.

### Legacy API — supported

```python
@client.on_message(filters.incoming & filters.text)
async def receive(event):
    await event.reply("Received")
```

### Next-Generation API

```python
from gramflux import filters
from gramflux.routing import Router

router = Router("messages")


@router.message(filters.incoming & filters.text)
async def receive(event):
    await event.reply("Received")


subscription = client.events.include(router)
```

The callback receives the original MessageEvent, with its existing bound helpers.
Other event subscriptions retain their respective event types, not CommandContext.

## Supported subscriptions

| Router method | Delivered event |
| --- | --- |
| message | MessageEvent for new messages by default |
| edited_message | MessageEvent for edits |
| raw_update | RawUpdateEvent |
| deleted_messages | DeletedMessagesEvent |
| read_history | ReadHistoryEvent |
| user_status | UserStatusEvent |
| chat_action | ChatActionEvent |
| callback_query | CallbackQueryEvent |
| inline_query | InlineQueryEvent |
| on(EventClass, predicate) | The selected supported event class |

`message(..., edited=True)` is equivalent to edited_message. Generic `on(MessageEvent)`
uses the existing generic event contract and can match new and edited events. Raw
selection does not enable unsupported qts/secret-chat synchronization.

## Nest routers in definition order

```python
root = Router("application")
root.include(router)
client.events.include(root)
```

A child is expanded at its inclusion position among parent definitions. All handlers
then enter the existing stable priority sort: smaller integers first, registration
order for ties. Legacy callbacks participate in the same order according to when
they were registered. No router-specific scheduling policy is added.

Cycles and overlapping trees are rejected. A late-created diamond is checked before
any subscriptions are added. The same tree may be used by different clients; its
mounts and removal are independent.

## Definitions freeze at first client inclusion

Inclusion freezes the entire tree. Register handlers and include children before
mounting; later mutation raises LifecycleError. Closing a mount does not unfreeze
definitions. This keeps each client's installed snapshot predictable and still lets
you remount/reuse a finished tree.

Including the same root twice on one client is idempotent and returns the same active
Subscription. Mounting an already included child separately raises ConfigurationError.
Repeatedly defining the same callback for the same event kind in one router is rejected;
compose predicates explicitly rather than accidentally registering duplicate work.

## Remove exactly what you own

```python
subscription.close()  # Idempotent; returns removed registration count.
client.events.exclude(root)  # Equivalent root removal when you retained the Router.
client.events.remove(receive)  # Remove matching routed and direct registrations.
```

Before mounting, `router.remove(callback)` removes mutable definitions. For routed
callbacks use the event manager or the Subscription: legacy `off_event` sees the
actual registered wrapper, while `events.remove` also tracks its original callback.
Existing legacy callbacks can still use off_message/off_event as before.

Changes affect the next dispatch snapshot; an already executing snapshot finishes
according to the original dispatcher contract. Subscription.active is read-only.
Mounted definitions persist across Client disconnect/reconnect until explicitly
removed; disconnect stops execution, not the subscription definitions.

## Errors, cancellation and backpressure

Callbacks are awaited by the original single worker. StopPropagation stops remaining
callbacks for that event. Exceptions and callback cancellation use the original
on_handler_error policy, receiving the original event. Slow handlers still delay
later events; queue bounds and update checkpoint boundaries are unchanged.

Routers do not acknowledge jobs in an independent queue or create background tasks.
See [delivery guarantees](../concepts/updates.md) before moving work into your own workers.
