# Errors, transports, troubleshooting and FAQ

Public errors live in `gramflux.errors`. ConfigurationError, SerializationError,
SchemaError, SessionError, LifecycleError, TransportError, FileTransferError and
UnsupportedFeature distinguish local failures. RPCError includes sanitized `code`
and `name`; AuthenticationError, PasswordRequired, FloodWait (`seconds`) and
MigrationRequired (`dc`) specialize server responses. Server identifiers are mapped
from the pinned backend's error classes; unknown dynamic errors use a safe fallback.
Python TimeoutError and asyncio.CancelledError retain their standard meanings.

```python
import asyncio
from gramflux.errors import FloodWait, TransportError

try:
    await client.get_me()
except FloodWait as error:
    await asyncio.sleep(error.seconds)  # explicit, cancellation-friendly policy
except TransportError:
    # Decide recovery from the operation's semantics. A write may have completed.
    raise
```

The example does not retry a request. Do not resend message writes just because they
time out. The backend can resend protocol messages during reconnection using its
protocol machinery; GramFlux does not add a new arbitrary retry loop. Preauthorization
code/bot/password operations allow at most two migration retries after server rejection
and backend DC switching. Other migration responses surface to the application.

Use `Config(request_timeout=30, max_concurrent_requests=32,
event_queue_size=256, reconnect_attempts=3, transport="intermediate")`.
Full/intermediate/abridged TCP are supported through the backend; TLS is not disabled
because these transports use MTProto encryption rather than a TLS wrapper. Backend
reconnect attempts are bounded. Proxy configuration, MTProxy, HTTP/WebSocket, IPv6 and
transport obfuscation are not exposed by this release. Independent Framing is a
reference/probe component, not the backend's packet decoder.

Questions that recur:

- **Why am I unauthorized inside `async with`?** Connecting does not log in. Run the
  login example once and reuse the same GramFlux session.
- **Why is my other library's session rejected?** Formats are not interchangeable.
  Preserve that file and log in using a new GramFlux filename.
- **Why are updates not arriving?** Register before connecting, keep the context alive,
  check account permissions and handler filters. Do not block the event loop.
- **Why did my generated object fail invoke?** Independent definitions and runtime
  bindings have separate layers. Use `gramflux.raw.functions` on the network.
- **Why is a download rejected?** Check expected size, supported media type, writable
  trusted directory, DC, file-reference expiry, and whether a CDN redirect was returned.
- **Why is a session locked?** Another process owns it; shut that process down. Do not
  copy or delete a live database to bypass locking.
- **Does cancellation undo a message?** No. It stops waiting, not a server action.
- **Is this faster than Telethon?** Not established. The recorded independent-codec
  microbenchmark is slower, and the runtime currently depends on Telethon.
- **Can I use Windows persistent storage?** Not currently; POSIX flock is required.
- **Can I recover corrupted data automatically?** No. Preserve the file, secure it,
  and authorize a new session. Never publish it for debugging.

Backend diagnostics deliberately omit payloads and exceptions; enabling verbose logs
does not restore them. For application observability use latency/error-class metrics
without message/credential labels. No built-in metrics exporter is shipped.
