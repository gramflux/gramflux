"""Read dialogs/history from an existing session without logging private text."""

import argparse
import asyncio
import os

from gramflux import Client, Session


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="example")
    parser.add_argument("--peer", default="me", help="username or me")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    async with Client(
        Session.open(args.session),
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    ) as client:
        for dialog in await client.get_dialogs(limit=10):
            print(f"Dialog {dialog.id}: unread={dialog.unread_count}")
        async for message in client.iter_history(args.peer, limit=args.limit):
            print(f"Message ID: {message.id}")


if __name__ == "__main__":
    asyncio.run(main())
