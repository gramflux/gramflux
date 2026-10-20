"""A callback signals the main task, which owns shutdown."""

import asyncio
import os

from gramflux import Client, MessageEvent, Session, filters


async def main() -> None:
    stop = asyncio.Event()
    client = Client(
        Session.open("example"),
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    )
    me_id: int | None = None

    @client.on_message(filters.text & filters.regex(r"^/stop$"))
    async def stop_from_saved_messages(event: MessageEvent) -> None:
        if event.chat_id == me_id and event.sender_id == me_id:
            stop.set()

    async with client:
        me_id = (await client.get_me()).id
        await stop.wait()


if __name__ == "__main__":
    asyncio.run(main())
