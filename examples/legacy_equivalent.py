"""Supported equivalent of examples.next_app, using existing decorators and login."""

import asyncio
import os

from gramflux import Client, MessageEvent, Session, filters


async def serve(client: Client, *, bot_token: str, username: str) -> None:
    @client.on_message(
        filters.incoming & filters.private & filters.command("hello", username=username)
    )
    async def hello(event: MessageEvent) -> None:
        await event.reply("Hello from GramFlux")

    async with client:
        await client.login(bot_token=bot_token)
        await client.run_until_disconnected()


async def main() -> None:
    client = Client(
        Session.temporary(),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    )
    await serve(
        client,
        bot_token=os.environ["GRAMFLUX_BOT_TOKEN"],
        username=os.environ["GRAMFLUX_BOT_USERNAME"],
    )


if __name__ == "__main__":
    asyncio.run(main())
