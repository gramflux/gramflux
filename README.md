# GramFlux

An asyncio Telegram client and independently verifiable TL schema toolkit for Python 3.11+.

**783 typed asynchronous raw API methods** are available under `client.api`, generated
from the pinned official schema and routed through the independent native engine.
See [typed API and update selectors](docs/guides/async-api.md). Raw coverage is separate
from high-level convenience methods and authenticated interoperability.

High-level messaging, history, contacts and chat operations now include typed bot callbacks,
inline queries, read/deletion/status events, reactions, drafts and native keyboards.
See [bot operations and events](docs/guides/bots-and-events.md) for a working API example.

**0.5.0a2 is a native MTProto engineering alpha, not production ready.** GramFlux
now owns TCP framing, RSA_PAD/DH key creation, MTProto 2.0 envelopes, request correlation,
service messages, SRP, update counters and difference recovery. **No Telethon,
Pyrogram or other Telegram client is a runtime dependency or fallback.** The sole
direct runtime dependency is cryptography for OpenSSL-backed AES/DH primitives.

Real Telegram RSA/DH and encrypted ping/pong have been verified over full,
intermediate and abridged TCP. Account login, messaging, media and live gap recovery
remain unverified with personal/bot credentials. Deterministic tests exercise those
native API boundaries. Independent cryptographic review and fault/soak testing remain
release blockers. See the [hardening and production assessment](docs/releases/0.5.0a2.md).

The design principle is: Simple by default. Powerful when needed. Correct by design.
Fast when measured. Maintainable by architecture.

## Install

From a checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Normal installation ships generated source and exact schemas; no schema download is
required. Distribution name `gramflux` returned HTTP 404 from PyPI on 2026-10-20.
That is a point-in-time lookup, not a reservation or trademark clearance.

## Quick start

