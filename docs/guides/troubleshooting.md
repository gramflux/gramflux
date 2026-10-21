---
title: Troubleshooting and FAQ
description: Diagnose authorization, session locking, missing peers, updates and interrupted requests.
---

# Troubleshooting and FAQ

## AUTH_KEY_UNREGISTERED when calling get_me

A connection or a newly created MTProto key is not completed user authorization.
Create a named session and call `await client.login()` once. Reuse it with
`Session.open(name)` afterward. For an interrupted login, use
`Session.open(name, require_authorized=False)` and continue its saved step.

Never delete an authenticated file merely to silence an authorization error.
See [authentication](authentication.md).

## SessionAlreadyExists or SessionNotFound

Create and open have intentionally different semantics. `Session.create` refuses
replacement; `Session.open` requires an existing GramFlux file. An interrupted login
also has a real session file—open it instead of creating it again.

## The session is locked

Persistent storage is single-owner. Another process may be using the same file.
Shut it down normally or wait for it to exit; OS locks are released on process death.
Do not copy, remove or overwrite a live database to bypass its lock.

## A saved login code no longer works

GramFlux persists the challenge, not a guarantee that Telegram will keep it valid.
Incorrect codes preserve retryable progress. Expired/invalidated hashes clear it;
request a new code deliberately. No challenge exists for temporary sessions after
their process exits. Password-stage progress can be resumed without resubmitting a code.

## PeerNotFound for a numeric ID

User and channel IDs usually need access hashes. Resolve the current username,
load accessible dialogs/contacts or provide a valid native InputPeer. A marked ID
alone cannot create access to a peer. `refresh=True` invalidates an old username
binding rather than trusting it forever.

## No messages arrive

Register before connecting, authorize the session and keep the async context alive.
Check filter direction: `filters.incoming` excludes your own sends. Slow or blocking
handlers delay later events; callbacks execute sequentially. Check handler errors
and account permissions. Use `on_message` for messages, including those recovered
from differences; raw Update subscriptions do not receive fabricated wrappers.

## A callback failed

The dispatcher reports the error and continues to other eligible handlers. It does
not silently drop all later updates. You can supply an async `on_handler_error`
callback; redact exception messages and private content in application logs.
See [event ordering](events.md).

## A send timed out: can I retry?

Not blindly. The server may have accepted the write before the connection or reply
was lost. `RequestOutcomeUnknown` highlights uncertain outcomes, but other transport
failures are not automatically safe either. Reconcile state and use an
operation-specific policy. [Error handling](errors.md) explains the boundaries.

## Downloads fail or a media request migrates

Check the known size, supported photo/document metadata, trusted destination,
file-reference lifetime and target data center. CDN redirects, automatic cross-DC
media authorization, expired-reference refresh and interrupted-transfer resumability
are not implemented. Failures are explicit.

## Can I reuse a Telethon or Pyrogram session?

No. Database formats and authorization assumptions are not interchangeable.
Preserve the source and create a distinct GramFlux session. The
[migration guide](migration.md) maps concepts without promising conversion.

## Is GramFlux faster than other clients?

No comparative performance claim has been established. Native protocol ownership,
local microbenchmarks and controlled tests are not a fair end-to-end comparison.
See [performance methodology](../design/performance-plan.md).

## Is a cryptography FFDH warning a login failure?

The pinned provider warns that finite-field DH will be removed in a future release.
Telegram's handshake still requires that protocol. A warning is not account
authorization evidence; suppressing it does not resolve the maintenance risk.
Provider support and independent cryptographic review remain release blockers.

## How should I report a bug?

Include the GramFlux/Python versions, platform, transport, exception class and a
minimal reproduction without credentials or message bodies. Never upload a session
file, login code, phone-code hash, password, API hash or bot token. Report security
issues through [SECURITY.md](https://github.com/gramflux/gramflux/blob/main/SECURITY.md).
