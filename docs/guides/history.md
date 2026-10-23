---
title: Dialogs, history and pagination
description: Choose lists or streams, control total and per-page limits, understand cursors and retrieve specific IDs.
---

# Dialogs, history and pagination

Retrieval helpers have two shapes: finite list-returning coroutines and lazy async
iterators. All examples assume an authorized Client. Choose a finite limit while
learning to avoid accidentally traversing a very large history.

## Start with a finite list

```python
history = await client.get_history("me", limit=20)
```

The returned list is held in memory. `limit` is the total maximum, not the number of
items requested in every RPC. Fewer accessible results can be returned. History is
newest first, and it may include ordinary messages and service messages.

## Stream larger results

```python
async for message in client.iter_history("me", limit=250, page_size=50):
    print(message.id)
```

`limit=250` bounds total output; `page_size=50` controls the per-request size. History,
search and dialog page sizes accept 1–100, while members accept 1–200. Iterator
`limit=None` permits unbounded traversal; list helpers require a finite nonnegative
integer. `limit=0` performs no peer resolution or pagination RPC.

The iterator fetches on demand and does not prefetch the next page after you stop.
Errors can appear during iteration. Accumulating every yielded object in your own
list defeats the memory advantage of streaming.

## Continue with the correct cursor

```python
async for message in client.iter_history("me", limit=20, offset_id=older_than_id):
    print(message.id)
```

Set `older_than_id` from a real message in the same conversation. The cursor is
exclusive: this traversal requests older messages, not an array slice. Zero starts
from the newest accessible history. Do not reuse a channel's message ID as a cursor
for another conversation.

Dialog pagination has a compound cursor, including peer and top-message date/ID.
Use the iterator instead of approximating that cursor with one integer.

## Search within a conversation

```python
matches = await client.search_messages("me", "meeting", limit=30)
async for message in client.iter_search("me", "meeting", limit=100, page_size=25):
    print(message.id)
```

Search uses Telegram's server-side semantics. It is not Python regex matching and
does not search an unlimited local cache. The optional sender selects a supported
peer in that conversation; the query and sender are different filters. For event
text regexes, use [filters.regex](../reference/helpers/filters-regex.md).

## Retrieve explicit IDs

```python
selected = await client.get_messages("me", [first_id, second_id, first_id])
```

Supply IDs from real accessible messages. Results preserve input order and duplicate
positions. Missing, deleted or other-chat entries are represented by None. Explicit
ID retrieval accepts at most 10,000 input IDs and uses at most 100 per request.
Check for None before accessing message fields.

## Browse conversations and members

```python
async for dialog in client.iter_dialogs(limit=50, folder_id=0):
    print(dialog.id, dialog.unread_count)

async for member in client.iter_members(group_peer, limit=100, page_size=50):
    print(member.id, member.role)
```

`folder_id=0` selects the main folder and 1 the archive. Pinned dialogs are handled
separately from the ordinary cursor. Group member visibility depends on account
permissions and server privacy settings; pagination cannot expose a forbidden list.

## Understand concurrent changes

A traversal is not a snapshot transaction. New messages, deletions, reordered dialogs
and membership changes can occur between requests. GramFlux uses bounded overlap
suppression and detects stalled cursors, raising PaginationError instead of looping
forever. This is not a durable exactly-once export or a resumable export checkpoint.

See [get_history](../reference/client/get_history.md),
[iter_dialogs](../reference/client/iter_dialogs.md),
[iter_members](../reference/client/iter_members.md) and
[message result types](../concepts/messages.md) for exact contracts.
