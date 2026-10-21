"""Native bot UI builders; no network calls or hidden formatting parser."""

from collections.abc import Sequence

from .errors import ConfigurationError
from .raw import types
from .tl.model import TLObject


def callback(text: str, data: bytes | str) -> types.KeyboardButtonCallback:
    if not isinstance(text, str) or not text:
        raise ConfigurationError("button text must not be empty")
    if not isinstance(data, (str, bytes)):
        raise ConfigurationError("callback data must be bytes or text")
    encoded = data.encode("utf-8") if isinstance(data, str) else data
    if not 1 <= len(encoded) <= 64:
        raise ConfigurationError("callback data requires 1..64 UTF-8 bytes")
    return types.KeyboardButtonCallback(text=text, data=encoded)


def url(text: str, url: str) -> types.KeyboardButtonUrl:
    if not isinstance(text, str) or not text or not isinstance(url, str) or not url:
        raise ConfigurationError("provide button text and URL")
    return types.KeyboardButtonUrl(text=text, url=url)


def inline(rows: Sequence[Sequence[types.TypeKeyboardButton]]) -> types.ReplyInlineMarkup:
    if not rows or isinstance(rows, (str, bytes)):
        raise ConfigurationError("provide nonempty keyboard rows")
    result: list[TLObject] = []
    for row in rows:
        if (
            not row
            or isinstance(row, (str, bytes))
            or any(
                getattr(getattr(button, "definition", None), "result", None) != "KeyboardButton"
                for button in row
            )
        ):
            raise ConfigurationError("keyboard rows must contain native buttons")
        # Reply-only request/contact/phone buttons cannot be inline keyboard entries.
        if any(
            not isinstance(
                button,
                (
                    types.KeyboardButtonCallback,
                    types.KeyboardButtonUrl,
                    types.KeyboardButtonSwitchInline,
                    types.InputKeyboardButtonUserProfile,
                    types.KeyboardButtonGame,
                    types.KeyboardButtonBuy,
                ),
            )
            for button in row
        ):
            raise ConfigurationError("button kind is unsupported in this inline builder")
        result.append(types.KeyboardButtonRow(buttons=list(row)))
    return types.ReplyInlineMarkup(rows=result)


def article(
    id: str,
    title: str,
    text: str,
    *,
    description: str | None = None,
    reply_markup: types.TypeReplyMarkup | None = None,
    entities: list[types.TypeMessageEntity] | None = None,
) -> types.InputBotInlineResult:
    if not isinstance(id, str) or not 1 <= len(id.encode("utf-8")) <= 64:
        raise ConfigurationError("inline result IDs require 1..64 UTF-8 bytes")
    if not isinstance(title, str) or not title or not isinstance(text, str):
        raise ConfigurationError("provide a title and literal message text")
    if description is not None and not isinstance(description, str):
        raise ConfigurationError("description must be text")
    return types.InputBotInlineResult(
        id=id,
        type="article",
        title=title,
        description=description,
        send_message=types.InputBotInlineMessageText(
            message=text,
            reply_markup=reply_markup,
            entities=entities,
        ),
    )
