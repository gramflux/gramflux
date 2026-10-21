---
title: Configuration and transports
description: Configure deadlines, bounded concurrency, update queues and supported TCP framing.
---

# Configuration and transports

Use the immutable `Config` dataclass for predictable client behavior:

```python
from gramflux import Client, Config, Session

client = Client(
    Session.open("account"),
    api_id=api_id,
    api_hash=api_hash,
    config=Config(
        request_timeout=30.0,
        max_concurrent_requests=32,
        event_queue_size=256,
        update_queue_bytes=16 * 1024 * 1024,
        transport="intermediate",
    ),
)
```

## Limits and deadlines

| Setting | Default | Meaning |
| --- | --- | --- |
| `request_timeout` | 30 seconds | Total request deadline, including admission; also bounds complete connection setup |
| `max_concurrent_requests` | 32 | Application RPC admission bound |
| `event_queue_size` | 256 | Bounded event/receive queue count setting |
| `update_queue_bytes` | 16 MiB | Queued native updates measured by uncompressed TL body bytes |
| `reconnect_attempts` | 3 | Initial TCP establishment retry budget, not pending-request replay |
| `peer_cache_size` | 2048 | Bounded entity/access-hash cache, valid range 1–4096 |
| `transport` | `intermediate` | TCP framing: `full`, `intermediate` or `abridged` |

Queue budgets are not a hard Python heap/RSS limit. Your handlers can retain their
own data. Native overflow terminates the connection explicitly so recovery can
resynchronize; updates are not silently discarded to satisfy a queue budget.

## Supported transports

All three TCP framing modes use the same native MTProto 2.0 encryption and
correlation engine. Anonymous key exchange and encrypted ping have been tested
against Telegram in each mode. This is separate from authenticated account testing.

Proxy settings, MTProxy, transport obfuscation, HTTP/WebSocket and configurable IPv6
routes are not currently exposed. Do not pass options copied from another library.

## Reconnection and migrations

An established connection failing does not trigger automatic replay of pending
application requests. Disconnect before explicitly reconnecting an existing Client.
Assess each outstanding operation's outcome before attempting it again.

A small set of authorization requests can repeat after a recognized, completed DC
switch. Other migrations raise `MigrationRequired`; media CDN and cross-DC recovery
workflows remain unsupported. See [errors](errors.md) for policy details and
[Config reference](../reference/configuration.md) for generated field types.
