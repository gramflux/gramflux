# Sessions

`Client(session=None, ...)` uses MemoryStorage. `Client(session="example", ...)`
opens `example.session`; a filename with a suffix is used as given. The parent directory
must already exist. To customize:

```python
from gramflux.storage import MemoryStorage, SQLiteStorage

store = SQLiteStorage("private/account.sqlite")
client = Client(session=store, api_id=api_id, api_hash=api_hash)
```

Storage implements async `open`, `load`, `save`, `close`; snapshots are opaque
`SessionData` values. Treat them as secrets. MemoryStorage retains a snapshot when the
same instance is reused, but not after process exit. SQLite stores version-1 JSON
snapshots atomically, with a 1-MiB snapshot limit and format/application ID checks. It
persists authorization key, DC and update states, not arbitrary Python objects.

POSIX files have mode 0600 and a lifetime nonblocking flock, preventing two cooperating
GramFlux processes from using the same database. A second owner fails; the OS releases
locks on process exit. Do not delete an active session to defeat the lock. No-follow
open rejects symlinks where supported. Use a private, trusted parent directory; this is
not protection against an attacker who controls that directory or your machine.

SQLite and filesystem operations execute off the event loop. Cancelled operations join
their worker before returning. Existing authenticated state is loaded, not silently
replaced. Foreign session databases and unknown versions are rejected. No automatic
upgrade/conversion or corruption repair is implemented; preserve the original and
reauthorize into a new filename if necessary. A clean disconnect flushes backend
update state; abrupt process death can lose recent changes and cause replay or gaps.

The database is **not encrypted**. Use OS disk encryption, protect backups, and revoke
compromised sessions from an official Telegram client. Copying another library's
session database is unsupported and rejected. Username/access-hash caches are not
persisted; resolve peers again or supply explicit raw input peers after restart.
