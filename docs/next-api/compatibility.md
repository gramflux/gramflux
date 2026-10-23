---
title: Coverage, compatibility and limits
description: Coverage, compatibility and limits for the additive GramFlux Next-Generation API.
---

# Coverage, compatibility and limits

This is an additive public API layer. It does not claim a new MTProto engine, API
layer or live-feature coverage. GramFlux remains an engineering alpha with the
existing release assessment and runtime limitations.

## Implemented and controlled-test verified

- Cached local auth, account, peers, files, contacts, dialogs, bot, invites and membership views.
- Local chat resources with messaging, history/search/member views, metadata and supported media helpers.
- Typed raw namespaces plus invoke on the original Client path.
- Independent and nested Routers mounted on the existing dispatcher.
- Original typed events, composable filters, stable priorities, StopPropagation and error reporting.
- Explicit mounts, idempotent repeated root inclusion, overlap/cycle rejection and selective removal.
- Message-only commands, whitespace argument parsing, parse opt-out and original event access.
- Legacy signature snapshots, result/exception forwarding, lazy streams, SQLite login checkpoint reuse and file boundaries.

## Intentionally constrained

Router trees freeze when first mounted. There is no dynamic post-mount editing,
router-specific worker, dependency-injection container, command argument schema or
shell grammar. Application-owned jobs remain outside the dispatcher checkpoint.

No general TransferOptions is added: uploads and downloads expose different controls,
and the existing explicit keywords preserve their contracts. No empty namespace is
created for operations without an existing implementation.

client.chat is a cached callable ChatFactory producing peer-bound local views.
Resources do not memoize a resolved username, assert membership or guarantee access.
Remote requests resolve and validate through existing Client operations.

## Existing unsupported workflows remain unsupported

This work does not add proxy transports, secret-chat/qts synchronization, general
DC migration/replay, CDN downloads, resumable file transfer, session conversion,
payment/call workflows or durable exactly-once callbacks. Raw declaration availability
is not implementation of those workflows.

No account credentials were available for new live Telegram tests. Automated evidence
uses controlled backend responses, actual serialization/storage/file pipelines and
the existing event dispatcher. Independent security review and authenticated live
interoperability remain release blockers.

See [the compatibility matrix](../design/compatibility.md),
[verification procedure](../guides/live-validation.md) and
[legacy migration](migration.md) before adopting the new surface in production.
