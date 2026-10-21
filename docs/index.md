---
title: Introduction
description: Build Telegram clients with an independent, typed, asyncio-first Python library.
sidebar_label: Introduction
---

# Build with GramFlux

GramFlux is an asyncio-first Python client for the official Telegram MTProto API.
Use a consistent high-level API for everyday messaging, then access the pinned
Telegram schema through typed raw methods when you need more control.

The runtime belongs to GramFlux: connection framing, authorization-key exchange,
encrypted envelopes, request correlation, SRP, update recovery and file pipelines.
No competing Telegram client is a runtime dependency or fallback.

## Choose your next step

| You want to… | Read |
| --- | --- |
| Install and send your first message | [Quick start](getting-started/quickstart.md) |
| Register, reopen or temporarily authorize an account | [Authentication](guides/authentication.md) |
| Stop login now and resume in another process | [Resumable login](guides/authentication.md#resume-login-after-stopping-the-process) |
| React to messages, callbacks and inline queries | [Events and filters](guides/events.md) |
| Upload documents or stream downloads | [File transfers](guides/files.md) |
| Call an official method directly | [Typed raw API](guides/async-api.md) |
| Check a signature or parameter | [Client reference](reference/client.md) |
| Understand defaults, variants and optional arguments | [Parameter guide](guides/parameters.md) |

## Know the current boundaries

GramFlux **0.5.0a2 is an engineering alpha**. Generated coverage, local correctness
tests and live account interoperability are different things.

| Area | Current evidence |
| --- | --- |
| 783 raw API functions, layer 225 | Generated signatures, request serialization and controlled forwarding tests |
| 1573 TL data constructors | Pinned official schema; IDs and fields verified against official JSON |
| Eight high-level event classes | Controlled native update/dispatcher tests |
| 156 raw Update constructors | Registry-validated selection through the raw event interface |
| TCP key exchange and encrypted ping | Verified against Telegram on full, intermediate and abridged TCP |
| Account login, messaging, media and live recovery | Implemented; controlled tests only in this environment |
| Resumable login | SQLite/process-boundary tests, including abrupt process termination |
| Production certification | Outstanding: authenticated live verification, independent security review and soak testing |

Secret chats/qts synchronization, automatic application-RPC replay, proxy support,
CDN downloads, cross-library session conversion and resumable file transfers are
unsupported. See [compatibility](design/compatibility.md) and the
[release assessment](releases/0.5.0a2.md) before adopting GramFlux.

## Working principles

**Explicit lifecycle.** Connecting does not silently prompt or log in. A session's
intent—new, saved or temporary—is visible in your code.

**Predictable failure.** Requests have deadlines, admission is bounded, cancellation
is isolated, and ambiguous writes are not automatically repeated.

**A shared native path.** High-level operations, `client.api` and `client.invoke`
all use the same native protocol implementation.

**Verifiable maintenance.** Schema snapshots, reproducible reference generation,
quality checks and measured evidence stay in the repository. No comparative speed
claim is made without a fair benchmark.
