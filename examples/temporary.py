"""Sign in without a session file and remain online until Ctrl-C."""

import asyncio
import os

from gramflux import Client, Session


async def main() -> None:
    async with Client(
        Session.temporary(),
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    ) as client:
        me = await client.login()
        print(f"Temporary authorized account ID: {me.id}")
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
