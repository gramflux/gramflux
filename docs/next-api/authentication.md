---
title: Authentication and lifecycle
description: Authentication and lifecycle for the additive GramFlux Next-Generation API.
---

# Authentication and lifecycle

Domain access is local. Authorization and the connection lifetime still belong to the
original Client. `client.auth.login` does not make context entry prompt implicitly.

## Choose session intent first

| Intent | Session factory |
| --- | --- |
| New persistent account | Session.create("account") |
| Reuse completed authorization | Session.open("account") |
| Resume pending login | Session.open("account", require_authorized=False) |
| Process-local authorization | Session.temporary() |

### Legacy API — supported

```python
async with client:
    user = await client.login(bot_token=token)
    me = await client.get_me()
```

### Next-Generation API

```python
async with client:
    user = await client.auth.login(bot_token=token)
    me = await client.account.me()
```

The same account is checked and the same login implementation runs. Invalid bot tokens
do not switch to phone login. An already authorized session returns its account;
these calls do not silently replace it with another user.

## Resume a staged login

Legacy `request_login_code`, `sign_in` and `check_password` correspond directly to
`client.auth.request_login_code`, `.sign_in` and `.check_password`. Each remains a
single attempt. Interactive `.login(max_attempts=3)` retains bounded per-stage input
retries, explicit server waits and cancellation behavior.

```python
from gramflux import Client, Session
from gramflux.errors import PasswordRequired

async with Client(
    Session.open("account", require_authorized=False),
    api_id=api_id,
    api_hash=api_hash,
) as client:
    if await client.auth.is_authorized():
        user = await client.account.me()
    elif client.auth.stage == "password":
        user = await client.auth.check_password(password)
    else:
        try:
            user = await client.auth.sign_in(code=code)
        except PasswordRequired:
            user = await client.auth.check_password(password)
```

Provide your own credentials and user-entered code/password. The saved stage is local
progress, not proof that Telegram has not expired a code. `client.auth.challenge`
delegates to `client.login_challenge`; read its values instead of relying on identity
between two reads. Phone/code-hash checkpoints are sensitive, and passwords/codes are
not persisted. [Existing checkpoint rules](../guides/authentication.md) apply unchanged.

## Keep lifecycle ownership explicit

Use `async with client` or the existing `connect`/`disconnect` methods. There is no
separate domain start/stop lifecycle. Closing a resource does not disconnect the
client; views are ordinary local objects and provide no close operation.

`client.auth.log_out()` is the existing remote logout operation. It is different from
exiting a context or deleting a local temporary session. `client.account.sessions()`
reports remote account authorizations, not local SQLite files.

Use [lifecycle and shutdown](../guides/lifecycle.md) for application task ownership.
Timeouts and cancellation do not retract accepted writes. No general automatic
replay, implicit reauthorization or session conversion is introduced by these views.
