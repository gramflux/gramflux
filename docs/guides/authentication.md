---
title: Authentication
description: Authorize user or bot accounts, retry invalid inputs and resume saved login checkpoints.
---

# Authentication

Use your own api_id/api_hash via arguments or your application's secret mechanism.
Examples read environment variables; the library does not mandate their names.
`async with client` connects. **Only an explicit `await client.login()` starts the
interactive flow.** Opening Session.open(name) instead requires authorization that
already exists and never prompts to create it.

```python
from gramflux import Client, Session

async with Client(Session.create("example"), api_id=api_id, api_hash=api_hash) as client:
    me = await client.login(max_attempts=3)
    await client.send_message("me", "Hello from GramFlux")
```

Use Session.temporary() instead for memory-only login, or
Session.open("example", require_authorized=False) to resume an unfinished saved login.
See [session modes](sessions.md). The login example exposes --create, --open, --resume
and --temporary explicitly. A bot uses `await client.login(bot_token=token)` or the
single-attempt sign_in_bot(token); bot-token errors do not trigger a phone login.

The interactive flow allows three input attempts **per stage** by default:

- An invalid/empty phone number can be entered again.
- An incorrect/empty code re-prompts using the **same** challenge; it does not keep
  sending codes. A server-expired code requests a fresh challenge within the same
  bounded code-attempt budget.
- A password challenge switches to a separate password budget. An incorrect/empty
  password re-prompts without sending another login code.
- Exhaustion raises LoginAttemptsExceeded with stage, attempts and last_error_name.
  Secrets are never included in notification strings or exception messages.
- FLOOD_WAIT, bans, other fatal server rejections, network failures, timeouts, EOF and
  cancellation propagate immediately; they are not invalid-input retry opportunities.

Already authorized login() calls return the existing user without prompting or replacing
that account. Concurrent login() calls on one client are serialized. To switch accounts,
use a different session. Inputs are never automatically repeated unchanged.

Phone input uses input(); code/password use getpass(), which hides typed characters.
With unconfigured logging, backend diagnostics do not print through Python's fallback
handler into the phone prompt. If your application explicitly installs console log
handlers, direct diagnostic logging to a file for an uninterrupted terminal UI.
Default reads run in worker threads. Cancelling a blocking terminal read cannot
interrupt its underlying OS thread; use cancellation-aware async UI callbacks if needed.

For an application-controlled UI, pass LoginPrompts with async phone(prompt), code(prompt)
and password(prompt) callbacks plus a synchronous notify(message). Prompt failures are
not swallowed. Keep secret values scoped to the input/auth operation; Python cannot
promise secure string erasure. No passwords or login codes are stored on disk.

## Single-attempt primitives

Use request_login_code(phone), sign_in(challenge, code), check_password(password)
and sign_in_bot(token) for application-controlled input. They never prompt or add input retries:

```python
from gramflux.errors import PasswordRequired

challenge = await client.request_login_code(phone)
try:
    user = await client.sign_in(challenge, code)
except PasswordRequired:
    user = await client.check_password(password)
```

Use login() for bounded interactive retries, or implement an explicit retry policy
around these single-attempt primitives. SRP computation
uses GramFlux's own SRP proof with hashlib/PBKDF2 and validated DH parameters in a worker thread. Authorization is checked separately
from connection state; get_me on an unauthorized connection raises AuthenticationRequired
with actionable login guidance.

The library does not register new Telegram accounts or bypass official-app SMS, email,
QR, passkey or payment requirements. See [Telegram authorization](https://core.telegram.org/api/auth).
Authenticated flows have controlled-test coverage; real-account behavior remains
unverified in this environment. Session files are account credentials; never publish them.


## Resume login after stopping the process

Persistent GramFlux sessions save the pending code challenge (phone and server
phone_code_hash) and the two-step password stage. These checkpoints are committed
before request_login_code returns or PasswordRequired reaches your application.
Disconnect is not required to commit these authentication checkpoints. A successful
login clears them; a wrong code/password retains the relevant step for retry.
Expired or rejected code hashes clear the pending challenge.

First process, run once:

```python
async with Client(Session.create("account"), api_id=api_id, api_hash=api_hash) as client:
    await client.request_login_code(phone)
# The process may exit now. The named session contains the pending challenge.
```

Another process, using the same API credentials and session file:

```python
from gramflux.errors import PasswordRequired

async with Client(
    Session.open("account", require_authorized=False),
    api_id=api_id,
    api_hash=api_hash,
) as client:
    if await client.is_authorized():
        user = await client.get_me()
    elif client.login_stage == "password":
        user = await client.check_password(password)
    else:
        try:
            user = await client.sign_in(code=code)
        except PasswordRequired:
            # The password checkpoint is already saved. You can exit here and
            # supply the password from a later process instead.
            user = await client.check_password(password)
```

`client.login_challenge` retrieves a pending LoginChallenge after connect, so the
existing `sign_in(challenge, code)` form also works across restarts without having
to export the challenge yourself. `sign_in(code=...)` uses the saved challenge.
`login_stage` is `"code"`, `"password"` or None; it is local saved progress, not a
replacement for `await client.is_authorized()` and not a server expiry guarantee.
No pending challenge raises LifecycleError instead of silently sending a new code.

The interactive `await client.login()` also resumes the saved step automatically:
it skips phone/code submission when the saved stage is password, and does not send
a second code when a challenge is already saved. `python examples/login.py --resume
account` follows this behavior. Supplying a different phone explicitly requests a
new code rather than reusing another phone's challenge.

Use `require_authorized=False` for unfinished logins: ordinary `Session.open(...)`
intentionally requires completed authorization. `Session.create(...)` remains
exclusive and cannot overwrite an existing file. Temporary sessions cannot survive
process exit. Existing session snapshots without this metadata remain compatible.

Codes and passwords are never saved. Phone numbers, phone-code hashes and auth keys
are sensitive: SQLite files have owner-only permissions and transactional writes,
but are not encrypted at rest. Do not share them or log their contents. Telegram
can expire codes or revoke keys while the script is stopped; request a new code
when appropriate. Abrupt termination during a request before its checkpoint completes
cannot guarantee that the server response was saved. Parallel login flows on the
same Client are not supported. These restart tests use a controlled Telegram backend;
live authenticated restart interoperability remains unverified.

The staged command-line example also supports separate invocations:

```bash
python examples/resumable_login.py request account
python examples/resumable_login.py code account
# Only when Telegram requires two-step verification:
python examples/resumable_login.py password account
python examples/resumable_login.py status account
```

Credentials come from GRAMFLUX_API_ID and GRAMFLUX_API_HASH; codes/passwords
are read with a hidden prompt rather than command-line arguments.
