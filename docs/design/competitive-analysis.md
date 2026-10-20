# Competitive research — 2026-10-20

Primary sources: official project repositories, package metadata, checked-out metadata
snapshots in `research/*-repository.json`, and `research/test-inventory.json`. File
counts include helpers and package files, so they do not measure quality or coverage.
No competitor performance claim is inferred from architecture. No source implementation
was copied. Repository metadata can change; the recorded date matters.

| Project | Observed maintenance | Architecture/API and dependencies | Compatibility/testing observations |
| --- | --- | --- | --- |
| [Telethon](https://pypi.org/project/Telethon/1.45.0/) | GitHub mirror archived; current package links to [Codeberg](https://codeberg.org/Lonami/Telethon), v1 described as maintenance mode. PyPI 1.45.0 released 2026-09-10 | asyncio TelegramClient, generated TL, Python MTProto, pyaes/rsa; optional acceleration. Familiar raw functions and high-level helpers | Package declares Python >=3.5; installed version tested here on 3.12. GitHub mirror test inventory includes crypto/RSA, helpers, events and client tests; not a current Codeberg CI audit |
| [Pyrogram](https://github.com/pyrogram/pyrogram) | Repository archived, pushed 2024-12-23 | Decorator Client API, generated raw layer, own sessions/dispatcher, pyaes 1.6.1/pysocks 1.7.1; optional TgCrypto | setup declares ~=3.7; classifiers through 3.11 are not modern-version verification. Tests inspected include commands/HTML/file IDs; GitHub Python workflow exists |
| [Hydrogram](https://github.com/hydrogram/hydrogram) | Not archived; pushed 2026-04-10 at inspection | Pyrogram-derived API; pyproject depends on pyaes, pysocks, aiosqlite; optional TgCrypto/uvloop | Python >=3.9, classifiers through 3.13; pytest/pytest-asyncio/Ruff development tools; API-update workflow; small test directory observed |
| [gotd/td](https://github.com/gotd/td) | Not archived; pushed 2026-10-19 | Go, generated TL, explicit contexts, modular transport/auth/storage; substantial Go dependency graph | go.mod declares Go 1.25; hundreds of *_test.go files, benchmark/e2e/nightly/schema-update workflows. Not a Python API substitute |

Limitations are contextual: Telethon's flexible high-level calls and backend retry/update
behavior require careful policy integration; archived Pyrogram is a maintenance risk;
Hydrogram and Pyrogram share an ecosystem/API heritage rather than GramFlux session
compatibility; gotd requires Go. None of these observations establish GramFlux superiority.

GramFlux's current differentiators are auditable official TL-vs-JSON verification,
fail-closed schema changes, explicit admission deadlines, value-free error diagnostics,
and a small streaming/persistence API. Their developer and performance benefits have
not been established in user studies or server workloads. The native codec is currently
slower on the recorded benchmark. In the initial 0.2 baseline core networking was dependency-backed. Since 0.3.0a1
the engine is independent; that change does not establish a performance advantage.

Official protocol research: [API](https://core.telegram.org/api),
[schema](https://core.telegram.org/schema), [MTProto schema](https://core.telegram.org/schema/mtproto),
[protocol](https://core.telegram.org/mtproto), [TL](https://core.telegram.org/mtproto/TL),
[serialization](https://core.telegram.org/mtproto/serialize),
[transports](https://core.telegram.org/mtproto/transports),
[authorization](https://core.telegram.org/api/auth),
[terms](https://core.telegram.org/api/terms),
[credentials](https://core.telegram.org/api/obtaining_api_id).
The official machine-readable JSON was retained as an independent check against HTML
TL extraction, rather than substituting a competitor's schema.
