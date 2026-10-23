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

## Recommended organization for new projects

Use the [Next-Generation API](next-api/index.md): independent Routers, typed command
contexts, local chat resources and domains sharing the existing Client implementation.
Existing Client methods and decorators remain supported. Read its development-install
notice before using these additions with a previously published wheel.

## Start here

New to GramFlux? Follow [Installation](getting-started/installation.md), then run the
[complete quick start](getting-started/quickstart.md). Continue with
[Where to go next](getting-started/next-steps.md) to choose a user-account, bot or
existing-service learning path. The Next/Previous links follow the sidebar order.

Already using the library? Open the [Client quick reference](quick-references/client.md)
to find an operation by task, or the [event quick reference](quick-references/events.md)
to choose a subscription. Every entry leads to a separate detailed API page.

## Documentation map

### Getting started and tutorials

- [Installation](getting-started/installation.md): requirements, development installs and version checks.
- [Your first client](getting-started/quickstart.md): authorize once, reopen a session, send and receive.
- [Build a command bot](tutorials/reply-bot.md): a complete application with observable test steps.
- [Learning paths](getting-started/next-steps.md): prerequisites and recommended chapter order.

### Concepts

- [Core concepts](getting-started/concepts.md): connection, authorization, sessions and API levels.
- [Asyncio and concurrency](concepts/asyncio.md): await, async iterators, task ownership and cancellation.
- [Entities and identifiers](concepts/entities.md): input peers, access hashes, marked IDs and username caching.
- [Messages and results](concepts/messages.md): constructor variants, formatting, media and helper ownership.
- [Updates and delivery](concepts/updates.md): ordering, filtering, recovery, backpressure and checkpoints.
- [Parameter conventions](guides/parameters.md): required fields, omission, defaults and raw flags.

### How-to guides

- [Authenticate](guides/authentication.md), [resume a login](guides/authentication.md#resume-login-after-stopping-the-process)
  and [choose session storage](guides/sessions.md).
- [Own the client lifecycle](guides/lifecycle.md) and [configure its bounds](guides/configuration.md).
- [Send and manage messages](guides/messaging.md) and [paginate history or dialogs](guides/history.md).
- [Receive events](guides/events.md), [answer bot interactions](guides/bots-and-events.md)
  and [transfer files](guides/files.md).
- [Call the raw API](guides/async-api.md), [handle failures](guides/errors.md)
  and [migrate an application](guides/migration.md).

### References and help

- [Client methods at a glance](quick-references/client.md) and [events at a glance](quick-references/events.md).
- [Detailed Client reference](reference/client.md), [events](reference/events.md),
  [filters](reference/filters.md), [buttons](reference/buttons.md) and [configuration](reference/configuration.md).
- [Raw Telegram API](reference/raw/index.md): 783 pinned method declarations, native inputs and results.
- [FAQ](guides/faq.md), [troubleshooting](guides/troubleshooting.md)
  and [compatibility](design/compatibility.md).

## How to read the examples

Complete tutorials include imports, credentials, session intent and the entry point.
Short guide snippets assume the prerequisites stated on their page. Reference examples
show an individual operation; raw call templates require real application/server data.
Read the linked return and error sections instead of assuming all calls return a Message.

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

## Direct high-level Client API

Use direct Client methods for everyday operations; optional resources and Routers
organize larger applications. See [Client Methods — High-Level API](client-methods/index.md)
for media, albums, administration, entities, exact contracts and current limits.
