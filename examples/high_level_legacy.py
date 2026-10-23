"""Equivalent operations using only the pre-existing direct Client API."""

import argparse
import asyncio
import os
from pathlib import Path

from gramflux import Client, Session


async def main(session: str, source: Path | None) -> None:
    async with Client(
        Session.open(session),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    ) as client:
        me = await client.get_me()
        print(f"Authorized user ID: {me.id}")
        sent = await client.send_message("me", "Hello from GramFlux")
        await client.edit_message("me", sent.id, "Updated from GramFlux")
        selected = await client.get_messages("me", [sent.id])
        print(f"Fetched {len(selected)} message slots")
        if source is not None:
            uploaded = await client.upload_file(source)
            await client.send_file(
                "me", uploaded, caption="Uploaded with GramFlux", as_document=True
            )
        async for message in client.iter_history("me", limit=5):
            print(f"Message ID: {message.id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="account")
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()
    asyncio.run(main(args.session, args.file))
