"""Send/edit one Saved Message; optionally delete only that new message."""

import argparse
import asyncio
import os

from gramflux import Client, Session


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delete", action="store_true", help="delete the one message this script sends"
    )
    args = parser.parse_args()
    async with Client(
        Session.open("example"),
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    ) as client:
        sent = await client.send_message("me", "GramFlux message-management example")
        await client.edit_message("me", sent.id, "Edited by the GramFlux example")
        retrieved = await client.get_messages("me", [sent.id])
        print(f"Retrieved message ID: {retrieved[0].id if retrieved[0] else 'unavailable'}")
        if args.delete:
            await client.delete_messages("me", [sent.id])


if __name__ == "__main__":
    asyncio.run(main())
