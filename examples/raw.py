"""Raw wire API uses the pinned backend's generated bindings."""

import asyncio
import os

from gramflux import Client, Session
from gramflux.raw import LAYER, functions, types


async def main() -> None:
    async with Client(
        Session.open("example"),
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    ) as client:
        users = await client.invoke(functions.users.GetUsersRequest(id=[types.InputUserSelf()]))
        print(f"Runtime layer {LAYER}: current user ID {users[0].id}")


if __name__ == "__main__":
    asyncio.run(main())
