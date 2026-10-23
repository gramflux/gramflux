---
title: Messages, dialogs and results
description: Understand native message variants, text, entities, media, result shapes and helper ownership.
---

# Messages, dialogs and results

Telegram returns structured objects rather than a uniform response dictionary.
GramFlux keeps native TL data available and adds helpers at explicit boundaries.
Learn which object you have before assuming it supports a field or action.

## A message can have different constructors

History can contain both ordinary `types.Message` objects and
`types.MessageService` objects. Service messages describe actions such as membership
changes and do not share every ordinary message field. Explicit ID retrieval can
also return None for unavailable entries.

```python
from gramflux.raw import types

async for message in client.iter_history("me", limit=20):
    if isinstance(message, types.Message):
        print(message.id, bool(message.media))
    elif isinstance(message, types.MessageService):
        print(message.id, type(message.action).__name__)
```

Inspect the constructor before using variant-specific attributes. Do not assume a
nonempty history response contains only text messages or that all IDs remain
accessible after a later deletion.

## Text and captions are literal

An ordinary message's `message` field carries text, including media captions.
`MessageEvent.text` provides the event-facing text view. Neither causes implicit
HTML or Markdown parsing. A string containing `**bold**` is literal text unless
you provide supported native entities through the method's `entities` parameter.

```python
from gramflux.raw import types

sent = await client.send_message(
    "me",
    "Hello",
    entities=[types.MessageEntityBold(offset=0, length=5)],
)
```

Entity offsets and lengths use UTF-16 code units. Emoji outside the BMP consume
two units, so Python character offsets are not always interchangeable. Not every
convenience method exposes entities or keyboard markup; check its exact signature
rather than forwarding options from another method.

## Results are operation-specific

| Operation | Result shape |
| --- | --- |
| `send_message` | Native Message |
| `get_history` / `search_messages` | Finite list of ordinary/service messages |
| `get_messages` | List preserving requested ordering/duplicates, with missing entries represented by None |
| `edit_message` / pin operations | Native update result, not necessarily a Message |
| `forward_messages` | Actual update results for its batches |
| `iter_dialogs` | Stream of GramFlux Dialog records |
| Raw API call | Its schema-declared native result constructor |

Consult the individual return section for the exact current contract. Accessing
`.id` on every RPC result is not a general API pattern.

## Dialogs describe conversations

A Dialog record exposes `id`, `name`, `entity`, `message`, `unread_count`, `pinned`,
`folder_id` and `raw`. Its top message can be None. A dialog's marked ID identifies
the conversation; it is not the ID of its current top message.

Dialog ordering can change while you paginate. GramFlux tracks the documented
cursor fields and bounded overlap, but pagination is not a transaction snapshot of
Telegram state. See [history and pagination](../guides/history.md).

## Data objects and event helpers have different roles

Raw native objects hold data. Use Client operations to execute Telegram methods.
A client-bound MessageEvent adds contextual conveniences:

```python
@client.on_message(filters.incoming & filters.command("hello"))
async def hello(event):
    await event.reply("Hello")
```

Here `filters` is imported from `gramflux` and the handler is registered before
connecting. `event.reply` uses the original conversation and message ID. It still
obeys the Client's request limits, permissions and errors. Detached events cannot
execute helpers without their bound context.

## Media references are not local files

A native photo/document describes a remote resource. `download_media` obtains bytes;
`upload_file` returns an uploaded handle; `send_file` uses a supported handle/media
input. None of these stages is interchangeable with a local path argument on every
method. Remote references can expire, and unsupported cross-DC/CDN pathways fail
explicitly. Read [file transfers](../guides/files.md) before retaining media references.
