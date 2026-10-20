# Roadmap and phase assessment

The initial vertical slice is working and testable, but the master product definition
is not complete. Directories/classes do not count as completion evidence.

| Phase | Assessment |
| --- | --- |
| Research/foundation | Primary-source snapshots, installable package and CI configured; CI matrix not run locally |
| Schema generation | Deterministic official snapshot generation/verification implemented; strict type unions, other grammar/layers and wire integration remain |
| Core protocol | Independent codec/framing and first native exchange verified; encrypted engine delegated, not independently implemented |
| Auth/persistence | Real backend flows, own async stores, deterministic tests; account interoperability unverified |
| Core operations | Backend get_me/send_message/raw implemented; live account work pending |
| Events/files | Local pipelines tested, backend reconciliation inherited; durability, full memory bounds, CDN/cross-DC and live transfers incomplete |
| Performance/reliability | One local codec baseline; no superiority, soak, server fault-injection recovery or transfer performance evidence |
| Developer experience | Guides/examples/release procedure in place; examples compile and controlled flows tested, credentials needed for live execution |
| Release readiness | Alpha artifacts built/tested; production release blocked below |

Priority order:

1. Dedicated-account interoperability tests: code, SRP, bot, session reuse, send/receive,
   photo/document transfer, real migration/flood/disconnection cases; never use customer
   credentials in CI. Strengthen malformed server-data and secret-log regression tests.
2. End-to-end update backpressure, persistent entity/access hashes and durable cursor
   advancement tied to dispatch; prove gaps/differences/dedup/channel state recovery.
3. Audit backend cryptography, reconnect cancellation and protocol resending; replace
   private adapter hooks with a supported integration boundary. Decide whether a native
   engine provides enough value to justify the protocol maintenance/security burden.
4. Resolve official page/backend schema divergence and add verified native wire adapters,
   generic result readers and precise generated type unions; add schema-change CI review.
5. Cross-DC export/import authorization for media, CDN decryption, expiring references,
   bounded concurrent parts, conservative retry policy and partial-transfer recovery.
6. Profile realistic codec/event/file/session workloads and optimize measured bottlenecks.
   Run multi-session RSS, controlled reconnect, cancellation storms and soak benchmarks.
7. Verify Python/OS matrix, implement non-POSIX storage if desired, configure hosted
   security/maintainer contacts, audit licensing/branding and sign release artifacts.
