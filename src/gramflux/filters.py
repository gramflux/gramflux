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
