"""Standalone route definitions: no Client is constructed here."""

from gramflux.routing import Chat, CommandContext, Direction, Router


def build_router(username: str) -> Router:
    router = Router("greetings")

    @router.command("hello", chat=Chat.PRIVATE, direction=Direction.INCOMING, username=username)
    async def hello(ctx: CommandContext) -> None:
        await ctx.reply("Hello from GramFlux")

    return router
