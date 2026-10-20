# File transfers

Transfers use GramFlux's chunk pipeline and the shared Client.invoke request policy.
MTProto transport/encryption now use GramFlux's native engine and OpenSSL-backed primitives. Deterministic tests cover the
pipeline; no actual Telegram media exchange has been verified in this environment.

```python
await client.send_document(
    "me", "report.pdf", name="report.pdf", on_progress=progress, concurrency=4
)
await client.send_photo("me", "photo.jpg", caption="Photo", on_progress=progress)

uploaded = await client.upload_file("report.pdf", part_size=256 * 1024, concurrency=4)
message = await client.send_file("me", uploaded, caption="Report")
await client.download_media(message, "report-copy.pdf", on_progress=progress)
```

## Uploads and bounded concurrency

Upload accepts paths or seekable binary streams, starting at the stream's current
position. Caller-owned streams remain open. Library-owned handles close on success,
failure and cancellation. Nonseekable streams and empty uploads are rejected. Do not
mutate a source concurrently. An early end, invalid binary return or oversized read
fails explicitly, rather than submitting corrupted parts.

`part_size` defaults to 512 KiB; allowed values are powers of two from 1 KiB through
512 KiB. Every part except the last has this size. The conservative maximum remains
4000 parts, without guessing Premium/config-dependent limits. Files <=10 MiB use
saveFilePart and an MD5 checksum over **source order**, regardless of response order;
larger files use saveBigFilePart. MD5 is a required protocol checksum, not a security
primitive.

`concurrency` is 1–16, default **1**. Reads remain sequential; at most this many part
RPC tasks are outstanding. No task is created for every part in advance. Acknowledged
parts free space for further reads. Data retained by this pipeline is proportional to
concurrency times part_size, plus a constant number of temporary chunks; this is not
a bound on backend buffers, total process RSS or all simultaneous transfers. The
client's global RPC admission limit still applies. Concurrency uses one client's
ordinary connection; dedicated media connections are not implemented.

Cancellation, a failed part or an exception in progress stops new scheduling and
cancels/joins all outstanding part tasks before returning. Some remote parts may
already have been accepted; there is no rollback, automatic retry or resume token.
Higher concurrency must respect server waits; GramFlux surfaces waits rather than
bypassing them. Start conservatively and measure your own conditions.

`send_document` and `send_photo` combine streaming upload with an explicit media send.
Document name/MIME type may be supplied; photos must already satisfy Telegram's
format/size rules. No image resizing is performed. Captions are literal text; reply_to
is optional. `send_file` takes an uploaded handle or raw InputMedia, not a path to read
implicitly. A successful upload followed by a failed send is not retried or rolled back.

## Lazy streams and exact byte ranges

```python
import hashlib

digest = hashlib.sha256()
async for block in client.iter_download_media(message, offset=123, length=100_000):
    digest.update(block)

# Advanced callers can provide a raw InputFileLocation and its known total size.
async for block in client.iter_download(location, size=total_size, request_size=64 * 1024):
    await application_sink(block)

# A path contains only the requested range, not padding up to offset.
await client.download_media(message, "excerpt.bin", offset=123, length=100_000)
```

`iter_download` and `iter_download_media` yield bytes on demand and perform no prefetch.
Breaking/closing iteration sends no further requests and leaves no background task.
`offset` is a nonnegative byte offset; `length=None` selects the rest of the file.
Explicit length must fit within the known size; invalid ranges fail instead of silently
clamping. Zero length and end-of-file empty ranges make no file RPC.

`request_size` defaults to 512 KiB; it must be a power of two between 4 KiB and 512 KiB.
Requests align down to request_size boundaries, remain inside a 1-MiB protocol window,
and satisfy Telegram's offset/limit alignment rules. Arbitrary requested range edges
are trimmed locally. Up to a chunk of neighboring bytes can be fetched at either edge;
yielded data contains exactly the requested range. Full response lengths are validated
against the known total size, including the final short part. The size must be current;
stale metadata/truncated responses fail explicitly.

`download_file(location, destination, size=...)` uses the same reader. `download_media`
and `iter_download_media` resolve document/photo locations and known size from the
message; photo selection uses the largest supported size rather than list position.
Encrypted CDN redirects, expired references and cross-DC media recovery remain
unsupported. Range reads are **not** resumable-transfer checkpoints or automatic
interruption recovery. No independent upload.getFileHashes verification is implemented;
transport integrity remains the native MTProto message-key validation's responsibility.

## Destinations, progress and cancellation

Download destinations may be a path or a binary writable stream, including for media.
Caller streams remain open, write from their current position, support partial writes,
and can retain a partial result on error. Return value is Path for paths and None for
caller streams. No entire-file buffering is required.

For a path, a private temporary file is written in the destination directory, flushed,
fsynced, then atomically linked into place without replacing an existing file. Cleanup
closes/unlinks temporary resources, including cancellation during acquisition. The
parent directory must be trusted and support hard links. There is no directory fsync,
resume journal or power-loss guarantee. Cancellation concurrent with successful final
publication can leave the completed destination; cancellation cannot undo a write that
has already committed.

`progress(done, total)` may be sync or async. Upload reports accepted bytes, possibly
noncontiguous when parts complete out of order, **not a resumable prefix**. Downloads
report written bytes within the requested range; total is the range length. Callbacks
run serially, first at zero then after each acknowledgment/written chunk; successful
final progress reaches total. Empty downloads report (0, 0). Progress failure or
cancellation aborts the operation; upload progress does not imply message delivery.

Disk I/O runs in worker threads. Cancellation waits for in-progress work and cleanup,
even after repeated cancellation, so file handles cannot be closed while workers still
use them. This cannot interrupt a permanently blocked custom stream or OS operation.
Each RPC has its own deadline; use asyncio.timeout around a transfer for an application
budget, subject to joined disk cleanup. SIGKILL/machine failure cannot guarantee cleanup.

Protocol basis: [Telegram file API](https://core.telegram.org/api/files),
[saveFilePart](https://core.telegram.org/method/upload.saveFilePart) and
[getFile](https://core.telegram.org/method/upload.getFile). No new rate-limit evasion or
cryptographic primitive is introduced.
