# Security model

Assets: authorization keys, API hash, bot tokens, passwords/codes, session files,
private messages and user-provided file destinations. Boundaries: local filesystem,
Telegram MTProto backend, schema downloads, untrusted incoming binary objects, callbacks
and dependencies. MTProto cloud chats are not end-to-end encrypted secret chats.

| Threat | Protection | Residual risk |
| --- | --- | --- |
| Credential leakage | No credential repr in LoginChallenge/SessionData/native objects; sanitized RPC identifiers, backend log redaction, handler exceptions logged by type only | Python does not guarantee secret zeroization; callbacks and debuggers can expose objects; raw/backend objects may have value-bearing reprs |
| Local session theft | POSIX mode 0600, no-follow open, regular-file validation, exclusive ownership lock, transactional SQLite snapshot | Keys are plaintext at rest; machine compromise, backups, malicious parent directory or privilege escalation compromise accounts |
| Corrupt/foreign database | application_id and schema version checks; unrelated databases refused; version upgrades fail explicitly | No automatic repair or migration; untrusted SQLite input itself is not a sandbox |
| Malformed TL | Bounded lengths, vector counts, depth, ID registry; unknown flags and trailing input rejected | These bounds govern independent codec only; live decoding is backend policy |
| Resource exhaustion | Bounded admitted public RPCs and event dispatcher queue, chunked files | Backend update queues and some caches can grow; end-to-end memory bounds not established |
| Unsafe transfer paths | Only caller-supplied destination; secure temp in destination directory; atomic no-overwrite hard-link publication; cleanup on failure | Trusted local directory required; POSIX hard-link semantics; not durable resume; no CDN support; file references may expire |
| Event-loop blocking | SQLite/file I/O and SRP moved to threads; cancellation joins active workers | Backend key generation/other CPU code needs profiling; arbitrary user callbacks may block indefinitely |
| Schema supply chain | Explicit HTTPS fetch with normal certificate verification, exact source/hash/date, deterministic regeneration and JSON cross-check | Hash proves snapshot identity, not upstream authenticity; no signed schema publication verified |
| Network tampering | Established backend's MTProto implementation; native probe never accepts credentials or establishes trust | No new independent crypto audit; pinning a library is not proof of cryptographic correctness |
| Ambiguous request outcome | No broad application retry; bounded auth-only migration retries; explicit waits/errors | Backend retransmits protocol messages during reconnect; a timeout/cancellation cannot retract a server action |
| Interrupted shutdown | Shielded cleanup and worker joining; atomic session transaction, temporary download cleanup | SIGKILL/power loss can lose recent auth/update snapshots; callback delivery is not transactional |

No encryption-at-rest feature or secrets vault is invented. Use encrypted storage provided
by the OS and protect backups; adding application encryption requires external key
management and another dependency/security review. Session files must not be uploaded as
bug reports. No cross-library conversion or silent authenticated-session replacement.

Runtime dependency audit is recorded in `research/dependency-audit.txt`; results apply
only at scan time. The release still requires independent cryptographic review, live
fault injection, memory/soak testing, verified dependency artifacts, a private security
reporting channel, and a supported response policy. See SECURITY.md. No anti-abuse
bypass, spam tooling, flood evasion or unauthorized login functionality is implemented.
