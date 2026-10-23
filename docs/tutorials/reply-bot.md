---
title: Build a command bot
description: Build an async private-chat bot from credentials through handlers, bounded login, observation and clean shutdown.
---

# Build a command bot

This tutorial builds a bot that answers `/hello` in private chats. You will choose a
session lifetime, register a filtered handler, authorize explicitly and keep the
application alive. It uses the official MTProto API, so a bot token is accompanied
by your application's api_id and api_hash.

## 1. Prepare credentials

Create your bot with Telegram's BotFather and obtain your own application credentials
from [Telegram](https://core.telegram.org/api/obtaining_api_id). Store them outside
the source file. The variable names below are an example application convention:

```bash
export GRAMFLUX_API_ID='YOUR_NUMERIC_API_ID'
export GRAMFLUX_API_HASH='YOUR_API_HASH'
export GRAMFLUX_BOT_TOKEN='YOUR_BOT_TOKEN'
export GRAMFLUX_BOT_USERNAME='YOUR_BOT_USERNAME_WITHOUT_AT'
```

Install GramFlux using the [installation guide](../getting-started/installation.md).
A bot cannot initiate an arbitrary private conversation; use your Telegram app to
open the bot and send the test command yourself.

## 2. Save the application

Save this complete script as `reply_bot.py`:

```python
import asyncio
import os

from gramflux import Client, Session, filters


async def main() -> None:
    client = Client(
        Session.temporary(),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    )

    @client.on_message(
        filters.incoming
        & filters.private
        & filters.command("hello", username=os.environ["GRAMFLUX_BOT_USERNAME"])
    )
    async def hello(event):
        await event.reply("Hello from GramFlux")

    async with client:
        me = await client.login(bot_token=os.environ["GRAMFLUX_BOT_TOKEN"])
        print(f"Bot connected: {me.id}")
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
```

Run it with `python reply_bot.py`. A successful authorization prints the bot's
numeric identity. The program then waits for events; lack of further console output
is expected, because the handler replies in Telegram instead of printing content.

## 3. Understand each boundary

**Session.temporary()** keeps the local authorization only in this process. There
is no session database to manage in this first example. Process exit does not revoke
the server authorization. For recurring deployments, follow the persistent-session
variant below instead of creating fresh authorizations on every restart.

**The decorator** registers the callback before connecting. Direction, chat type and
command predicates are combined with `&`. The explicit username prevents addressed
commands for another bot from matching. Command matching uses the first token;
this example does not parse a command argument language.

**async with** owns the connection lifetime. **login(bot_token=...)** explicitly
performs bot authorization and does not fall back to a phone-code prompt when the
token is rejected.

**event.reply** supplies the event's conversation and original message ID. It runs
through the same Client policy as an explicit send. Permissions, deadlines and
server waits still apply.

**run_until_disconnected** keeps this coroutine alive while the event loop runs
other tasks. Leaving the context cleans up the Client. Press Ctrl+C in the terminal
to stop this standalone script.

## 4. Observe the behavior

1. In Telegram, open your bot's private conversation.
2. Send `/hello`; the bot should reply to that message.
3. Send unrelated text; the command filter should ignore it.
4. Send `/hello@YOUR_BOT_USERNAME`; the configured address should match.
5. Stop the script; its handlers are no longer running.

This is a manual account/network verification procedure, not a claim that a real
bot-token test was performed in the project's controlled test environment. If the
identity line never appears, inspect authorization errors before debugging filters.

## 5. Reuse a named session

For the first persistent run, replace `Session.temporary()` with
`Session.create("bot")`. After successful authorization, future runs use
`Session.open("bot")`. `create` never overwrites an existing file. Keep `login()` if
you want its already-authorized identity check; it returns the existing account
without replacing it.

Do not implement automatic create-on-any-open-error behavior: a corrupt or
unauthorized existing file requires a different response from a missing file.
See [session modes](../guides/sessions.md) for unfinished login and storage errors.

## 6. Add one feature at a time

Use [buttons and callbacks](../guides/bots-and-events.md) for interactive controls,
[handler delivery](../concepts/updates.md) to understand slow callbacks and failures,
and [lifecycle](../guides/lifecycle.md) to integrate a service shutdown signal.

If no reply arrives, confirm the process is alive, the bot was authorized, the
username is correct and your message came from an incoming private chat. The
[troubleshooting guide](../guides/troubleshooting.md) lists connection and update
failures. Bot eligibility differs across Telegram methods; raw availability does
not grant user-only permissions.
