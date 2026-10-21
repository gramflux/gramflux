"""Separate-process login: request, code, password or status against a named session."""

import argparse
import asyncio
import getpass
import os

from gramflux import Client, Session
from gramflux.errors import PasswordRequired


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["request", "code", "password", "status"])
    parser.add_argument("session", help="GramFlux session name or path")
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    session = (
        Session.create(args.session)
        if args.action == "request"
        else Session.open(args.session, require_authorized=False)
    )
    async with Client(
        session,
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    ) as client:
        if args.action == "request":
            phone = await asyncio.to_thread(input, "Phone number: ")
            await client.request_login_code(phone)
            print("Challenge saved. Exit now and run the code step later.")
        elif args.action == "code":
            code = await asyncio.to_thread(getpass.getpass, "Login code: ")
            try:
                await client.sign_in(code=code)
            except PasswordRequired:
                print("Password stage saved. Run the password step later.")
            else:
                print("Authorized.")
        elif args.action == "password":
            password = await asyncio.to_thread(getpass.getpass, "Two-step password: ")
            await client.check_password(password)
            print("Authorized.")
        else:
            authorized = await client.is_authorized()
            print("Authorized." if authorized else f"Pending step: {client.login_stage}")


if __name__ == "__main__":
    asyncio.run(main(arguments()))
