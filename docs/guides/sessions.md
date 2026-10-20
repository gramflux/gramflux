# Sessions: open, create, temporary

These operations have distinct meanings; connecting is not signing in:

| Choice | File behavior | Authorization behavior |
| --- | --- | --- |
| `Session.open("example")` | Opens an existing `example.session`; never creates | Checks saved authorization before context entry; never prompts |
| `Session.create("work")` | Exclusively creates a new `work.session`; refuses an existing file | Connects without an account; explicitly call `await client.login()` |
| `Session.temporary()` | No session file | Explicit login; key remains only in memory for this process |

The parent directory of a saved session must already exist. A filename with a suffix
is used as given; a plain name gets `.session`. These modes apply only to GramFlux
session files, not foreign Telethon/Pyrogram/Hydrogram sessions.

Create a named session once:

```python
from gramflux import Client, Session

async with Client(Session.create("example"), api_id=api_id, api_hash=api_hash) as client:
    await client.login()  # prompts for phone, code and password if needed
    me = await client.get_me()
```

Open it later, using the same working directory or an explicit path:

```python
async with Client(Session.open("example"), api_id=api_id, api_hash=api_hash) as client:
    me = await client.get_me()  # context entry has checked saved authorization
```

Temporary login:

```python
async with Client(Session.temporary(), api_id=api_id, api_hash=api_hash) as client:
    await client.login()
    await client.run_until_disconnected()
```

No temporary session is recoverable by a new process. This does **not** promise that
Telegram revokes the remote authorization when your process exits or crashes; no
logout request is implied. Python does not guarantee wiping key bytes from memory.
A temporary client's in-memory key can be reused if that same client reconnects during
its lifetime. Keep the context alive as long as you need the connection.

`SessionNotFound` means an open-only file (or parent) is missing. `SessionAlreadyExists`
means a new name would replace an existing file; choose another name or open it.
`AuthenticationRequired` means the saved file has no authorized account, or Telegram
rejected its authorization. It is never silently replaced or automatically logged in.
A new file is reserved at connect time and may remain after interrupted/failed login.
To deliberately resume that file without assuming authorization:

```python
session = Session.open("example", require_authorized=False)
async with Client(session, api_id=api_id, api_hash=api_hash) as client:
    await client.login()
```

`python examples/login.py --create example`, `--open example`, `--resume example`
and `--temporary` expose these choices at the terminal. Do not delete a live or
partially authorized file just to bypass errors.

Since 0.1.0a2 a bare Client string/path is shorthand for `Session.open(name)`, a
behavior change from 0.1.0a1's automatic open-or-create. `session=None` still means
memory-only for compatibility. Prefer explicit Session factories in new code.

## Storage details

Custom Storage implements async open/load/save/close with opaque SessionData snapshots.
The advanced `SQLiteStorage(path, mode="open" | "create" | "open_or_create")` and
MemoryStorage implement that interface; low-level storage is not an account login.
MemoryStorage retains a snapshot when its instance is reused, never after process exit.
The default low-level SQLite mode remains open_or_create for custom-store compatibility.

SQLite format/version are unchanged: application ID plus schema version 1, transactional
JSON snapshot, 1-MiB payload limit, auth key/DC/update state. It does not persist arbitrary
Python objects. Since 0.2.0a1 an optional bounded ID/access-hash/primary-username/self
cache is included; names are re-resolved after restart, and titles, phone numbers,
full names and message contents are not persisted by that cache. Clean disconnect flushes native handler-committed update state.
Native salt/time-offset metadata is additive in version-1 snapshots. Abrupt process death can lose recent changes; there is no durable event journal.

Persistent files require POSIX flock. Mode 0600, no-follow regular-file checks and an
exclusive lifetime lock protect cooperating processes. Initial create uses O_EXCL,
so racing creators cannot overwrite each other. Locks release on process exit. Normal
SQLite reads/writes run off-loop; cancelled workers are joined before lock release.
A trusted parent directory is required. This does not protect against machine compromise.

The session key is **not encrypted at rest**. Use OS encryption and secure backups.
Foreign formats, corrupt databases and unknown schema versions are rejected; preserve
the original before manual recovery. No automatic conversion or corruption repair.
