# Authentication

Supply your own `api_id` and `api_hash` as constructor arguments. Environment variables
are used by examples only; the library does not require a secrets naming scheme.
`async with client` connects without authorization prompts. First authorize using
`examples/login.py`, or explicitly call:

```python
from gramflux.errors import PasswordRequired

challenge = await client.request_login_code(phone)
try:
    user = await client.sign_in(challenge, code)
except PasswordRequired:
    user = await client.check_password(password)
```

A bot uses `await client.sign_in_bot(token)` with the same application API credentials.
`await client.is_authorized()` checks authorization, not just connection state. Existing
authorized sessions reject a second login attempt; use a separate session for another
account. GramFlux does not implement new account registration. User code/password and
bot flows are implemented but have not been exercised against a real account here.

`LoginChallenge` carries phone/hash without showing them in repr. Keep it only until
login completes. Passwords and codes are not persisted or logged. Python strings cannot
be reliably erased, so keep their scope small; application code and tracebacks can
still expose locals. SRP computation uses Telethon's primitives in a joined worker
thread. Incorrect/expired codes and passwords map to AuthenticationError with a safe
server identifier. FloodWait reports seconds; there is no automatic waiting.

Telegram may require official-app code delivery, email verification, QR or passkeys;
these paths are not implemented. See the current
[authorization rules](https://core.telegram.org/api/auth). Never bypass these restrictions.
Network errors or application cancellation can leave a remote operation completed.
Follow the error identifier rather than blindly repeating authentication requests.
