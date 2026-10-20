"""Composable synchronous event predicates. No user content is logged."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


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


text = Filter(lambda e: bool(e.text))
incoming = Filter(lambda e: not e.outgoing)
outgoing = Filter(lambda e: e.outgoing)
all_messages = Filter(lambda e: True)


def chat(*ids: int) -> Filter:
    selected = frozenset(ids)
    return Filter(lambda e: e.chat_id in selected)


def sender(*ids: int) -> Filter:
    selected = frozenset(ids)
    return Filter(lambda e: e.sender_id in selected)


def regex(pattern: str, flags: int = 0) -> Filter:
    compiled = re.compile(pattern, flags)
    return Filter(lambda e: bool(compiled.search(e.text or "")))


private = Filter(lambda e: e.chat_type == "private")
group = Filter(lambda e: e.chat_type == "group")
channel = Filter(lambda e: e.chat_type == "channel")
media = Filter(lambda e: getattr(e.message, "media", None) is not None)
photo = Filter(lambda e: getattr(e.message, "photo", None) is not None)
document = Filter(lambda e: getattr(e.message, "document", None) is not None)
video = Filter(lambda e: getattr(e.message, "video", None) is not None)
audio = Filter(lambda e: getattr(e.message, "audio", None) is not None)
voice = Filter(lambda e: getattr(e.message, "voice", None) is not None)
sticker = Filter(lambda e: getattr(e.message, "sticker", None) is not None)


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
        token = (event.text or "").split(maxsplit=1)
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
