"""Hash a document/photo range from a saved session without writing it to disk."""

import argparse
import asyncio
import hashlib
import os

from gramflux import Client, Session


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="example")
    parser.add_argument("--peer", default="me", help="me or an accessible username")
    parser.add_argument("--message-id", type=int, required=True)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--length", type=int, default=None)
    args = parser.parse_args()
    async with Client(
        Session.open(args.session),
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    ) as client:
        selected = await client.get_messages(args.peer, [args.message_id])
        message = selected[0]
        if message is None:
            raise ValueError("message is unavailable in the selected chat")
        digest = hashlib.sha256()
        received = 0
        async for block in client.iter_download_media(
            message, offset=args.offset, length=args.length
        ):
            digest.update(block)
            received += len(block)
        print(f"Read {received} bytes; SHA256={digest.hexdigest()}")


if __name__ == "__main__":
    asyncio.run(main())
