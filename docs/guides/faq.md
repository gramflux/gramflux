---
title: Frequently asked questions
description: Direct answers about login, sessions, async use, missing methods, events, formatting, retries and compatibility.
---

# Frequently asked questions

## Why does get_me say authentication is required?

A connection and MTProto key are not completed account login. Create a named session
once and explicitly call `login()`, or reopen a session that is already authorized.
`async with client` does not prompt automatically. Follow the
[authentication guide](authentication.md), rather than repeatedly reconnecting an
unauthorized key.

## Can a login continue in another process?

Yes, for persistent GramFlux sessions. Reopen with
`Session.open("account", require_authorized=False)` and use `login()` or the saved
single-attempt stage. The phone/code-hash checkpoint and password stage persist;
login codes and passwords do not. Telegram may expire the challenge while you are
away. See [resumable login](authentication.md#resume-login-after-stopping-the-process).

## Is a temporary session logged out when the process exits?

No. Its local key/checkpoint disappear, but local deletion is not remote revocation.
`log_out()` is an explicit server operation. Repeatedly creating temporary logins can
leave account authorizations on Telegram; choose persistent sessions when reuse is
the intended behavior.

## Can I open a Telethon or Pyrogram session directly?

No supported cross-library session conversion exists. Session formats and metadata
are not interchangeable just because they use SQLite. Preserve the original file
and authorize a separate GramFlux session. Read [migration](migration.md).

## Why does a numeric user ID fail while a username works?

The username lookup can obtain required access metadata. An unknown numeric user or
channel ID does not contain an access hash. Use an accessible resolved entity, load
dialog metadata or pass a valid native input peer. See [entities](../concepts/entities.md).

## Why is bold markup sent literally?

There is no implicit Markdown/HTML parser. Use supported native MessageEntity values
on methods exposing `entities`, with UTF-16 offsets. An unsupported `parse_mode`
keyword is an error, not a hidden compatibility setting. Read [messages](../concepts/messages.md).

## Why does an iterator need async for instead of await?

It yields multiple results as pages arrive; it is not a coroutine returning a list.
Use `async for` on `iter_history`, or await the finite `get_history` helper. See
[asyncio](../concepts/asyncio.md) and [pagination](history.md).

## Why are messages not reaching my handler?

Register before connecting and keep the context alive. Check the event class and
filter: `incoming` excludes your own send, and text filters require text/captions.
Confirm completed authorization and inspect connection/update failures. Slow handlers
also delay later delivery. Follow [troubleshooting](troubleshooting.md).

## Does a raw method mean the whole feature works?

No. Schema bindings expose requests and constructors. Payments, calls, secret chats,
media migration and other workflows can require additional runtime support. Read
the [compatibility matrix](../design/compatibility.md); generated coverage and live
feature coverage are separate.

## Should I repeat a request after a timeout?

Not automatically. A write can succeed remotely before its response is lost. Inspect
the failure, respect server-directed waits and reconcile state before retrying. There
is no general automatic application-write replay. Read [error handling](errors.md).

## Are proxies, CDN downloads and resumable file transfers available?

They are unsupported in the current documented runtime. Full, intermediate and
abridged TCP are supported. A raw constructor or a byte-range download parameter does
not implement those missing workflows. See [configuration](configuration.md) and
[file transfers](files.md).

## Is GramFlux production-certified?

No. It is an engineering alpha. Controlled tests, generated coverage and anonymous
protocol probes are documented evidence; authenticated live account testing,
independent security review and soak testing remain release blockers. See
[release assessment](../releases/0.5.0a2.md).
