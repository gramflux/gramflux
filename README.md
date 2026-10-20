# GramFlux

An asyncio Telegram client and independently verifiable TL schema toolkit for Python 3.11+.

**0.1.0a1 is an engineering alpha, not a production release candidate.** The live
MTProto runtime is provided by **Telethon 1.45.0**; GramFlux owns its public lifecycle,
request admission, error mapping, session format, ordered event dispatch, streaming
file pipeline, and independent schema generator/codec. It is not yet the independent,
higher-performance replacement described in the long-term roadmap.

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
Run `python examples/login.py` to authorize a new session, then:

```python
import asyncio
import os
from gramflux import Client, filters


async def main() -> None:
    client = Client(
        session="example",
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
Session files contain authentication keys; keep them private.

## Feature status

| Capability | Status and evidence |
| --- | --- |
| Official schema snapshot | 1,573 constructors + 783 methods; IDs and fields matched against official JSON |
| Independent typed declarations | Deterministic generated dataclasses, all 1,572 non-vector constructor minimal round trips tested |
| Independent TL codec | Primitive/property, flags, limits, malformed data and selected differential tests |
| Raw API at runtime | Backend bindings via `gramflux.raw`, backend layer 229; no all-method live coverage claim |
| Native TCP framing | Full/intermediate/abridged reference implementations, differential tests |
| Native initial handshake | One real `req_pq_multi` exchange with DC 2 verified; no authorization key created by native code |
| User codes, bot login, SRP password | Implemented using backend; controlled tests only, no account login verified |
| SQLite and memory sessions | Own format; persistence, permissions, locking, corrupt/foreign data tests |
| Concurrent RPC, deadlines, cancellation | Controlled backend tests; no real-account throughput measurements |
| New/edited messages, filters | Ordered bounded dispatcher tested; gap recovery delegated to backend, not independently verified |
| File upload/download | Streaming pipeline and boundary/interruption tests; no live transfer verified |
| Independent encrypted runtime | Unsupported; cryptography and update reconciliation delegated to backend |
| Proxy, CDN, resume, foreign sessions | Unsupported by the public API |
| Production readiness / superiority | Not claimed; see [release assessment](docs/release-report.md) |

Generated bindings and wire runtime use separate schema sources. Independent
`gramflux.tl.generated.objects` values are offline-only and are rejected by `invoke`.
Use backend-generated functions for live raw access:

```python
from gramflux.raw import functions, types

users = await client.invoke(functions.users.GetUsersRequest([types.InputUserSelf()]))
```

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
· [Security](SECURITY.md) · [Measured benchmark](research/benchmark.json).
The initial independent codec is slower than the backend on the recorded input;
there is no performance superiority claim.
