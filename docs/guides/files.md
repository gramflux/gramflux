# File transfers

```python
uploaded = await client.upload_file("report.pdf", on_progress=progress)
message = await client.send_file("me", uploaded, caption="Report")
await client.download_media(message, "report-copy.pdf", on_progress=progress)
```

`progress(done, total)` can be synchronous or async. It is called first at zero and
after each accepted/uploaded or written/downloaded chunk, monotonically for one
transfer; final progress reaches total. An empty permitted download reports (0, 0).
Exceptions and cancellation from progress abort the transfer. `send_file` accepts the
uploaded handle, not an implicit file read. These operations have deterministic tests;
no actual Telegram media exchange was performed during development.

Upload accepts paths or seekable binary streams, starting at the stream's current
position. Caller-owned streams remain open; library-owned handles close on success,
failure and cancellation. One 512-KiB chunk is sent at a time (plus bounded temporary
copies). Up to 4000 parts are allowed conservatively. Small files <=10 MiB use
saveFilePart and the required MD5 checksum; larger files use saveBigFilePart. MD5 is
used for the protocol checksum, not as a security primitive. Empty uploads and
nonseekable streams are rejected. Do not concurrently mutate a source during transfer.

`download_file(location, destination, size=...)` accepts raw input locations and an
explicit expected size. `download_media` resolves supported documents/photos from a
Message. Sequential getFile parts are checked for truncation and alignment. Downloads
do not buffer entire media. Caller streams support partial writes and remain open.
For a path, a private temporary file is written in the destination directory, flushed,
then atomically linked into place without overwriting an existing file; interruption
cleans temporary resources. The destination directory must be trusted and support
hard links. There is no directory fsync/power-loss guarantee.

No automatic retry of ambiguous failures, resume, parallel upload, CDN decryption,
cross-DC media migration handling or file-reference refresh is implemented. These
conditions fail explicitly or surface mapped server errors; the caller must resolve a
fresh location/reference or choose an appropriate DC through future supported APIs.
A failed upload can leave temporary server parts; Telegram expires those, and there
is no claimed rollback or resumability. Each RPC has a deadline; total transfer time
is controlled by wrapping the transfer in the application's `asyncio.timeout`.
