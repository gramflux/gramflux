# Authentication and input retries

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
With unconfigured logging, backend warnings no longer print through Python's fallback
handler into the phone prompt. If your application explicitly installs console log
handlers, direct diagnostic logging to a file for an uninterrupted terminal UI.
Default reads run in worker threads. Cancelling a blocking terminal read cannot
interrupt its underlying OS thread; use cancellation-aware async UI callbacks if needed.

For an application-controlled UI, pass LoginPrompts with async phone(prompt), code(prompt)
and password(prompt) callbacks plus a synchronous notify(message). Prompt failures are
not swallowed. Keep secret values scoped to the input/auth operation; Python cannot
promise secure string erasure. No passwords or login codes are stored on disk.

## Single-attempt primitives

The existing request_login_code(phone), sign_in(challenge, code), check_password(password)
and sign_in_bot(token) remain available and never prompt or add input retries:

```python
from gramflux.errors import PasswordRequired

challenge = await client.request_login_code(phone)
try:
    user = await client.sign_in(challenge, code)
except PasswordRequired:
    user = await client.check_password(password)
```

Calling these once and exiting from an application's exception handler naturally gives
one attempt; the old login example did exactly that. Use login() for the tested bounded
re-prompt behavior, or implement your own policy around these primitives. SRP computation
uses GramFlux's own SRP proof with hashlib/PBKDF2 and validated DH parameters in a worker thread. Authorization is checked separately
from connection state; get_me on an unauthorized connection raises AuthenticationRequired
with actionable login guidance.

The library does not register new Telegram accounts or bypass official-app SMS, email,
QR, passkey or payment requirements. See [Telegram authorization](https://core.telegram.org/api/auth).
Live flows remain only partially verified; deterministic tests do not replace dedicated
account integration tests. Session files are account credentials; never publish them.
