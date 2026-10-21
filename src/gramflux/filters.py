"""Composable synchronous event predicates. No user content is logged."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .tl.model import TLObject


@dataclass(frozen=True, slots=True)
class Filter:
    predicate: Callable[[Any], bool]

    def __call__(self, event: Any) -> bool:
        return self.predicate(event)

    def __and__(self, other: "Filter") -> "Filter":
        return Filter(lambda e: self(e) and other(e))

    def __or__(self, other: "Filter") -> "Filter":
        return Filter(lambda e: self(e) or other(e))

    def __invert__(self) -> "Filter":
        return Filter(lambda e: not self(e))


text = Filter(lambda e: bool(getattr(e, "text", "")))
incoming = Filter(lambda e: hasattr(e, "outgoing") and not e.outgoing)
outgoing = Filter(lambda e: bool(getattr(e, "outgoing", False)))
all_messages = Filter(lambda e: True)


def chat(*ids: int) -> Filter:
    selected = frozenset(ids)
    return Filter(lambda e: getattr(e, "chat_id", None) in selected)


def sender(*ids: int) -> Filter:
    selected = frozenset(ids)
    return Filter(lambda e: getattr(e, "sender_id", None) in selected)


def regex(pattern: str, flags: int = 0) -> Filter:
    compiled = re.compile(pattern, flags)
    return Filter(lambda e: bool(compiled.search(getattr(e, "text", "") or "")))


private = Filter(lambda e: getattr(e, "chat_type", None) == "private")
group = Filter(lambda e: getattr(e, "chat_type", None) == "group")
channel = Filter(lambda e: getattr(e, "chat_type", None) == "channel")
media = Filter(lambda e: getattr(getattr(e, "message", None), "media", None) is not None)
photo = Filter(lambda e: getattr(getattr(e, "message", None), "photo", None) is not None)
document = Filter(lambda e: getattr(getattr(e, "message", None), "document", None) is not None)
video = Filter(lambda e: getattr(getattr(e, "message", None), "video", None) is not None)
audio = Filter(lambda e: getattr(getattr(e, "message", None), "audio", None) is not None)
voice = Filter(lambda e: getattr(getattr(e, "message", None), "voice", None) is not None)
sticker = Filter(lambda e: getattr(getattr(e, "message", None), "sticker", None) is not None)


def command(
    *names: str,
    prefix: str = "/",
    username: str | None = None,
    case_sensitive: bool = False,
) -> Filter:
    """Match the first token; optional username prevents addressing another bot.

    Does not parse/execute arguments, mutate events, or request the bot identity.
    Without username, addressed commands for any username can match.
    """
    from .errors import ConfigurationError

    if (
        not names
        or any(
            not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]+", name) for name in names
        )
        or not isinstance(prefix, str)
        or not prefix
    ):
        raise ConfigurationError("provide command names without prefixes or whitespace")
    if username is not None and not re.fullmatch(r"[A-Za-z0-9_]+", username):
        raise ConfigurationError("username must not contain @ or whitespace")
    normalize = (lambda value: value) if case_sensitive else str.casefold
    selected = frozenset(normalize(name) for name in names)

    def matches(event: Any) -> bool:
        token = (getattr(event, "text", "") or "").split(maxsplit=1)
        if not token or not token[0].startswith(prefix):
            return False
        body = token[0][len(prefix) :]
        name, separator, address = body.partition("@")
        if separator and (not address or "@" in address):
            return False
        if separator and username is not None and address.casefold() != username.casefold():
            return False
        return normalize(name) in selected

    return Filter(matches)


def data(value: bytes | str) -> Filter:
    """Match callback data exactly, using UTF-8 for a text value."""
    from .errors import ConfigurationError

    if not isinstance(value, (bytes, str)):
        raise ConfigurationError("callback data filter requires bytes or text")
    expected = value.encode("utf-8") if isinstance(value, str) else value
    return Filter(lambda event: getattr(event, "data", None) == expected)


def update_type(*constructors: type[TLObject]) -> Filter:
    """Select official Update constructors on ``on_raw_update`` events.

    This selects accepted native updates; it does not bypass update recovery or
    enable unsupported qts/secret-chat processing. Multiple constructors mean OR.
    """
    from .errors import ConfigurationError
    from .tl.generated.objects import REGISTRY

    if not constructors or any(
        not isinstance(cls, type)
        or not issubclass(cls, TLObject)
        or getattr(cls, "definition", None) is None
        or cls.definition.result != "Update"
        or REGISTRY.get(cls.definition.id) is not cls
        for cls in constructors
    ):
        raise ConfigurationError("update_type requires official native Update constructor classes")
    selected = tuple(constructors)
    return Filter(lambda event: isinstance(getattr(event, "update", None), selected))
