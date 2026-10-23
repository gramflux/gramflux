---
title: Parameters and native objects
description: Required fields, omission, defaults, peer types, formatting, pagination, file options and raw flags explained with examples.
---

# Understand parameters before calling a method

Each Client method and raw function now has an individual reference page. Use the
parameter table for the exact supported keywords, then read each parameter's own
section for meaning, allowed values and interactions. Parameters from Telethon,
Pyrogram or another GramFlux method are not automatically forwarded.

## Required, optional and keyword-only arguments

```python
sent = await client.send_message(
    "me",  # peer: positional or keyword
    "Hello",  # text: positional or keyword
    silent=True,  # keyword-only
    link_preview=False,  # keyword-only
)
```

Unknown keywords such as `parse_mode="markdown"` raise TypeError on this signature.
For additional raw TL options, choose the [typed raw API](async-api.md) rather than
assuming there is a hidden `**kwargs` escape hatch.

[send_message: every parameter](../reference/client/send_message.md).

## None, False and empty values are different

| Value | Typical interpretation | Important exception |
| --- | --- | --- |
| Omitted keyword | Use the Python default shown in the signature | Required raw parameters have no invented default |
| `None` | Omit an optional TL value or select a documented high-level fallback | `reactions=None` deliberately sends an empty reaction vector |
| `False` | Disable a boolean option | For flag-only TL `true`, leaves the flag bit unset |
| `""` | Present empty text | Nonempty fields reject it; profile about/last_name can use it to clear |
| `[]` | Present empty vector | Not the same as omitting an optional vector |
| `0` | Actual integer value | Zero is not a universal cache, cursor or clear sentinel |

For example, `update_profile(about=None)` omits that field, while
`update_profile(about="")` requests clearing it. At least one profile field must
be supplied; a call where all fields are None is rejected.

```python
await client.update_profile(about="New biography")
await client.update_profile(about="")  # Explicitly request clearing the biography.
```

[update_profile](../reference/client/update_profile.md) ·
[send_reaction](../reference/client/send_reaction.md).

## High-level peers versus native input peers

High-level methods resolve supported representations:

```python
await client.send_message("me", "Saved Messages")
peer = await client.resolve_peer("public_username", refresh=True)
await client.send_message(peer, "Hello")
```

Raw functions require the exact native input type, not a username string:

```python
from gramflux.raw import types

history = await client.api.messages.get_history(
    peer=types.InputPeerSelf(),
    offset_id=0,
    offset_date=0,
    add_offset=0,
    limit=10,
    max_id=0,
    min_id=0,
    hash=0,
)
```

`InputPeer`, `InputUser` and `InputChannel` are different TL result types. For example,
`users.getUsers` accepts a vector of InputUser, so use `types.InputUserSelf()` rather
than `types.InputPeerSelf()`:

```python
users = await client.api.users.get_users(id=[types.InputUserSelf()])
```

User/channel access hashes must come from real server-visible metadata. A numeric
ID alone cannot manufacture access. Native constructor choices are listed on each
raw parameter's page; a type-compatible empty/self variant is not guaranteed to be
valid for every endpoint.

## Text, entities and keyboard markup

Text and captions are literal. For explicit formatting, send native MessageEntity
objects where the high-level signature exposes `entities`:

```python
from gramflux import buttons
from gramflux.raw import types

keyboard = buttons.inline(
    [
        [buttons.callback("Confirm", "confirm")],
        [buttons.url("Project", "https://github.com/gramflux/gramflux")],
    ]
)

message = await client.send_message(
    "me",
    "Hello",
    entities=[types.MessageEntityBold(offset=0, length=5)],
    reply_markup=keyboard,
    link_preview=False,
)
```

Entity offsets/lengths are UTF-16 code units. For an emoji outside the BMP, one Python
character can consume two UTF-16 code units. Do not calculate all offsets using
`len(text)` without accounting for this. These explicit entities are separate from
Markdown source syntax.

`send_document` and `send_photo` do not expose an `entities` parameter. `edit_message`
exposes neither `entities` nor `reply_markup`; its implementation sends an empty
entities vector. Use a suitable raw request if you need supported TL fields absent
from a convenience signature. Omitted edit markup does not universally mean removal.

