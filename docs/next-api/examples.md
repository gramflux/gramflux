---
title: Complete legacy and modular examples
description: Complete legacy and modular examples for the additive GramFlux Next-Generation API.
---

# Complete legacy and modular examples

The repository includes two complete applications with equivalent behavior. Both
answer /hello in a private incoming bot conversation, use the same lifecycle and
return the same reply through the original Client execution path.

## Configuration

Install this checkout, then provide your own credentials and a bot username without @:

```bash
export GRAMFLUX_API_ID='YOUR_NUMERIC_API_ID'
export GRAMFLUX_API_HASH='YOUR_API_HASH'
export GRAMFLUX_BOT_TOKEN='YOUR_BOT_TOKEN'
export GRAMFLUX_BOT_USERNAME='YOUR_BOT_USERNAME_WITHOUT_AT'
```

## Legacy API — supported

From the repository root:

```bash
python examples/legacy_equivalent.py
```

The source is [examples/legacy_equivalent.py](https://github.com/gramflux/gramflux/blob/v0.x-dev/examples/legacy_equivalent.py).
It uses client.on_message, existing filters.command, event.reply and client.login.
No changes to an old application are required to keep using that pattern.

## Next-Generation API — recommended for new projects

```bash
python -m examples.next_app
```

The [application entry point](https://github.com/gramflux/gramflux/blob/v0.x-dev/examples/next_app/__main__.py)
constructs Client and mounts definitions from a separate
[handler module](https://github.com/gramflux/gramflux/blob/v0.x-dev/examples/next_app/handlers.py).
The handler module defines a Router without creating a Client. router.command builds
CommandContext only for matching new messages, and ctx.reply uses the original helper.

These examples use a temporary local session for easy initial execution. For repeated
deployments, create a named session once, then explicitly reopen it on future runs.
Local temporary-session loss does not revoke the server authorization.

## Observe the result

Run one application, open your bot in Telegram and send /hello in a private chat.
It should reply to that message. Other text and commands addressed to a different
bot should not match. Stop the application before running the equivalent example.

This is a reader-run account test procedure. Automated tests execute both serve
functions with the real Client/dispatcher and a controlled backend, then verify the
same text and reply ID. Those tests are not live Telegram bot-token verification.

## Other new surfaces

The [domain guide](domains.md), [chat guide](chats.md), [files guide](files.md) and
[raw guide](raw.md) each pair legacy and new snippets. Their prerequisites are stated
on the page. [Exact signatures](reference.md) cover every new public operation.
