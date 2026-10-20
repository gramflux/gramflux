"""Explicit interactive authorization. Never prints credentials or account objects."""

import asyncio
import getpass
import os

from gramflux import Client
from gramflux.errors import AuthenticationError, PasswordRequired


async def main() -> None:
    async with Client(
        "example",
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
    ) as client:
        if not await client.is_authorized():
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            try:
                if bot_token:
                    await client.sign_in_bot(bot_token)
                else:
                    phone = await asyncio.to_thread(input, "Phone number: ")
                    challenge = await client.request_login_code(phone)
                    code = await asyncio.to_thread(getpass.getpass, "Login code: ")
                    try:
                        await client.sign_in(challenge, code)
                    except PasswordRequired:
                        password = await asyncio.to_thread(getpass.getpass, "Two-step password: ")
                        await client.check_password(password)
                        del password
                    del code, challenge
            except AuthenticationError as error:
                print(f"Authorization failed: {error.name}")
                return
        me = await client.get_me()
        print(f"Authorized account ID: {me.id}")


if __name__ == "__main__":
    asyncio.run(main())
