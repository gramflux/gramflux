# Native compatibility and coverage

0.3.0a1 uses Python >=3.11. Local Python/platform results are recorded in the
[current report](../releases/0.3.0a1.md); CI targets Python 3.11–3.14 on Ubuntu.
Configured jobs are not evidence of hosted CI execution. Persistent storage requires
POSIX flock; Windows/macOS storage/transfer behavior remains unverified.

Official sources: tl/data/api.tl, api.json, mtproto.tl and metadata.json, retrieved
2026-10-20. Advertised and native negotiated layer: **225**. API TL SHA256:
13d9c9f4a4ecc7282725b5a558f719cea5af0c3bafcf62531cac3a18bfaca046.
Generated declarations: 1573 constructors, 783 methods; all IDs/fields matched against
retained official JSON. 1572 non-vector constructor minimal shapes round-trip. Protocol
parser recognizes 46 explicit-ID declarations, with specialized service/container logic.
Generation coverage is not end-to-end method or exhaustive flag coverage.

The former layer-229 dependency bindings are gone. gramflux.raw and independent
objects now reference the same generated classes used by Sender. Constructors are
keyword-only; raw dates are Unix seconds. Foreign library TL objects are not accepted.
This is an intentional 0.3 alpha compatibility break. No drop-in API/session promise.

| Feature | Verification/status |
| --- | --- |
| Native RSA_PAD/DH and encrypted ping | Real Telegram DC 2 on full/intermediate/abridged TCP |
| Native RPC/auth/user/bot/SRP | Serialization and controlled response tests; SRP proof checked against server algebra; real account authorization unverified |
| Peers/messages/dialogs/members/media | Native objects and RPC path, existing deterministic suites; real account/media exchange unverified |
| Update differences/counters | Controlled global/channel gap, cancellation/commit, duplicate and short-update tests; live recovery unverified |
| Session format | Own version-1 snapshots with additive salt/time metadata; deterministic old-own-format restore tests, not foreign conversion/live migration |
| Failure policy | Bounded in-flight work, explicit overflow/disconnect, no ambiguous write replay; automatic in-flight reconnect recovery unsupported |
| Unsupported | Secret chats/PFS, signup/QR/passkeys, CDN, cross-DC media recovery/resume, proxies, durable callback journal |

The anonymous API probe returned CONNECTION_NOT_INITED without application credentials;
it is recorded as a rejection, not successful account API coverage. Key-destruction
confirmation after the probe is uncertain when the server closes the socket; it is
never inferred from EOF. The old req_pq-only probe remains a separate tool.
