---
title: Error handling
description: Learn which failures are retryable and how to handle uncertain request outcomes.
---

# Error handling

GramFlux separates configuration, storage, authentication, transport, RPC and
synchronization failures. Exceptions preserve useful context without including
credentials, message bodies or native request payloads in routine diagnostics.

## Authentication failures

An opened connection may still be unauthorized. `AuthenticationRequired` explains
that login must be completed. `PasswordRequired` is a transition into two-step
verification, not a reason to discard the session file.

Wrong login codes and passwords can be retried. Interactive `login()` applies
`max_attempts`; low-level methods perform one attempt and let your UI choose the
next action. A saved login checkpoint survives retryable failures.

```python
from gramflux.errors import PasswordRequired

try:
    user = await client.sign_in(code=code)
except PasswordRequired:
    user = await client.check_password(password)
```

The password step is committed before PasswordRequired propagates, so you can also
stop the process here and resume later. See [authentication](authentication.md).

## Server-directed waits

`FloodWait.seconds` is Telegram's requested wait. An application may wait explicitly;
this example does not automatically repeat the original operation:

```python
import asyncio

from gramflux.errors import FloodWait

try:
    await client.get_me()
except FloodWait as error:
    await asyncio.sleep(error.seconds)
```

Respect server limits. Do not implement flood-limit evasion or indefinite retry loops.

## Timeouts, cancellation and uncertain writes

Python `TimeoutError` and `asyncio.CancelledError` retain their meanings.
`RequestOutcomeUnknown` distinguishes lost replies or potentially committed writes.
It is a transport error: a caller losing the response does not prove the server
rejected the operation. Other TransportError failures may also be unsafe to retry.

Do not blindly repeat sends, forwards, deletions or uploads after a lost response.
Reconcile application state where possible, then choose an operation-specific,
bounded recovery policy. GramFlux does not replay pending writes after reconnecting.

## Local and RPC errors

| Error family | What to inspect |
| --- | --- |
| `ConfigurationError` | Invalid arguments or unsupported settings |
| `LifecycleError` | Request before connect, after disconnect or invalid login state |
| `SessionNotFound` / `SessionAlreadyExists` | Explicit open/create intent |
| `SessionError` | File locking, corruption, permissions or snapshot validation |
| `SerializationError` / `SchemaError` | Native TL input, pinned schema or malformed wire data |
| `RPCError` | Sanitized server `code` and `name`; specialized classes where applicable |
| `MigrationRequired` | Target `dc`; no general automatic migration workflow |
| `PeerNotFound` / `PaginationError` | Missing identity metadata or stalled pagination |
| `FileTransferError` | Transfer validation, unsupported response or interrupted stream |
| `UnsupportedFeature` | Explicitly unsupported runtime workflow |

User-defined callback failures are isolated by the dispatcher. Supply
`on_handler_error` for application reporting, and take responsibility for redacting
exception contents. See [events](events.md) and the generated
[exception hierarchy](../reference/errors.md).
