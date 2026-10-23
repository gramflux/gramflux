---
title: Commands and CommandContext
description: Commands and CommandContext for the additive GramFlux Next-Generation API.
---

# Commands and CommandContext

Router.command adds a message-only command subscription and optional argument parsing.
It uses the existing filters.command selector without changing that filter's behavior.

### Legacy API — supported

```python
@client.on_message(
    filters.incoming & filters.private & filters.command("hello", username=bot_username)
)
async def hello(event):
    await event.reply("Hello")
```

### Next-Generation API

```python
from gramflux.routing import Chat, CommandContext, Direction, Router

router = Router("commands")


@router.command("hello", chat=Chat.PRIVATE, direction=Direction.INCOMING, username=bot_username)
async def hello(ctx: CommandContext):
    await ctx.reply("Hello")
```

Include the router before connecting. A callback receives CommandContext only after a
new MessageEvent matches; edited messages and unrelated event classes do not become
commands through this decorator.

## Parameters

| Parameter | Default | Meaning |
| --- | --- | --- |
| *names | Required | One or more command names, without prefix or whitespace; same validation as filters.command |
| chat | None | Any classification, or Chat.PRIVATE / GROUP / CHANNEL |
| direction | Direction.INCOMING | INCOMING, OUTGOING or ANY; affects selection, not request routing |
| username | None | Restrict addressed commands to this bot name without @; None allows any address as the existing filter does |
| prefix | "/" | Nonempty command prefix |
| case_sensitive | False | Case-insensitive selection and casefolded ctx.command; True preserves matched token case |
| parse_args | True | Split the suffix on Unicode whitespace; False leaves ctx.args as None |
| predicate | filters.all_messages | Additional composable Filter, ANDed with the command and ready-made conditions |
| priority | 0 | Shared dispatcher priority; lower numbers execute first |

Conditions compare existing event fields and do not resolve peers. In bot projects,
pass the bot username explicitly to avoid matching commands addressed to another bot.

## Context fields

| Field | Contract |
| --- | --- |
| event | Original MessageEvent, including its native payload and contextual helpers |
| message | The original native message object, not a copy |
| command | Matched command token without prefix/address; casefolded unless case_sensitive=True |
| raw_args | Exact original text after the command token, including separating/trailing whitespace |
| args | Tuple from raw_args.split(), or None when parsing is disabled |
| client | Bound original Client; detached contexts raise LifecycleError on this property |
| reply(text, silent=False) | Delegates to event.reply, retaining reply ID, deadlines and errors |

## Argument rules are deliberately small

For `/HELLO  one "two words"\x`, default matching gives command `hello`. The suffix
retains its two leading spaces. The parsed tuple contains `one`, `"two` and `words"\x`.
Quotes are ordinary characters. Backslashes, variables, redirection and shell
expansion have no special interpretation.

Leading whitespace before the command is accepted as by the existing command filter.
An addressed token such as `/hello@MyBot` is checked before creating the context.
Malformed addresses, unrelated commands and nonmatching chat/direction filters are
ignored rather than being treated as parser errors in a callback.

Disable parsing when your application owns a different grammar:

```python
@router.command("search", parse_args=False)
async def search(ctx):
    original_suffix = ctx.raw_args
    await ctx.reply("Your application can parse this suffix explicitly")
```

No argument schema, shell parser, dependency injection, automatic error reply or
background command task is introduced. Handler errors use the existing event policy.
For arbitrary message selection, use router.message with composable filters instead.
