# Architecture and implementation boundary

GramFlux is currently a dependency-backed alpha. It is not an independent MTProto engine
and is not a superficial renamed fork: no competitor implementation is vendored, and
the schema pipeline, codec, session persistence, dispatch, request admission, file I/O
and public lifecycle are original modules with separate tests. Independence and measurable
advantages remain roadmap goals, not shipped claims.

| Component | Responsibility |
| --- | --- |
| `client.py`, `config.py` | Explicit connect/auth/shutdown; typed convenience methods, deadlines, concurrency admission |
| `backend.py`, `raw.py` | Pinned Telethon integration; sanitized RPC errors/logs, snapshot adapter, wire bindings |
| `storage.py` | Async storage protocol, memory store, off-loop transactional SQLite, ownership lock |
| `events.py`, `filters.py` | Bounded ordered callback queue, async handlers, composable synchronous filters |
| `files.py` | Seekable uploads, official small/big parts, streaming downloads, progress, atomic no-overwrite paths |
| `tl/parser.py`, `model.py`, `generator.py` | Source diagnostics, validation, deterministic typed definitions |
| `tl/codec.py`, `generated/` | Independent bounded TL binary codec and constructor registry |
| `mtproto/framing.py`, `probe.py` | Independently checked transport reference and native unencrypted handshake probe |
| `tools/schema.py`, `benchmark.py` | Explicit refresh, offline verify, diff, reproducible local measurements |

The live backend owns RSA/DH authorization-key creation, MTProto 2.0 encryption,
message IDs/seqnos/session salts, containers, acknowledgments, response correlation,
protocol resends, reconnects, migration and update pts/qts/seq recovery. GramFlux does
not claim to independently audit these merely by depending on them. SRP computation
uses backend primitives in a worker thread. Other backend CPU-heavy operations may
still block the event loop; benchmark/audit work is outstanding.

The client creates one child task per admitted operation. Timeout includes semaphore
admission, cancellation propagates to that operation, and disconnect cancels admitted
operations before closing the backend and persisting state. Waiting callers recheck
lifecycle state after admission. No broad application RPC retry is configured. At most
two additional attempts are allowed for explicit preauthorization code/bot/password
operations rejected with a migration response after the pinned backend switches DC.
Network ambiguity does not authorize creating another send-message request.

Dispatcher callbacks run one at a time in registration order. A failure is reported
without exception contents and later handlers still receive that event. Full queues
block producers. This does **not** bound Telethon's internal update queue; a slow
consumer can still accumulate upstream updates. End-to-end bounded update buffering,
durable event delivery and application-level deduplication are release blockers.

SQLite saves auth/DC and backend update-state snapshots. Entity/access-hash caches
are in-memory only. State is synchronized to disk on auth changes and clean disconnect;
there is no crash-consistent update cursor/durable callback transaction. SQLite methods
run off-loop; cancelled workers are joined before releasing their lifetime lock.

Independent generated declarations use the source page advertised as layer 225.
The backend's runtime uses layer 229. `Client.invoke` only accepts backend TLRequest
instances. Joining those two schema universes without negotiated-layer validation
would be unsafe. The native probe checks nonce and envelope structure but does not
authenticate Telegram; no keys or credentials are involved.

Dependencies were selected for a functional and reviewable vertical slice rather than
a new cryptographic implementation. There is no plugin framework, compiled extension,
or Pydantic dependency. Storage and the backend are injectable test boundaries; the
private `_backend` constructor argument is not a promised extension API. Native framing
and codec are currently independent test/tool subsystems, not the live wire stack.
