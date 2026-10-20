"""Reuse a session, send to Saved Messages, and receive with filters. Ctrl-C closes."""

import asyncio
import os

from gramflux import Client, MessageEvent, Session, filters


async def main() -> None:
    client = Client(
        Session.open("example"),
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    )

    @client.on_message(filters.text & filters.incoming)
    async def on_message(event: MessageEvent) -> None:
        print(f"New message in chat {event.chat_id}")

    async with client:
        await client.send_message("me", "Hello from GramFlux")
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