[send_message](../reference/client/send_message.md) ·
[edit_message](../reference/client/edit_message.md) ·
[inline keyboard](../reference/helpers/buttons-inline.md).

## Total limits, page sizes and cursors

```python
async for message in client.iter_history(
    "me",
    limit=250,  # Total maximum across pages.
    page_size=50,  # Per-RPC request size.
    offset_id=0,  # Start at the newest accessible history.
):
    print(message.id)
```

- Iterator `limit=None` permits an unbounded traversal; list-returning helpers require
  a finite nonnegative integer.
- `limit=0` performs no peer resolution or pagination RPC.
- History/dialog/search page sizes are 1–100; member page sizes are 1–200.
- `offset_id` is an exclusive message-ID cursor, not a list index.
- Native `offset_date` is Unix seconds, not a datetime or milliseconds.
- Inline `offset` is an opaque string cursor, while download `offset` is a byte count.

Iterator factories such as `iter_history` are not awaited. Use `async for` directly.
Errors can arise while consuming the iterator; creating it does not certify that all
future pages are accessible.

[iter_history](../reference/client/iter_history.md) ·
[get_history](../reference/client/get_history.md) ·
[get_inline_results](../reference/client/get_inline_results.md).

## Source paths, uploaded handles and remote locations

These arguments belong to different stages:

| Argument | Meaning | Example |
| --- | --- | --- |
| `source` | Local path or seekable binary input stream | `upload_file("report.pdf")` |
| `file` | Local path/stream, uploaded InputFile/InputFileBig or supported InputMedia | `send_file("me", handle)` |
| `message` | Native message carrying document/photo metadata | `download_media(message, "copy.pdf")` |
| `location` | Native remote InputFileLocation | `download_file(location, "copy.bin", size=size)` |
| `destination` | New path or writable binary output stream | A new trusted filename, not an untrusted media path |

```python
handle = await client.upload_file("report.pdf", part_size=256 * 1024, concurrency=4)
message = await client.send_file("me", handle, caption="Report", as_document=True)
await client.download_media(message, "report-copy.pdf")
```

Upload part size is a power of two from 1 KiB to 512 KiB, with at most 4000 parts.
Upload concurrency is 1–16 and bounds outstanding part RPCs; reads remain sequential.
Download request size is a power of two from 4 KiB to 512 KiB. It is not download
concurrency: the current download pipeline is lazy and does not prefetch.

For a range, `size` is the complete known remote size, `offset` the start byte and
`length` the number of output bytes. None length means the remainder. Path destinations
never overwrite existing files; caller-owned streams remain open and can retain
partial data after failure.

[upload_file](../reference/client/upload_file.md) ·
[send_file](../reference/client/send_file.md) ·
[download_file](../reference/client/download_file.md).

## Raw flags and conditional groups

Most raw TL flag words have schema type `#` and are computed by the codec. The public
method signature omits those words. Optional values use None and flag-only booleans
use False. Two fields sharing a flag bit must agree about presence:

```python
await client.api.messages.save_draft(
    peer=types.InputPeerSelf(),
    message="Draft",
    no_webpage=True,
    reply_to=None,
    entities=[],
)
```

An ordinary integer field *named* `flags` is a different case. For example,
`auth.importBotAuthorization` exposes a required `flags:int`; it is not a computed
`flags:#` word. Follow that method's explicit reference instead of applying a
name-based rule.

Each raw method page lists the exact conditional group and all native argument
alternatives. Constructor availability does not provide the multi-step workflow
needed for payments, secret chats, calls or cross-DC media support.

## Safe examples and verification

Client examples assume a connected, authorized client and real account-visible IDs.
Raw call templates intentionally use `*_value` variables for required application
inputs: the documentation does not fabricate access hashes, authentication
challenges, consent amounts or protocol state. Do not run mutation templates until
you understand their method-specific behavior and permissions.

The signatures, defaults, field types, conditional groups and constructor options
are generated from source/schema and tested. Official short excerpts/error identifiers
are pinned separately with retrieval timestamps and hashes. This is documentation
coverage, not a claim that every raw workflow was successfully exercised on Telegram.
