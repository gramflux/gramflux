"""Explicit saved/new/temporary login: python examples/login.py --help."""

import argparse
import asyncio
import os

from gramflux import Client, Session
from gramflux.errors import (
    AuthenticationError,
    FloodWait,
    LoginAttemptsExceeded,
    SessionError,
    TransportError,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--create", metavar="NAME", help="create a new named session; never overwrite"
    )
    mode.add_argument("--open", metavar="NAME", help="open an existing authorized GramFlux session")
    mode.add_argument("--resume", metavar="NAME", help="continue an unfinished saved login")
    mode.add_argument("--temporary", action="store_true", help="memory only; no saved session file")
    parser.add_argument(
        "--attempts", type=int, default=3, help="input attempts per stage (default: 3)"
    )
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    if args.create is not None:
        session = Session.create(args.create)
    elif args.open is not None:
        session = Session.open(args.open)
    elif args.resume is not None:
        session = Session.open(args.resume, require_authorized=False)
    else:
        session = Session.temporary()
    try:
        async with Client(
            session,
            api_id=int(os.environ["TELEGRAM_API_ID"]),
            api_hash=os.environ["TELEGRAM_API_HASH"],
        ) as client:
            me = await client.login(
                bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
                max_attempts=args.attempts,
            )
            print(f"Authorized account ID: {me.id}")
            if args.temporary:
                print("Temporary session: no file saved; this process will now exit.")
    except FloodWait as error:
        raise SystemExit(
            f"Telegram requires waiting {error.seconds} seconds before retrying."
        ) from None
    except (AuthenticationError, LoginAttemptsExceeded, SessionError, TransportError) as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    try:
        asyncio.run(main(arguments()))
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("Login cancelled.") from None
