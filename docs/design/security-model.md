# Native security model

Assets include auth keys, API hashes, bot tokens, codes/passwords, private content and
session files. Boundaries include network inputs, local storage, schemas, callbacks
and the cryptographic provider. Cloud MTProto is not an end-to-end secret chat.

| Threat | Implemented protection | Residual limitation |
| --- | --- | --- |
| Fake server/key exchange | Pinned production RSA public key, RSA_PAD, nonce/hash checks, strict official 2048-bit prime/generator/public bounds, OpenSSL DH | Trust constants require reviewed updates; no independent crypto audit |
| Altered/replayed messages | MTProto 2 SHA256 message-key check with constant-time comparison, session/key/length/padding checks, time/ID window and replay floor | Full adversarial protocol review and stress tests outstanding |
| Salt/clock spoofing | Corrections require authenticated matching request/service references; replayed envelopes cannot roll metadata back | Only selected rejection recovery is implemented; no blind reconnect/resend |
| Malformed input/exhaustion | Bounded framing/codec/depth/vectors, bounded request/update counts, bounded gzip, ack/resend tracking limits | Count/wire bounds are not a complete RSS or multi-client/application-memory guarantee |
| Secrets in diagnostics | Native TL repr omits values; RPC identifiers sanitized; no keys/payloads/user tracebacks in routine logs | Python heap/debugger/application callbacks can expose data; no guaranteed zeroization |
| Local session theft | 0600 POSIX files, no-follow regular-file checks, ownership lock, transactional SQLite | Keys are plaintext at rest; trusted directories, machines and backups required |
| Corrupt/foreign state | Application/schema IDs, atomic snapshot validation before mutation, bounded typed counter metadata | No foreign conversion or automatic repair; untrusted SQLite is not a sandbox |
| File paths/interruption | Caller-selected paths, private temporary files, no-overwrite atomic link, joined worker cleanup | No power-loss/resume guarantee; non-cooperative OS/custom streams can block cleanup |
| Callback loss/gaps | Own pts/seq/differences, bounded queues with explicit overflow failure, handler completion before cursor commit, producer stopped before callback shutdown | No transactional journal/exactly-once claim; crash/partial batches can replay; live recovery unverified |
| Supply chain | Explicit HTTPS schema refresh, retained sources/hashes, deterministic namespaces, locked provider deps | Hashes are provenance, not signatures; provider/upstream authenticity still needs review |

Only public RSA/DH/DC protocol constants were extracted from official references,
with source URL/commit/hash in tl/data/trust.json. No competitor protocol code is shipped.
AES/DH primitives use cryptography/OpenSSL; Python IGE glue and SRP bigint operations
have not been audited for constant-time behavior. Telegram requires finite-field DH;
cryptography 50 warns about future FFDH API deprecation. Provider maintenance is a known
release blocker, not a reason to substitute an incompatible key exchange.

Session peer metadata is minimal/bounded; min entities cannot overwrite full hashes,
usernames expire and are re-resolved after restart. Sensitive identity decisions should
verify stable numeric IDs freshly. Scoped deletion prevents wrong-chat global-ID deletes.
Neither logout nor deleting a snapshot securely erases historic DB pages/backups.

A real anonymous key/ping probe does not prove account auth, complete protocol security
or remote deletion of its key. Cleanup is reported as uncertain if the server closes
without a parsed confirmation. No user credentials are used by that probe. No secrets
vault/encryption-at-rest feature, spam tooling, evasion or unauthorized access is added.
See SECURITY.md for reporting and the release report for outstanding security work.

The native waiting-update queue is bounded by both envelope count and decoded-wire byte charges. Byte charges are released at dequeue; active objects and Python allocation amplification remain outside this wire budget. Lost-reply/committed-write errors use RequestOutcomeUnknown. Dedicated live validation must not expose sessions as CI artifacts; the manual workflow uses owner-only temporary files and explicitly selected mutation scope.
