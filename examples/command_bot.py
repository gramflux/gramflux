"""Reply to /help using an already authorized bot session; Ctrl-C disconnects."""

import asyncio
import os

from gramflux import Client, MessageEvent, Session, filters


async def main() -> None:
    client = Client(
        Session.open("example"),
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    )
    username = os.environ["TELEGRAM_BOT_USERNAME"]  # without @

    @client.on_message(filters.command("help", username=username) & filters.incoming, priority=-10)
    async def help_command(event: MessageEvent) -> None:
        await event.reply("Available command: /help")

    async with client:
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
