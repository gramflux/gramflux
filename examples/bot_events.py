"""Real MTProto bot API; supply credentials securely and enable inline mode for the bot."""

import asyncio
import os

from gramflux import Client, Session, buttons, events, filters
from gramflux.raw import types


async def main() -> None:
    client = Client(
        Session.temporary(),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    )

    @client.on_message(filters.command("start"))
    async def start(event: events.MessageEvent) -> None:
        if event.chat_id is not None:
            await client.send_message(
                event.chat_id,
                "Choose an action",
                reply_markup=buttons.inline([[buttons.callback("Confirm", "confirm")]]),
            )

    @client.on_callback_query(filters.data("confirm"))
    async def confirm(event: events.CallbackQueryEvent) -> None:
        await event.answer("Confirmed")

    @client.on_inline_query()
    async def inline(event: events.InlineQueryEvent) -> None:
        await event.answer([buttons.article("help", "Help", "Hello from GramFlux")], private=True)

    async with client:
        await client.sign_in_bot(os.environ["GRAMFLUX_BOT_TOKEN"])
        try:
            await client.set_bot_commands(
                [types.BotCommand(command="start", description="Show menu")]
            )
            await client.run_until_disconnected()
        finally:
            if client.connected:
                await client.log_out()


if __name__ == "__main__":
    asyncio.run(main())
