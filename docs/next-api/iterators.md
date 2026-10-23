---
title: Lists and lazy streams
description: Lists and lazy streams for the additive GramFlux Next-Generation API.
---

# Lists and lazy streams

The new API keeps list-returning operations distinct from async iterators. Resource
construction does not fetch data, and an iterator does not secretly collect all pages.

### Legacy API — supported

```python
messages = await client.get_history(peer, limit=100)
async for message in client.iter_history(peer, limit=None, page_size=50):
    print(message.id)
```

### Next-Generation API

```python
chat = client.chat(peer)
messages = await chat.history.fetch(limit=100)
async for message in chat.history.iter(limit=None, page_size=50):
    print(message.id)
```

Both traversals use the existing pagination engine. List helpers retain their finite
nonnegative limits and memory usage. Iterators retain None for an unbounded total;
use an explicit finite limit in exploratory scripts.

## Choose the corresponding view

| Task | Collected result | Lazy result |
| --- | --- | --- |
| History | chat.history.fetch | chat.history.iter |
| Search | chat.search.fetch | chat.search.iter |
| Members | chat.members.fetch | chat.members.iter |
| Dialogs | client.dialogs.list | client.dialogs.iter |
| Explicit message IDs | chat.history.get | No additional invented streaming operation |
| File bytes | client.files.download to a destination | client.files.iter_download |

```python
results = await chat.search.fetch("meeting", limit=20)
selected = await chat.history.get([first_id, second_id])
async for member in chat.members.iter(limit=100, page_size=50):
    print(member.id)
```

Use actual IDs from the same accessible conversation. Explicit ID results preserve
input ordering/duplicates and None for unavailable entries.

## Defaults, limits and cursors stay the same

History/dialog/search page sizes remain 1–100 and members 1–200. `limit` is total
output across pages; `page_size` is per RPC. Zero total limit performs no pagination
or peer resolution. History offset_id is exclusive and goes toward older messages.
The view does not add a date parameter absent from the original Client signature.

Breaking iteration does not prefetch another page. Validation and network failures
can occur while consuming the stream; obtaining the iterator does not certify later
pages. Calls execute on the same Client loop and use the same request deadlines.

Pagination remains subject to concurrent Telegram changes and bounded overlap
suppression; it is not a durable exactly-once export or transaction snapshot. See the
[history guide](../guides/history.md) for cursor progression and stalled-page errors.
