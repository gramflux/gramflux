# Roadmap after the native engine transition

The native runtime removes the competing-client runtime. Native key creation, encryption, framing,
request correlation, auth RPCs, SRP and update synchronization are implemented with
focused tests. Real Telegram evidence covers key exchange and encrypted ping/pong over
three TCP modes. This is an engineering alpha; the original production definition is
not complete, and file/class counts are not completion evidence.

Priorities based on current evidence:

1. Dedicated account/bot integration: login codes, password, reuse, messages, media,
   channel/global differences, reconnects, salt/clock errors and real DC migrations.
   The anonymous API probe did not pass application initialization; do not treat it
   as account/API coverage. Never embed credentials in tests or CI.
2. Independent cryptographic/protocol audit, service-message/resend/state coverage,
   native fault-injection and soak tests. Resolve uncertain destroy_auth_key EOF
   confirmation and plan cryptography's FFDH deprecation migration.
3. Profile the native hot paths. Python IGE remains costly despite a measured XOR
   improvement. Measure real RPC/transfer/RSS before selecting optional acceleration;
   no Rust/C rewrite merely for marketing, no competitor performance claim yet.
4. Durable application acknowledgment/cursor journal and
   controlled reconnect recovery with explicit write-outcome rules. Current queues
   fail closed on overflow and do not replay ambiguous application writes.
5. Media DC authorization, authenticated CDN/file-hash verification, reference refresh
   and safe resumability. Current native file pipeline supports bounded concurrent
   upload parts and lazy byte ranges, not automatic interruption recovery.
6. Continue refining generated field typing, schema-change review and broader administrative/
   bot convenience APIs. Raw declarations are not proof every method works end to end.
7. Verify OS/provider/Python matrix and configure hosted security/maintainer channels
   before any production release or stable-API promise.
