---
title: Quick references
description: Find related methods, event subscriptions and parameter conventions without reading every API page.
---

# Quick references

Use these indexes when you know the task but not its method name. Each entry links
to its detailed contract. They complement the learning chapters, not replace them.

| Need | Open |
| --- | --- |
| Find a high-level operation by task | [Client methods](client.md) |
| Choose an event and subscription | [Events and subscriptions](events.md) |
| Check omission, flags and argument variants | [Parameter conventions](../guides/parameters.md) |
| Find a filter or builder | [Filters](../reference/filters.md) · [Buttons](../reference/buttons.md) |
| Call a pinned official function | [Raw API namespaces](../reference/raw/index.md) |
| Diagnose a failure | [Error handling](../guides/errors.md) · [Exception hierarchy](../reference/errors.md) |

The Client reference groups convenience methods by purpose. Raw functions belong to
Telegram's schema namespaces and can require workflows outside the high-level API.
An event class is a delivered data shape, while a subscription method chooses that
shape; neither should be counted as an additional Telegram RPC.
