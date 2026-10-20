# Changelog

## 0.1.0a1 — unreleased

- Project and distribution renamed to GramFlux (`gramflux`); import with `import gramflux`.

- Initial engineering alpha with explicit Telethon 1.45.0 runtime integration.
- Official schema provenance, deterministic typed generation, JSON cross-check and diff CLI.
- Independent bounded TL codec and reference TCP framing, with native initial handshake probe.
- Bounded public request admission, cancellation/deadline behavior and safe error mapping.
- GramFlux SQLite/memory session snapshots, ordered events, composable filters and streaming files.
- Deterministic tests, opt-in identity test, local codec benchmark, documentation and CI.

Not a production release candidate. Real-account authorization, message exchange,
update recovery and media interoperability have not been verified.
