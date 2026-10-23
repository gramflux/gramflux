---
title: File transfers
description: File transfers for the additive GramFlux Next-Generation API.
---

# File transfers

The files view delegates to the current chunk pipelines. Accessing client.files does
not open a path, create a destination or start a task. Upload and download keep their
different parameter sets rather than forcing unlike operations into one configuration.

### Legacy API — supported

```python
handle = await client.upload_file(source, part_size=524288, concurrency=2, on_progress=progress)
await client.download_file(location, destination, size=remote_size, on_progress=progress)
```

### Next-Generation API

```python
handle = await client.files.upload(source, part_size=524288, concurrency=2, on_progress=progress)
await client.files.download(location, destination, size=remote_size, on_progress=progress)
```

These fragments assume a connected Client, a supported binary source, a native remote
location, a known remote size and an application callback. Upload completion produces
a server handle; it does not send a message by itself.

## Send an uploaded file through a chat

```python
handle = await client.files.upload("report.pdf", concurrency=2)
message = await client.chat("me").send_file(handle, caption="Report", as_document=True)
```

For the combined local-source workflow, chat.send_document and chat.send_photo retain
their original progress/chunk/window parameters. `client.send_file` also accepts local paths/streams in this checkout;
`client.chat(peer).send_file` delegates to the same implementation.

## Preserve transfer parameters

| Setting | Contract |
| --- | --- |
| Upload part_size | Default 524288; power of two from 1024 through 524288 |
| Upload concurrency | Default 1; integer 1–16; ordered reads with bounded outstanding RPCs |
| Download request_size | Default 524288; power of two from 4096 through 524288 |
| size on download | Complete known remote size, not the requested slice length |
| offset / length | Start byte and requested range; None length means remainder |
| on_progress | Existing sync/awaitable callback; failures propagate and work is not launched unboundedly |

No TransferOptions object is added in this release. Upload windows and download
ranges have different semantics; explicit shared keywords already retain useful
configuration without an ambiguous general-purpose options object.

## Media and byte streams

```python
await client.files.download_media(message, "new-copy.pdf")
async for chunk in client.files.iter_download(location, size=remote_size, request_size=4096):
    consume(chunk)
```

`consume` is your synchronous application consumer; use an awaited consumer if that
function is async. iter_download_media remains available for lazy media-location
resolution and ranged bytes. No whole-file buffering or prefetch is added by the view.

Caller-owned binary streams remain open. Path destinations do not overwrite existing
files; temporary output cleanup and atomic destination handling stay in the current
pipeline. Cancelling can leave partial bytes in caller-owned streams and uploaded
remote parts. There is no newly introduced retry, CDN support, cross-DC migration,
file-reference refresh or resumable-transfer workflow.

Read [the original file guide](../guides/files.md) and the [exact signatures](reference.md)
for supported sources/locations, boundary validation and interruption errors.