Obtain your own [API credentials](https://core.telegram.org/api/obtaining_api_id)
and follow [Telegram's API terms](https://core.telegram.org/api/terms).
Choose the session's intent explicitly:

| Intent | API | Behavior |
| --- | --- | --- |
| Open a saved session | `Session.open("example")` | File must exist and be authorized; never creates or prompts |
| Register a new named session | `Session.create("example")` | Creates `example.session` exclusively; call `await client.login()` |
| Temporary session | `Session.temporary()` | Memory only; call `await client.login()`; nothing persisted across processes |

Unfinished logins now persist their code challenge or password stage; reopening with
`Session.open("example", require_authorized=False)` resumes without resending the code.
See [authentication and restart examples](docs/guides/authentication.md).

For your first login, run `python examples/login.py --create example`. Incorrect codes
and passwords can be corrected up to three times per stage. If you interrupted an
unfinished login, use `python examples/login.py --resume example`. To check a saved
session without logging in again, use `python examples/login.py --open example`.

After creating and authorizing `example`, receive messages with:

```python
import asyncio
import os
from gramflux import Client, Session, filters


async def main() -> None:
    client = Client(
        session=Session.open("example"),
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    )

    @client.on_message(filters.incoming & filters.text)
    async def on_message(event):
        print(f"Message received in chat {event.chat_id}")

    async with client:
        me = await client.get_me()
        print(f"Authenticated as {me.id}")
        await client.send_message("me", "Hello from GramFlux")
        await client.run_until_disconnected()


asyncio.run(main())
```

The context manager connects; it never prompts, logs in implicitly, or keeps the
program alive after the context exits. Register handlers before connecting. Text is
sent literally, without implicit Markdown parsing. Ctrl-C triggers context cleanup.
Session files contain authentication keys; keep them private. For a temporary login,
use `python examples/temporary.py` or `Client(Session.temporary(), ...)` followed by
`await client.login()`. Temporary means no local persistence, not a remote logout.
Bare path strings now mean open-only (a change from 0.1.0a1); `session=None` still
means memory-only. No user code needs credentials embedded in source.

## Core operations

The high-level API now includes peer resolution and persistent access hashes,
pinned/archive dialog iteration, lazy history/search, ordered ID lookup, replies,
edits/deletion/forwarding, pinning/read receipts, members, contacts, group join/leave,
blocking, direct photo/document upload, handler management and explicit logout.

```python
async for dialog in client.iter_dialogs(limit=100):
    print(dialog.id, dialog.unread_count)

async for message in client.iter_history("me", limit=50):
    print(message.id)

sent = await client.send_message("me", "Literal text", silent=True)
await client.edit_message("me", sent.id, "Edited text")
selected = await client.get_messages("me", [sent.id])
```

These are additional operations inside a connected client context. See the
[core operations guide](docs/guides/core-operations.md) for return types, safe deletion,
peer IDs/access hashes, pagination limits and server restrictions. They are tested at
controlled RPC boundaries; they have not all been exercised against real accounts.

## Feature status

| Capability | Status and evidence |
| --- | --- |
| Official schema snapshot | 1,573 constructors + 783 methods; IDs and fields matched against official JSON |
| Independent typed declarations | Deterministic generated dataclasses, all 1,572 non-vector constructor minimal round trips tested |
| Independent TL codec | Primitive/property, flags, limits, malformed data and selected differential tests |
| Native raw API | gramflux.raw aliases the independently generated layer-225 classes; same schema as the wire runtime |
| TCP/encrypted protocol | Own full/intermediate/abridged framing, auth key exchange and encrypted ping/pong verified with Telegram |
| Code/bot login and SRP | Own request flows and password proof; deterministic/algebra tests, no real-account login claimed |
| SQLite/memory sessions | Explicit open/create/temporary, protected own snapshots and minimal peer metadata |
| Requests | Bounded in-flight work, correlation, deadlines/cancellation, containers/gzip/acks, explicit failure on disconnect |
| Salt/clock correction | Correlated protocol rejections permit bounded resends; controlled tests, no blind write retries |
| Core operations and files | Native peers/history/dialog/message/member services; bounded concurrent uploads and streamed ranges; controlled tests |
| Events/state | Own pts/seq checks, global/channel difference recovery, bounded queues, handler completion boundary; live recovery unverified |
| Unsupported | CDN/resume, secret chats/PFS, proxies, foreign sessions, automatic in-flight recovery after disconnect, durable event journal |
| Performance | A measured IGE optimization exists; no network/competitor superiority claim |

Raw functions use keyword arguments and return GramFlux's own dataclasses. Raw date
fields use Unix seconds. Objects from another library are not accepted. Example:

```python
from gramflux.raw import functions, types

users = await client.invoke(functions.users.GetUsersRequest(id=[types.InputUserSelf()]))
```

The first native exchange can be tested without account credentials:

```bash
python -m gramflux.tools.native_probe --mode intermediate
```

This explicitly contacts Telegram, creates an anonymous auth key and performs an
encrypted ping. It does not log into an account or persist a key. Remote key-deletion
confirmation is reported separately; EOF is not interpreted as successful deletion.

## Development checks

```bash
ruff check .
ruff format --check .
mypy src
pytest
python -m gramflux.tools.schema verify
python -m build
python -m gramflux.tools.benchmark
```

[Guides and API reference](docs/index.md) · [Architecture](docs/design/architecture.md)
· [Compatibility](docs/design/compatibility.md) · [Contributing](CONTRIBUTING.md)
· [Security](SECURITY.md) · [Codec benchmark](research/benchmark-0.2.0a1.json) · [Controlled transfer benchmark](research/transfers-0.2.0a2.json).
The older comparative codec file is historical. Current runtime independence and
a measured local IGE optimization do not establish end-to-end performance superiority.

Typed callback/inline queries, deletion/read/status/chat-action events and bot UI builders are documented in [bot operations and events](docs/guides/bots-and-events.md). The [checked API inventory](docs/api-surface.json) separates actual Client methods from generated TL declarations.

## Documentation website

The English Docusaurus site includes tutorials, guides, generated API reference and
search across the pinned raw API. Individual method pages describe parameters,
defaults, native input variants, results and errors. Follow the
[learning paths](docs/getting-started/next-steps.md), browse the
[Client quick reference](docs/quick-references/client.md), or read the
[parameter guide](docs/guides/parameters.md). See [documentation development](docs/documentation.md)
for setup, production builds and browser checks.

```bash
cd website
npm ci
npm start
```

GitHub Pages target: [gramflux.github.io/gramflux](https://gramflux.github.io/gramflux/).
After an administrator enables **Settings → Pages → Source → GitHub Actions**,
verified pushes to `v0.x-dev` publish automatically through the Documentation workflow.
