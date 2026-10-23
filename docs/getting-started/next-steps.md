---
title: Where to go next
description: Choose a learning path and understand the difference between tutorials, concepts, task guides and reference pages.
---

# Where to go next

You have connected a client. The next step is understanding which parts of the API
belong together, rather than collecting unrelated snippets. Read this documentation
in the order below when learning GramFlux. Use the sidebar and search when returning
for a particular operation.

## Follow a learning path

| Your goal | Recommended sequence |
| --- | --- |
| A user-account application | [Quick start](quickstart.md) → [Sessions](../guides/sessions.md) → [Entities](../concepts/entities.md) → [Messaging](../guides/messaging.md) |
| A bot with commands | [Reply-bot tutorial](../tutorials/reply-bot.md) → [Events](../guides/events.md) → [Buttons and callbacks](../guides/bots-and-events.md) |
| A process that pauses during login | [Authentication](../guides/authentication.md) → [Saved checkpoints](../guides/authentication.md#resume-login-after-stopping-the-process) → [Errors](../guides/errors.md) |
| An existing asyncio service | [Asyncio](../concepts/asyncio.md) → [Lifecycle and shutdown](../guides/lifecycle.md) → [Update delivery](../concepts/updates.md) |
| An unfamiliar Telegram method | [API levels](../guides/async-api.md) → [Raw index](../reference/raw/index.md) → [Parameters](../guides/parameters.md) |
| Migration from another library | [Migration](../guides/migration.md) → [Client quick reference](../quick-references/client.md) → [Compatibility](../design/compatibility.md) |

## Know which kind of page to open

**Tutorials** build one complete application, explain each step and give a way to
observe the result. Start there when you have not written this kind of application.

**Concepts** explain the model: what a peer is, how asyncio affects execution, why a
session is sensitive and what an update acknowledgement means. These explanations
apply across many methods.

**How-to guides** solve a concrete task. They assume a connected client where stated
and link to each operation's reference for all optional arguments.

**Quick references** group related operations into compact tables. Use them to find
the correct method before reading its full page.

**API references** specify signatures, every exposed parameter, defaults, return
values, failure behavior and native constructor choices. A raw method declaration is
not evidence that every surrounding workflow has been implemented or live-tested.

## Read examples with their prerequisites

A short `await client...` fragment belongs inside your own coroutine and usually
assumes completed authorization. A complete application includes imports, credential
loading, session intent, connection lifetime and its entry point. The bot tutorial
provides all of those pieces.

Choose test data you control. Do not paste someone else's access hashes or replace
unknown IDs with guessed values. A username is resolved by Telegram; an integer
user/channel ID normally needs previously obtained access metadata.

## Before deploying an application

Work through [lifecycle](../guides/lifecycle.md), [error handling](../guides/errors.md)
and [update delivery](../concepts/updates.md). Then review the
[compatibility matrix](../design/compatibility.md) and
[live verification procedure](../guides/live-validation.md). GramFlux remains an
engineering alpha; local protocol tests and generated coverage do not certify live
account behavior or production reliability.
