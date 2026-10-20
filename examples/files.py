"""Upload/send a user-selected file, download it to a NEW path. Requires user auth."""

import asyncio
import os
import sys
from pathlib import Path

from gramflux import Client, Session


async def progress(done: int, total: int) -> None:
    print(f"{done}/{total} bytes")


async def main() -> None:
    source, destination = Path(sys.argv[1]), Path(sys.argv[2])
    async with Client(
        Session.open("example"),
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    ) as client:
        uploaded = await client.upload_file(source, on_progress=progress)
        message = await client.send_file("me", uploaded, caption="GramFlux transfer example")
        await client.download_media(message, destination, on_progress=progress)


if __name__ == "__main__":
    asyncio.run(main())
