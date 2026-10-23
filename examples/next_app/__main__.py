"""Run from the repository root after installing GramFlux and setting credentials."""

import asyncio
import os

from gramflux import Client, Session

from .handlers import build_router


async def serve(client: Client, *, bot_token: str, username: str) -> None:
    client.events.include(build_router(username))
    async with client:
        await client.auth.login(bot_token=bot_token)
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
