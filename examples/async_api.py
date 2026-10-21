"""Read Saved Messages through typed raw methods using an existing session."""

import asyncio
import os

from gramflux import Client, Session, filters
from gramflux.raw import types


async def main() -> None:
    client = Client(
        session=Session.open(os.environ["GRAMFLUX_SESSION"]),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    )

    @client.on_raw_update(filters.update_type(types.UpdateUserTyping))
    async def on_typing(event):
        print(event.update.definition.name)

    async with client:
        result = await client.api.messages.get_history(
            peer=types.InputPeerSelf(),
            offset_id=0,
            offset_date=0,
            add_offset=0,
            limit=10,
            max_id=0,
            min_id=0,
            hash=0,
        )
        # MessagesNotModified has no messages field.
        if isinstance(result, types.messages.MessagesNotModified):
            print("History unchanged")
        else:
            print(f"Received {len(result.messages)} message objects")
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
