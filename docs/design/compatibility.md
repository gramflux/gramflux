# Compatibility and coverage

Actual local verification: CPython 3.12.3, Linux x86_64 (glibc 2.39). Python >=3.11
is the declared minimum. CI is configured for Ubuntu Python 3.11–3.14; configuration
is not evidence that these jobs have run. Persistent storage currently requires POSIX
flock; Windows persistent sessions and full cross-platform transfers are unsupported.
Memory-store use on Windows/macOS has not been verified here.

Pinned official source: `tl/data/api.tl`, official JSON, `mtproto.tl` and `metadata.json`.
Retrieved 2026-10-20. Advertised page layer: **225**. API TL SHA256:
`13d9c9f4a4ecc7282725b5a558f719cea5af0c3bafcf62531cac3a18bfaca046`.
Generated independent declarations: **1,573 constructors, 783 methods**, all IDs and
fields cross-checked against retained official JSON. The polymorphic vector constructor
has specialized codec semantics; 1,572 other constructor minimal shapes round-trip.
That is not exhaustive flag combinations, all possible objects or live method coverage.
Protocol parser verifies 46 explicit-ID declarations; primitive/vector preludes and
bare message records are special cases. Independent protocol object generation and
bare-type serialization are not advertised as supported runtime features.

Runtime: Telethon **1.45.0**, generated layer **229**, imported via `gramflux.raw`.
Different source provenance/layer from independent output is intentional and visible.
Neither runtime binding count nor generator count proves Telegram accepts every method.
Independent declarations cannot be passed to Client.invoke. No live account test has
run; the credential-free native initial handshake probe is the only Telegram wire
exchange verified in this environment.

| Area | Coverage boundary |
| --- | --- |
| High-level client | get_me, literal send_message, explicit code/password/bot auth, raw invoke, upload/send_file, document/photo download |
| Events | New/edited messages; text/direction/chat/sender/regex filters; serialized callbacks |
| State recovery | Backend pts/qts/seq handling; own snapshot persists clean-shutdown state, no durable event journal |
| Transports | Backend full/intermediate/abridged TCP; independent framing checked separately |
| Media | Seekable binary uploads up to 4000 512-KiB parts, empty upload rejected; explicit-size downloads; no CDN/parallel/resume/cross-DC file retry |
| Errors | GramFlux sanitized RPC/auth/wait/migration/transport/session/serialization errors; timeout and cancellation remain asyncio/Python exceptions |
| Session formats | GramFlux version-1 SQLite or MemoryStorage; no Telethon/Pyrogram/Hydrogram/Pyrofork file compatibility |
| Unsupported auth | Signup, QR, passkey, email verification, special official-app SMS/payment flows |

Migration guides map supported operations only. There is no drop-in compatibility
promise. Read `docs/guides/migration.md` for behavioral differences.
