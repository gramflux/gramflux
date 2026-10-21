# Errors, transports, troubleshooting and FAQ

Public errors live in `gramflux.errors`. ConfigurationError, SerializationError,
SchemaError, SessionError, LifecycleError, TransportError, FileTransferError and
UnsupportedFeature distinguish local failures. PeerNotFound reports missing valid peer/access-hash information; PaginationError reports unusable/stalled cursors rather than silently ending results. SessionNotFound and SessionAlreadyExists
distinguish open-only and exclusive-create mistakes. AuthenticationRequired provides
login guidance; LoginAttemptsExceeded is a local input-budget error, not a Telegram RPC. RPCError includes sanitized `code`
and `name`; AuthenticationError, PasswordRequired, FloodWait (`seconds`) and
MigrationRequired (`dc`) specialize server responses. Server error_code/error_message fields are mapped directly by the native runtime;
unknown or unsafe identifiers use a value-free fallback.
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

The example does not retry a request. Timeout/cancellation cannot retract a write.
The native sender does not replay pending application requests after a lost connection.
It fails them with an explicit ambiguous-outcome TransportError. Reconnect explicitly
using the same Client/session; decide write recovery from application semantics.
Correlated bad-salt/time rejections permit one protocol resend; sequence-repair and
arbitrary server rejection retries are not implemented. Code/bot authorization may
repeat at most twice only after the runtime actually switches to a recognized DC.
Other migrations surface to the caller; no unchanged-DC retry loop is permitted.

Use Config(request_timeout=30, max_concurrent_requests=32, event_queue_size=256,
reconnect_attempts=3, peer_cache_size=2048, transport="intermediate"). The transport
modes use GramFlux's own framing and MTProto 2.0 encryption; no TLS certificate setting
is disabled. reconnect_attempts bounds initial TCP establishment retries, not automatic
replay after a disconnect. The native heartbeat detects dead connections. Proxy,
MTProxy, HTTP/WebSocket, IPv6 configuration and obfuscation are not exposed.

Questions that recur:

- **Why am I unauthorized inside `async with`?** Connecting does not log in. Run the
  login example with `--create example` once, then use `Session.open("example")`.
- **Why is my other library's session rejected?** Formats are not interchangeable.
  Preserve that file and log in using a new GramFlux filename.
- **Why are updates not arriving?** Register before connecting, keep the context alive,
  check account permissions and handler filters. Do not block the event loop.
- **Why did my generated object fail invoke?** Use a native generated method with keyword arguments. Independent
  definitions and wire bindings now use the same layer; foreign library objects are rejected.
- **Why is a download rejected?** Check expected size, supported media type, writable
  trusted directory, DC, file-reference expiry, and whether a CDN redirect was returned.
- **Why is a session locked?** Another process owns it; shut that process down. Do not
  copy or delete a live database to bypass locking.
- **Does cancellation undo a message?** No. It stops waiting, not a server action.
- **Is this faster than Telethon?** Not established. The runtime is now independent, but no fair
  end-to-end competitor benchmark or live transfer measurement has been performed.
- **Can I use Windows persistent storage?** Not currently; POSIX flock is required.
- **Can I recover corrupted data automatically?** No. Preserve the file, secure it,
  and authorize a new session. Never publish it for debugging.

Native runtime diagnostics do not include keys, credentials, request payloads or
user exception contents. An unconfigured logger does not interrupt terminal prompts.
For observability record latency/error class without private-content labels. OpenSSL's
FFDH API emits a cryptography deprecation warning in version 50; Telegram requires
finite-field DH, and replacing it with another key exchange would break the protocol.
The warning is documented; supported-provider maintenance remains a release blocker.

If a numeric user/channel ID raises PeerNotFound, load accessible dialogs/contacts,
resolve its current username, or provide a known full raw entity/input peer. Access
hashes are not guessed. resolve_peer(name, refresh=True) invalidates the old binding;
names expire after 60 monotonic seconds and are not trusted after restart. Metadata
persists at session snapshots, not after every response. History cursors that cannot
advance raise PaginationError. Non-channel deletion preflights the chat for every ID
before sending any delete batch. Multi-batch writes can partially succeed.

Connection setup bounds TCP establishment and preamble draining by the transport I/O deadline. The public Client applies its request timeout to the complete authorization-key/API setup. Cancelling or rejecting setup closes the socket and any started native sender. Reopening a full TCP transport starts new framing sequence counters. Initialization rejections and uncertain server errors are not cached as successful initialization; requests are never automatically replayed by this mechanism.

`Config(update_queue_bytes=16 * 1024 * 1024)` bounds waiting native updates by uncompressed TL body size as well as count. It is not a Python heap/RSS limit. Overflow terminates the connection for explicit resynchronization. `RequestOutcomeUnknown` distinguishes lost replies or potentially committed writes; do not automatically repeat mutations. Its absence does not make arbitrary TransportError failures safe to retry.
