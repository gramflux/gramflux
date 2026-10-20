# Native runtime architecture (0.3)

The production path is Client → own generated raw method → Codec → Sender →
MTProto 2.0 encryption → Connection/Framing → asyncio TCP. No external Telegram client,
session implementation, update engine or error reader is imported or used as fallback.
cryptography supplies OpenSSL AES and finite-field DH primitives, not Telegram logic.

| Component | Implemented responsibility |
| --- | --- |
| client/auth/sessions/config | Explicit lifecycle, login retries, high-level facade, deadlines and configuration |
| raw/tl/generated | Deterministic aliases and dataclasses for the pinned official layer 225; same objects used on wire |
| tl/codec/parser/generator/namespaces | Bounded schema-verified encoding/decoding and auditable generation |
| mtproto/connection/framing | Async sockets, serialized framed writes, full/intermediate/abridged TCP |
| mtproto/crypto/auth_key/srp | RSA_PAD, pinned trust/prime, nonce checks, OpenSSL DH, AES-IGE glue, MTProto 2 KDF/MAC, password SRP |
| mtproto/sender | Bounded correlation/admission, sequence/IDs, containers/gzip, ack batching, replay window, salt/clock correction, terminal disconnect semantics |
| backend | Own native runtime orchestration, layer/init wrapper, auth RPCs, send-response normalization, heartbeat, safe snapshot mapping |
| mtproto/updates | pts/seq checks, global/channel differences, duplicate checks, short updates, session-reset recovery |
| peers/peer_utils | Own identity conversion, bounded access-hash/entity caches and username expiry |
| messages/dialogs/chats/pagination | Existing demand-driven high-level services, now native requests/results |
| events/filters | Bounded ordered dispatcher, priorities/removal, errors and handler completion boundary |
| files/storage | Bounded chunk pipeline, joined file I/O, atomic destinations, protected own SQLite/memory sessions |

Request admission includes its timeout; one request cancellation does not cancel
other correlations. Completed/late responses are acknowledged. New requests have
monotonic fractional message IDs and content sequence numbers. A committed write is
joined on cancellation; cancelling cannot retract bytes already sent. Broken streams
fail pending requests with an ambiguous-outcome TransportError. There is no arbitrary
replay after reconnect; initial TCP establishment has bounded retries. Only explicit
correlated bad-salt/time rejection permits a bounded protocol resend. Other sequence
repair is unsupported, with explicit failure. Heartbeats use two reserved bounded
control slots so a full application-RPC window cannot prevent liveness checks.

Both update queues are count-bounded. Native receive overflow disconnects explicitly
rather than dropping an update or blocking the reader needed by handler RPCs. The
producer awaits dispatcher completion before committing counters. Shutdown stops that
producer before cancelling callbacks. Difference slices commit only after their handler
boundary. Snapshot persistence is not a transactional event journal: partial batches,
crashes and failed callbacks can still require idempotent application processing.
Too-long differences, missing channel hashes and secret-chat updates fail explicitly.

TCP/key setup and ping/pong have real Telegram evidence. Account APIs, channel recovery,
reconnect/fault behavior and file transfer remain controlled-test verified only. A native
engine is not a performance-superiority or cryptographic-audit result. Remaining
boundaries and verification are in the current release report.
